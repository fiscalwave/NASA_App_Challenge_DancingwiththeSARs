"""
Processing API endpoints for flood detection analysis.
"""

from typing import Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from pathlib import Path
import numpy as np
from app.processing.gcov_reader import GCOVReader
from app.processing.change_detection import ChangeDetectionEngine
from app.exports.geotiff import GeoTIFFExporter
from app.utils.errors import ProcessingError, ValidationError
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class BoundsModel(BaseModel):
    """Geographic bounds."""
    west: float
    south: float
    east: float
    north: float


class ProcessRequestModel(BaseModel):
    """Flood detection processing request."""
    before_scene: str
    after_scene: str
    bounds: BoundsModel
    polarization: str = "VVVV"
    flood_change_threshold_db: float = -2.0
    low_backscatter_threshold_db: float = -15.0


class ProcessResponseModel(BaseModel):
    """Processing response with analysis results."""
    status: str
    message: str
    results: Dict[str, Any] = None
    error: str = None


@router.post("/analyze", response_model=ProcessResponseModel)
async def analyze_flood_change(request: ProcessRequestModel):
    """
    Analyze backscatter change between two GCOV scenes.
    
    **Process:**
    1. Load before-event GCOV subset
    2. Load after-event GCOV subset
    3. Spatially align both datasets
    4. Calculate backscatter change (Δσ⁰)
    5. Apply flood classification masks
    6. Generate statistics
    
    **Classification Results:**
    - Possible new inundation: Significant backscatter decrease + low post-event backscatter
    - Persistent water: Low backscatter in both pre and post events
    
    Args:
        request: Processing parameters
        
    Returns:
        Analysis results with statistics and classifications
        
    Raises:
        HTTPException: If processing fails
    """
    try:
        bounds_tuple = (
            request.bounds.west, request.bounds.south,
            request.bounds.east, request.bounds.north
        )
        
        logger.info(f"Starting flood analysis between scenes")
        logger.info(f"Polarization: {request.polarization}")
        logger.info(f"Thresholds: flood_change={request.flood_change_threshold_db}dB, "
                   f"low_backscatter={request.low_backscatter_threshold_db}dB")
        
        # Load and validate GCOV subsets
        logger.info("Loading before-event scene...")
        before_data = GCOVReader.load_gcov_subset(
            Path(request.before_scene),
            request.polarization,
            bounds_tuple
        )
        
        logger.info("Loading after-event scene...")
        after_data = GCOVReader.load_gcov_subset(
            Path(request.after_scene),
            request.polarization,
            bounds_tuple
        )
        
        # Align and compute change
        logger.info("Aligning scenes and computing backscatter change...")
        change, aligned_before, aligned_after, pixel_area_km2 = (
            ChangeDetectionEngine.align_and_compare(before_data, after_data)
        )
        
        # Generate classification masks
        logger.info("Generating flood classification masks...")
        possible_flood, possible_flooded_vegetation, persistent_low_backscatter, screening_stats = (
            ChangeDetectionEngine.create_flood_classification_masks(
                aligned_before,
                aligned_after,
                change,
                request.flood_change_threshold_db,
                request.low_backscatter_threshold_db,
                pixel_area_km2
            )
        )
        
        # Calculate change statistics
        change_stats = ChangeDetectionEngine.calculate_change_statistics(change)
        
        # Export results as GeoTIFF
        logger.info("Exporting results as GeoTIFF...")
        before_tiff = GeoTIFFExporter.export_to_geotiff(
            aligned_before,
            before_data["transform"],
            before_data["crs"]
        )
        after_tiff = GeoTIFFExporter.export_to_geotiff(
            aligned_after,
            after_data["transform"],
            after_data["crs"]
        )
        change_tiff = GeoTIFFExporter.export_to_geotiff(
            change,
            after_data["transform"],
            after_data["crs"]
        )
        possible_flood_tiff = GeoTIFFExporter.export_to_geotiff(
            possible_flood,
            after_data["transform"],
            after_data["crs"]
        )
        possible_flooded_vegetation_tiff = GeoTIFFExporter.export_to_geotiff(
            possible_flooded_vegetation,
            after_data["transform"],
            after_data["crs"]
        )
        persistent_water_tiff = GeoTIFFExporter.export_to_geotiff(
            persistent_low_backscatter,
            after_data["transform"],
            after_data["crs"]
        )
        
        results = {
            "before_scene": request.before_scene,
            "after_scene": request.after_scene,
            "polarization": request.polarization,
            "thresholds": {
                "flood_change_db": request.flood_change_threshold_db,
                "low_backscatter_db": request.low_backscatter_threshold_db,
            },
            "change_statistics": change_stats,
            "classification_statistics": screening_stats,
            "exports": {
                "before_geotiff": "base64:" + before_tiff.hex()[:50] + "...",
                "after_geotiff": "base64:" + after_tiff.hex()[:50] + "...",
                "change_geotiff": "base64:" + change_tiff.hex()[:50] + "...",
                "possible_flood_geotiff": "base64:" + possible_flood_tiff.hex()[:50] + "...",
                "possible_flooded_vegetation_geotiff": "base64:" + possible_flooded_vegetation_tiff.hex()[:50] + "...",
                "persistent_water_geotiff": "base64:" + persistent_water_tiff.hex()[:50] + "...",
            },
            "pixel_area_km2": pixel_area_km2,
        }
        
        logger.info("Analysis complete")
        logger.info(f"Possible flood area: {screening_stats['possible_flood_area_km2']:.2f} km²")
        logger.info(f"Possible flooded vegetation area: {screening_stats['possible_flooded_vegetation_area_km2']:.2f} km²")
        logger.info(f"Persistent water area: {screening_stats['persistent_low_backscatter_area_km2']:.2f} km²")
        
        return ProcessResponseModel(
            status="success",
            message="Flood analysis completed successfully",
            results=results
        )
    
    except (ProcessingError, ValidationError) as e:
        logger.error(f"Processing error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Processing failed")
