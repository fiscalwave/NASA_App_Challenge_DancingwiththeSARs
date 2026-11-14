"""
Benchmark spike: HTTPS partial/range-based reads (fsspec + h5netcdf + xarray
+ rioxarray) vs. the current "download whole file, then read locally with
h5py" approach, for a real NISAR L2 GCOV granule.

Background: https://asfopensarlab.github.io/NISAR_Cookbook/nisar-gcov-time-series-example/
demonstrates opening a remote GCOV HDF5 file lazily over plain HTTPS (not
AWS S3 - so no region lock-in, unlike Henry Rodman's S3-direct benchmark:
https://gist.github.com/hrodmn/5a377531c19da6f6d2c2bb149c450b3d) and
spatially clipping to a small AOI before any pixel data is actually
transferred. This script measures whether that approach is actually faster
than our current pipeline for a realistic small-AOI search, on our own
real GCP VM <-> NASA Earthdata Cloud network path - not just taking the
cookbook's own benchmark numbers (measured in a different environment) on faith.

This is a READ-ONLY benchmark script. It does not modify gcov_reader.py or
any production code path - it exists purely to produce real evidence for
the decision of whether to invest in rewriting the reader to support
remote partial reads.

Usage:
    python scripts/benchmark_remote_read.py
"""

from __future__ import annotations

import base64
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, Tuple

import requests
from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")

GCOV_CACHE_DIR = BACKEND_DIR / "data" / "cache"
MANIFEST_PATH = GCOV_CACHE_DIR / "manifest.json"

# A real, already-discovered granule (its remote URL and a local copy are
# both available, so we can time the "remote partial read" approach against
# a real NASA Earthdata Cloud endpoint while still having a local file for a
# fair apples-to-apples "already downloaded, read locally" comparison).
TARGET_GRANULE_ID = "NISAR_L2_PR_GCOV_028_040_A_015_4005_DHDH_A_20260815T230527_20260815T230601_P05023_N_F_J_001"

# A realistic small search-radius AOI (~15km across) placed inside the
# granule's real footprint (track 40, frame 15, over Assam/Brahmaputra -
# same general area as the Majuli Island featured location).
AOI_BBOX_4326 = dict(minx=94.60, miny=26.85, maxx=94.75, maxy=26.98)  # (west, south, east, north)

POLARIZATION_GROUP_PATH = "/science/LSAR/GCOV/grids/frequencyA"


def get_edl_bearer_token() -> str:
    """Mint a real EDL bearer token from our existing Earthdata credentials
    (find_or_create_token - reuses an existing valid token if one exists,
    avoiding hitting the 2-token-per-user limit on repeated benchmark runs)."""
    user = os.environ["ASF_USERNAME"]
    password = os.environ["ASF_PASSWORD"]
    basic = base64.b64encode(f"{user}:{password}".encode()).decode()
    resp = requests.post(
        "https://urs.earthdata.nasa.gov/api/users/find_or_create_token",
        headers={"Authorization": f"Basic {basic}"},
        timeout=30,
    )
    resp.raise_for_status()
    token = resp.json()["access_token"]
    return token


def get_granule_url_and_local_path() -> Tuple[str, Any]:
    """Resolve the real download URL for the target granule. Prefers the
    local download-manifest (so we can also run the Approach A local-file
    comparison if that file happens to still be on disk), but falls back to
    querying real NASA CMR directly by granule_id if the manifest entry or
    the raw file was already cleaned up (e.g. by the Featured Locations
    pre-seed script's disk-space management) - either way this is a real
    granule's real URL, never a placeholder."""
    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)
        entry = manifest.get(TARGET_GRANULE_ID)
        if entry and entry.get("url"):
            local_path = Path(entry["local_path"])
            return entry["url"], (local_path if local_path.exists() else None)

    # Fall back to a real, direct CMR lookup for this exact granule_id.
    import requests as _requests
    resp = _requests.get(
        "https://cmr.earthdata.nasa.gov/search/granules.json",
        params={"producer_granule_id": TARGET_GRANULE_ID, "page_size": 1},
        timeout=30,
    )
    resp.raise_for_status()
    entries = resp.json()["feed"]["entry"]
    if not entries:
        raise RuntimeError(f"Granule {TARGET_GRANULE_ID} not found in real NASA CMR either")
    links = entries[0]["links"]
    url = next(l["href"] for l in links if l.get("rel", "").endswith("/data#") and l["href"].startswith("https://"))
    return url, None


def benchmark_local_h5py(local_path: Path, bbox: Dict[str, float]) -> Dict[str, Any]:
    """Approach A (current production path): read the real, already-fully-
    downloaded local HDF5 file with our actual GCOVReader, exactly as the
    live app does once a granule has finished downloading."""
    from app.processing.gcov_reader import GCOVReader

    bounds_tuple = (bbox["minx"], bbox["miny"], bbox["maxx"], bbox["maxy"])
    t0 = time.perf_counter()
    data = GCOVReader.load_gcov_subset(local_path, "HHHH", bounds_tuple)
    elapsed = time.perf_counter() - t0
    return {
        "approach": "local h5py (already downloaded)",
        "seconds": elapsed,
        "shape": data["data"].shape,
    }


