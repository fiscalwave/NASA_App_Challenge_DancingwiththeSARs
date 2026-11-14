"""
CMR (Common Metadata Repository) adapter for NASA Earthdata.

Provides direct, maturity-tier-aware discovery of NISAR L2 GCOV granules via
CMR's public search API. Unlike a generic platform/processingLevel query
(which does not distinguish between the three NISAR GCOV quality tiers),
this adapter queries each tier's exact collection concept-id explicitly, so
callers can choose/prioritize Validated > Provisional > Beta data.

Collection concept-ids were verified directly against CMR (search.earthdata.nasa.gov
is backed by this same API) on 2026-11-07:
  - NISAR_L2_GCOV_V1             (C3622241360-ASF) - Validated / SCIENCE_QUALITY
  - NISAR_L2_GCOV_PROVISIONAL_V1 (C2854338529-ASF) - Provisional
  - NISAR_L2_GCOV_BETA_V1        (C3622214170-ASF) - Beta (not for research)

This module performs metadata-only discovery - no science data is downloaded
here. CMR granule search does not require Earthdata authentication; only the
actual data download (handled by download_manager.py) does.
"""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

import requests

from app.utils.errors import DataIngestionError
from app.utils.logging import get_logger

logger = get_logger(__name__)

CMR_GRANULE_SEARCH_URL = "https://cmr.earthdata.nasa.gov/search/granules.json"

# Verified NISAR L2 GCOV collection concept-ids, highest quality first.
GCOV_COLLECTIONS: Dict[str, str] = {
    "VALIDATED": "C3622241360-ASF",
    "PROVISIONAL": "C2854338529-ASF",
    "BETA": "C3622214170-ASF",
}

# Extracts fields from NISAR's producer granule id, e.g.:
# NISAR_L2_PR_GCOV_<abs_orbit>_<track>_<pass>_<frame>_...
GRANULE_ID_PATTERN = re.compile(
    r"^NISAR_L2_PR_GCOV_(?P<orbit>\d+)_(?P<track>\d+)_(?P<pass_dir>[AD])_(?P<frame>\d+)_"
)


def _parse_granule_id_fields(granule_id: str) -> Dict[str, Any]:
    """Best-effort extraction of orbit/track/frame/pass-direction from a NISAR
    granule id. Used to flag incompatible before/after pairs - different track,
    frame, or pass direction materially change SAR look geometry independent
    of any real surface change."""
    match = GRANULE_ID_PATTERN.match(granule_id)
    if not match:
        return {"orbit": None, "track": None, "frame": None, "pass_direction": None}
    return {
        "orbit": int(match.group("orbit")),
        "track": int(match.group("track")),
        "frame": int(match.group("frame")),
        "pass_direction": "Ascending" if match.group("pass_dir") == "A" else "Descending",
    }


# Matches the acquisition start/end timestamps embedded in NISAR granule ids,
# e.g. ..._20251122T024618_20251122T024652_...
ACQUISITION_TIME_PATTERN = re.compile(r"_(\d{8}T\d{6})_(\d{8}T\d{6})_")


def _parse_granule_acquisition_time(granule_id: str) -> Optional[str]:
    """Extract the real acquisition start time embedded in a NISAR granule id
    as an ISO-8601 string, or None if it cannot be parsed. Used for honest
    'how old is this observation' reporting - never guessed or defaulted to
    the current date."""
    match = ACQUISITION_TIME_PATTERN.search(granule_id)
    if not match:
        return None
    raw = match.group(1)  # YYYYMMDDTHHMMSS
    try:
        from datetime import datetime
        dt = datetime.strptime(raw, "%Y%m%dT%H%M%S")
        return dt.isoformat() + "Z"
    except ValueError:
        return None


