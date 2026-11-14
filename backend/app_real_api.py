"""
VAMIKA - Backend API (NISAR-based Flood & Wetland Monitoring)
Uses REAL ASF/NASA data only - NO MOCK DATA
Requires Earthdata login credentials for authentication
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import os
import sys
import hashlib
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import asf_search

# Add backend directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Import imagery handler (real-data GeoTIFF-to-PNG rendering only - the
# previous synthetic/fabricated visualization path has been removed)
try:
    from imagery_handler import render_real_sar_layer, render_timeseries_frame
except ImportError as e:
    print(f"Warning: Could not import imagery_handler: {e}")
    render_real_sar_layer = None
    render_timeseries_frame = None

# Import Phase 4 real-data discovery/download pipeline (dormant app/ package,
# now wired into the live API additively - does not replace /api/search)
try:
    from app.ingestion.cmr_adapter import CMRAdapter, _parse_granule_acquisition_time
    from app.ingestion.download_manager import DownloadManager
    from app.ingestion.edl_token import get_edl_token_manager
except ImportError as e:
    print(f"Warning: Could not import discovery/download pipeline: {e}")
    CMRAdapter = None
    DownloadManager = None
    _parse_granule_acquisition_time = None
    get_edl_token_manager = None

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

# Import Phase 7b optional free external result cache (Cloudflare R2 / any
# S3-compatible store). Gracefully no-ops if R2_* env vars are not set, so
# this is purely additive - never required for real analysis to function.
try:
    from app.storage.r2_cache import (
        upload_analysis_result,
        download_analysis_result,
        download_single_file,
        ENABLED as R2_CACHE_ENABLED,
    )
except ImportError as e:
    print(f"Warning: Could not import external result cache: {e}")
    upload_analysis_result = None
    download_analysis_result = None
    download_single_file = None
    R2_CACHE_ENABLED = False


# Load environment variables from .env (in backend directory)
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)

print(f"\nLoading .env from: {env_path}")
print(f"Env file exists: {env_path.exists()}")

app = FastAPI(
    title="VAMIKA",
    description="VAMIKA: interactive mapping and analysis of satellite-detected flood and wetland changes, powered by NASA NISAR",
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

# ============================================================================
# PHASE 8: REAL MULTI-DATE BACKSCATTER TIME SERIES (ASF OpenSARlab NISAR
# Cookbook sections 7-8: time-series animation + time series of means,
# additive, /api/v2/timeseries*)
# ============================================================================

GCOV_TIMESERIES_CACHE_DIR = Path(__file__).parent / "data" / "timeseries_cache"
GCOV_TIMESERIES_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Real NISAR L2 GCOV science-quality data collection start, used as the
# earliest date to search for a real time series (same value the pre-seed
# script uses) - not a hardcoded mission launch date, just the start of the
# real archive this app searches.
NISAR_MISSION_START = date(2025, 8, 1)

# ============================================================================
# TIER 1 SPEED: PRE-SEEDED "FEATURED LOCATIONS" (instant real-data demo cache)
# ============================================================================
# featured_locations.json is the static, version-controlled curated list of
# 25 real, diverse flood/wetland-significant places (metadata only: name,
# country, category, lat/lon/radius, a short factual blurb). It never
# changes at runtime.
#
# featured_cache.json is generated by scripts/preseed_featured_locations.py
# (run offline/out-of-band - never by a web request) and maps each location
# id to the exact real before/after granule request that was already
# computed, so GET /api/v2/featured can tell the frontend "this one is
# ready" and hand it the exact request body to replay against the existing
# /api/v2/analyze cache (an instant cache hit - no download, no reprocessing).
# This file is NOT version-controlled since its contents (which real
# granules were found, which analysis_id) are specific to whatever NISAR has
# actually imaged by the time the pre-seed script last ran.
FEATURED_LOCATIONS_PATH = Path(__file__).parent / "data" / "featured_locations.json"
FEATURED_CACHE_PATH = Path(__file__).parent / "data" / "featured_cache.json"

# ============================================================================
# PHASE 7c: BACKGROUND JOB INFRASTRUCTURE FOR LONG-RUNNING REAL PROCESSING
# ============================================================================
# Render's own documented best practice (and ours, learned the hard way) is
# that a web request handler must return quickly: Render's reverse proxy
# enforces a request timeout, so a single synchronous HTTP call blocked on
# real multi-minute processing (GCOV change detection, or ~90s of live
# Overpass queries) gets killed mid-flight, surfacing as a bare "Internal
# Server Error" with no JSON body (a proxy-level timeout, not our own
# exception handling) - or, from the browser, as the request simply hanging
# forever. /api/v2/analyze and its /impact endpoint are therefore "thin
# handlers": they kick off the real work in a background thread and return
# immediately with a status the client polls, instead of blocking.
import threading
from concurrent.futures import ThreadPoolExecutor

_background_executor = ThreadPoolExecutor(max_workers=2)
_job_lock = threading.Lock()
_analysis_jobs: Dict[str, Dict[str, Any]] = {}  # analysis_id -> {"status": "processing"|"failed", "error": str}
_impact_jobs: Dict[str, Dict[str, Any]] = {}    # analysis_id -> {"status": "processing"|"failed", "error": str}
_timeseries_jobs: Dict[str, Dict[str, Any]] = {}  # analysis_id -> {"status": "processing"|"failed", "error": str}

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

# Real HTTPS partial-read support (see app/processing/gcov_reader.py
# .load_gcov_subset_remote() and app/ingestion/edl_token.py): lets the
# analysis path read just the requested AOI directly from the remote
# granule instead of downloading the full multi-GB file first - measured
# ~8x faster (122s -> 15s) for a small AOI on the real GCP VM. Disabled
# automatically if credentials or the EDL token manager aren't available;
# the existing download-then-read path is always the fallback.
REMOTE_READ_ENABLED = os.getenv("REMOTE_READ_ENABLED", "true").strip().lower() not in ("false", "0", "no")
edl_token_manager = None
if REMOTE_READ_ENABLED and get_edl_token_manager is not None and ASF_USERNAME and ASF_PASSWORD:
    edl_token_manager = get_edl_token_manager(ASF_USERNAME, ASF_PASSWORD)
else:
    REMOTE_READ_ENABLED = False

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

    If before_download_url/after_download_url are provided, the backend
    first attempts a real remote partial (byte-range) HTTPS read of just
    the requested AOI - no full-granule download required - which is
    dramatically faster for small AOIs against large (multi-GB) granules
    (measured ~8x on a real GCP VM: 122s full download vs 15s remote read).
    If a URL is missing, or the remote read fails for any reason, the
    backend transparently falls back to downloading the full granule (via
    the existing DownloadManager) and reading it locally - so this field
    is fully optional and backward compatible. Either way, the granule
    must ultimately be resolvable: already downloaded locally, or have a
    real download URL available for a fallback download."""
    before_granule_id: str
    after_granule_id: str
    before_download_url: Optional[str] = None
    after_download_url: Optional[str] = None
    bounds: BoundsModel
    polarization: str = "HHHH"
    flood_change_threshold_db: float = -2.0
    low_backscatter_threshold_db: float = -15.0


