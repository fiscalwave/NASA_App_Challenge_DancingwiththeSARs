"""
Pre-seed the "Featured Locations" cache (Tier 1 speed plan).

For each curated real location in data/featured_locations.json, this script:
  1. Queries NASA CMR directly (no mock data) for every real NISAR L2 GCOV
     granule covering that area across the mission's full lifetime so far,
     and picks the real before/after pair (same track/frame/pass direction)
     with the largest time separation - this is a real, honest discovery
     step, just not constrained to a narrow pre/post-event window like a
     live user search.
  2. Downloads both real granules via the already-running server's download
     manager (so dedup/concurrency/manifest tracking all stay correct).
  3. Calls the normal /api/v2/analyze and /api/v2/analyze/{id}/impact
     endpoints (polling until done) - this is the exact same real pipeline a
     live user search uses, so a pre-seeded result is indistinguishable from
     one a user triggered themselves.
  4. Records the analysis linkage in data/featured_cache.json so
     GET /api/v2/featured can tell the frontend "this one is ready" and hand
     it the exact request body to replay (an instant cache hit).
  5. Deletes the raw (multi-GB) HDF5 files for that location and removes
     their download-manager manifest entries - the cached analysis result
     (a few small GeoTIFFs/GeoJSON/JSON files) is all that's needed for
     instant reads afterward, so there is no reason to keep gigabytes of raw
     granules around for 25 locations (this script is designed to run on a
     disk that cannot hold all of them simultaneously).

Run this once to initially populate the cache, and periodically afterward
(e.g. via a systemd timer - see backend/scripts/featured-preseed.timer) to
pick up newer real NISAR acquisitions for the same curated locations. It is
always safe to re-run: already-ready locations are skipped unless
--force-refresh is passed.

Usage:
    python scripts/preseed_featured_locations.py [--base-url http://localhost:8000] [--force-refresh] [--only id1,id2]
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.ingestion.cmr_adapter import CMRAdapter  # noqa: E402
from app.processing.gcov_reader import GCOVReader  # noqa: E402

FEATURED_LOCATIONS_PATH = BACKEND_DIR / "data" / "featured_locations.json"
FEATURED_CACHE_PATH = BACKEND_DIR / "data" / "featured_cache.json"
GCOV_CACHE_DIR = BACKEND_DIR / "data" / "cache"
MANIFEST_PATH = GCOV_CACHE_DIR / "manifest.json"

# Preference order for flood detection (HH/VV co-pol channels are most
# sensitive to the open-water/double-bounce signatures used here; see
# NASA/JPL's "Floods" StoryMap). Not every granule carries every
# polarization, so the actual channel used is auto-detected per pair rather
# than assumed.
POLARIZATION_PREFERENCE = ["HHHH", "VVVV", "HVHV", "VHVH", "HHHV", "VVVH"]

# NISAR launched 2025-07-30; science-quality data generally begins once the
# commissioning phase ends. Starting the search a little before that is
# harmless (CMR just returns nothing for dates with no data) and avoids
# missing any early-released product.
MISSION_START = date(2025, 8, 1)

# Real NISAR GCOV granules are 1-7GB each. A download abandoned mid-flight
# by this script (e.g. after exhausting its retry budget) keeps running on
# the server in the background with no cancellation mechanism, so repeated
# abandoned downloads can silently accumulate disk usage across an
# unattended multi-hour run. Refuse to start a new location below this
# threshold rather than risk filling the disk and taking down the live app.
MIN_FREE_DISK_GB = 15

POLL_INTERVAL_SECONDS = 5
DOWNLOAD_TIMEOUT_SECONDS = 20 * 60  # large real GCOV files can take a while
ANALYZE_TIMEOUT_SECONDS = 10 * 60
IMPACT_TIMEOUT_SECONDS = 6 * 60  # best-effort; Overpass can be flaky
TIMESERIES_TIMEOUT_SECONDS = 10 * 60  # best-effort; several real remote reads


def bbox_from_center(lat: float, lon: float, radius_km: float) -> Tuple[float, float, float, float]:
    """(west, south, east, north) bounding box approximating a circle of the
    given radius around (lat, lon). Same simple equirectangular approximation
    used throughout this project for AOI math."""
    lat_offset = radius_km / 111.0
    lon_offset = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return (lon - lon_offset, lat - lat_offset, lon + lon_offset, lat + lat_offset)


def find_best_real_pair(granules: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Group real granules by (track, frame, pass_direction) and return the
    pair with the largest real time separation among groups with at least 2
    acquisitions - maximizing the chance of a visible real surface change
    for a compelling demo, while still only ever comparing geometrically
    compatible acquisitions."""
    groups: Dict[Tuple[Any, Any, Any], List[Dict[str, Any]]] = {}
    for g in granules:
        key = (g.get("track"), g.get("frame"), g.get("pass_direction"))
        if key[0] is None:
            continue
        groups.setdefault(key, []).append(g)

    best_pair = None
    best_span = -1.0
    for key, members in groups.items():
        if len(members) < 2:
            continue
        members.sort(key=lambda g: g.get("time_start") or "")
        before, after = members[0], members[-1]
        try:
            t0 = datetime.fromisoformat((before["time_start"] or "").replace("Z", "+00:00"))
            t1 = datetime.fromisoformat((after["time_start"] or "").replace("Z", "+00:00"))
            span = (t1 - t0).total_seconds()
        except (ValueError, KeyError):
            span = 0.0
        if span > best_span:
            best_span = span
            best_pair = (before, after)

    if best_pair is None:
        return None
    before, after = best_pair
    return {
        "before": before["granule_id"],
        "after": after["granule_id"],
        "before_meta": before,
        "after_meta": after,
    }


