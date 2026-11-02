"""
Lightweight demo backend for NASA Space Apps Challenge - NISAR Flood & Wetland Monitor
Works without heavy geospatial dependencies for MOCK mode demonstration.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import random
import math

app = FastAPI(
    title="NISAR Flood & Wetland Monitor",
    description="Interactive mapping and analysis of satellite-detected flood and wetland changes",
    version="1.0.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# DATA MODELS
# ============================================================================

class Scene(BaseModel):
    """NISAR scene metadata."""
    id: str
    datetime: str
    polarization: str
    processing_level: str
    orbit: int
    bounds: Dict[str, float]  # {west, south, east, north}


class SearchRequest(BaseModel):
    """Search request for NISAR scenes."""
    bounds: Dict[str, float]  # {west, south, east, north}
    start_date: str
    end_date: str
    polarization: Optional[str] = "VVVV"


class SearchResponse(BaseModel):
    """Search response with available scenes."""
    status: str
    count: int
    scenes: List[Scene]


class ProcessRequest(BaseModel):
    """Flood detection processing request."""
    before_scene_id: str
    after_scene_id: str
    bounds: Dict[str, float]
    flood_threshold_db: float = -2.0
    water_threshold_db: float = -15.0


class AnalysisResult(BaseModel):
    """Analysis result with flood detection metrics."""
    status: str
    before_scene: str
    after_scene: str
    flood_area_km2: float
    water_area_km2: float
    confidence: float
    affected_locations: List[Dict[str, Any]]


# ============================================================================
# MOCK DATA GENERATOR
# ============================================================================

def generate_mock_scenes(bounds: Dict[str, float], start_date: str, end_date: str) -> List[Scene]:
    """Generate mock NISAR scenes for demonstration."""
    scenes = []
    base_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
    end = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
    
    # Generate scenes every 6 days (simulating NISAR revisit cycle)
    current = base_date
    orbit = 1000
    
    while current <= end:
        scene = Scene(
            id=f"NISAR_20{current.year % 100}{current.month:02d}{current.day:02d}_{orbit:05d}",
            datetime=current.isoformat() + "Z",
            polarization="VVVV",
            processing_level="GCOV",
            orbit=orbit,
            bounds=bounds.copy()
        )
        scenes.append(scene)
        current += timedelta(days=6)
        orbit += 1
    
    return scenes


def generate_mock_analysis(before_id: str, after_id: str) -> AnalysisResult:
    """Generate mock flood analysis results."""
    # Simulate realistic flood detection metrics
    base_flood_area = random.uniform(2.5, 8.5)  # km²
    base_water_area = random.uniform(12.0, 28.0)  # km²
    
    return AnalysisResult(
        status="success",
        before_scene=before_id,
        after_scene=after_id,
        flood_area_km2=base_flood_area + random.uniform(-0.5, 1.5),
        water_area_km2=base_water_area + random.uniform(-2.0, 3.5),
        confidence=random.uniform(0.75, 0.95),
        affected_locations=[
            {
                "name": "Settlement 1",
                "lat": 41.32,
                "lon": 12.72,
                "type": "residential",
                "distance_to_flood_km": random.uniform(0.1, 2.0),
                "exposure": random.choice(["HIGH", "MEDIUM", "LOW"])
            },
            {
                "name": "Road Network",
                "lat": 41.31,
                "lon": 12.73,
                "type": "infrastructure",
                "distance_to_flood_km": random.uniform(0.2, 1.5),
                "exposure": random.choice(["HIGH", "MEDIUM"])
            },
            {
                "name": "Hospital",
                "lat": 41.33,
                "lon": 12.71,
                "type": "hospital",
                "distance_to_flood_km": random.uniform(0.5, 3.0),
                "exposure": random.choice(["MEDIUM", "LOW"])
            },
            {
                "name": "Wetland Area",
                "lat": 41.325,
                "lon": 12.725,
                "type": "wetland",
                "distance_to_flood_km": random.uniform(0.05, 0.5),
                "exposure": "HIGH"
            }
        ]
    )


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", tags=["System"])
async def root():
    """Health check and API information."""
    return {
        "name": "NISAR Flood & Wetland Monitor",
        "version": "1.0.0",
        "status": "running",
        "mode": "MOCK (demonstration)",
        "docs": "/docs",
        "endpoints": {
            "search": "POST /api/search",
            "analyze": "POST /api/analyze",
            "export": "POST /api/export",
            "health": "GET /health"
        }
    }


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }


@app.post("/api/search", response_model=SearchResponse, tags=["Discovery"])
async def search_scenes(request: SearchRequest) -> SearchResponse:
    """
    Search for available NISAR GCOV scenes within geographic bounds and time range.
    
    Returns mock data in demonstration mode.
    """
    try:
        # Generate mock scenes
        scenes = generate_mock_scenes(request.bounds, request.start_date, request.end_date)
        
        return SearchResponse(
            status="success",
            count=len(scenes),
            scenes=scenes
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/analyze", response_model=AnalysisResult, tags=["Analysis"])
async def analyze_flood_change(request: ProcessRequest) -> AnalysisResult:
    """
    Analyze backscatter change between two NISAR GCOV scenes.
    
    Detects:
    - New inundation (negative backscatter change)
    - Wetland expansion
    - Exposed infrastructure
    
    Returns mock analysis results in demonstration mode.
    """
    try:
        # Validate scenes
        if not request.before_scene_id or not request.after_scene_id:
            raise ValueError("Both before and after scene IDs are required")
        
        # Generate mock analysis
        result = generate_mock_analysis(request.before_scene_id, request.after_scene_id)
        
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/export", tags=["Export"])
async def export_results(request: Dict[str, Any]):
    """
    Export analysis results as GeoTIFF, GeoJSON, or PDF.
    
    Returns mock export metadata in demonstration mode.
    """
    try:
        export_format = request.get("format", "geojson")
        
        if export_format not in ["geotiff", "geojson", "pdf"]:
            raise ValueError(f"Unsupported export format: {export_format}")
        
        return {
            "status": "success",
            "format": export_format,
            "message": f"Export to {export_format.upper()} generated successfully",
            "download_url": f"/exports/result_{datetime.utcnow().timestamp()}.{export_format}"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/docs", tags=["Documentation"])
async def api_docs():
    """API documentation and usage guide."""
    return {
        "title": "NISAR Flood & Wetland Monitor API",
        "description": "RESTful API for satellite-based flood and wetland monitoring",
        "endpoints": {
            "search_scenes": {
                "method": "POST",
                "path": "/api/search",
                "description": "Search for NISAR GCOV scenes in geographic area and time range",
                "example": {
                    "bounds": {"west": 12.70, "south": 41.30, "east": 12.75, "north": 41.35},
                    "start_date": "2025-01-01T00:00:00Z",
                    "end_date": "2025-03-01T00:00:00Z",
                    "polarization": "VVVV"
                }
            },
            "analyze_flood": {
                "method": "POST",
                "path": "/api/analyze",
                "description": "Detect and analyze flood extent changes between two scenes",
                "example": {
                    "before_scene_id": "NISAR_20250105_01000",
                    "after_scene_id": "NISAR_20250111_01001",
                    "bounds": {"west": 12.70, "south": 41.30, "east": 12.75, "north": 41.35},
                    "flood_threshold_db": -2.0,
                    "water_threshold_db": -15.0
                }
            },
            "export": {
                "method": "POST",
                "path": "/api/export",
                "description": "Export analysis results in various formats",
                "formats": ["geojson", "geotiff", "pdf"]
            }
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