class TimeSeriesRequest(BaseModel):
    """Real multi-date backscatter time-series request for one AOI (ASF
    OpenSARlab NISAR Cookbook sections 7-8: time-series animation + time
    series of means).

    Unlike /api/v2/analyze (exactly two granules a caller already picked),
    this endpoint does its own real CMR discovery internally: it finds every
    real granule covering this AOI that shares the same acquisition geometry
    (track/frame/pass direction - required for a scientifically meaningful
    time series, for the same reason a before/after pair needs it), and uses
    the most recent max_acquisitions of them, oldest first."""
    bounds: BoundsModel
    polarization: str = "HHHH"
    max_acquisitions: int = 12


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
        "name": "VAMIKA",
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
        "name": "VAMIKA",
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


@app.get("/api/v2/diagnostics/earthdata-auth", tags=["System"])
async def diagnose_earthdata_auth():
    """
    Safely verify whether this deployment's NASA Earthdata credentials
    (ASF_USERNAME/ASF_PASSWORD) are configured and actually authenticate -
    without ever exposing the username or password value itself. Useful for
    diagnosing 'works locally but fails on Render' credential issues, since
    the env vars are deliberately not stored in git (render.yaml sync: false)
    and must be set manually per-deployment.
    """
    configured = bool(ASF_USERNAME) and bool(ASF_PASSWORD)
    result = {
        "credentials_configured": configured,
        "username_length": len(ASF_USERNAME) if ASF_USERNAME else 0,
        "password_length": len(ASF_PASSWORD) if ASF_PASSWORD else 0,
        "username_has_whitespace": (ASF_USERNAME != ASF_USERNAME.strip()) if ASF_USERNAME else None,
        "password_has_whitespace": (ASF_PASSWORD != ASF_PASSWORD.strip()) if ASF_PASSWORD else None,
    }

    if not configured:
        result["auth_check"] = "not_attempted"
        result["detail"] = "ASF_USERNAME and/or ASF_PASSWORD are empty in this deployment's environment."
        return result

    try:
        session = asf_search.ASFSession()
        session.auth_with_creds(ASF_USERNAME, ASF_PASSWORD)
        result["auth_check"] = "success"
    except Exception as e:
        result["auth_check"] = "failed"
        result["error"] = str(e)

    return result


@app.get("/api/v2/diagnostics/granule-info/{granule_id}", tags=["System"])
async def diagnose_granule_info(granule_id: str):
    """
    Safely inspect a downloaded real GCOV HDF5 file's structure (frequency
    groups, available polarization datasets, projection, coordinate array
    sizes/ranges) without running the full analysis pipeline. Used to
    diagnose real-world failures (e.g. an unhandled crash during analysis)
    by confirming what the file actually contains, rather than guessing.
    """
    try:
        file_path = _resolve_granule_path(granule_id)
    except HTTPException as e:
        return {"status": "error", "detail": e.detail}

    if GCOVReader is None:
        raise HTTPException(status_code=503, detail="GCOV processing pipeline not available")

    import h5py
    try:
        with h5py.File(file_path, "r") as f:
            freq_group = GCOVReader.find_frequency_group(f)
            pol_datasets = [
                k for k in freq_group.keys()
                if k in GCOVReader.SUPPORTED_POLARIZATIONS
            ]
            x_coords = freq_group["xCoordinates"][:]
            y_coords = freq_group["yCoordinates"][:]
            projection = GCOVReader._scalar(freq_group["projection"][()])
            return {
                "status": "success",
                "granule_id": granule_id,
                "file_size_bytes": file_path.stat().st_size,
                "frequency_group_path": freq_group.name,
                "available_polarizations": pol_datasets,
                "all_keys_in_group": list(freq_group.keys()),
                "projection_epsg": int(projection),
                "x_coord_count": int(x_coords.size),
                "y_coord_count": int(y_coords.size),
                "x_range": [float(x_coords.min()), float(x_coords.max())],
                "y_range": [float(y_coords.min()), float(y_coords.max())],
            }
    except Exception as e:
        return {"status": "error", "detail": f"{type(e).__name__}: {e}"}


