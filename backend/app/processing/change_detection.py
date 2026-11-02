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
    def create_flood_classification_masks(
        before: np.ndarray,
        after: np.ndarray,
        change: np.ndarray,
        flood_change_threshold_db: float = -2.0,
        low_backscatter_threshold_db: float = -15.0,
        pixel_area_km2: float = 1.0,
    ) -> Tuple[np.ndarray, np.ndarray, Dict[str, float]]:
        """
        Create flood detection and water classification masks.
        
        Classification logic:
        
        POSSIBLE_FLOOD:
        - Backscatter decreased significantly (≤ -flood_change_threshold_db)
        - Post-event backscatter is low (≤ -low_backscatter_threshold_db)
        - Indicates surface became smoother, consistent with open water
        
        PERSISTENT_LOW_BACKSCATTER:
        - Both pre and post have low backscatter (≤ -low_backscatter_threshold_db)
        - Likely permanent water or permanent smooth surfaces
        
        Args:
            before: Pre-event backscatter in dB
            after: Post-event backscatter in dB
            change: Backscatter change (after - before)
            flood_change_threshold_db: Minimum backscatter decrease to flag as potential flood
            low_backscatter_threshold_db: Backscatter threshold for water-like surfaces
            pixel_area_km2: Area per pixel for area calculations
            
        Returns:
            Tuple of:
                - possible_flood: Binary mask of potential new inundation
                - persistent_low_backscatter: Binary mask of permanent water
                - stats: Dictionary with area and pixel counts
        """
        try:
            # Create validity mask
            valid = np.isfinite(before) & np.isfinite(after) & np.isfinite(change)
            
            # Initialize masks
            possible_flood = np.full(change.shape, np.nan, dtype=np.float32)
            persistent_low_backscatter = np.full(change.shape, np.nan, dtype=np.float32)
            
            # Apply classification logic
            possible_flood[valid] = (
                (change[valid] <= -flood_change_threshold_db)
                & (after[valid] <= low_backscatter_threshold_db)
            ).astype(np.float32)
            
            persistent_low_backscatter[valid] = (
                (before[valid] <= low_backscatter_threshold_db)
                & (after[valid] <= low_backscatter_threshold_db)
            ).astype(np.float32)
            
            # Calculate statistics
            valid_pixels = int(valid.sum())
            possible_flood_pixels = float(np.nansum(possible_flood))
            persistent_pixels = float(np.nansum(persistent_low_backscatter))
            
            stats = {
                "possible_flood_pixels": possible_flood_pixels,
                "persistent_low_backscatter_pixels": persistent_pixels,
                "possible_flood_area_km2": possible_flood_pixels * pixel_area_km2,
                "persistent_low_backscatter_area_km2": persistent_pixels * pixel_area_km2,
                "valid_pixels": float(valid_pixels),
            }
            
            logger.info(
                f"Classification complete: "
                f"possible_flood_area={stats['possible_flood_area_km2']:.2f}km², "
                f"persistent_water_area={stats['persistent_low_backscatter_area_km2']:.2f}km²"
            )
            
            return possible_flood, persistent_low_backscatter, stats
            
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
            return {
                "mean_change_db": np.nan,
                "std_change_db": np.nan,
                "min_change_db": np.nan,
                "max_change_db": np.nan,
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