def benchmark_remote_fsspec(url: str, bbox: Dict[str, float], token: str) -> Dict[str, Any]:
    """Approach B (candidate new path): lazily open the REMOTE file over
    plain HTTPS with fsspec (tuned block cache, per the ASF Cookbook
    example), then spatially clip to the AOI with rioxarray and materialize
    only that subset - no local file ever fully downloaded."""
    import fsspec
    import xarray as xr
    import rioxarray  # noqa: F401 - registers the .rio accessor on DataArray/Dataset

    MB = 1024 * 1024
    t_open_start = time.perf_counter()
    fs = fsspec.filesystem(
        "http",
        headers={"Authorization": f"Bearer {token}"},
        cache_type="background",
        block_size=8 * MB,
    )
    f = fs.open(url, "rb")
    tree = xr.open_datatree(
        f,
        engine="h5netcdf",
        decode_timedelta=False,
        phony_dims="access",
        chunks="auto",
        group=POLARIZATION_GROUP_PATH,
    )
    t_open_elapsed = time.perf_counter() - t_open_start

    ds = tree.ds
    # Real NISAR GCOV grids carry their CRS as an "epsg_code" HDF5 ATTRIBUTE
    # on the "projection" variable (confirmed directly against a real local
    # granule - it is NOT a plain scalar dataset value as a literal .item()
    # read might suggest), so rioxarray can clip by real geographic bounds.
    epsg = int(ds["projection"].attrs["epsg_code"])
    hhhh = ds["HHHH"].rio.write_crs(f"EPSG:{epsg}")

    # bbox is in EPSG:4326 (lat/lon, matching what our frontend sends); the
    # real GCOV grid is in a local UTM-like projection, so reproject the
    # clip box to match before clipping.
    import pyproj
    transformer = pyproj.Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    minx, miny = transformer.transform(bbox["minx"], bbox["miny"])
    maxx, maxy = transformer.transform(bbox["maxx"], bbox["maxy"])

    t_clip_start = time.perf_counter()
    subset = hhhh.rio.clip_box(minx=minx, miny=miny, maxx=maxx, maxy=maxy)
    t_clip_elapsed = time.perf_counter() - t_clip_start

    t_load_start = time.perf_counter()
    subset = subset.load()  # this is where real remote byte-range requests happen
    t_load_elapsed = time.perf_counter() - t_load_start

    f.close()

    return {
        "approach": "remote fsspec+h5netcdf+rioxarray (no full download)",
        "open_seconds": t_open_elapsed,
        "clip_plan_seconds": t_clip_elapsed,
        "materialize_seconds": t_load_elapsed,
        "total_seconds": t_open_elapsed + t_clip_elapsed + t_load_elapsed,
        "shape": subset.shape,
    }


def main() -> None:
    print("=== Remote partial-read benchmark spike ===\n")

    print("Minting real EDL bearer token from existing Earthdata credentials...")
    token = get_edl_bearer_token()
    print(f"  Got token (length {len(token)})\n")

    url, local_path = get_granule_url_and_local_path()
    print(f"Target granule: {TARGET_GRANULE_ID}")
    print(f"  Remote URL: {url}")
    print(f"  Local path: {local_path if local_path else '(not available on this machine - skipping Approach A)'}")
    print(f"  AOI bbox (EPSG:4326): {AOI_BBOX_4326}\n")

    result_a = None
    if local_path:
        print("--- Approach A: local h5py (file already fully downloaded) ---")
        try:
            result_a = benchmark_local_h5py(local_path, AOI_BBOX_4326)
            print(f"  Result: {result_a}\n")
        except Exception as e:
            result_a = {"error": str(e)}
            print(f"  FAILED: {e}\n")
    else:
        print("--- Approach A skipped: no local copy of this granule on this machine ---\n")

    print("--- Approach B: remote fsspec partial read (no full download) ---")
    try:
        result_b = benchmark_remote_fsspec(url, AOI_BBOX_4326, token)
        print(f"  Result: {result_b}\n")
    except Exception as e:
        import traceback
        result_b = {"error": str(e)}
        print(f"  FAILED: {e}")
        traceback.print_exc()
        print()

    print("=== Summary ===")
    print(f"Approach A (local, already downloaded): {result_a}")
    print(f"Approach B (remote, partial read):      {result_b}")
    print()
    print("Note: Approach A assumes the file is ALREADY downloaded (the real production")
    print("cost of a full download is NOT included here - that's the multi-GB transfer")
    print("time we're trying to avoid). Approach B's total_seconds is the FULL real cost")
    print("of getting this AOI's pixels with no prior download at all. Compare Approach B's")
    print("total_seconds against how long downloading this file has taken via /api/v2/download")
    print("(~60MB/s measured earlier this session) to see the real net benefit.")


if __name__ == "__main__":
    main()