@app.get("/api/v2/diagnostics/external-cache", tags=["System"])
async def diagnose_external_cache():
    """
    Safely verify whether the optional free external result cache
    (Cloudflare R2 / any S3-compatible store) is configured and reachable -
    without exposing the access key or secret key values. This cache is
    purely a performance optimization (see app/storage/r2_cache.py) so the
    app works correctly even if this reports disabled/unreachable.
    """
    from app.storage.r2_cache import R2_ACCOUNT_ID, R2_BUCKET_NAME

    result = {
        "enabled": R2_CACHE_ENABLED,
        "bucket_name": R2_BUCKET_NAME or None,
        "account_id_configured": bool(R2_ACCOUNT_ID),
    }

    if not R2_CACHE_ENABLED:
        result["detail"] = (
            "External cache is disabled: set R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, "
            "R2_SECRET_ACCESS_KEY, and R2_BUCKET_NAME to enable it. The app "
            "works correctly without it; real analysis results just won't "
            "survive a Render restart/redeploy."
        )
        return result

    try:
        import app.storage.r2_cache as r2
        client = r2._get_client()
        client.head_bucket(Bucket=R2_BUCKET_NAME)
        result["connection_check"] = "success"
    except Exception as e:
        result["connection_check"] = "failed"
        result["error"] = str(e)

    return result


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


@app.get("/api/v2/featured", tags=["Discovery v2"])
async def list_featured_locations():
    """
    Curated, real, geographically diverse flood/wetland-significant
    locations, for an instant demo experience that doesn't require waiting
    on a fresh multi-gigabyte NASA download.

    Each entry is tagged "ready": true only if scripts/preseed_featured_locations.py
    has already computed and cached a real before/after analysis for it (see
    featured_cache.json) - in which case the exact request body to replay
    against the normal, already-cached /api/v2/analyze + .../impact endpoints
    is included, so the frontend can load it with zero new downloads or
    processing. Locations without a ready cache entry are still shown (with
    their real metadata/blurb) but are "ready": false - a normal live search
    is still required for those until the next pre-seed run covers them.
    """
    if not FEATURED_LOCATIONS_PATH.exists():
        return {"status": "success", "locations": []}

    try:
        with open(FEATURED_LOCATIONS_PATH) as f:
            static_locations = json.load(f).get("locations", [])
    except (OSError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"Could not read featured locations: {e}")

    cache: Dict[str, Any] = {}
    if FEATURED_CACHE_PATH.exists():
        loaded = _load_json_safe(FEATURED_CACHE_PATH)
        if loaded is not None:
            cache = loaded

    results = []
    for loc in static_locations:
        entry = dict(loc)
        cached = cache.get(loc["id"])
        if cached:
            entry["ready"] = True
            entry["analysis_request"] = {
                "before_granule_id": cached["before_granule_id"],
                "after_granule_id": cached["after_granule_id"],
                "bounds": cached["bounds"],
                "polarization": cached.get("polarization", "HHHH"),
            }
            entry["before_date"] = cached.get("before_date")
            entry["after_date"] = cached.get("after_date")
            entry["last_preseeded_at"] = cached.get("last_preseeded_at")
            # Present only if the pre-seed script successfully built a real
            # time series for this AOI (best-effort - may be absent for a
            # location with too few real repeat acquisitions so far).
            entry["timeseries_analysis_id"] = cached.get("timeseries_analysis_id")
        else:
            entry["ready"] = False
        results.append(entry)

    return {"status": "success", "locations": results}


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


# Bounded wall-clock budget for a single remote partial read attempt before
# giving up and falling back to the (slower but battle-tested) download+
# local-read path. Chosen comfortably above the ~15s measured on the real
# GCP VM for a typical small-AOI read, while still being much less than a
# full multi-GB download (~120s+) so a failing remote read doesn't make
# the fallback path slower than just downloading from the start.
REMOTE_READ_TIMEOUT_SECONDS = 90

# How long to wait for a server-triggered fallback download to finish
# before giving up (generous - some granules are 7GB+ and slow networks
# exist; the analysis job already runs in a background thread so blocking
# here does not tie up the request/response cycle).
FALLBACK_DOWNLOAD_TIMEOUT_SECONDS = 20 * 60


def _wait_for_download_complete(granule_id: str, timeout_seconds: float) -> Path:
    """Poll the real download_manager status in-process until the granule
    is fully downloaded (or raise on failure/timeout). Used by the remote-
    read fallback path when the granule was never explicitly downloaded by
    the client."""
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        status = download_manager.get_status(granule_id)
        if status.get("status") == "complete":
            local_path = Path(status["local_path"])
            if local_path.exists():
                return local_path
            raise ProcessingError(f"Cached file missing on disk for granule '{granule_id}'")
        if status.get("status") == "failed":
            raise ProcessingError(
                f"Download failed for granule '{granule_id}': {status.get('error', 'unknown error')}"
            )
        time.sleep(2)
    raise ProcessingError(
        f"Timed out waiting for granule '{granule_id}' to finish downloading "
        f"after {int(timeout_seconds)}s"
    )