class CMRAdapter:
    """Direct CMR client for NISAR L2 GCOV discovery across all maturity tiers."""

    @staticmethod
    def _bounding_box_str(bounds: Tuple[float, float, float, float]) -> str:
        west, south, east, north = bounds
        return f"{west},{south},{east},{north}"

    @classmethod
    def discover_granules(
        cls,
        bounds: Tuple[float, float, float, float],
        start: date,
        end: date,
        tiers: Optional[List[str]] = None,
        page_size: int = 50,
        timeout: int = 30,
    ) -> List[Dict[str, Any]]:
        """
        Discover real NISAR L2 GCOV granules via CMR, across the requested
        maturity tiers (metadata-first; no data is downloaded here).

        Args:
            bounds: (west, south, east, north) in EPSG:4326
            start: Search window start date
            end: Search window end date
            tiers: Subset/order of tiers to search, e.g. ["VALIDATED", "PROVISIONAL"].
                   Defaults to all three, highest quality first.
            page_size: Max granules to return per tier
            timeout: HTTP timeout in seconds

        Returns:
            List of granule metadata dicts, each tagged with its maturity
            "tier", sorted by acquisition start time. Empty list if nothing
            is found - callers must not substitute mock data for an empty result.

        Raises:
            DataIngestionError: If the CMR request itself fails (network/HTTP error)
        """
        tiers = tiers or ["VALIDATED", "PROVISIONAL", "BETA"]
        temporal = f"{start.isoformat()}T00:00:00Z,{end.isoformat()}T23:59:59Z"
        bbox = cls._bounding_box_str(bounds)

        all_granules: List[Dict[str, Any]] = []
        seen_ids = set()

        for tier in tiers:
            concept_id = GCOV_COLLECTIONS.get(tier)
            if not concept_id:
                logger.warning(f"Unknown GCOV maturity tier requested: {tier}")
                continue

            params = {
                "collection_concept_id": concept_id,
                "temporal": temporal,
                "bounding_box": bbox,
                "page_size": page_size,
                "sort_key": "start_date",
            }

            try:
                logger.info(f"Querying CMR tier={tier} ({concept_id}) bbox={bbox} temporal={temporal}")
                resp = requests.get(CMR_GRANULE_SEARCH_URL, params=params, timeout=timeout)
                resp.raise_for_status()
            except requests.RequestException as e:
                raise DataIngestionError(f"CMR granule search failed for tier {tier}: {e}")

            entries = resp.json().get("feed", {}).get("entry", [])
            logger.info(f"  Tier {tier}: {len(entries)} granule(s) found")

            for entry in entries:
                granule_id = entry.get("producer_granule_id") or entry.get("title")
                if not granule_id or granule_id in seen_ids:
                    continue
                seen_ids.add(granule_id)

                links = entry.get("links", [])
                download_url = next(
                    (l["href"] for l in links
                     if l.get("rel", "").endswith("/data#") and l.get("href", "").startswith("https://")),
                    None
                )
                s3_url = next(
                    (l["href"] for l in links
                     if l.get("rel", "").endswith("/s3#") and l.get("href", "").startswith("s3://")
                     and l["href"].endswith(".h5")),
                    None
                )
                browse_urls = [
                    l["href"] for l in links
                    if l.get("rel", "").endswith("/browse#") and l.get("href", "").startswith("https://")
                ]

                granule = {
                    "granule_id": granule_id,
                    "collection_concept_id": entry.get("collection_concept_id", concept_id),
                    "tier": tier,
                    "time_start": entry.get("time_start"),
                    "time_end": entry.get("time_end"),
                    "size_mb": float(entry.get("granule_size", 0.0)) if entry.get("granule_size") else None,
                    "download_url": download_url,
                    "s3_url": s3_url,
                    "browse_urls": browse_urls,
                    "polygons": entry.get("polygons"),
                    **_parse_granule_id_fields(granule_id),
                }
                all_granules.append(granule)

        all_granules.sort(key=lambda g: g.get("time_start") or "")
        return all_granules

    @classmethod
    def discover_pre_post_event(
        cls,
        bounds: Tuple[float, float, float, float],
        event_start: date,
        event_end: date,
        pre_event_days: int = 30,
        post_event_days: int = 30,
        tiers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Discover candidate pre-event and post-event granules for a flood/change
        analysis, and flag which before/after combinations share compatible
        acquisition geometry (same track, frame, and pass direction) versus
        combinations that would require extra caution - different geometry can
        itself change backscatter independent of any real surface change.

        Returns:
            {
                "pre_event": [...granules before event_start...],
                "post_event": [...granules after event_end...],
                "compatible_pairs": [{"before": granule_id, "after": granule_id, ...}, ...],
                "geometry_warning": "..." (present only if no compatible pair exists)
            }
        """
        pre_start = event_start - timedelta(days=pre_event_days)
        pre_granules = cls.discover_granules(bounds, pre_start, event_start, tiers=tiers)

        post_finish = event_end + timedelta(days=post_event_days)
        post_granules = cls.discover_granules(bounds, event_end, post_finish, tiers=tiers)

        compatible_pairs = []
        for before in pre_granules:
            for after in post_granules:
                if (
                    before.get("track") is not None
                    and before["track"] == after.get("track")
                    and before["frame"] == after.get("frame")
                    and before["pass_direction"] == after.get("pass_direction")
                ):
                    compatible_pairs.append({
                        "before": before["granule_id"],
                        "after": after["granule_id"],
                        "before_tier": before["tier"],
                        "after_tier": after["tier"],
                    })

        result: Dict[str, Any] = {
            "pre_event": pre_granules,
            "post_event": post_granules,
            "compatible_pairs": compatible_pairs,
        }

        if pre_granules and post_granules and not compatible_pairs:
            result["geometry_warning"] = (
                "No pre/post-event granule pair shares the same track, frame, and "
                "pass direction. Any before/after comparison using these granules "
                "will mix different SAR look geometries, which can itself change "
                "backscatter independent of real surface change. Treat results as "
                "lower confidence and prefer a compatible pair if one becomes available."
            )

        return result

    @classmethod
    def discover_time_series(
        cls,
        bounds: Tuple[float, float, float, float],
        start: date,
        end: date,
        max_acquisitions: int = 12,
        tiers: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Discover the real chronological acquisition history for an AOI, for
        a multi-date backscatter time series (per the ASF OpenSARlab NISAR
        Cookbook's time-series techniques) - different from
        discover_pre_post_event(), which only looks at two narrow pre/post
        windows around a single event date.

        Groups every real granule found in [start, end] by (track, frame,
        pass_direction) - only acquisitions sharing the same real SAR look
        geometry are comparable in a time series, for the same reason a
        before/after pair requires it - and returns the LARGEST such group
        (the one real repeat-pass geometry with the most actual coverage for
        this AOI), capped to the most recent max_acquisitions dates in
        chronological order.

        Returns:
            {
                "acquisitions": [...real granule metadata dicts, oldest first...],
                "track": int or None, "frame": int or None, "pass_direction": str or None,
                "total_candidates": total real granules found across all geometries,
                "total_in_group": real granules found for the selected geometry
                                  (before capping to max_acquisitions),
            }
            Empty "acquisitions" list (with track/frame/pass_direction all
            None) if no real granule in this AOI/window has track/frame
            metadata at all - never substitutes a fabricated time series.
        """
        granules = cls.discover_granules(bounds, start, end, tiers=tiers)

        groups: Dict[Tuple[Any, Any, Any], List[Dict[str, Any]]] = {}
        for g in granules:
            if g.get("track") is None:
                continue
            key = (g["track"], g["frame"], g["pass_direction"])
            groups.setdefault(key, []).append(g)

        if not groups:
            return {
                "acquisitions": [],
                "track": None,
                "frame": None,
                "pass_direction": None,
                "total_candidates": len(granules),
                "total_in_group": 0,
            }

        best_key, best_group = max(groups.items(), key=lambda kv: len(kv[1]))
        best_group = sorted(best_group, key=lambda g: g.get("time_start") or "")
        capped = best_group[-max_acquisitions:] if max_acquisitions else best_group

        return {
            "acquisitions": capped,
            "track": best_key[0],
            "frame": best_key[1],
            "pass_direction": best_key[2],
            "total_candidates": len(granules),
            "total_in_group": len(best_group),
        }

