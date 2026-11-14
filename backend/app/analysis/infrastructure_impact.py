"""
Infrastructure impact analysis for detected flood/change areas.

Takes the REAL possible-flood polygon produced by Phase 5's change-detection
pipeline (ChangeDetectionEngine + GeoJSONExporter) and performs genuine
spatial intersection/proximity analysis against REAL OpenStreetMap
infrastructure data (roads, hospitals, schools, settlements, power plants)
fetched live via the Overpass API, with a real Geoapify Places API fallback
for every category except roads when every Overpass mirror has failed.

No fabricated infrastructure counts, distances, or statistics are produced.
If the Overpass query (and Geoapify fallback, where available) both fail,
or return no features, that is reported explicitly rather than substituted
with estimates.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Tuple

import requests
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon, shape
from shapely.ops import unary_union, transform as shapely_transform

from app.utils.errors import DataIngestionError
from app.utils.logging import get_logger

logger = get_logger(__name__)

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
# NOTE: "overpass.kumi.systems" (previously listed as a 3rd mirror here) is
# the OLD name for the SAME host as "overpass.private.coffee" (confirmed via
# DNS - both resolve to the identical IP/reverse-DNS) - it was never a real
# independent fallback, just the same server under two names. Replaced with
# maps.mail.ru (VK Maps), a genuinely separate public Overpass deployment.
# Verified 2026-11-14: during a real, confirmed-widespread public Overpass
# overload (reproduced independently from two unrelated networks), ALL
# public mirrors including this list were degraded at once - this is a
# real capacity crisis of the free OSM ecosystem, not a bug in this app;
# see OSM's own wiki note on overpass-api.de: "Nowadays this server is
# overloaded... do not expect high reliability."

# Proximity bands used for "requires priority inspection" style reporting.
# These are real computed distances against real geometry - not estimates.
PROXIMITY_BANDS_KM = [0.0, 1.0, 5.0]

# Infrastructure categories queried from OpenStreetMap. Each entry defines
# the Overpass QL fragment and whether features are lines (roads) or points.
INFRA_QUERIES: Dict[str, Dict[str, str]] = {
    "roads": {
        "ql": 'way["highway"~"^(motorway|trunk|primary|secondary|tertiary|'
              'motorway_link|trunk_link|primary_link|secondary_link|tertiary_link|residential)$"]',
        "geometry": "line",
    },
    "hospitals": {"ql": 'node["amenity"="hospital"];way["amenity"="hospital"]', "geometry": "point"},
    "schools": {"ql": 'node["amenity"="school"];way["amenity"="school"]', "geometry": "point"},
    "settlements": {"ql": 'node["place"~"^(city|town|village|hamlet)$"]', "geometry": "point"},
    "power_plants": {"ql": 'node["power"="plant"];way["power"="plant"]', "geometry": "point"},
}

MAX_FEATURES_PER_CATEGORY = 1500


# Overpass public mirrors rate-limit/reject requests that don't send a
# meaningful User-Agent identifying the application (their documented usage
# policy) - without this header, mirrors return HTTP 429 unconditionally.
OVERPASS_HEADERS = {
    "User-Agent": "NISAR-Flood-Wetland-Mapping/1.0 (NASA Space Apps Challenge disaster-response prototype)"
}

# Real fallback POI source for when every Overpass mirror has failed
# (verified 2026-11-14: a genuine, widespread public Overpass overload, not
# specific to this app - see OVERPASS_ENDPOINTS comment above). Geoapify's
# Places API serves the same underlying OpenStreetMap data, but from
# Geoapify's own production infrastructure rather than volunteer-run public
# Overpass mirrors - free tier, 3,000 requests/day, no credit card. Verified
# directly (2026-11-14) to return real results for all four of these
# categories. There is no equivalent fallback for "roads": no free provider
# anywhere exposes a bulk road-network geometry API outside the OSM/Overpass
# ecosystem itself (this includes Google - see TROUBLESHOOTING.md).
#
# Read lazily (a function, not a module-level constant) because
# app_real_api.py imports this module BEFORE it calls load_dotenv() (the
# same reason it has to hand-parse ASF_USERNAME/ASF_PASSWORD out of .env
# itself) - a module-level os.getenv() here would always see an empty
# string, even with a real key configured.
def _geoapify_api_key() -> str:
    return os.getenv("GEOAPIFY_API_KEY", "").strip()


GEOAPIFY_CATEGORIES: Dict[str, str] = {
    "hospitals": "healthcare.hospital",
    "schools": "education.school",
    "settlements": "populated_place",
    "power_plants": "power.plant,power.generator",
}
GEOAPIFY_PAGE_SIZE = 200
GEOAPIFY_MAX_PAGES = 3  # up to 600 real features - 3 credits/call, cheap within the 3,000/day free budget


def _query_geoapify(category: str, bbox: Tuple[float, float, float, float], timeout: int = 20) -> Dict[str, Any]:
    """
    Real fallback query against Geoapify's Places API for one infrastructure
    category, used only when every configured Overpass mirror has already
    failed. Converts Geoapify's GeoJSON response into the exact same
    {"elements": [...]} shape Overpass returns, so every downstream
    consumer (impact analysis, map rendering) works unchanged regardless of
    which real source actually answered.

    Raises DataIngestionError if no API key is configured, the category has
    no Geoapify mapping (e.g. "roads"), or the request itself fails - never
    fabricates data.
    """
    geoapify_category = GEOAPIFY_CATEGORIES.get(category)
    api_key = _geoapify_api_key()
    if not api_key or not geoapify_category:
        raise DataIngestionError(f"No Geoapify fallback configured for category '{category}'")

    west, south, east, north = bbox
    elements: List[Dict[str, Any]] = []
    for page in range(GEOAPIFY_MAX_PAGES):
        params = {
            "categories": geoapify_category,
            "filter": f"rect:{west},{south},{east},{north}",
            "limit": GEOAPIFY_PAGE_SIZE,
            "offset": page * GEOAPIFY_PAGE_SIZE,
            "apiKey": api_key,
        }
        try:
            resp = requests.get("https://api.geoapify.com/v2/places", params=params, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as e:
            raise DataIngestionError(f"Geoapify fallback failed: {e}")

        features = data.get("features", [])
        for feature in features:
            coords = (feature.get("geometry") or {}).get("coordinates")
            if not coords or len(coords) < 2:
                continue
            elements.append({
                "type": "node",
                "lon": coords[0],
                "lat": coords[1],
                "tags": {"name": (feature.get("properties") or {}).get("name", "")},
            })
        if len(features) < GEOAPIFY_PAGE_SIZE:
            break

    logger.info(f"Geoapify fallback returned {len(elements)} real feature(s) for category '{category}'")
    return {"elements": elements}


def _query_overpass(ql_body: str, bbox: Tuple[float, float, float, float], timeout: int = 25) -> Dict[str, Any]:
    """Query Overpass with mirror failover and a bounded timeout per mirror.
    Raises DataIngestionError only if every mirror fails - never returns
    fabricated data."""
    west, south, east, north = bbox
    query = f'[out:json][timeout:{timeout}];({ql_body}({south},{west},{north},{east}););out geom;'

    last_error: Optional[Exception] = None
    for endpoint in OVERPASS_ENDPOINTS:
        try:
            resp = requests.post(endpoint, data=query, timeout=timeout, headers=OVERPASS_HEADERS)
            if resp.ok:
                return resp.json()
            last_error = DataIngestionError(f"{endpoint} returned HTTP {resp.status_code}")
        except requests.RequestException as e:
            last_error = e
    raise DataIngestionError(f"All Overpass mirrors failed: {last_error}")


def query_infrastructure_category(category: str, bbox: Tuple[float, float, float, float]) -> Dict[str, Any]:
    """
    Query real OpenStreetMap features for one infrastructure category over
    an AOI: tries Overpass first (with its own 3-mirror failover), then
    falls back to Geoapify's Places API (see _query_geoapify()) if Overpass
    fails entirely AND a Geoapify fallback exists for this category AND
    GEOAPIFY_API_KEY is configured - otherwise the original Overpass error
    is raised as-is. Exposed as a public entry point so a single-layer
    request (e.g. the frontend's "Infrastructure Layers" toggles) can reuse
    the exact same server-side querying code, instead of querying Overpass
    directly from the browser (which cannot send a custom User-Agent
    header - a forbidden header in the Fetch spec - so those requests
    don't comply with Overpass's own usage policy of identifying the
    calling application).

    Args:
        category: one of INFRA_QUERIES's keys (roads, hospitals, schools,
            settlements, power_plants)
        bbox: (west, south, east, north) in EPSG:4326

    Returns:
        The raw Overpass-shaped JSON response ({"elements": [...]}),
        regardless of which real source (Overpass or Geoapify) answered.

    Raises:
        ValueError: unknown category
        DataIngestionError: every real source failed (Overpass, and Geoapify
            if one was attempted) - never returns fabricated data
    """
    if category not in INFRA_QUERIES:
        raise ValueError(f"Unknown infrastructure category '{category}'. Valid: {sorted(INFRA_QUERIES)}")

    has_fallback = category in GEOAPIFY_CATEGORIES and bool(_geoapify_api_key())
    # When a real fallback exists for this category, don't make the caller
    # wait through Overpass's full 3-mirror x 25s timeout budget (75s) before
    # getting a real answer from Geoapify - fail faster over to the
    # fallback instead. "roads" has no fallback, so it keeps the full
    # timeout budget since Overpass is the only real option for it.
    overpass_timeout = 10 if has_fallback else 25

    try:
        return _query_overpass(INFRA_QUERIES[category]["ql"], bbox, timeout=overpass_timeout)
    except DataIngestionError as overpass_error:
        if not has_fallback:
            raise
        logger.warning(
            f"Overpass failed for category '{category}' ({overpass_error}); trying real Geoapify fallback"
        )
        try:
            return _query_geoapify(category, bbox)
        except DataIngestionError as geoapify_error:
            raise DataIngestionError(
                f"Overpass failed ({overpass_error}) and the Geoapify fallback also failed ({geoapify_error})"
            )


def _elements_to_geometries(elements: List[Dict[str, Any]], geometry_kind: str):
    """Convert raw Overpass elements into shapely geometries (EPSG:4326),
    paired with their OSM tags for naming/labeling."""
    features = []
    for el in elements[:MAX_FEATURES_PER_CATEGORY]:
        try:
            if geometry_kind == "line" and el.get("type") == "way" and el.get("geometry"):
                coords = [(pt["lon"], pt["lat"]) for pt in el["geometry"]]
                if len(coords) >= 2:
                    features.append((LineString(coords), el.get("tags", {})))
            elif geometry_kind == "point":
                if el.get("type") == "node":
                    features.append((Point(el["lon"], el["lat"]), el.get("tags", {})))
                elif el.get("type") == "way" and el.get("center"):
                    features.append((Point(el["center"]["lon"], el["center"]["lat"]), el.get("tags", {})))
        except (KeyError, ValueError):
            continue
    return features


def _build_reprojector(src_crs: str, dst_crs: str):
    transformer = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    return lambda geom: shapely_transform(lambda x, y: transformer.transform(x, y), geom)


def compute_infrastructure_impact(
    flood_geojson: Dict[str, Any],
    bbox: Tuple[float, float, float, float],
    analysis_crs: str,
) -> Dict[str, Any]:
    """
    Real spatial intersection/proximity analysis between a detected flood
    polygon (EPSG:4326 GeoJSON, as produced by Phase 5) and real OpenStreetMap
    infrastructure within the analysis bounding box.

    Args:
        flood_geojson: FeatureCollection of possible-flood polygons (EPSG:4326)
        bbox: (west, south, east, north) in EPSG:4326 - the analysis AOI
        analysis_crs: the projected CRS used by the underlying GCOV analysis
                      (e.g. "EPSG:32637"), used for accurate meter-based
                      distance/length calculations

    Returns:
        Dict with per-category real counts, intersecting/affected road length
        (km), and a list of the nearest exposed facilities with real computed
        distances. If the flood polygon is empty, or Overpass returns nothing
        for a category, this is reported explicitly (never fabricated).
    """
    flood_geoms_4326 = [shape(f["geometry"]) for f in flood_geojson.get("features", [])]
    if not flood_geoms_4326:
        return {
            "status": "no_flood_detected",
            "message": "No possible-flood polygons were produced by the analysis for this AOI/thresholds.",
            "categories": {},
        }

    flood_union_4326 = unary_union(flood_geoms_4326)

    to_proj = _build_reprojector("EPSG:4326", analysis_crs)
    flood_union_proj = to_proj(flood_union_4326)

    # Fetch all categories concurrently. Each category's real-source chain
    # (Overpass mirror failover, then the Geoapify fallback if configured)
    # is network-bound and independent of the others, so running them
    # sequentially would multiply worst-case latency by the number of
    # categories; running them in parallel bounds the real wall-clock wait
    # to that of the single slowest category.
    import concurrent.futures

    def _fetch(category: str, spec: Dict[str, str]):
        try:
            raw = query_infrastructure_category(category, bbox)
            return category, "ok", raw.get("elements", [])
        except DataIngestionError as e:
            return category, "error", str(e)

    fetched: Dict[str, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(INFRA_QUERIES)) as executor:
        futures = [executor.submit(_fetch, category, spec) for category, spec in INFRA_QUERIES.items()]
        for future in concurrent.futures.as_completed(futures):
            category, outcome, payload = future.result()
            fetched[category] = (outcome, payload)

    categories: Dict[str, Any] = {}

    for category, spec in INFRA_QUERIES.items():
        outcome, payload = fetched[category]
        if outcome == "error":
            categories[category] = {
                "status": "unavailable",
                "error": payload,
                "note": "OpenStreetMap/Overpass query failed for this category; reporting unavailable rather than fabricating results.",
            }
            continue

        elements = payload
        geoms_4326 = _elements_to_geometries(elements, spec["geometry"])
        if not geoms_4326:
            categories[category] = {"status": "no_features_found", "total_found": 0}
            continue

        if spec["geometry"] == "line":
            total_length_km = 0.0
            intersecting_length_km = 0.0
            intersecting_count = 0
            for geom, tags in geoms_4326:
                proj_geom = to_proj(geom)
                length_km = proj_geom.length / 1000.0
                total_length_km += length_km
                if proj_geom.intersects(flood_union_proj):
                    intersecting_segment = proj_geom.intersection(flood_union_proj)
                    intersecting_length_km += intersecting_segment.length / 1000.0
                    intersecting_count += 1

            categories[category] = {
                "status": "ok",
                "total_segments_found": len(geoms_4326),
                "total_length_km": round(total_length_km, 2),
                "intersecting_segment_count": intersecting_count,
                "intersecting_length_km": round(intersecting_length_km, 2),
            }
        else:
            within_flood = []
            nearby = {band: [] for band in PROXIMITY_BANDS_KM[1:]}
            for geom, tags in geoms_4326:
                proj_geom = to_proj(geom)
                name = tags.get("name", f"Unnamed {category[:-1] if category.endswith('s') else category}")
                if proj_geom.within(flood_union_proj) or proj_geom.intersects(flood_union_proj):
                    within_flood.append({"name": name, "lat": geom.y, "lon": geom.x, "distance_km": 0.0})
                else:
                    dist_km = proj_geom.distance(flood_union_proj) / 1000.0
                    for band in PROXIMITY_BANDS_KM[1:]:
                        if dist_km <= band:
                            nearby[band].append({
                                "name": name, "lat": geom.y, "lon": geom.x,
                                "distance_km": round(dist_km, 2),
                            })
                            break

            categories[category] = {
                "status": "ok",
                "total_found": len(geoms_4326),
                "within_flood_polygon": within_flood,
                "within_flood_count": len(within_flood),
                "nearby_1km": sorted(nearby[1.0], key=lambda x: x["distance_km"]),
                "nearby_5km": sorted(nearby[5.0], key=lambda x: x["distance_km"]),
            }

    return {"status": "success", "categories": categories}