def _get_gcov_data(
    granule_id: str,
    download_url: Optional[str],
    polarization: str,
    bounds_tuple: tuple[float, float, float, float],
) -> Dict[str, Any]:
    """
    Get the real GCOV subset for one granule, trying a fast remote partial
    (byte-range HTTPS) read first when possible, and transparently falling
    back to a real full download + local read otherwise. Never substitutes
    mock data - every path here reads a real NISAR granule, either over the
    network a subset at a time, or from a fully downloaded local file.

    Fallback is triggered by (in order of likelihood): the granule is already
    fully downloaded locally (reading the local file directly is always at
    least as fast as a remote read, so there's no reason to go over the
    network in that case), no download_url provided (old-style request),
    remote read disabled, or any exception from the remote read itself
    (network error, timeout, or an HDF5 edge case the remote path doesn't
    yet handle) - logged as a warning, never silently swallowed.
    """
    already_local = (
        download_manager is not None
        and download_manager.get_status(granule_id).get("status") == "complete"
    )
    if REMOTE_READ_ENABLED and download_url and not already_local and GCOVReader is not None:
        try:
            token = edl_token_manager.get_token()
            remote_result: Dict[str, Any] = {}
            remote_error: List[Exception] = []

            def _attempt_remote() -> None:
                try:
                    remote_result["data"] = GCOVReader.load_gcov_subset_remote(
                        download_url, polarization, bounds_tuple, token
                    )
                except Exception as e:  # noqa: BLE001 - must not crash the thread
                    remote_error.append(e)

            thread = threading.Thread(target=_attempt_remote, daemon=True)
            thread.start()
            thread.join(timeout=REMOTE_READ_TIMEOUT_SECONDS)

            if thread.is_alive():
                print(
                    f"Remote partial read for {granule_id} exceeded "
                    f"{REMOTE_READ_TIMEOUT_SECONDS}s, falling back to download"
                )
            elif remote_error:
                print(f"Remote partial read for {granule_id} failed, falling back to download: {remote_error[0]}")
            elif "data" in remote_result:
                print(f"Remote partial read succeeded for {granule_id} (no full download needed)")
                return remote_result["data"]
        except Exception as e:
            print(f"Remote read setup failed for {granule_id}, falling back to download: {e}")

    # Fallback: ensure the granule is fully downloaded locally, then read it
    # with the existing, battle-tested local path.
    if download_manager is None:
        raise HTTPException(status_code=503, detail="Download manager not available")

    status = download_manager.get_status(granule_id)
    if status.get("status") != "complete":
        if not download_url:
            raise HTTPException(
                status_code=404,
                detail=(
                    f"Granule '{granule_id}' is not downloaded yet and no download_url was "
                    f"provided to fetch it (status: {status.get('status', 'not_found')}). Use "
                    f"/api/v2/download/start first and poll /api/v2/download/status/{{granule_id}}, "
                    f"or include *_download_url in this request."
                ),
            )
        download_manager.start_download(granule_id, download_url)
        local_path = _wait_for_download_complete(granule_id, FALLBACK_DOWNLOAD_TIMEOUT_SECONDS)
    else:
        local_path = Path(status["local_path"])
        if not local_path.exists():
            raise HTTPException(status_code=404, detail=f"Cached file missing on disk for granule '{granule_id}'")

    return GCOVReader.load_gcov_subset(local_path, polarization, bounds_tuple)


def _analysis_id_for(request: AnalyzeRequest) -> str:
    seed = (
        f"{request.before_granule_id}|{request.after_granule_id}|"
        f"{request.bounds.west}|{request.bounds.south}|{request.bounds.east}|{request.bounds.north}|"
        f"{request.polarization}|{request.flood_change_threshold_db}|{request.low_backscatter_threshold_db}"
    )
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def _load_json_safe(path: Path) -> Optional[Dict[str, Any]]:
    """
    Load a cached JSON result file, rejecting any NaN/Infinity tokens
    (non-standard JSON that real statistics could contain from an older
    version of the pipeline, or from an edge case with zero valid pixels).
    Returns None - and deletes the bad file - instead of ever returning
    data that would crash response serialization or be silently wrong.
    """
    def _reject_non_finite(_):
        raise ValueError("file contains a non-finite (NaN/Infinity) value")

    try:
        with open(path) as f:
            return json.load(f, parse_constant=_reject_non_finite)
    except (ValueError, OSError) as e:
        print(f"Discarding invalid cached file {path}: {e}")
        try:
            path.unlink()
        except OSError:
            pass
        return None


def _run_real_analysis(analysis_id: str, request: "AnalyzeRequest", result_dir: Path, summary_path: Path) -> None:
    """
    The actual real GCOV processing work (runs in a background thread - see
    PHASE 7c above). Writes summary.json (and layer/geojson files) on success,
    or records a failure in _analysis_jobs on error. Never raises back to the
    caller since nothing is awaiting this directly.
    """
    try:
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

        # Tries a fast remote partial read first (when a download_url was
        # provided), falling back to a real full download + local read
        # otherwise - see _get_gcov_data() for the full fallback logic.
        before_data = _get_gcov_data(
            request.before_granule_id, request.before_download_url, request.polarization, bounds_tuple
        )
        after_data = _get_gcov_data(
            request.after_granule_id, request.after_download_url, request.polarization, bounds_tuple
        )

        change, aligned_before, aligned_after, pixel_area_km2 = ChangeDetectionEngine.align_and_compare(
            before_data, after_data
        )
        possible_flood, possible_flooded_vegetation, persistent_water, classification_stats = (
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
            "possible_flooded_vegetation": possible_flooded_vegetation,
            "persistent_water": persistent_water,
        }
        for name, arr in layers.items():
            tif_bytes = GeoTIFFExporter.export_to_geotiff(arr, after_data["transform"], after_data["crs"])
            (result_dir / f"{name}.tif").write_bytes(tif_bytes)

        # Vectorize the classification masks to real GeoJSON polygons
        for name in ("possible_flood", "possible_flooded_vegetation", "persistent_water"):
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
                for name in ("possible_flood", "possible_flooded_vegetation", "persistent_water")
            },
            "visual": {
                "before": f"/api/v2/analyze/{analysis_id}/visual/before",
                "after": f"/api/v2/analyze/{analysis_id}/visual/after",
            },
        }

        with open(summary_path, "w") as f:
            json.dump(summary, f, indent=2)

        # Best-effort: persist this real result to the free external cache
        # so a future Render restart (which wipes local disk) can restore it
        # instantly instead of re-downloading/re-processing. Never blocks or
        # fails the response if the external cache is unavailable/unconfigured.
        if upload_analysis_result:
            upload_analysis_result(analysis_id, result_dir)

        with _job_lock:
            _analysis_jobs[analysis_id] = {"status": "success"}

    except (ProcessingError, ValidationError) as e:
        with _job_lock:
            _analysis_jobs[analysis_id] = {"status": "failed", "error": str(e)}
    except HTTPException as e:
        with _job_lock:
            _analysis_jobs[analysis_id] = {"status": "failed", "error": str(e.detail)}
    except Exception as e:
        with _job_lock:
            _analysis_jobs[analysis_id] = {"status": "failed", "error": f"Analysis error: {e}"}


