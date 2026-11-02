"""
NISAR GCOV (Geocoded Polarimetric Radar Backscatter) reader.
Handles HDF5 file reading and extraction of polarimetric data.

This module contains logic extracted from the original Streamlit app.py,
refactored for use in the FastAPI backend.
"""

from pathlib import Path
from typing import Dict, Any, List
import numpy as np
import h5py
from pyproj import Transformer
from rasterio.transform import from_origin
from app.utils.errors import ProcessingError, ValidationError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GCOVReader:
    """Reader for NISAR GCOV HDF5 files."""
    
    SUPPORTED_POLARIZATIONS = ("HHHH", "HVHV", "VVVV", "HHHV", "VHVH", "VVVH")
    MAX_SUBSET_PIXELS = 15_000_000

    @staticmethod
    def find_frequency_group(h5_file: h5py.File) -> h5py.Group:
        """
        Find the frequency group in a GCOV HDF5 file.
        
        NISAR GCOV products organize data by frequency bands.
        This function locates the frequency group containing spatial data.
        
        Args:
            h5_file: Open HDF5 file object
            
        Returns:
            The frequency group containing polarimetric data
            
        Raises:
            ProcessingError: If no valid frequency group is found
        """
        groups: List[h5py.Group] = []

        def collect(name: str, item: Any) -> None:
            if (
                isinstance(item, h5py.Group)
                and name.rsplit("/", 1)[-1].startswith("frequency")
                and "xCoordinates" in item
                and "yCoordinates" in item
                and "projection" in item
            ):
                groups.append(item)

        h5_file.visititems(collect)
        
        if not groups:
            raise ProcessingError(
                "No GCOV frequency grid with coordinates found in this HDF5 file."
            )
        
        logger.info(f"Found {len(groups)} frequency group(s), using first one")
        return groups[0]

    @classmethod
    def list_polarizations(cls, path: Path) -> List[str]:
        """
        List available 2D polarization channels in a GCOV file.
        
        Args:
            path: Path to GCOV HDF5 file
            
        Returns:
            List of available polarization channels
        """
        try:
            with h5py.File(path, "r") as h5_file:
                group = cls.find_frequency_group(h5_file)
                polarizations = [
                    pol for pol in cls.SUPPORTED_POLARIZATIONS
                    if pol in group
                    and isinstance(group[pol], h5py.Dataset)
                    and group[pol].ndim == 2
                ]
                logger.info(f"Found polarizations: {polarizations}")
                return polarizations
        except Exception as e:
            raise ProcessingError(f"Failed to list polarizations: {str(e)}")

    @staticmethod
    def _scalar(value: object) -> int:
        """Convert numpy scalar to Python int."""
        return int(np.asarray(value).item())

    @classmethod
    def load_gcov_subset(
        cls,
        path: Path,
        polarization: str,
        bounds: tuple[float, float, float, float],
    ) -> Dict[str, Any]:
        """
        Load a subset of GCOV data for a specified geographic area.
        
        This function:
        1. Reads HDF5 polarimetric dataset
        2. Extracts coordinates and projection info
        3. Reprojects bounds to local coordinate system
        4. Extracts spatial subset
        5. Converts to dB scale if needed
        6. Validates output
        
        Args:
            path: Path to GCOV HDF5 file
            polarization: Polarization channel (e.g., 'VVVV', 'HVHV')
            bounds: Geographic bounds (west, south, east, north) in EPSG:4326
            
        Returns:
            Dictionary with keys:
                - 'data': numpy array of backscatter in dB
                - 'transform': rasterio Affine transform
                - 'crs': Coordinate reference system EPSG code
                - 'pixel_area_km2': Area per pixel in km²
                
        Raises:
            ProcessingError: If file reading or processing fails
            ValidationError: If data validation fails
        """
        try:
            with h5py.File(path, "r") as h5_file:
                group = cls.find_frequency_group(h5_file)
                
                # Validate polarization exists
                if polarization not in group or not isinstance(group[polarization], h5py.Dataset):
                    available = ", ".join(cls.list_polarizations(path)) or "none"
                    raise ValidationError(
                        f"Polarization {polarization} not found. Available: {available}"
                    )

                # Extract data and coordinates
                dataset = group[polarization]
                x_coordinates = np.asarray(group["xCoordinates"][:], dtype=np.float64)
                y_coordinates = np.asarray(group["yCoordinates"][:], dtype=np.float64)
                
                # Validate dimensions
                if dataset.shape != (y_coordinates.size, x_coordinates.size):
                    raise ValidationError(
                        f"Dataset dimensions {dataset.shape} do not match "
                        f"grid coordinates {(y_coordinates.size, x_coordinates.size)}"
                    )

                # Get projection
                projection = cls._scalar(group["projection"][()])
                
                # Reproject bounds to local coordinate system
                transformer = Transformer.from_crs(
                    "EPSG:4326",
                    f"EPSG:{projection}",
                    always_xy=True,
                )
                west, south, east, north = bounds
                projected_bounds = transformer.transform_bounds(
                    west, south, east, north,
                    densify_pts=21,
                )
                projected_west, projected_south, projected_east, projected_north = projected_bounds
                
                # Find indices of relevant pixels
                x_indices = np.flatnonzero(
                    (x_coordinates >= projected_west) & (x_coordinates <= projected_east)
                )
                y_indices = np.flatnonzero(
                    (y_coordinates >= projected_south) & (y_coordinates <= projected_north)
                )
                
                if x_indices.size == 0 or y_indices.size == 0:
                    raise ValidationError(
                        "Selected study area does not overlap with this file."
                    )

                x_slice = slice(int(x_indices.min()), int(x_indices.max()) + 1)
                y_slice = slice(int(y_indices.min()), int(y_indices.max()) + 1)
                subset_shape = (y_slice.stop - y_slice.start, x_slice.stop - x_slice.start)
                
                # Validate subset size
                if subset_shape[0] * subset_shape[1] > cls.MAX_SUBSET_PIXELS:
                    raise ValidationError(
                        f"Selected area is too large: {subset_shape[0] * subset_shape[1]} pixels "
                        f"exceeds maximum of {cls.MAX_SUBSET_PIXELS}"
                    )

                # Extract raw values
                raw_values = np.asarray(dataset[y_slice, x_slice])
                if np.iscomplexobj(raw_values):
                    raw_values = raw_values.real
                raw_values = raw_values.astype(np.float32, copy=False)
                
                # Extract sliced coordinates
                x_coordinates = x_coordinates[x_slice]
                y_coordinates = y_coordinates[y_slice]
                
                # Handle units and fill values
                units = str(dataset.attrs.get("units", "")).lower()
                fill_value = dataset.attrs.get("_FillValue", dataset.attrs.get("fillValue"))

            # Create validity mask
            valid = np.isfinite(raw_values)
            if fill_value is not None:
                valid &= raw_values != float(np.asarray(fill_value).item())
            
            # Convert to dB scale
            if "db" in units or "decibel" in units:
                backscatter_db = raw_values
            else:
                valid &= raw_values > 0
                backscatter_db = np.full(raw_values.shape, np.nan, dtype=np.float32)
                backscatter_db[valid] = 10.0 * np.log10(raw_values[valid])
            
            backscatter_db[~valid] = np.nan

            # Validate coordinate arrays
            if x_coordinates.size < 2 or y_coordinates.size < 2:
                raise ValidationError(
                    "Not enough grid coordinates to map the data."
                )
            
            # Calculate pixel spacing
            x_step = float(np.median(np.abs(np.diff(x_coordinates))))
            y_step = float(np.median(np.abs(np.diff(y_coordinates))))
            
            # Ensure coordinate order is consistent
            if x_coordinates[0] > x_coordinates[-1]:
                x_coordinates = x_coordinates[::-1]
                backscatter_db = backscatter_db[:, ::-1]
            if y_coordinates[0] < y_coordinates[-1]:
                y_coordinates = y_coordinates[::-1]
                backscatter_db = backscatter_db[::-1, :]

            # Create rasterio transform
            transform = from_origin(
                float(x_coordinates[0]) - x_step / 2,
                float(y_coordinates[0]) + y_step / 2,
                x_step,
                y_step,
            )
            
            result = {
                "data": backscatter_db,
                "transform": transform,
                "crs": f"EPSG:{projection}",
                "pixel_area_km2": (x_step * y_step) / 1_000_000,
            }
            
            logger.info(
                f"Successfully loaded GCOV subset: "
                f"shape={backscatter_db.shape}, "
                f"crs={result['crs']}, "
                f"valid_pixels={valid.sum()}"
            )
            
            return result
            
        except (ProcessingError, ValidationError):
            raise
        except Exception as e:
            raise ProcessingError(f"Failed to load GCOV subset: {str(e)}")
