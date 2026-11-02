"""
Search API endpoints for data discovery.
"""

from datetime import date
from typing import List
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from app.config import get_config, DataMode
from app.ingestion.asf_adapter import ASFAdapter
from app.ingestion.local_adapter import LocalAdapter
from app.utils.errors import DataIngestionError
from app.utils.logging import get_logger

logger = get_logger(__name__)

router = APIRouter()


class BoundsModel(BaseModel):
    """Geographic bounds model."""
    west: float
    south: float
    east: float
    north: float


class SearchRequestModel(BaseModel):
    """NISAR GCOV search request."""
    bounds: BoundsModel
    start_date: date
    end_date: date
    username: str = None
    password: str = None


class SceneResultModel(BaseModel):
    """Individual scene result."""
    name: str
    url: str = None
    path: str = None
    timestamp: str


class SearchResponseModel(BaseModel):
    """Search response."""
    scenes: List[SceneResultModel]
    total: int
    mode: str


@router.post("/scenes", response_model=SearchResponseModel)
async def search_scenes(request: SearchRequestModel):
    """
    Search for available NISAR GCOV scenes in a geographic area and time range.
    
    **Modes:**
    - MOCK: Returns simulated results
    - LOCAL: Searches local data directory
    - API: Searches ASF via API (requires credentials)
    
    Args:
        request: Search parameters
        
    Returns:
        List of available scenes
        
    Raises:
        HTTPException: If search fails
    """
    try:
        config = get_config()
        bounds_tuple = (request.bounds.west, request.bounds.south, 
                       request.bounds.east, request.bounds.north)
        
        if config.DATA_MODE == DataMode.MOCK:
            # Return simulated results
            logger.info("Returning MOCK search results")
            mock_scenes = [
                SceneResultModel(
                    name="NISAR_SLC_G4S1_2024_10_25_151802_VV_20241025151800.h5",
                    url=None,
                    path="data/sample_scenes/mock_before.h5",
                    timestamp="2024-10-25"
                ),
                SceneResultModel(
                    name="NISAR_SLC_G4S1_2024_11_01_151802_VV_20241101151800.h5",
                    url=None,
                    path="data/sample_scenes/mock_after.h5",
                    timestamp="2024-11-01"
                ),
            ]
            return SearchResponseModel(
                scenes=mock_scenes,
                total=len(mock_scenes),
                mode="MOCK"
            )
        
        elif config.DATA_MODE == DataMode.LOCAL:
            # Search local directory
            logger.info(f"Searching LOCAL directory: {config.DATA_DIR}")
            local_files = LocalAdapter.discover_gcov_files(config.DATA_DIR)
            
            scenes = [
                SceneResultModel(
                    name=f.name,
                    url=None,
                    path=str(f),
                    timestamp=f.name.split('_')[4] if len(f.name.split('_')) > 4 else "unknown"
                )
                for f in local_files
            ]
            
            return SearchResponseModel(
                scenes=scenes,
                total=len(scenes),
                mode="LOCAL"
            )
        
        elif config.DATA_MODE == DataMode.API:
            # Search via ASF API
            if not request.username or not request.password:
                raise HTTPException(
                    status_code=400,
                    detail="Username and password required for API mode"
                )
            
            logger.info("Searching ASF API")
            urls = ASFAdapter.search_gcov(
                request.username,
                request.password,
                bounds_tuple,
                request.start_date,
                request.end_date
            )
            
            scenes = [
                SceneResultModel(
                    name=url.split('/')[-1],
                    url=url,
                    path=None,
                    timestamp=url.split('_')[4] if len(url.split('_')) > 4 else "unknown"
                )
                for url in urls
            ]
            
            return SearchResponseModel(
                scenes=scenes,
                total=len(scenes),
                mode="API"
            )
        
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Unsupported data mode: {config.DATA_MODE}"
            )
    
    except DataIngestionError as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error during search: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/polarizations")
async def get_available_polarizations(scene_path: str = Query(...)):
    """
    Get available polarization channels for a GCOV scene.
    
    Args:
        scene_path: Path to GCOV HDF5 file
        
    Returns:
        List of available polarizations
    """
    try:
        from pathlib import Path
        from app.processing.gcov_reader import GCOVReader
        
        scene_file = Path(scene_path)
        if not scene_file.exists():
            raise HTTPException(status_code=404, detail="Scene file not found")
        
        polarizations = GCOVReader.list_polarizations(scene_file)
        
        return {
            "scene": scene_file.name,
            "polarizations": polarizations,
            "total": len(polarizations)
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get polarizations: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get polarizations")