@app.post("/api/v2/analyze", tags=["Analysis v2"])
async def analyze_real_change(request: AnalyzeRequest):
    """
    Real NISAR L2 GCOV before/after change detection.

    Reads actual HDF5 backscatter data for both granules - either via a real
    fast remote partial (byte-range HTTPS) read directly from the granule's
    real NASA Earthdata Cloud URL (when before_download_url/after_download_url
    are provided; no full download needed), or from a local copy already
    downloaded via /api/v2/download/start, falling back to triggering that
    download itself if a URL is given but the file isn't local yet - then
    reprojects/aligns them, computes the real backscatter difference (delta
    sigma0 = sigma0_post - sigma0_pre), and classifies possible new
    inundation vs persistent low-backscatter (existing water) using
    documented, configurable thresholds.

    This is a THIN HANDLER: real processing can take minutes for a large
    AOI, which exceeds Render's reverse-proxy request timeout if done
    synchronously. The actual work runs in a background thread; this
    endpoint returns immediately with {"status": "processing", ...} (or the
    full cached result if already computed). Poll
    GET /api/v2/analyze/status/{analysis_id} for completion.

    Never fabricates results - if either granule is not yet downloaded, or
    the AOI does not overlap one of the files, a clear error is returned
    (via the status endpoint) instead of mock data.
    """
    if GCOVReader is None or ChangeDetectionEngine is None:
        raise HTTPException(status_code=503, detail="GCOV processing pipeline not available")

    analysis_id = _analysis_id_for(request)
    result_dir = GCOV_ANALYSIS_CACHE_DIR / analysis_id
    summary_path = result_dir / "summary.json"

    try:
        # Cache hit: identical request already processed - skip reprocessing
        if summary_path.exists():
            cached = _load_json_safe(summary_path)
            if cached is not None:
                cached["cached"] = True
                return cached

        # Cache hit (external): local disk was wiped (e.g. a Render free-tier
        # restart) but this exact real result was already computed once and
        # persisted to the free external cache - restore it instead of
        # re-downloading the multi-GB granule and re-running the full pipeline.
        if download_analysis_result and download_analysis_result(analysis_id, result_dir):
            cached = _load_json_safe(summary_path)
            if cached is not None:
                cached["cached"] = True
                cached["cache_source"] = "external"
                return cached

        # Fail fast (synchronously) if the granule isn't downloaded yet AND no
        # download_url was given to fetch/remote-read it - this is a fast
        # local check, not real processing, so it's fine in the thin handler.
        # If a download_url IS present, resolution (remote-read-first, with
        # download fallback) happens inside the background job itself.
        if not request.before_download_url:
            _resolve_granule_path(request.before_granule_id)
        if not request.after_download_url:
            _resolve_granule_path(request.after_granule_id)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"UNEXPECTED ERROR in analyze_real_change pre-check: {e}\n{tb}")
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}")

    with _job_lock:
        existing = _analysis_jobs.get(analysis_id)
        if existing and existing.get("status") == "processing":
            return {"status": "processing", "analysis_id": analysis_id,
                    "message": "Real analysis already in progress for this request."}
        _analysis_jobs[analysis_id] = {"status": "processing"}

    _background_executor.submit(_run_real_analysis, analysis_id, request, result_dir, summary_path)

    return {
        "status": "processing",
        "analysis_id": analysis_id,
        "message": "Real NISAR change-detection analysis started in the background.",
        "status_url": f"/api/v2/analyze/status/{analysis_id}",
    }


@app.get("/api/v2/analyze/status/{analysis_id}", tags=["Analysis v2"])
async def get_analyze_status(analysis_id: str):
    """Poll the status of a real analysis started via POST /api/v2/analyze."""
    result_dir = GCOV_ANALYSIS_CACHE_DIR / analysis_id
    summary_path = result_dir / "summary.json"

    if summary_path.exists():
        cached = _load_json_safe(summary_path)
        if cached is not None:
            cached["cached"] = True
            return cached

    with _job_lock:
        job = _analysis_jobs.get(analysis_id)

    if job is None:
        if download_analysis_result and download_analysis_result(analysis_id, result_dir):
            cached = _load_json_safe(summary_path)
            if cached is not None:
                cached["cached"] = True
                cached["cache_source"] = "external"
                return cached
        raise HTTPException(status_code=404, detail="No analysis found or in progress for this analysis_id")

    if job.get("status") == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "Analysis failed"))

    return {"status": "processing", "analysis_id": analysis_id}



