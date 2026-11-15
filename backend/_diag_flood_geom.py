import json
import time

from shapely.geometry import shape, Point
from shapely.ops import unary_union
from shapely.validation import make_valid
from shapely.prepared import prep

from app.analysis.infrastructure_impact import _build_reprojector

ANALYSIS_DIR = "/home/technojogi/vamika/backend/data/analysis_cache/7db7196019b7c241"

with open(f"{ANALYSIS_DIR}/summary.json") as f:
    summary = json.load(f)

with open(f"{ANALYSIS_DIR}/possible_flood.geojson") as f:
    flood_geojson = json.load(f)

combined_features = list(flood_geojson.get("features", []))
try:
    with open(f"{ANALYSIS_DIR}/possible_flooded_vegetation.geojson") as f:
        veg = json.load(f)
    combined_features.extend(veg.get("features", []))
except Exception as e:
    print("no veg geojson:", e)

print("total features:", len(combined_features))

t0 = time.time()
geoms_4326 = [shape(f["geometry"]) for f in combined_features]


def count_coords(g):
    if g.geom_type == "Polygon":
        return len(g.exterior.coords) + sum(len(r.coords) for r in g.interiors)
    if hasattr(g, "geoms"):
        return sum(count_coords(x) for x in g.geoms)
    if hasattr(g, "coords"):
        return len(g.coords)
    return 0


total_verts_raw = sum(count_coords(g) for g in geoms_4326)
print("raw total vertices across all features:", total_verts_raw)
print("time to shape():", round(time.time() - t0, 2))

t0 = time.time()
flood_union_4326 = unary_union(geoms_4326)
print("time unary_union:", round(time.time() - t0, 2), "valid:", flood_union_4326.is_valid, "type:", flood_union_4326.geom_type)
print("union vertices:", count_coords(flood_union_4326))

if not flood_union_4326.is_valid:
    t0 = time.time()
    flood_union_4326 = make_valid(flood_union_4326)
    print("time make_valid (4326):", round(time.time() - t0, 2), "type:", flood_union_4326.geom_type)
    print("post-make_valid vertices:", count_coords(flood_union_4326))

bbox = tuple(summary["bounds"])
crs = summary["crs"]
to_proj = _build_reprojector("EPSG:4326", crs)

t0 = time.time()
flood_union_proj = to_proj(flood_union_4326)
print("time reproject:", round(time.time() - t0, 2))

if not flood_union_proj.is_valid:
    t0 = time.time()
    flood_union_proj = make_valid(flood_union_proj)
    print("time make_valid (proj):", round(time.time() - t0, 2), "type:", flood_union_proj.geom_type)
    print("post-make_valid proj vertices:", count_coords(flood_union_proj))

t0 = time.time()
flood_prepared = prep(flood_union_proj)
print("time prep():", round(time.time() - t0, 2))

# single, non-concurrent query timing
cx, cy = flood_union_proj.centroid.x, flood_union_proj.centroid.y
test_point = Point(cx, cy)
t0 = time.time()
result = flood_prepared.intersects(test_point)
print("single intersects() call:", round(time.time() - t0, 3), "s, result=", result)

t0 = time.time()
result2 = flood_union_proj.intersects(test_point)
print("single UNPREPARED intersects() call:", round(time.time() - t0, 3), "s, result=", result2)
