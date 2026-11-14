"""
SAR backscatter change detection and analysis.

This module implements core algorithms for:
- Spatial alignment of pre and post-event imagery
- Backscatter difference calculation (Δσ⁰ = σ⁰_post - σ⁰_pre)
- Water classification
- Flood detection screening

All logic extracted and refactored from the original Streamlit app.py.
"""

from typing import Dict, Tuple, Any
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject
from app.utils.errors import ProcessingError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class ChangeDetectionEngine:
    """SAR change detection and flood screening engine."""

    @staticmethod
    def align_and_compare(
        before: Dict[str, Any],
        after: Dict[str, Any],
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, float]:
        """
        Align pre-event and post-event imagery and compute backscatter change.
        
        Processing steps:
        1. Reproject pre-event data to post-event grid
        2. Mask invalid pixels in both datasets
        3. Calculate change: Δσ⁰ = σ⁰_post - σ⁰_pre
        4. Return aligned datasets and change matrix
        
        Args:
            before: Pre-event GCOV subset from GCOVReader
            after: Post-event GCOV subset from GCOVReader
            
        Returns:
            Tuple of:
                - change: Backscatter difference in dB
                - aligned_before: Pre-event data reprojected to post-event grid
                - aligned_after: Post-event data (same as input)
                - pixel_area_km2: Area per pixel
                
        Raises:
            ProcessingError: If alignment fails
        """
        try:
            before_data = np.asarray(before["data"], dtype=np.float32)
            after_data = np.asarray(after["data"], dtype=np.float32)
            
            # Reproject before data to after's coordinate system
            aligned_before = np.full(after_data.shape, np.nan, dtype=np.float32)
            
            reproject(
                source=before_data,
                destination=aligned_before,
                src_transform=before["transform"],
                src_crs=before["crs"],
                src_nodata=np.nan,
                dst_transform=after["transform"],
                dst_crs=after["crs"],
                dst_nodata=np.nan,
                resampling=Resampling.bilinear,
            )
            
            # Create validity mask (both datasets must have valid data)
            valid = np.isfinite(aligned_before) & np.isfinite(after_data)
            aligned_before[~valid] = np.nan
            
            aligned_after = after_data.copy()
            aligned_after[~valid] = np.nan
            
            # Calculate change
            change = np.full(after_data.shape, np.nan, dtype=np.float32)
            change[valid] = aligned_after[valid] - aligned_before[valid]
            
            pixel_area = float(after["pixel_area_km2"])
            
            logger.info(
                f"Alignment complete: "
                f"valid_pixels={valid.sum()}, "
                f"mean_change={np.nanmean(change):.2f}dB, "
                f"std_change={np.nanstd(change):.2f}dB"
            )
            
            return change, aligned_before, aligned_after, pixel_area
            
        except Exception as e:
            raise ProcessingError(f"Alignment failed: {str(e)}")

    @staticmethod
    def _remove_speckle_noise(mask: np.ndarray, min_cluster_pixels: int = 9) -> np.ndarray:
        """
        Removes isolated small clusters of candidate pixels (SAR speckle
        noise) from a binary classification mask, preserving NaN (invalid)
        pixels. This is a standard "minimum mapping unit" filter used in
        real SAR flood-mapping practice: coherent water bodies/vegetation
        change spans multiple contiguous pixels, while single- or few-pixel
        clusters passing a backscatter threshold are typically measurement
        noise (speckle), not real surface change. Without this, a noisy real
        classification mask can contain hundreds of thousands of isolated
        tiny "polygons" when vectorized to GeoJSON - both scientifically
        spurious and, for large AOIs, slow enough to make the whole analysis
        appear to hang (observed directly: an unfiltered mask produced a
        200+MB GeoJSON with an enormous polygon count for a real AOI).
        """
        from scipy import ndimage

        valid = np.isfinite(mask)
        binary = np.nan_to_num(mask, nan=0.0) > 0.5
        labeled, num_features = ndimage.label(binary)
        if num_features > 0:
            sizes = ndimage.sum(binary, labeled, range(1, num_features + 1))
            small_labels = np.where(sizes < min_cluster_pixels)[0] + 1
            if len(small_labels) > 0:
                binary[np.isin(labeled, small_labels)] = False

        cleaned = np.full(mask.shape, np.nan, dtype=np.float32)
        cleaned[valid] = binary[valid].astype(np.float32)
        return cleaned

    @staticmethod
    def create_flood_classification_masks(
        before: np.ndarray,
        after: np.ndarray,
        change: np.ndarray,
        flood_change_threshold_db: float = -2.0,
        low_backscatter_threshold_db: float = -15.0,
        pixel_area_km2: float = 1.0,
        vegetation_increase_threshold_db: float = 2.0,
        min_cluster_pixels: int = 9,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, Dict[str, float]]:
        """
        Create flood detection and water classification masks.

        Classification logic implements two distinct, physically-documented
        SAR flood signatures (see NASA/JPL "Floods" StoryMap:
        https://storymaps.arcgis.com/stories/c00d7691b8004b20a14f28df710d05fd) -
        radar brightness is NOT one-directional for flooding:

        POSSIBLE_FLOOD (open water - specular/surface scattering, radar-DARK):
        - Backscatter decreased significantly (≤ -flood_change_threshold_db)
        - Post-event backscatter is low (≤ low_backscatter_threshold_db)
        - Indicates surface became smoother, consistent with new open water

        POSSIBLE_FLOODED_VEGETATION (double-bounce scattering, radar-BRIGHT):
        - Backscatter increased significantly (≥ vegetation_increase_threshold_db)
        - Pre-event surface was not already water-like (before > low_backscatter_threshold_db)
        - Indicates water now present beneath standing vegetation/forest canopy:
          the double-bounce path (ground -> canopy -> sensor) makes these
          areas brighter, not darker. This signature is often the dominant
          one in forested floodplains and wetlands, where open-water-only
          detection under-estimates true flood extent.

        PERSISTENT_LOW_BACKSCATTER:
        - Both pre and post have low backscatter (≤ low_backscatter_threshold_db)
        - Likely permanent water or permanent smooth surfaces

        The two "new flood" signatures are mutually exclusive (one requires a
        backscatter decrease, the other an increase), so their pixel counts
        can be summed directly for a combined total without double-counting.

        Args:
            before: Pre-event backscatter in dB
            after: Post-event backscatter in dB
            change: Backscatter change (after - before)
            flood_change_threshold_db: Minimum backscatter decrease to flag as potential flood
            low_backscatter_threshold_db: Backscatter threshold for water-like surfaces
            pixel_area_km2: Area per pixel for area calculations
            vegetation_increase_threshold_db: Minimum backscatter increase to flag potential flooded vegetation
            min_cluster_pixels: Minimum connected-pixel cluster size to keep (speckle-noise/minimum-mapping-unit
                filter); isolated smaller clusters are removed before vectorization

        Returns:
            Tuple of:
                - possible_flood: Binary mask of potential new open-water inundation
                - possible_flooded_vegetation: Binary mask of potential new flooded vegetation
                - persistent_low_backscatter: Binary mask of permanent water
                - stats: Dictionary with area and pixel counts (including the combined total)
        """
        try:
            # Create validity mask
            valid = np.isfinite(before) & np.isfinite(after) & np.isfinite(change)
            
            # Initialize masks
            possible_flood = np.full(change.shape, np.nan, dtype=np.float32)
            possible_flooded_vegetation = np.full(change.shape, np.nan, dtype=np.float32)
            persistent_low_backscatter = np.full(change.shape, np.nan, dtype=np.float32)
            
            # Apply classification logic
            possible_flood[valid] = (
                (change[valid] <= -flood_change_threshold_db)
                & (after[valid] <= low_backscatter_threshold_db)
            ).astype(np.float32)

            possible_flooded_vegetation[valid] = (
                (change[valid] >= vegetation_increase_threshold_db)
                & (before[valid] > low_backscatter_threshold_db)
            ).astype(np.float32)
            
            persistent_low_backscatter[valid] = (
                (before[valid] <= low_backscatter_threshold_db)
                & (after[valid] <= low_backscatter_threshold_db)
            ).astype(np.float32)

            # Remove isolated speckle-noise clusters before computing stats/
            # vectorizing - see _remove_speckle_noise docstring for why this
            # matters (scientific validity + avoiding pathologically large/
            # slow-to-vectorize noisy masks on real data).
            if min_cluster_pixels > 1:
                possible_flood = ChangeDetectionEngine._remove_speckle_noise(possible_flood, min_cluster_pixels)
                possible_flooded_vegetation = ChangeDetectionEngine._remove_speckle_noise(
                    possible_flooded_vegetation, min_cluster_pixels
                )
                persistent_low_backscatter = ChangeDetectionEngine._remove_speckle_noise(
                    persistent_low_backscatter, min_cluster_pixels
                )
            
            # Calculate statistics
            valid_pixels = int(valid.sum())
            possible_flood_pixels = float(np.nansum(possible_flood))
            flooded_vegetation_pixels = float(np.nansum(possible_flooded_vegetation))
            persistent_pixels = float(np.nansum(persistent_low_backscatter))
            total_flood_pixels = possible_flood_pixels + flooded_vegetation_pixels
            
            stats = {
                "possible_flood_pixels": possible_flood_pixels,
                "possible_flooded_vegetation_pixels": flooded_vegetation_pixels,
                "persistent_low_backscatter_pixels": persistent_pixels,
                "possible_flood_area_km2": possible_flood_pixels * pixel_area_km2,
                "possible_flooded_vegetation_area_km2": flooded_vegetation_pixels * pixel_area_km2,
                "persistent_low_backscatter_area_km2": persistent_pixels * pixel_area_km2,
                "total_flood_extent_pixels": total_flood_pixels,
                "total_flood_extent_area_km2": total_flood_pixels * pixel_area_km2,
                "valid_pixels": float(valid_pixels),
            }
            
            logger.info(
                f"Classification complete: "
                f"open_water_flood_area={stats['possible_flood_area_km2']:.2f}km², "
                f"flooded_vegetation_area={stats['possible_flooded_vegetation_area_km2']:.2f}km², "
                f"total_flood_extent_area={stats['total_flood_extent_area_km2']:.2f}km², "
                f"persistent_water_area={stats['persistent_low_backscatter_area_km2']:.2f}km²"
            )
            
            return possible_flood, possible_flooded_vegetation, persistent_low_backscatter, stats
            
        except Exception as e:
            raise ProcessingError(f"Classification failed: {str(e)}")

    @staticmethod
    def calculate_change_statistics(
        change: np.ndarray,
        threshold_db: float = 2.0,
    ) -> Dict[str, float]:
        """
        Calculate statistics for backscatter change.
        
        Args:
            change: Backscatter change matrix
            threshold_db: Threshold for considering significant change
            
        Returns:
            Dictionary with statistical measures
        """
        valid = np.isfinite(change)
        
        if not valid.any():
            # No valid (finite) pixels at all in this AOI/granule-pair
            # combination - honestly report "unknown" (null) rather than a
            # raw NaN, which is not valid JSON and can crash response
            # serialization further up the stack.
            return {
                "mean_change_db": None,
                "std_change_db": None,
                "min_change_db": None,
                "max_change_db": None,
                "candidate_pixels": 0.0,
                "candidate_area_km2": 0.0,
            }
        
        candidate = np.abs(change[valid]) >= threshold_db
        
        return {
            "mean_change_db": float(np.nanmean(change)),
            "std_change_db": float(np.nanstd(change)),
            "min_change_db": float(np.nanmin(change)),
            "max_change_db": float(np.nanmax(change)),
            "candidate_pixels": float(candidate.sum()),
        }