@app.get("/api/v2/analyze/{analysis_id}/layer/{layer_name}", tags=["Analysis v2"])
async def get_analysis_layer(analysis_id: str, layer_name: str):
    """Download a real GeoTIFF raster layer from a completed analysis."""
    file_path = GCOV_ANALYSIS_CACHE_DIR / analysis_id / layer_name
    if not file_path.exists() and download_single_file:
        download_single_file(analysis_id, layer_name, file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Layer not found")
    return FileResponse(file_path, media_type="image/tiff")


@app.get("/api/v2/analyze/{analysis_id}/geojson/{layer_name}", tags=["Analysis v2"])
async def get_analysis_geojson(analysis_id: str, layer_name: str):
    """Download a real vectorized GeoJSON layer from a completed analysis."""
    file_path = GCOV_ANALYSIS_CACHE_DIR / analysis_id / layer_name
    if not file_path.exists() and download_single_file:
        download_single_file(analysis_id, layer_name, file_path)
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
    possible_flood.tif (open water, neon orange) and
    possible_flooded_vegetation.tif (flooded vegetation, lime green)
    classification masks. No synthetic/procedurally generated imagery is produced.
    """
    if layer not in ("before", "after"):
        raise HTTPException(status_code=400, detail="layer must be 'before' or 'after'")
    if render_real_sar_layer is None:
        raise HTTPException(status_code=503, detail="Imagery renderer not available")

    result_dir = GCOV_ANALYSIS_CACHE_DIR / analysis_id
    tif_path = result_dir / f"{layer}.tif"
    if not tif_path.exists() and download_single_file:
        download_single_file(analysis_id, f"{layer}.tif", tif_path)
    if not tif_path.exists():
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' or layer '{layer}' not found")

    flood_mask_path = result_dir / "possible_flood.tif"
    if layer == "after" and not flood_mask_path.exists() and download_single_file:
        download_single_file(analysis_id, "possible_flood.tif", flood_mask_path)
    veg_mask_path = result_dir / "possible_flooded_vegetation.tif"
    if layer == "after" and not veg_mask_path.exists() and download_single_file:
        download_single_file(analysis_id, "possible_flooded_vegetation.tif", veg_mask_path)
    try:
        image_data_url = render_real_sar_layer(
            str(tif_path),
            title=f"{'Pre-Flood' if layer == 'before' else 'Post-Flood'} NISAR Backscatter (Real Data)",
            colormap="grayscale",
            inundation_mask_path=str(flood_mask_path) if layer == "after" and flood_mask_path.exists() else None,
            vegetation_flood_mask_path=str(veg_mask_path) if layer == "after" and veg_mask_path.exists() else None,
        )
        return {"status": "success", "analysis_id": analysis_id, "layer": layer, "image": image_data_url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering error: {str(e)}")


# ============================================================================
# PHASE 6: EMERGENCY MANAGEMENT INTELLIGENCE (real infrastructure impact +
# explainable priority scoring, built on real Phase 5 output, /api/v2/*)
# ============================================================================

def _run_real_impact(
    analysis_id: str, result_dir: Path, summary_path: Path,
    flood_geojson_path: Path, veg_geojson_path: Path, impact_path: Path,
) -> None:
    """The actual real infrastructure-impact work (runs in a background
    thread - Overpass queries can take up to ~90s, which exceeds Render's
    reverse-proxy request timeout if done synchronously)."""
    try:
        with open(summary_path) as f:
            summary = json.load(f)

        with open(flood_geojson_path) as f:
            flood_geojson = json.load(f)

        # Combine the open-water and flooded-vegetation polygons into one
        # "total flood extent" FeatureCollection for impact analysis - a
        # forested/vegetated flood area (radar-bright, double-bounce
        # signature) is just as real an impact as open water (radar-dark),
        # and omitting it would understate infrastructure exposure in
        # vegetated floodplains/wetlands. See NASA/JPL "Floods" StoryMap:
        # https://storymaps.arcgis.com/stories/c00d7691b8004b20a14f28df710d05fd
        combined_features = list(flood_geojson.get("features", []))
        if veg_geojson_path.exists():
            try:
                with open(veg_geojson_path) as f:
                    veg_geojson = json.load(f)
                combined_features.extend(veg_geojson.get("features", []))
            except (OSError, json.JSONDecodeError) as e:
                print(f"Could not read flooded-vegetation geojson for impact analysis: {e}")
        total_flood_geojson = {"type": "FeatureCollection", "features": combined_features}

        bbox = tuple(summary["bounds"])
        crs = summary["crs"]

        impact = compute_infrastructure_impact(total_flood_geojson, bbox, crs)

        acquisition_time = _parse_granule_acquisition_time(summary["after_granule_id"]) if _parse_granule_acquisition_time else None
        observation_age_days = compute_observation_age_days(acquisition_time) if compute_observation_age_days else None

        classification_stats = summary["classification_statistics"]
        total_inundation_area_km2 = classification_stats.get(
            "total_flood_extent_area_km2", classification_stats["possible_flood_area_km2"]
        )
        priority = compute_priority(
            inundation_area_km2=total_inundation_area_km2,
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

        # Only persist to disk if OpenStreetMap actually returned usable data
        # for at least one category (or the flood polygon was genuinely
        # empty). If every category failed - e.g. all 3 Overpass mirrors were
        # rate-limited - that is a transient network condition, not a real
        # analysis result, so we deliberately do not cache it and allow the
        # next call to retry.
        categories = impact.get("categories", {})
        has_real_data = impact.get("status") == "no_flood_detected" or any(
            cat.get("status") in ("ok", "no_features_found") for cat in categories.values()
        )
        if has_real_data:
            with open(impact_path, "w") as f:
                json.dump(result, f, indent=2)
            if upload_analysis_result:
                upload_analysis_result(analysis_id, result_dir)
        else:
            result["note"] = "Not cached: all OpenStreetMap categories were unavailable (transient network failure). Retry the request."

        with _job_lock:
            _impact_jobs[analysis_id] = {"status": "success", "result": result}

    except Exception as e:
        with _job_lock:
            _impact_jobs[analysis_id] = {"status": "failed", "error": f"Impact analysis error: {e}"}


@app.post("/api/v2/analyze/{analysis_id}/impact", tags=["Impact v6"])
async def analyze_infrastructure_impact(analysis_id: str):
    """
    Real emergency-management intelligence for a completed Phase 5 analysis.

    Performs genuine spatial intersection/proximity analysis between the
    detected possible-flood polygon and real OpenStreetMap infrastructure
    (roads, hospitals, schools, settlements, power plants), then produces an
    explainable, rule-based priority classification (Critical/High/Moderate/
    Low) with the full list of real factors that produced it.

    This is a THIN HANDLER: Overpass queries can take up to ~90s, which
    exceeds Render's reverse-proxy request timeout if done synchronously.
    The actual work runs in a background thread; this endpoint returns
    immediately with {"status": "processing", ...} (or the full cached
    result if already computed). Poll
    GET /api/v2/analyze/{analysis_id}/impact/status for completion.

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
    veg_geojson_path = result_dir / "possible_flooded_vegetation.geojson"
    impact_path = result_dir / "impact.json"

    # Restore from the external cache if a Render restart wiped local disk
    # but this exact analysis_id was already fully computed once before.
    if not summary_path.exists() and download_analysis_result:
        download_analysis_result(analysis_id, result_dir)

    if not summary_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Analysis '{analysis_id}' not found. Run /api/v2/analyze first.",
        )

    if not flood_geojson_path.exists() and download_single_file:
        download_single_file(analysis_id, "possible_flood.geojson", flood_geojson_path)
    if not veg_geojson_path.exists() and download_single_file:
        download_single_file(analysis_id, "possible_flooded_vegetation.geojson", veg_geojson_path)

    if impact_path.exists():
        cached = _load_json_safe(impact_path)
        if cached is not None:
            cached["cached"] = True
            return cached

    with _job_lock:
        existing = _impact_jobs.get(analysis_id)
        if existing and existing.get("status") == "processing":
            return {"status": "processing", "analysis_id": analysis_id,
                    "message": "Real infrastructure-impact analysis already in progress."}
        _impact_jobs[analysis_id] = {"status": "processing"}

    _background_executor.submit(
        _run_real_impact, analysis_id, result_dir, summary_path, flood_geojson_path, veg_geojson_path, impact_path
    )

    return {
        "status": "processing",
        "analysis_id": analysis_id,
        "message": "Real infrastructure-impact analysis started in the background (OpenStreetMap queries can take up to ~90 seconds).",
        "status_url": f"/api/v2/analyze/{analysis_id}/impact/status",
    }