def load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    tmp.replace(path)


def wait_for_download(base_url: str, granule_id: str, download_url: str, expected_size_mb: Optional[float]) -> str:
    """Starts/polls a real download to completion and returns the local file
    path. The server can be briefly slow to respond while a CPU-heavy real
    GCOV analysis is running concurrently on another location (single-process
    uvicorn, GIL-bound numpy/rasterio work) - retries a few times on a
    request timeout rather than failing the whole location outright."""
    last_error = None
    for attempt in range(5):
        try:
            resp = requests.post(
                f"{base_url}/api/v2/download/start",
                json={"granule_id": granule_id, "download_url": download_url, "expected_size_mb": expected_size_mb},
                timeout=90,
            )
            resp.raise_for_status()
            break
        except requests.RequestException as e:
            last_error = e
            print(f"    (retry {attempt + 1}/5) could not start download for {granule_id}: {e}")
            time.sleep(10)
    else:
        raise RuntimeError(f"Could not start download for {granule_id} after retries: {last_error}")

    deadline = time.time() + DOWNLOAD_TIMEOUT_SECONDS
    consecutive_failures = 0
    while time.time() < deadline:
        try:
            status = requests.get(f"{base_url}/api/v2/download/status/{granule_id}", timeout=60).json()
        except requests.RequestException as e:
            consecutive_failures += 1
            if consecutive_failures > 10:
                raise RuntimeError(f"Too many consecutive status-poll failures for {granule_id}: {e}")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue
        consecutive_failures = 0
        if status.get("status") == "complete":
            return status["local_path"]
        if status.get("status") in ("error", "failed"):
            raise RuntimeError(f"Download failed for {granule_id}: {status.get('error')}")
        time.sleep(POLL_INTERVAL_SECONDS)
    raise TimeoutError(f"Download timed out for {granule_id}")


def pick_best_polarization(before_path: str, after_path: str) -> str:
    """Picks the best real polarization channel present in BOTH granules
    (not every polarization is present in every real NISAR GCOV product),
    preferring HH/VV co-pol channels for flood detection per NASA/JPL's
    "Floods" StoryMap guidance."""
    before_pols = set(GCOVReader.list_polarizations(Path(before_path)))
    after_pols = set(GCOVReader.list_polarizations(Path(after_path)))
    common = before_pols & after_pols
    for pol in POLARIZATION_PREFERENCE:
        if pol in common:
            return pol
    if common:
        return sorted(common)[0]
    raise RuntimeError(f"No common polarization between before ({before_pols}) and after ({after_pols})")


