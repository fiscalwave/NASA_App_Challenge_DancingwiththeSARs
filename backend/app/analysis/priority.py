"""
Explainable emergency-response prioritization (Phase 6.3).

Produces a transparent, rule-based priority classification (Critical / High /
Moderate / Low) from real, already-computed factors: detected inundation
extent, real infrastructure exposure counts, data confidence (geometry
compatibility from Phase 5), and observation age. Every score is returned
alongside the explicit list of factors that produced it.

Population exposure is intentionally NOT estimated here: no gridded
population dataset (e.g. WorldPop/GPW) is currently integrated, and the
project's data-integrity rules explicitly forbid generating unsupported
population statistics. This is reported as an honest limitation rather than
a fabricated number.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def compute_observation_age_days(acquisition_iso: Optional[str]) -> Optional[float]:
    """Real elapsed time since the 'after' granule's acquisition, in days.
    Returns None if the acquisition timestamp could not be determined -
    never fabricates an age."""
    if not acquisition_iso:
        return None
    try:
        acq = datetime.fromisoformat(acquisition_iso.replace("Z", "+00:00"))
        if acq.tzinfo is None:
            acq = acq.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        return round((now - acq).total_seconds() / 86400.0, 2)
    except ValueError:
        return None


def compute_priority(
    inundation_area_km2: float,
    infrastructure_categories: Dict[str, Any],
    geometry_compatible: bool,
    observation_age_days: Optional[float],
) -> Dict[str, Any]:
    """
    Explainable, rule-based priority classification.

    Every contributing factor is real and already computed upstream (Phase 5
    change detection + Phase 6.2 infrastructure intersection). No population
    or infrastructure counts are invented here.

    Returns:
        {
            "level": "Critical" | "High" | "Moderate" | "Low",
            "score": int,
            "factors": [ {"factor": str, "value": ..., "points": int, "explanation": str}, ... ],
            "population_exposure": None,
            "population_data_available": False,
            "limitations": [...]
        }
    """
    factors = []
    score = 0

    # Factor 1: detected inundation extent
    if inundation_area_km2 >= 20:
        pts = 40
    elif inundation_area_km2 >= 5:
        pts = 25
    elif inundation_area_km2 > 0:
        pts = 10
    else:
        pts = 0
    score += pts
    factors.append({
        "factor": "inundation_extent",
        "value_km2": inundation_area_km2,
        "points": pts,
        "explanation": f"Detected possible-flood area of {inundation_area_km2:.2f} km^2 in the analyzed AOI.",
    })

    # Factor 2: hospitals exposed (within the flood polygon) - highest weight,
    # since hospital access is critical during a flood event
    hospitals = infrastructure_categories.get("hospitals", {})
    hospitals_within = hospitals.get("within_flood_count", 0) if hospitals.get("status") == "ok" else 0
    hospitals_nearby = len(hospitals.get("nearby_1km", [])) if hospitals.get("status") == "ok" else 0
    pts = 35 if hospitals_within > 0 else (15 if hospitals_nearby > 0 else 0)
    score += pts
    factors.append({
        "factor": "hospital_exposure",
        "hospitals_within_flood": hospitals_within,
        "hospitals_within_1km": hospitals_nearby,
        "points": pts,
        "explanation": (
            f"{hospitals_within} hospital(s) intersect the detected flood polygon; "
            f"{hospitals_nearby} additional hospital(s) within 1km."
            if hospitals.get("status") == "ok"
            else "Hospital data unavailable from OpenStreetMap for this AOI."
        ),
    })

    # Factor 3: settlements exposed
    settlements = infrastructure_categories.get("settlements", {})
    settlements_within = settlements.get("within_flood_count", 0) if settlements.get("status") == "ok" else 0
    pts = 20 if settlements_within >= 3 else (10 if settlements_within > 0 else 0)
    score += pts
    factors.append({
        "factor": "settlement_exposure",
        "settlements_within_flood": settlements_within,
        "points": pts,
        "explanation": (
            f"{settlements_within} settlement(s)/populated place(s) intersect the detected flood polygon."
            if settlements.get("status") == "ok"
            else "Settlement data unavailable from OpenStreetMap for this AOI."
        ),
    })

    # Factor 4: road connectivity impact
    roads = infrastructure_categories.get("roads", {})
    intersecting_km = roads.get("intersecting_length_km", 0.0) if roads.get("status") == "ok" else 0.0
    pts = 15 if intersecting_km >= 5 else (8 if intersecting_km > 0 else 0)
    score += pts
    factors.append({
        "factor": "road_connectivity",
        "intersecting_road_length_km": intersecting_km,
        "points": pts,
        "explanation": (
            f"{intersecting_km:.2f} km of major roads intersect the detected flood polygon."
            if roads.get("status") == "ok"
            else "Road data unavailable from OpenStreetMap for this AOI."
        ),
    })

    # Factor 5: data confidence (geometry compatibility between before/after)
    pts = 0 if geometry_compatible else -15
    score += pts
    factors.append({
        "factor": "data_confidence",
        "geometry_compatible": geometry_compatible,
        "points": pts,
        "explanation": (
            "Before/after acquisitions share compatible SAR look geometry (same track/frame/pass)."
            if geometry_compatible
            else "Before/after acquisitions have DIFFERENT look geometry - detected change may be partly "
                 "geometric rather than real surface change. Confidence reduced accordingly."
        ),
    })

    # Factor 6: observation age (older detections are less actionable for
    # immediate emergency response)
    if observation_age_days is None:
        pts = 0
        age_note = "Acquisition date could not be determined."
    elif observation_age_days <= 3:
        pts = 10
        age_note = f"Detection is {observation_age_days:.1f} day(s) old - very recent."
    elif observation_age_days <= 14:
        pts = 5
        age_note = f"Detection is {observation_age_days:.1f} day(s) old."
    else:
        pts = -10
        age_note = f"Detection is {observation_age_days:.1f} day(s) old - conditions may have changed significantly."
    score += pts
    factors.append({
        "factor": "observation_age",
        "observation_age_days": observation_age_days,
        "points": pts,
        "explanation": age_note,
    })

    score = max(0, score)
    if score >= 70:
        level = "Critical"
    elif score >= 45:
        level = "High"
    elif score >= 20:
        level = "Moderate"
    else:
        level = "Low"

    return {
        "level": level,
        "score": score,
        "factors": factors,
        "population_exposure": None,
        "population_data_available": False,
        "limitations": [
            "Population exposure is not estimated: no gridded population dataset "
            "(e.g. WorldPop, GPW) is currently integrated. Reporting this honestly "
            "rather than fabricating a figure.",
            "Infrastructure counts reflect OpenStreetMap coverage for this area, "
            "which may be incomplete in some regions.",
            "All flood/inundation areas are satellite-derived SAR backscatter "
            "classifications and represent POTENTIAL inundation requiring field "
            "verification, not confirmed flood damage.",
        ],
    }