@app.get("/api/v2/analyze/{analysis_id}/impact/status", tags=["Impact v6"])
async def get_impact_status(analysis_id: str):
    """Poll the status of a real impact analysis started via POST /api/v2/analyze/{analysis_id}/impact."""
    result_dir = GCOV_ANALYSIS_CACHE_DIR / analysis_id
    impact_path = result_dir / "impact.json"

    if impact_path.exists():
        cached = _load_json_safe(impact_path)
        if cached is not None:
            cached["cached"] = True
            return cached

    with _job_lock:
        job = _impact_jobs.get(analysis_id)

    if job is None:
        raise HTTPException(status_code=404, detail="No impact analysis found or in progress for this analysis_id")

    if job.get("status") == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "Impact analysis failed"))

    if job.get("status") == "success":
        result = job["result"]
        result["cached"] = False
        return result

    return {"status": "processing", "analysis_id": analysis_id}


# ============================================================================
# PHASE 8: REAL MULTI-DATE BACKSCATTER TIME SERIES (ASF OpenSARlab NISAR
# Cookbook sections 7-8, /api/v2/timeseries*)
# ============================================================================

def _timeseries_id_for(request: "TimeSeriesRequest") -> str:
    seed = (
        f"timeseries|{request.bounds.west}|{request.bounds.south}|"
        f"{request.bounds.east}|{request.bounds.north}|"
        f"{request.polarization}|{request.max_acquisitions}"
    )
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def _run_timeseries_analysis(analysis_id: str, request: "TimeSeriesRequest", result_dir: Path, summary_path: Path) -> None:
    """
    The actual real multi-date backscatter time-series work (runs in a
    background thread - real processing across ~8-12 real acquisitions can
    take a few minutes). Discovers every real granule sharing one real
    acquisition geometry for this AOI (CMRAdapter.discover_time_series),
    reads each one's real AOI subset (remote-read-first, same
    _get_gcov_data() helper /api/v2/analyze uses), computes the real
    per-date mean backscatter correctly in power scale before converting to
    dB (ASF OpenSARlab NISAR Cookbook section 8 - "Calculate the Time Series
    of Means"), renders a real per-date animation frame (section 7), and
    assembles a real animated GIF. Never fabricates a date, acquisition, or
    statistic that wasn't actually read from a real granule - any real
    acquisition that fails to read or has no valid pixels in this AOI is
    skipped (logged), not papered over with an invented value.
    """
    try:
        if CMRAdapter is None:
            raise ProcessingError("Discovery pipeline not available")

        bounds_tuple = (request.bounds.west, request.bounds.south, request.bounds.east, request.bounds.north)
        today = datetime.now().date()
        ts_info = CMRAdapter.discover_time_series(
            bounds_tuple, NISAR_MISSION_START, today, max_acquisitions=request.max_acquisitions
        )
        acquisitions = ts_info["acquisitions"]

        if len(acquisitions) < 3:
            raise ValidationError(
                f"Only {len(acquisitions)} real same-geometry acquisition(s) are available for this "
                f"area so far - at least 3 are needed for a meaningful time series. NISAR revisits this "
                f"area roughly every 12 days, so more will become available over time."
            )

        result_dir.mkdir(parents=True, exist_ok=True)

        dates: List[str] = []
        means_db: List[float] = []
        means_power: List[float] = []
        granule_ids: List[str] = []
        pil_frames = []

        for g in acquisitions:
            try:
                data = _get_gcov_data(g["granule_id"], g.get("download_url"), request.polarization, bounds_tuple)
            except Exception as e:
                # A single real granule failing to read (no overlap with
                # this exact AOI, a transient network error, etc.) must not
                # sink the whole real time series - skip it and keep going.
                print(f"Skipping real acquisition {g['granule_id']} in time series {analysis_id}: {e}")
                continue

            mean_db = GCOVReader.mean_backscatter_db(data["data"])
            if mean_db is None:
                print(
                    f"Skipping real acquisition {g['granule_id']} in time series {analysis_id}: "
                    f"no valid pixels in this AOI"
                )
                continue

            date_label = (g.get("time_start") or "")[:10] or g["granule_id"]
            dates.append(g.get("time_start"))
            means_db.append(mean_db)
            means_power.append(10.0 ** (mean_db / 10.0))
            granule_ids.append(g["granule_id"])

            if render_timeseries_frame is not None:
                frame_img = render_timeseries_frame(data["data"], date_label)
                frame_img.save(result_dir / f"frame_{len(pil_frames)}.png")
                pil_frames.append(frame_img)

        if len(dates) < 2:
            raise ValidationError(
                "Not enough real acquisitions had valid overlapping data for this AOI to build a time series."
            )

        gif_url = None
        if len(pil_frames) >= 2:
            gif_path = result_dir / "animation.gif"
            # 800ms/frame - slow enough to actually see each real date change
            pil_frames[0].save(gif_path, save_all=True, append_images=pil_frames[1:], duration=800, loop=0)
            gif_url = f"/api/v2/timeseries/{analysis_id}/animation.gif"

        summary = {
            "status": "success",
            "analysis_id": analysis_id,
            "track": ts_info["track"],
            "frame": ts_info["frame"],
            "pass_direction": ts_info["pass_direction"],
            "polarization": request.polarization,
            "bounds": list(bounds_tuple),
            "total_candidates": ts_info["total_candidates"],
            "total_in_group": ts_info["total_in_group"],
            "dates": dates,
            "granule_ids": granule_ids,
            "means_db": means_db,
            "means_power": means_power,
            "frame_count": len(pil_frames),
            "frames": [f"/api/v2/timeseries/{analysis_id}/frame/{i}" for i in range(len(pil_frames))],
            "gif_url": gif_url,
        }

        with open(summary_path, "w") as f:
            json.dump(summary, f)

        # Best-effort: persist to the free external cache so a Render
        # restart doesn't lose a result that took minutes of real remote
        # reads to compute (reuses the same analysis-result cache helpers -
        # they operate generically on any analysis_id/result_dir).
        if upload_analysis_result:
            upload_analysis_result(analysis_id, result_dir)

        with _job_lock:
            _timeseries_jobs[analysis_id] = {"status": "success"}

    except (ProcessingError, ValidationError) as e:
        with _job_lock:
            _timeseries_jobs[analysis_id] = {"status": "failed", "error": str(e)}
    except HTTPException as e:
        with _job_lock:
            _timeseries_jobs[analysis_id] = {"status": "failed", "error": str(e.detail)}
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"UNEXPECTED ERROR in _run_timeseries_analysis: {e}\n{tb}")
        with _job_lock:
            _timeseries_jobs[analysis_id] = {"status": "failed", "error": f"{type(e).__name__}: {e}"}


