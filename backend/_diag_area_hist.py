import json

ANALYSIS_DIR = "/home/technojogi/vamika/backend/data/analysis_cache/7db7196019b7c241"

with open(f"{ANALYSIS_DIR}/possible_flood.geojson") as f:
    flood = json.load(f)

areas = [f["properties"].get("area_m2") for f in flood.get("features", []) if f["properties"].get("area_m2") is not None]
areas.sort()
n = len(areas)
print("count:", n)
if n:
    print("min:", areas[0])
    print("p10:", areas[int(n * 0.10)])
    print("p25:", areas[int(n * 0.25)])
    print("median:", areas[int(n * 0.50)])
    print("p75:", areas[int(n * 0.75)])
    print("p90:", areas[int(n * 0.90)])
    print("p99:", areas[int(n * 0.99)])
    print("max:", areas[-1])
    print("total area m2:", sum(areas))
    for thresh in [100, 400, 900, 1600, 2500, 5000, 10000, 20000]:
        kept = [a for a in areas if a >= thresh]
        print(f"threshold {thresh} m2: keeps {len(kept)}/{n} features ({len(kept)/n*100:.1f}%), "
              f"retains {sum(kept)/sum(areas)*100:.1f}% of total area")