def preseed_timeseries(base_url: str, bbox: Tuple[float, float, float, float], polarization: str) -> Optional[str]:
    """
    Best-effort: pre-compute the real multi-date backscatter time series
    (ASF OpenSARlab NISAR Cookbook sections 7-8) for this location's AOI, so
    it loads instantly from the frontend just like the before/after result
    does - rather than the live ~2-4 minute wait a user would otherwise see.

    Never fatal to the overall location pre-seed: returns None (and the
    location is still marked "ready" for its before/after result) if the
    real time series can't be built yet (e.g. fewer than 3 real same-
    geometry acquisitions exist so far for this AOI).
    """
    try:
        body = {
            "bounds": {"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3]},
            "polarization": polarization,
            "max_acquisitions": 12,
        }
        resp = resilient_request("POST", f"{base_url}/api/v2/timeseries", json=body, timeout=90)
        data = resp.json()
        if data.get("status") == "processing":
            analysis_id = data["analysis_id"]
            deadline = time.time() + TIMESERIES_TIMEOUT_SECONDS
            while time.time() < deadline:
                time.sleep(POLL_INTERVAL_SECONDS)
                status = resilient_request(
                    "GET", f"{base_url}/api/v2/timeseries/status/{analysis_id}", timeout=60
                ).json()
                if status.get("status") != "processing":
                    data = status
                    break
            else:
                raise TimeoutError("Time series timed out")
        if data.get("status") != "success":
            raise RuntimeError(f"Time series failed: {data}")
        print(f"  Real time series ready: {data['frame_count']} date(s), track {data['track']}/frame {data['frame']}")
        return data["analysis_id"]
    except Exception as e:
        print(f"  Time series unavailable (non-fatal, continuing): {e}")
        return None


def cleanup_raw_granules(granule_ids: List[str]) -> None:
    """Delete raw HDF5 files and their manifest entries for the given
    granule_ids - safe once the small derived analysis result is cached on
    disk, since every downstream endpoint (/analyze, /impact, layer/geojson/
    visual) only ever reads from the analysis_cache directory, never the raw
    granule again, once summary.json exists."""
    manifest = load_json(MANIFEST_PATH)
    changed = False
    for granule_id in granule_ids:
        entry = manifest.pop(granule_id, None)
        changed = changed or entry is not None
        if entry:
            local_path = Path(entry.get("local_path", ""))
            if local_path.exists():
                try:
                    local_path.unlink()
                    print(f"    Cleaned up raw file: {local_path.name}")
                except OSError as e:
                    print(f"    Warning: could not delete {local_path}: {e}")
    if changed:
        save_json(MANIFEST_PATH, manifest)


def resilient_request(method: str, url: str, retries: int = 5, **kwargs) -> requests.Response:
    """A plain requests call with a few retries on transient network/timeout
    errors - the server can be briefly slow to respond while a CPU-heavy real
    GCOV analysis runs concurrently (single-process uvicorn, GIL-bound
    numpy/rasterio work), which is not a real failure."""
    last_error: Optional[Exception] = None
    for attempt in range(retries):
        try:
            resp = requests.request(method, url, **kwargs)
            resp.raise_for_status()
            return resp
        except requests.RequestException as e:
            last_error = e
            time.sleep(10)
    raise RuntimeError(f"{method} {url} failed after {retries} retries: {last_error}")


def preseed_location(base_url: str, location: Dict[str, Any], cache: Dict[str, Any]) -> bool:
    loc_id = location["id"]
    print(f"\n=== {location['name']} ({location['country']}) [{loc_id}] ===")

    bbox = bbox_from_center(location["lat"], location["lon"], location["radius_km"])
    today = datetime.now(timezone.utc).date()

    try:
        granules = CMRAdapter.discover_granules(bbox, MISSION_START, today)
    except Exception as e:
        print(f"  CMR discovery failed: {e}")
        return False

    print(f"  Found {len(granules)} real granule(s) across the mission lifetime so far")
    pair = find_best_real_pair(granules)
    if pair is None:
        print("  No compatible (same track/frame/pass) real pair with 2+ acquisitions yet - skipping for now")
        return False

    before_meta, after_meta = pair["before_meta"], pair["after_meta"]
    print(f"  Best real pair: {before_meta['time_start']} -> {after_meta['time_start']} "
          f"(track {before_meta['track']}, frame {before_meta['frame']}, {before_meta['pass_direction']})")

    try:
        # Download sequentially (not in parallel) during pre-seeding: this
        # script runs unattended for many locations back-to-back, and two
        # simultaneous multi-GB streaming downloads can starve the single-
        # process server's event loop under sustained load (confirmed during
        # the first real batch run: concurrent downloads caused the shared
        # download-manager thread pool/manifest lock to stall new requests).
        # The live user-facing app still downloads before/after in parallel
        # (fine under light single-user load) - this is pre-seed-specific.
        print("  Downloading real 'before' granule...")
        before_path = wait_for_download(base_url, before_meta["granule_id"], before_meta["download_url"], before_meta.get("size_mb"))
        print("  Downloading real 'after' granule...")
        after_path = wait_for_download(base_url, after_meta["granule_id"], after_meta["download_url"], after_meta.get("size_mb"))
        local_paths = {"before": before_path, "after": after_path}

        polarization = pick_best_polarization(local_paths["before"], local_paths["after"])
        print(f"  Using real polarization channel: {polarization}")

        print("  Running real change detection...")
        analyze_body = {
            "before_granule_id": before_meta["granule_id"],
            "after_granule_id": after_meta["granule_id"],
            "polarization": polarization,
            "bounds": {"west": bbox[0], "south": bbox[1], "east": bbox[2], "north": bbox[3]},
        }
        analyze_resp = resilient_request("POST", f"{base_url}/api/v2/analyze", json=analyze_body, timeout=90)
        analyze_data = analyze_resp.json()
        if analyze_data.get("status") == "processing":
            analysis_id = analyze_data["analysis_id"]
            deadline = time.time() + ANALYZE_TIMEOUT_SECONDS
            while time.time() < deadline:
                time.sleep(POLL_INTERVAL_SECONDS)
                status = resilient_request("GET", f"{base_url}/api/v2/analyze/status/{analysis_id}", timeout=60).json()
                if status.get("status") != "processing":
                    analyze_data = status
                    break
            else:
                raise TimeoutError("Analyze timed out")
        if analyze_data.get("status") not in ("success",):
            raise RuntimeError(f"Analyze failed: {analyze_data}")
        analysis_id = analyze_data["analysis_id"]
        print(f"  Analysis complete: {analysis_id}")

        print("  Computing real infrastructure impact (best-effort)...")
        try:
            impact_data = resilient_request("POST", f"{base_url}/api/v2/analyze/{analysis_id}/impact", timeout=90).json()
            if impact_data.get("status") == "processing":
                deadline = time.time() + IMPACT_TIMEOUT_SECONDS
                while time.time() < deadline:
                    time.sleep(POLL_INTERVAL_SECONDS)
                    status = requests.get(f"{base_url}/api/v2/analyze/{analysis_id}/impact/status", timeout=30).json()
                    if status.get("status") != "processing":
                        break
            print("  Impact computation finished (or unavailable - that's OK, UI handles it gracefully)")
        except Exception as e:
            print(f"  Impact computation failed (non-fatal, continuing): {e}")

        print("  Building real multi-date backscatter time series (best-effort)...")
        timeseries_analysis_id = preseed_timeseries(base_url, bbox, polarization)

        cache[loc_id] = {
            "analysis_id": analysis_id,
            "before_granule_id": before_meta["granule_id"],
            "after_granule_id": after_meta["granule_id"],
            "bounds": list(bbox),
            "polarization": polarization,
            "before_date": before_meta["time_start"],
            "after_date": after_meta["time_start"],
            "timeseries_analysis_id": timeseries_analysis_id,
            "last_preseeded_at": datetime.now(timezone.utc).isoformat(),
        }
        save_json(FEATURED_CACHE_PATH, cache)
        print(f"  Cached in featured_cache.json")

        cleanup_raw_granules([before_meta["granule_id"], after_meta["granule_id"]])
        return True

    except Exception as e:
        print(f"  FAILED: {e}")
        # Best-effort cleanup even on failure, so a partial download doesn't
        # sit around consuming disk indefinitely.
        cleanup_raw_granules([before_meta["granule_id"], after_meta["granule_id"]])
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the running VAMIKA server")
    parser.add_argument("--force-refresh", action="store_true", help="Re-process locations that already have a cached entry")
    parser.add_argument("--only", default=None, help="Comma-separated list of location ids to process (default: all)")
    args = parser.parse_args()

    if not FEATURED_LOCATIONS_PATH.exists():
        print(f"ERROR: {FEATURED_LOCATIONS_PATH} not found")
        sys.exit(1)

    with open(FEATURED_LOCATIONS_PATH) as f:
        locations = json.load(f)["locations"]

    if args.only:
        wanted = set(args.only.split(","))
        locations = [loc for loc in locations if loc["id"] in wanted]

    cache = load_json(FEATURED_CACHE_PATH)

    succeeded, skipped, failed = 0, 0, 0
    for location in locations:
        if not args.force_refresh and location["id"] in cache:
            print(f"Skipping {location['name']} ({location['id']}) - already cached (use --force-refresh to redo)")
            skipped += 1
            continue

        free_gb = shutil.disk_usage(GCOV_CACHE_DIR if GCOV_CACHE_DIR.exists() else BACKEND_DIR).free / 1e9
        if free_gb < MIN_FREE_DISK_GB:
            print(f"\nABORTING: only {free_gb:.1f}GB free disk (< {MIN_FREE_DISK_GB}GB threshold) - "
                  f"refusing to start a new multi-GB download. Free up disk space and re-run "
                  f"(already-cached locations will be skipped automatically).")
            break

        ok = preseed_location(args.base_url, location, cache)
        if ok:
            succeeded += 1
        else:
            failed += 1
        # Be polite to CMR/Earthdata/Overpass between locations
        time.sleep(3)

    print(f"\n=== Pre-seed run complete: {succeeded} succeeded, {skipped} skipped (already cached), {failed} failed/unavailable ===")


if __name__ == "__main__":
    main()