@app.post("/api/v2/timeseries", tags=["Time Series v8"])
async def start_timeseries(request: TimeSeriesRequest):
    """
    Start a real multi-date backscatter time-series analysis for an AOI.

    Thin handler (same background-job/polling pattern as /api/v2/analyze):
    real processing across several real acquisitions can take a few
    minutes, so this returns immediately with {"status": "processing", ...}
    (or the full cached result if this exact AOI/polarization/cap was
    already computed). Poll GET /api/v2/timeseries/status/{analysis_id}.
    """
    if CMRAdapter is None or GCOVReader is None:
        raise HTTPException(status_code=503, detail="Time series pipeline not available")

    analysis_id = _timeseries_id_for(request)
    result_dir = GCOV_TIMESERIES_CACHE_DIR / analysis_id
    summary_path = result_dir / "summary.json"

    if summary_path.exists():
        cached = _load_json_safe(summary_path)
        if cached is not None:
            cached["cached"] = True
            return cached

    if download_analysis_result and download_analysis_result(analysis_id, result_dir):
        cached = _load_json_safe(summary_path)
        if cached is not None:
            cached["cached"] = True
            cached["cache_source"] = "external"
            return cached

    with _job_lock:
        existing = _timeseries_jobs.get(analysis_id)
        if existing and existing.get("status") == "processing":
            return {"status": "processing", "analysis_id": analysis_id,
                    "message": "Real time-series analysis already in progress for this request."}
        _timeseries_jobs[analysis_id] = {"status": "processing"}

    _background_executor.submit(_run_timeseries_analysis, analysis_id, request, result_dir, summary_path)

    return {
        "status": "processing",
        "analysis_id": analysis_id,
        "message": "Real NISAR backscatter time-series analysis started in the background.",
        "status_url": f"/api/v2/timeseries/status/{analysis_id}",
    }


@app.get("/api/v2/timeseries/status/{analysis_id}", tags=["Time Series v8"])
async def get_timeseries_status(analysis_id: str):
    """Poll the status of a real time-series analysis started via POST /api/v2/timeseries."""
    result_dir = GCOV_TIMESERIES_CACHE_DIR / analysis_id
    summary_path = result_dir / "summary.json"

    if summary_path.exists():
        cached = _load_json_safe(summary_path)
        if cached is not None:
            cached["cached"] = True
            return cached

    with _job_lock:
        job = _timeseries_jobs.get(analysis_id)

    if job is None:
        raise HTTPException(status_code=404, detail="No time-series analysis found or in progress for this analysis_id")

    if job.get("status") == "failed":
        raise HTTPException(status_code=500, detail=job.get("error", "Time-series analysis failed"))

    return {"status": "processing", "analysis_id": analysis_id}


@app.get("/api/v2/timeseries/{analysis_id}/frame/{index}", tags=["Time Series v8"])
async def get_timeseries_frame(analysis_id: str, index: int):
    """Download one real per-date animation frame PNG from a completed time-series analysis."""
    file_path = GCOV_TIMESERIES_CACHE_DIR / analysis_id / f"frame_{index}.png"
    if not file_path.exists() and download_single_file:
        download_single_file(analysis_id, f"frame_{index}.png", file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Time-series frame not found")
    return FileResponse(file_path, media_type="image/png")


@app.get("/api/v2/timeseries/{analysis_id}/animation.gif", tags=["Time Series v8"])
async def get_timeseries_gif(analysis_id: str):
    """Download the real animated GIF (all real per-date frames) from a completed time-series analysis."""
    file_path = GCOV_TIMESERIES_CACHE_DIR / analysis_id / "animation.gif"
    if not file_path.exists() and download_single_file:
        download_single_file(analysis_id, "animation.gif", file_path)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Time-series animation not found")
    return FileResponse(file_path, media_type="image/gif")


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
