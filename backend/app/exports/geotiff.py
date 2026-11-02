"""
GeoTIFF export functionality.

Converts numpy arrays to Cloud-Optimized GeoTIFF format suitable for
geospatial analysis and web mapping.
"""

from typing import Union
from io import BytesIO
import numpy as np
import rasterio
from rasterio.io import MemoryFile
from app.utils.errors import ProcessingError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class GeoTIFFExporter:
    """Export raster data as GeoTIFF."""

    @staticmethod
    def export_to_geotiff(
        data: np.ndarray,
        transform: rasterio.Affine,
        crs: str,
        compress: str = "deflate",
    ) -> bytes:
        """
        Export numpy array as GeoTIFF in memory.
        
        Args:
            data: 2D numpy array of raster data
            transform: rasterio Affine transform
            crs: Coordinate reference system (e.g., "EPSG:4326")
            compress: Compression algorithm ("deflate", "lzw", etc.)
            
        Returns:
            Bytes containing GeoTIFF file
            
        Raises:
            ProcessingError: If export fails
        """
        try:
            height, width = data.shape
            
            with MemoryFile() as memory_file:
                with memory_file.open(
                    driver="GTiff",
                    height=height,
                    width=width,
                    count=1,
                    dtype="float32",
                    crs=crs,
                    transform=transform,
                    nodata=np.nan,
                    compress=compress,
                ) as dataset:
                    dataset.write(data.astype(np.float32, copy=False), 1)
                
                geotiff_bytes = memory_file.read()
            
            logger.info(f"Exported GeoTIFF: {height}x{width}, size={len(geotiff_bytes)} bytes")
            return geotiff_bytes
            
        except Exception as e:
            raise ProcessingError(f"GeoTIFF export failed: {str(e)}")

    @staticmethod
    def export_multiband_geotiff(
        data_dict: dict,
        transform: rasterio.Affine,
        crs: str,
        compress: str = "deflate",
    ) -> bytes:
        """
        Export multiple raster bands as a single GeoTIFF.
        
        Args:
            data_dict: Dictionary of band_name -> numpy_array
            transform: rasterio Affine transform
            crs: Coordinate reference system
            compress: Compression algorithm
            
        Returns:
            Bytes containing multiband GeoTIFF
        """
        try:
            first_array = next(iter(data_dict.values()))
            height, width = first_array.shape
            num_bands = len(data_dict)
            
            with MemoryFile() as memory_file:
                with memory_file.open(
                    driver="GTiff",
                    height=height,
                    width=width,
                    count=num_bands,
                    dtype="float32",
                    crs=crs,
                    transform=transform,
                    nodata=np.nan,
                    compress=compress,
                ) as dataset:
                    for idx, (band_name, band_data) in enumerate(data_dict.items(), 1):
                        dataset.write(band_data.astype(np.float32, copy=False), idx)
                        dataset.set_band_unit(idx, band_name)
                
                geotiff_bytes = memory_file.read()
            
            logger.info(
                f"Exported multiband GeoTIFF: "
                f"{height}x{width}x{num_bands}, "
                f"size={len(geotiff_bytes)} bytes"
            )
            return geotiff_bytes
            
        except Exception as e:
            raise ProcessingError(f"Multiband GeoTIFF export failed: {str(e)}")
