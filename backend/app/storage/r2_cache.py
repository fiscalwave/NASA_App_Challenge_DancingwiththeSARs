"""
Optional, free, external result cache (Cloudflare R2 by default, but works
with any S3-compatible endpoint) for the small REAL analysis outputs
produced by Phase 5/6 (summary.json, change-detection GeoTIFFs, flood
GeoJSON, infrastructure-impact JSON).

Why this exists: Render's free tier has no persistent disk option at all
(confirmed via Render's own docs - "any changes you make to a service's
local files are lost every time the service redeploys or restarts" without
a paid persistent disk). Free services also restart after ~15 minutes of
inactivity. Without this cache, every repeat visit to the SAME search area
and dates after a cold start would require re-downloading the multi-GB raw
NISAR granule and re-running the full real change-detection pipeline, even
though the real result for that exact AOI/dates/thresholds was already
computed once.

Only the small, already-computed, real analysis outputs are cached here -
never the raw multi-GB HDF5 granules, which are not worth (and too large
for a free tier) persisting externally.

This is purely a performance optimization for REAL results that were
already honestly computed - it never substitutes or fabricates data.
Gracefully disables itself (every function becomes a safe no-op returning
False) if R2 credentials are not configured in the environment, so the app
continues to work exactly as before (local-disk-only caching within a
single Render instance's lifetime) until the free bucket is set up.
"""

import os
from pathlib import Path
from typing import Optional

from app.utils.logging import get_logger

logger = get_logger(__name__)

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID", "").strip()
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID", "").strip()
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY", "").strip()
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "").strip()

ENABLED = bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY and R2_BUCKET_NAME)

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    import boto3  # imported lazily so the app still runs if boto3/creds are absent

    _client = boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )
    return _client


def upload_analysis_result(analysis_id: str, result_dir: Path) -> bool:
    """
    Upload every file in a completed real analysis's result directory to the
    external cache, under the key prefix 'analysis/{analysis_id}/'.

    Best-effort: logs and returns False on any failure rather than raising -
    this is a performance optimization, never a correctness requirement, so
    a misconfigured or unreachable bucket must never break real analysis.
    """
    if not ENABLED:
        return False
    try:
        client = _get_client()
        uploaded = 0
        for file_path in result_dir.iterdir():
            if not file_path.is_file():
                continue
            key = f"analysis/{analysis_id}/{file_path.name}"
            client.upload_file(str(file_path), R2_BUCKET_NAME, key)
            uploaded += 1
        logger.info(f"Uploaded real analysis result {analysis_id} to external cache ({uploaded} file(s))")
        return uploaded > 0
    except Exception as e:
        logger.warning(f"Could not upload analysis result {analysis_id} to external cache: {e}")
        return False


def download_analysis_result(analysis_id: str, result_dir: Path) -> bool:
    """
    Attempt to restore a previously-cached completed real analysis from the
    external cache into the local result_dir (e.g. after a Render free-tier
    restart wiped the local disk). Returns True only if summary.json was
    successfully restored AND is genuinely valid JSON - the minimum needed
    to consider this a real cache hit. A partial/corrupted upload (e.g. from
    an earlier attempt that crashed mid-upload) is treated as a cache miss
    so the caller falls through to a fresh real recomputation, rather than
    ever trusting broken cached data.
    """
    if not ENABLED:
        return False
    try:
        client = _get_client()
        prefix = f"analysis/{analysis_id}/"
        paginator = client.get_paginator("list_objects_v2")
        found_any = False
        result_dir.mkdir(parents=True, exist_ok=True)
        for page in paginator.paginate(Bucket=R2_BUCKET_NAME, Prefix=prefix):
            for obj in page.get("Contents", []):
                key = obj["Key"]
                filename = key[len(prefix):]
                if not filename:
                    continue
                local_path = result_dir / filename
                client.download_file(R2_BUCKET_NAME, key, str(local_path))
                found_any = True

        summary_path = result_dir / "summary.json"
        if not (found_any and summary_path.exists()):
            return False

        try:
            import json

            def _reject_non_finite(_):
                raise ValueError("summary.json contains a non-finite (NaN/Infinity) value")

            with open(summary_path) as f:
                json.load(f, parse_constant=_reject_non_finite)
        except (ValueError, OSError) as e:
            logger.warning(
                f"Restored summary.json for {analysis_id} from external cache is invalid "
                f"({e}) - treating as a cache miss and discarding it."
            )
            try:
                summary_path.unlink()
            except OSError:
                pass
            return False

        logger.info(f"Restored real analysis result {analysis_id} from external cache")
        return True
    except Exception as e:
        logger.warning(f"Could not restore analysis result {analysis_id} from external cache: {e}")
        return False


def download_single_file(analysis_id: str, filename: str, local_path: Path) -> bool:
    """Restore a single missing file for an analysis_id already known to
    exist (defense-in-depth for layer/geojson/visual endpoints in case a
    prior full restore was partial)."""
    if not ENABLED:
        return False
    try:
        client = _get_client()
        key = f"analysis/{analysis_id}/{filename}"
        local_path.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(R2_BUCKET_NAME, key, str(local_path))
        return local_path.exists()
    except Exception as e:
        logger.warning(f"Could not restore {filename} for analysis {analysis_id} from external cache: {e}")
        return False
