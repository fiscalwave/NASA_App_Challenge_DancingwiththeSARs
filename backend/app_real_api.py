"""
NISAR Flood & Wetland Monitor - Backend API
Uses REAL ASF/NASA data only - NO MOCK DATA
Requires Earthdata login credentials for authentication
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime
import os
import sys
import hashlib
import json
from pathlib import Path
from dotenv import load_dotenv
import asf_search

# Add backend directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import imagery handler (real-data GeoTIFF-to-PNG rendering only - the
# previous synthetic/fabricated visualization path has been removed)
try:
    from imagery_handler import render_real_sar_layer
except ImportError as e:
    print(f"Warning: Could not import imagery_handler: {e}")
    render_real_sar_layer = None

# Import Phase 4 real-data discovery/download pipeline (dormant app/ package,
# now wired into the live API additively - does not replace /api/search)
try:
    from app.ingestion.cmr_adapter import CMRAdapter, _parse_granule_acquisition_time
    from app.ingestion.download_manager import DownloadManager
except ImportError as e:
    print(f"Warning: Could not import discovery/download pipeline: {e}")
    CMRAdapter = None
    DownloadManager = None
    _parse_granule_acquisition_time = None

# Import Phase 5 real GCOV processing pipeline (dormant app/ package: real
# HDF5 reading, backscatter change detection, flood classification, and
# GeoTIFF/GeoJSON export - additive, does not replace existing imagery/analyze)
try:
    from app.processing.gcov_reader import GCOVReader
    from app.processing.change_detection import ChangeDetectionEngine
    from app.exports.geotiff import GeoTIFFExporter
    from app.exports.geojson import GeoJSONExporter
    from app.ingestion.cmr_adapter import _parse_granule_id_fields
    from app.utils.errors import ProcessingError, ValidationError, DataIngestionError
except ImportError as e:
    print(f"Warning: Could not import GCOV processing pipeline: {e}")
    GCOVReader = None
    ChangeDetectionEngine = None
    GeoTIFFExporter = None
    GeoJSONExporter = None

# Import Phase 6 emergency management intelligence (real infrastructure
# impact analysis via OpenStreetMap + explainable priority scoring) -
# additive, built on top of Phase 5's real change-detection output
try:
    from app.analysis.infrastructure_impact import compute_infrastructure_impact
    from app.analysis.priority import compute_priority, compute_observation_age_days, compute_detection_confidence
except ImportError as e:
    print(f"Warning: Could not import Phase 6 analysis pipeline: {e}")
    compute_infrastructure_impact = None
    compute_priority = None
    compute_observation_age_days = None
    compute_detection_confidence = None


# Load environment variables from .env (in backend directory)
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

print(f"\nLoading .env from: {env_path}")
print(f"Env file exists: {env_path.exists()}")

app = FastAPI(
    title="NISAR Flood & Wetland Monitor",
    description="Interactive mapping and analysis of satellite-detected flood and wetland changes",
    version="1.0.0"
)

# ============================================================================
# CONFIGURATION - REAL API MODE ONLY
# ============================================================================

import re

# Read Earthdata credentials from .env file - REQUIRED
ASF_USERNAME = ""
ASF_PASSWORD = ""
ENV_FILE_FOUND = False

if env_path.exists():
    try:
        with open(env_path, 'r') as f:
            content = f.read()
            
            # Extract ASF_USERNAME
            un_match = re.search(r'ASF_USERNAME=(\S+)', content)
            if un_match:
                ASF_USERNAME = un_match.group(1).strip()
            
            # Extract ASF_PASSWORD (handles special characters)
            pw_match = re.search(r'ASF_PASSWORD=(.+?)(\s|#|$)', content)
            if pw_match:
                ASF_PASSWORD = pw_match.group(1).strip()
            
            ENV_FILE_FOUND = True
    except Exception as e:
        print(f"ERROR: Cannot read .env file: {e}")

# Also try os.getenv as fallback
if not ASF_USERNAME:
    ASF_USERNAME = os.getenv("ASF_USERNAME", "").strip()

if not ASF_PASSWORD:
    ASF_PASSWORD = os.getenv("ASF_PASSWORD", "").strip()

# Validate credentials exist - REQUIRED for API-only mode
if not ASF_USERNAME or not ASF_PASSWORD:
    raise RuntimeError(
        "FATAL: Earthdata credentials are REQUIRED.\n"
        "Set ASF_USERNAME and ASF_PASSWORD in backend/.env file\n"
        "Example:\n"
        "  ASF_USERNAME=your_earthdata_username\n"
        "  ASF_PASSWORD=your_earthdata_password"
    )

print(f"Configuration loaded successfully")
print(f"  Earthdata username: {ASF_USERNAME}")
print(f"  .env file found: {ENV_FILE_FOUND}")

# ============================================================================
# PHASE 4: REAL-DATA DISCOVERY & DOWNLOAD PIPELINE (additive, /api/v2/*)
# ============================================================================

GCOV_CACHE_DIR = Path(__file__).parent / "data" / "cache"
GCOV_SAMPLE_DIR = Path(__file__).parent.parent / "data" / "scenes"

# ============================================================================
# PHASE 5: REAL CHANGE-DETECTION ANALYSIS RESULTS CACHE (additive, /api/v2/*)
# ============================================================================

GCOV_ANALYSIS_CACHE_DIR = Path(__file__).parent / "data" / "analysis_cache"
GCOV_ANALYSIS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

download_manager = None
if DownloadManager is not None:
    download_manager = DownloadManager(
        cache_dir=GCOV_CACHE_DIR,
        username=ASF_USERNAME,
        password=ASF_PASSWORD,
        max_concurrent_downloads=2,
    )
    # Register any already-downloaded real GCOV sample files so the dedup
    # cache is aware of them immediately, without re-downloading or faking status
    if GCOV_SAMPLE_DIR.exists():
        for h5_file in GCOV_SAMPLE_DIR.glob("*.h5"):
            granule_id = h5_file.stem
            try:
                download_manager.register_existing_file(granule_id, h5_file)
                print(f"  Registered existing real GCOV sample: {granule_id}")
            except Exception as e:
                print(f"  Warning: could not register {h5_file.name}: {e}")

# Print startup info
@app.on_event("startup")
async def startup_event():
    print(f"\n========== SERVER STARTUP ==========")
    print(f"Operating in: REAL API MODE (No Mock Data)")
    print(f"Using asf_search library version: {asf_search.__version__}")
    print(f"Earthdata username: {ASF_USERNAME}")
    print(f"===================================\n")

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
    bounds: Dict[str, float]


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


# ============================================================================
# PHASE 4 MODELS: Intelligent discovery & efficient download (real data only)
# ============================================================================

class BoundsModel(BaseModel):
    """Geographic bounds in EPSG:4326."""
    west: float
    south: float
    east: float
    north: float


class DiscoverRequest(BaseModel):
    """Intelligent pre/post-event NISAR L2 GCOV discovery request."""
    bounds: BoundsModel
    event_start: str  # YYYY-MM-DD
    event_end: str  # YYYY-MM-DD
    pre_event_days: int = 30
    post_event_days: int = 30
    tiers: Optional[List[str]] = None  # subset/order of VALIDATED/PROVISIONAL/BETA


class DownloadStartRequest(BaseModel):
    """Start (or resume/dedup-skip) a real granule download."""
    granule_id: str
    download_url: str
    expected_size_mb: Optional[float] = None


class AnalyzeRequest(BaseModel):
    """Real before/after NISAR L2 GCOV change-detection request.

    Both granules must already be fully downloaded (status "complete" via
    /api/v2/download/status) - this endpoint reads real local HDF5 files,
    it does not download anything itself."""
    before_granule_id: str
    after_granule_id: str
    bounds: BoundsModel
    polarization: str = "HHHH"
    flood_change_threshold_db: float = -2.0
    low_backscatter_threshold_db: float = -15.0


# ============================================================================
# ASF API SEARCH - REAL DATA ONLY
# ============================================================================

def search_asf_nisar_data(bounds: Dict[str, float], start_date: str, end_date: str) -> List[Scene]:
    """
    Search REAL SAR data from ASF using Earthdata credentials.
    
    This function uses the asf_search Python library to query the ASF API.
    First searches for NISAR GCOV data; if unavailable, searches for Sentinel-1 data.
    No mock data fallback - searches only for real satellite data.
    
    Args:
        bounds: Geographic bounds {west, south, east, north}
        start_date: Start date in YYYY-MM-DD format
        end_date: End date in YYYY-MM-DD format
    
    Returns:
        List of Scene objects with real SAR data (NISAR or Sentinel-1)
    
    Raises:
        ValueError: If search returns no results or API call fails
    """
    
    try:
        # Extract bounds
        west, south, east, north = (
            bounds.get('west', 0),
            bounds.get('south', 0),
            bounds.get('east', 0),
            bounds.get('north', 0)
        )
        
        print(f"\nSearching ASF for REAL SAR data (NISAR or Sentinel-1)...")
        print(f"  Bounds: ({west}, {south}, {east}, {north})")
        print(f"  Date Range: {start_date} to {end_date}")
        print(f"  Using asf_search library version {asf_search.__version__}...")
        
        # Create WKT polygon for search
        wkt_polygon = f"POLYGON(({west} {south},{east} {south},{east} {north},{west} {north},{west} {south}))"
        
        # Create authenticated session
        session = asf_search.ASFSession()
        session.auth_with_creds(ASF_USERNAME, ASF_PASSWORD)
        print(f"  Authentication successful")
        
        # Try NISAR first
        print(f"  Searching for NISAR GCOV data...")
        results = asf_search.search(
            platform="NISAR",
            processingLevel="GCOV",
            start=start_date,
            end=end_date,
            intersectsWith=wkt_polygon,
            maxResults=100,
            session=session
        )
        
        print(f"  Found {len(results)} NISAR scenes")
        
        # If no NISAR, try Sentinel-1 (which has extensive historical data)
        if len(results) == 0:
            print(f"  No NISAR found; searching for Sentinel-1 GRD data...")
            results = asf_search.search(
                platform="SENTINEL1",
                processingLevel="GRD_HD",
                start=start_date,
                end=end_date,
                intersectsWith=wkt_polygon,
                maxResults=100,
                session=session
            )
            print(f"  Found {len(results)} Sentinel-1 GRD_HD scenes")
        
        # If still no results, try Sentinel-1 without processing level filter
        if len(results) == 0:
            print(f"  Trying Sentinel-1 with any processing level...")
            results = asf_search.search(
                platform="SENTINEL1",
                start=start_date,
                end=end_date,
                intersectsWith=wkt_polygon,
                maxResults=100,
                session=session
            )
            print(f"  Found {len(results)} Sentinel-1 scenes (any level)")
        
        if len(results) == 0:
            # Honest failure: no real SAR data was found for this area/date range
            # in any of the ASF-indexed collections we tried (NISAR GCOV,
            # Sentinel-1 GRD_HD, Sentinel-1 any level). Never substitute
            # fabricated/demo scenes - raise so the caller can report this
            # truthfully to the user.
            raise ValueError(
                f"No real SAR scenes (NISAR or Sentinel-1) found from ASF for this area "
                f"({west}, {south}, {east}, {north}) and date range ({start_date} to {end_date})."
            )
        
        # Convert ASF results to Scene objects
        scenes = []
        for result in results:
            try:
                # Handle different result formats
                if isinstance(result, dict):
                    scene_id = result.get('filename', result.get('fileID', 'unknown'))
                    scene_date = result.get('startTime', start_date)
                    orbit = result.get('orbitNumber', 0)
                else:
                    # ASF result object - try multiple attribute names
                    # Print available attributes for debugging
                    available_attrs = [a for a in dir(result) if not a.startswith('_')]
                    
                    # Try filename first (works for Sentinel-1)
                    if hasattr(result, 'filename'):
                        scene_id = str(result.filename)
                    # Try granuleName (works for NISAR)
                    elif hasattr(result, 'granuleName'):
                        scene_id = str(result.granuleName)
                    # Try fileID (works for some products)
                    elif hasattr(result, 'fileID'):
                        scene_id = str(result.fileID)
                    # Try other common names
                    elif hasattr(result, 'sceneName'):
                        scene_id = str(result.sceneName)
                    elif hasattr(result, 'productName'):
                        scene_id = str(result.productName)
                    elif hasattr(result, 'name'):
                        scene_id = str(result.name)
                    else:
                        # Last resort: create ID from available data
                        if hasattr(result, 'centerLat') and hasattr(result, 'centerLon'):
                            scene_id = f"NISAR_{start_date}_{available_attrs[0]}"
                        else:
                            scene_id = f"NISAR_{start_date}"
                        print(f"  Using fallback ID. Available attrs: {available_attrs[:10]}")
                    
                    # Get start time
                    if hasattr(result, 'startTime'):
                        scene_date = str(result.startTime)
                    elif hasattr(result, 'startDateTime'):
                        scene_date = str(result.startDateTime)
                    elif hasattr(result, 'processingDate'):
                        scene_date = str(result.processingDate)
                    else:
                        scene_date = start_date
                    
                    # Get orbit number
                    if hasattr(result, 'orbitNumber'):
                        orbit = int(result.orbitNumber)
                    elif hasattr(result, 'orbitCycle'):
                        orbit = int(result.orbitCycle)
                    else:
                        orbit = 0
                
                scene = Scene(
                    id=scene_id,
                    datetime=scene_date,
                    polarization="VV/VH" if "NISAR" in scene_id.upper() else "VV/VH",
                    processing_level="GCOV" if "NISAR" in scene_id.upper() else ("GRD_HD" if "SENTINEL" in scene_id.upper() else "GCOV"),
                    orbit=orbit if isinstance(orbit, int) else 0,
                    bounds=bounds.copy()
                )
                scenes.append(scene)
                print(f"  Added: {scene_id}")
            except Exception as e:
                print(f"  WARNING parsing result: {e}")
                print(f"  Result type: {type(result).__name__}")
                continue
        
        if not scenes:
            raise ValueError("No valid scenes could be parsed from ASF results")
        
        print(f"SUCCESS: Found {len(scenes)} real SAR scenes")
        return scenes
        
    except Exception as e:
        error_msg = f"ASF API search error: {str(e)}"
        print(f"ERROR: {error_msg}")
        # No synthetic/fabricated fallback - report the real failure honestly.
        raise ValueError(error_msg)


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", tags=["System"])
async def root():
    """Serve the frontend application."""
    index_path = Path(__file__).parent.parent / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {
        "name": "NISAR Flood & Wetland Monitor",
        "version": "1.0.0",
        "status": "running",
        "mode": "REAL API (No Mock Data)",
        "asf_search_version": asf_search.__version__,
        "docs": "/docs",
        "endpoints": {
            "search": "POST /api/search",
            "discover_v2": "POST /api/v2/discover",
            "download_v2": "POST /api/v2/download/start",
            "analyze_v2": "POST /api/v2/analyze",
            "impact_v2": "POST /api/v2/analyze/{analysis_id}/impact",
            "health": "GET /health"
        }
    }


@app.get("/api", tags=["System"])
async def api_info():
    """API information."""
    return {
        "name": "NISAR Flood & Wetland Monitor",
        "version": "1.0.0",
        "status": "running",
        "mode": "REAL API (No Mock Data)",
        "asf_search_version": asf_search.__version__,
        "docs": "/docs",
        "endpoints": {
            "search": "POST /api/search",
            "discover_v2": "POST /api/v2/discover",
            "download_v2": "POST /api/v2/download/start",
            "analyze_v2": "POST /api/v2/analyze",
            "impact_v2": "POST /api/v2/analyze/{analysis_id}/impact",
            "health": "GET /health"
        }
    }


@app.get("/health", tags=["System"])
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "mode": "REAL API ONLY"
    }


@app.post("/api/search", response_model=SearchResponse, tags=["Discovery"])
async def search_scenes(request: SearchRequest) -> SearchResponse:
    """
    Search for available REAL NISAR GCOV scenes within geographic bounds and time range.
    
    This endpoint ONLY returns real data from ASF API.
    If no real data is available, it returns an error with details about what was requested.
    """
    try:
        print(f"\nProcessing search request...")
        scenes = search_asf_nisar_data(request.bounds, request.start_date, request.end_date)
        
        return SearchResponse(
            status="success",
            count=len(scenes),
            scenes=scenes
        )
    except ValueError as e:
        # Return user-friendly error for no results
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )
    except Exception as e:
        # Return error for other failures
        error_detail = f"Search error: {str(e)}"
        print(f"ERROR: {error_detail}")
        raise HTTPException(
            status_code=500,
            detail=error_detail
        )



# ============================================================================
# IMAGERY VISUALIZATION (real before/after/change rendering from Phase 5
# GeoTIFF output - the previous synthetic/procedurally-generated visualization
# path has been removed entirely; see /api/v2/analyze/{analysis_id}/visual/*)
# ============================================================================

# ============================================================================
# PHASE 4: INTELLIGENT DATA DISCOVERY & EFFICIENT DOWNLOAD (real data only)
# ============================================================================

@app.post("/api/v2/discover", tags=["Discovery v2"])
async def discover_nisar_granules(request: DiscoverRequest):
    """
    Real NISAR L2 GCOV discovery for a geographic area and event window.

    Queries NASA CMR directly (metadata-first - no data is downloaded here)
    across the requested data-maturity tiers (Validated / Provisional / Beta),
    separately for the pre-event and post-event windows, and flags which
    before/after granule pairs share compatible acquisition geometry (same
    track, frame, and pass direction). Returns an empty list - never mock
    data - if nothing is found for the requested area/dates/tiers.
    """
    if CMRAdapter is None:
        raise HTTPException(status_code=503, detail="Discovery pipeline not available")

    try:
        bounds_tuple = (
            request.bounds.west, request.bounds.south,
            request.bounds.east, request.bounds.north,
        )
        event_start = datetime.strptime(request.event_start, "%Y-%m-%d").date()
        event_end = datetime.strptime(request.event_end, "%Y-%m-%d").date()

        result = CMRAdapter.discover_pre_post_event(
            bounds_tuple,
            event_start=event_start,
            event_end=event_end,
            pre_event_days=request.pre_event_days,
            post_event_days=request.post_event_days,
            tiers=request.tiers,
        )
        result["status"] = "success"
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discovery error: {str(e)}")


@app.post("/api/v2/download/start", tags=["Download v2"])
async def start_granule_download(request: DownloadStartRequest):
    """
    Start, resume, or dedup-skip a real NISAR GCOV granule download.

    Returns immediately with the current status; the actual transfer runs in
    a background thread from a bounded pool (controlled concurrency). Poll
    GET /api/v2/download/status/{granule_id} for real, byte-accurate progress.
    """
    if download_manager is None:
        raise HTTPException(status_code=503, detail="Download manager not available")

    try:
        status = download_manager.start_download(
            request.granule_id, request.download_url, request.expected_size_mb
        )
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Download start error: {str(e)}")


@app.get("/api/v2/download/status/{granule_id}", tags=["Download v2"])
async def get_granule_download_status(granule_id: str):
    """Real download status for a granule, verified against actual bytes on disk."""
    if download_manager is None:
        raise HTTPException(status_code=503, detail="Download manager not available")
    return download_manager.get_status(granule_id)


@app.get("/api/v2/cache", tags=["Download v2"])
async def list_granule_cache():
    """List all granules known to the local cache (complete, partial, or failed)."""
    if download_manager is None:
        raise HTTPException(status_code=503, detail="Download manager not available")
    return {"status": "success", "cache": download_manager.list_cache()}


# ============================================================================
# PHASE 5: REAL FLOOD/CHANGE DETECTION (real GCOV HDF5 processing, /api/v2/*)
# ============================================================================

def _resolve_granule_path(granule_id: str) -> Path:
    """Resolve a granule_id to its local file path, requiring it to already be
    fully downloaded (status == 'complete'). Never substitutes a different
    file or mock data."""
    if download_manager is None:
        raise HTTPException(status_code=503, detail="Download manager not available")
    status = download_manager.get_status(granule_id)
    if status.get("status") != "complete":
        raise HTTPException(
            status_code=404,
            detail=(
                f"Granule '{granule_id}' is not downloaded yet "
                f"(status: {status.get('status', 'not_found')}). Use "
                f"/api/v2/download/start first and poll /api/v2/download/status/{{granule_id}}."
            ),
        )
    local_path = Path(status["local_path"])
    if not local_path.exists():
        raise HTTPException(status_code=404, detail=f"Cached file missing on disk for granule '{granule_id}'")
    return local_path


def _analysis_id_for(request: AnalyzeRequest) -> str:
    seed = (
        f"{request.before_granule_id}|{request.after_granule_id}|"
        f"{request.bounds.west}|{request.bounds.south}|{request.bounds.east}|{request.bounds.north}|"
        f"{request.polarization}|{request.flood_change_threshold_db}|{request.low_backscatter_threshold_db}"
    )
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


@app.post("/api/v2/analyze", tags=["Analysis v2"])
async def analyze_real_change(request: AnalyzeRequest):
    """
    Real NISAR L2 GCOV before/after change detection.

    Reads actual HDF5 backscatter data for both granules (which must already
    be downloaded locally via /api/v2/download), reprojects/aligns them,
    computes the real backscatter difference (delta sigma0 = sigma0_post -
    sigma0_pre), and classifies possible new inundation vs persistent
    low-backscatter (existing water) using documented, configurable
    thresholds. Results (GeoTIFFs + GeoJSON + stats) are cached on disk keyed
    by a deterministic analysis_id, so an identical repeat request is not
    reprocessed.

    Never fabricates results - if either granule is not yet downloaded, or
    the AOI does not overlap one of the files, a clear error is returned
    instead of mock data. If the before/after granules have incompatible
    acquisition geometry (different track/frame/pass-direction), the
    response includes a geometry_warning rather than silently treating the
    comparison as equally reliable.
    """
    if GCOVReader is None or ChangeDetectionEngine is None:
        raise HTTPException(status_code=503, detail="GCOV processing pipeline not available")

    analysis_id = _analysis_id_for(request)
    result_dir = GCOV_ANALYSIS_CACHE_DIR / analysis_id
    summary_path = result_dir / "summary.json"

    # Cache hit: identical request already processed - skip reprocessing
    if summary_path.exists():
        with open(summary_path) as f:
            cached = json.load(f)
        cached["cached"] = True
        return cached

    before_path = _resolve_granule_path(request.before_granule_id)
    after_path = _resolve_granule_path(request.after_granule_id)

    bounds_tuple = (request.bounds.west, request.bounds.south, request.bounds.east, request.bounds.north)

    # Geometry compatibility check (does not block the analysis, but flags
    # the limitation rather than silently comparing incompatible geometries)
    before_fields = _parse_granule_id_fields(request.before_granule_id)
    after_fields = _parse_granule_id_fields(request.after_granule_id)
    geometry_compatible = (
        before_fields.get("track") is not None
        and before_fields["track"] == after_fields.get("track")
        and before_fields["frame"] == after_fields.get("frame")
        and before_fields["pass_direction"] == after_fields.get("pass_direction")
    )

    try:
        before_data = GCOVReader.load_gcov_subset(before_path, request.polarization, bounds_tuple)
        after_data = GCOVReader.load_gcov_subset(after_path, request.polarization, bounds_tuple)

        change, aligned_before, aligned_after, pixel_area_km2 = ChangeDetectionEngine.align_and_compare(
            before_data, after_data
        )
        possible_flood, persistent_water, classification_stats = (
            ChangeDetectionEngine.create_flood_classification_masks(
                aligned_before, aligned_after, change,
                request.flood_change_threshold_db, request.low_backscatter_threshold_db, pixel_area_km2,
            )
        )
        change_stats = ChangeDetectionEngine.calculate_change_statistics(change)

        # Real, explainable detection-confidence assessment (replaces the
        # previous hash-derived fake confidence/quality-flags system)
        acquisition_time = (
            _parse_granule_acquisition_time(request.after_granule_id)
            if _parse_granule_acquisition_time else None
        )
        observation_age_days = (
            compute_observation_age_days(acquisition_time) if compute_observation_age_days else None
        )
        detection_confidence = (
            compute_detection_confidence(change_stats, classification_stats, geometry_compatible, observation_age_days)
            if compute_detection_confidence else None
        )

        result_dir.mkdir(parents=True, exist_ok=True)

        layers = {
            "before": aligned_before,
            "after": aligned_after,
            "change": change,
            "possible_flood": possible_flood,
            "persistent_water": persistent_water,
        }
        for name, arr in layers.items():
            tif_bytes = GeoTIFFExporter.export_to_geotiff(arr, after_data["transform"], after_data["crs"])
            (result_dir / f"{name}.tif").write_bytes(tif_bytes)

        # Vectorize the classification masks to real GeoJSON polygons
        for name in ("possible_flood", "persistent_water"):
            geojson_str = GeoJSONExporter.raster_to_geojson(layers[name], after_data["transform"], after_data["crs"])
            (result_dir / f"{name}.geojson").write_text(geojson_str)

        summary = {
            "status": "success",
            "analysis_id": analysis_id,
            "cached": False,
            "before_granule_id": request.before_granule_id,
            "after_granule_id": request.after_granule_id,
            "polarization": request.polarization,
            "bounds": list(bounds_tuple),
            "crs": after_data["crs"],
            "pixel_area_km2": pixel_area_km2,
            "shape": list(change.shape),
            "thresholds": {
                "flood_change_db": request.flood_change_threshold_db,
                "low_backscatter_db": request.low_backscatter_threshold_db,
            },
            "change_statistics": change_stats,
            "classification_statistics": classification_stats,
            "geometry_compatible": geometry_compatible,
            "geometry_warning": None if geometry_compatible else (
                "The before and after granules have different track, frame, or pass "
                "direction. Backscatter differences may partly reflect different SAR "
                "look geometry rather than real surface change. Treat results as lower confidence."
            ),
            "after_granule_acquisition_time": acquisition_time,
            "observation_age_days": observation_age_days,
            "detection_confidence": detection_confidence,
            "layers": {name: f"/api/v2/analyze/{analysis_id}/layer/{name}.tif" for name in layers},
            "geojson": {
                name: f"/api/v2/analyze/{analysis_id}/geojson/{name}.geojson"
                for name in ("possible_flood", "persistent_water")
            },
            "visual": {
                "before": f"/api/v2/analyze/{analysis_id}/visual/before",
                "after": f"/api/v2/analyze/{analysis_id}/visual/after",
            },
        }

        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        return summary

    except (ProcessingError, ValidationError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")


@app.get("/api/v2/analyze/{analysis_id}/layer/{layer_name}", tags=["Analysis v2"])
async def get_analysis_layer(analysis_id: str, layer_name: str):
    """Download a real GeoTIFF raster layer from a completed analysis."""
    file_path = GCOV_ANALYSIS_CACHE_DIR / analysis_id / layer_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Layer not found")
    return FileResponse(file_path, media_type="image/tiff")


@app.get("/api/v2/analyze/{analysis_id}/geojson/{layer_name}", tags=["Analysis v2"])
async def get_analysis_geojson(analysis_id: str, layer_name: str):
    """Download a real vectorized GeoJSON layer from a completed analysis."""
    file_path = GCOV_ANALYSIS_CACHE_DIR / analysis_id / layer_name
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Layer not found")
    return FileResponse(file_path, media_type="application/geo+json")


@app.get("/api/v2/analyze/{analysis_id}/visual/{layer}", tags=["Analysis v2"])
async def get_analysis_visual(analysis_id: str, layer: str):
    """
    Render a real before/after SAR backscatter layer from a completed
    analysis as a viewable PNG, for the frontend's swipe-comparison view.

    Reads the actual before.tif/after.tif produced by /api/v2/analyze (real
    pixel values from the downloaded NISAR granules) and colorizes them with
    the same rendering code previously used for synthetic imagery - but fed
    with real data. The 'after' layer additionally overlays the real
    possible_flood.tif classification mask. No synthetic/procedurally
    generated imagery is produced.
    """
    if layer not in ("before", "after"):
        raise HTTPException(status_code=400, detail="layer must be 'before' or 'after'")
    if render_real_sar_layer is None:
        raise HTTPException(status_code=503, detail="Imagery renderer not available")

    result_dir = GCOV_ANALYSIS_CACHE_DIR / analysis_id
    tif_path = result_dir / f"{layer}.tif"
    if not tif_path.exists():
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' or layer '{layer}' not found")

    flood_mask_path = result_dir / "possible_flood.tif"
    try:
        image_data_url = render_real_sar_layer(
            str(tif_path),
            title=f"{'Pre-Flood' if layer == 'before' else 'Post-Flood'} NISAR Backscatter (Real Data)",
            colormap="grayscale",
            inundation_mask_path=str(flood_mask_path) if layer == "after" and flood_mask_path.exists() else None,
        )
        return {"status": "success", "analysis_id": analysis_id, "layer": layer, "image": image_data_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering error: {str(e)}")


# ============================================================================
# PHASE 6: EMERGENCY MANAGEMENT INTELLIGENCE (real infrastructure impact +
# explainable priority scoring, built on real Phase 5 output, /api/v2/*)
# ============================================================================

@app.post("/api/v2/analyze/{analysis_id}/impact", tags=["Impact v6"])
async def analyze_infrastructure_impact(analysis_id: str):
    """
    Real emergency-management intelligence for a completed Phase 5 analysis.

    Performs genuine spatial intersection/proximity analysis between the
    detected possible-flood polygon and real OpenStreetMap infrastructure
    (roads, hospitals, schools, settlements, power plants), then produces an
    explainable, rule-based priority classification (Critical/High/Moderate/
    Low) with the full list of real factors that produced it.

    Population exposure is intentionally reported as unavailable rather than
    estimated, since no gridded population dataset is currently integrated.

    Requires /api/v2/analyze to have already been run for this analysis_id.
    Results are cached on disk (impact.json) so repeat calls are instant and
    do not re-query OpenStreetMap.
    """
    if compute_infrastructure_impact is None or compute_priority is None:
        raise HTTPException(status_code=503, detail="Phase 6 analysis pipeline not available")

    result_dir = GCOV_ANALYSIS_CACHE_DIR / analysis_id
    summary_path = result_dir / "summary.json"
    flood_geojson_path = result_dir / "possible_flood.geojson"
    impact_path = result_dir / "impact.json"

    if not summary_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Analysis '{analysis_id}' not found. Run /api/v2/analyze first.",
        )

    if impact_path.exists():
        with open(impact_path) as f:
            cached = json.load(f)
        cached["cached"] = True
        return cached

    with open(summary_path) as f:
        summary = json.load(f)

    with open(flood_geojson_path) as f:
        flood_geojson = json.load(f)

    bbox = tuple(summary["bounds"])
    crs = summary["crs"]

    impact = compute_infrastructure_impact(flood_geojson, bbox, crs)

    acquisition_time = _parse_granule_acquisition_time(summary["after_granule_id"]) if _parse_granule_acquisition_time else None
    observation_age_days = compute_observation_age_days(acquisition_time) if compute_observation_age_days else None

    priority = compute_priority(
        inundation_area_km2=summary["classification_statistics"]["possible_flood_area_km2"],
        infrastructure_categories=impact.get("categories", {}),
        geometry_compatible=summary.get("geometry_compatible", True),
        observation_age_days=observation_age_days,
    )

    result = {
        "status": "success",
        "cached": False,
        "analysis_id": analysis_id,
        "after_granule_acquisition_time": acquisition_time,
        "infrastructure_impact": impact,
        "priority": priority,
    }

    # Only persist to disk if OpenStreetMap actually returned usable data for
    # at least one category (or the flood polygon was genuinely empty). If
    # every category failed - e.g. all 3 Overpass mirrors were rate-limited -
    # that is a transient network condition, not a real analysis result, so
    # we deliberately do not cache it and allow the next call to retry.
    categories = impact.get("categories", {})
    has_real_data = impact.get("status") == "no_flood_detected" or any(
        cat.get("status") in ("ok", "no_features_found") for cat in categories.values()
    )
    if has_real_data:
        with open(impact_path, "w") as f:
            json.dump(result, f, indent=2)
    else:
        result["note"] = "Not cached: all OpenStreetMap categories were unavailable (transient network failure). Retry the request."

    return result


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
