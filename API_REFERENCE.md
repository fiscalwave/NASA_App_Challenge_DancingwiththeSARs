# API Reference

## Base URL

```
http://34.31.239.90:8000   (live GCP deployment)
http://localhost:8000       (local development)
```

## Real v2 API (used by the live frontend)

Everything below in this document (`/api/search`, `/api/imagery/comparison`, etc.) describes a **legacy v1 API** that is dormant and not called by the current frontend (`index.html`). It is kept for backward compatibility but should not be used for new integrations. **The real, live API is the `/api/v2/*` family**, summarized here:

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/v2/discover` | POST | Real NASA CMR discovery of NISAR L2 GCOV granules for a bounds + date range, across all 3 data-maturity tiers. Flags compatible before/after pairs (same track/frame/pass direction). Returns an empty list — never mock data — if nothing is found. |
| `/api/v2/featured` | GET | Lists curated "Featured Locations" (`backend/data/featured_locations.json`) with real metadata and `ready: true/false` depending on whether a real analysis has been pre-computed and cached for that location. |
| `/api/v2/download/start` | POST | Starts (or resumes/dedup-skips) a real, resumable granule download in a background thread pool. Body: `{granule_id, download_url, expected_size_mb}`. |
| `/api/v2/download/status/{granule_id}` | GET | Real, byte-accurate download progress, verified against the actual file on disk. |
| `/api/v2/cache` | GET | Lists all granules known to the local download cache. |
| `/api/v2/analyze` | POST | Thin handler: starts a real backscatter change-detection analysis in a background thread (real processing can take minutes) and returns `{"status": "processing", "status_url": ...}` immediately, or the full cached result if this exact request was already computed. Body: `{before_granule_id, after_granule_id, before_download_url, after_download_url, bounds, polarization, flood_change_threshold_db, low_backscatter_threshold_db}`. `before_download_url`/`after_download_url` are optional: if provided, the backend first tries a fast real remote partial (byte-range HTTPS) read of just the requested AOI directly from the granule's NASA Earthdata Cloud URL (~8x faster than a full download for a small AOI); it transparently falls back to triggering a full download + local read if the URL is omitted or the remote read fails for any reason. |
| `/api/v2/analyze/status/{analysis_id}` | GET | Poll until `status` is no longer `"processing"`. On success, returns the full real summary (change statistics, classification statistics for both open-water and flooded-vegetation signatures, detection confidence, layer/geojson/visual URLs). |
| `/api/v2/analyze/{id}/impact` | POST | Thin handler: starts real OpenStreetMap/Overpass-based infrastructure impact analysis (can take up to ~90s) in the background. |
| `/api/v2/analyze/{id}/impact/status` | GET | Poll for the real impact result: infrastructure categories (hospitals/settlements/roads/schools/power plants) and an explainable priority score. |
| `/api/v2/infrastructure/{layer}` | GET | Real single-category OpenStreetMap features (`roads`, `hospitals`, `settlements`, `power`, `schools`) for the frontend's "Infrastructure Layers" map toggles. Query params: `west, south, east, north`. Server-side mirror failover (`overpass-api.de`, `overpass.private.coffee`, `maps.mail.ru`) with a 7-day disk-backed cache, so repeated requests for the same area don't re-hit the fragile free public Overpass service. |
| `/api/v2/analyze/{id}/layer/{name}.tif` | GET | Real, full-resolution GeoTIFF layer (`before`, `after`, `change`, `possible_flood`, `possible_flooded_vegetation`, `persistent_water`). |
| `/api/v2/analyze/{id}/geojson/{name}.geojson` | GET | Real vectorized flood/vegetation/water polygons. |
| `/api/v2/analyze/{id}/visual/{before\|after}` | GET | Real SAR backscatter rendered as a base64 PNG for the swipe-comparison UI (downsampled for display only; the full-resolution GeoTIFF above is unaffected). |
| `/api/v2/diagnostics/earthdata-auth` | GET | Safe (never exposes secrets) check of whether real Earthdata credentials are configured and valid. |
| `/api/v2/diagnostics/external-cache` | GET | Whether the optional free external result cache (Cloudflare R2) is configured. |
| `/api/v2/timeseries` | POST | Thin handler: starts a real multi-date backscatter time-series analysis (ASF OpenSARlab NISAR Cookbook sections 7-8). Body: `{bounds, polarization, max_acquisitions}`. Does its own real CMR discovery internally (finds every real granule sharing one acquisition geometry for the AOI, capped to the most recent `max_acquisitions`, default 12) - no granule IDs required from the caller. Computed automatically alongside every search in the live UI. |
| `/api/v2/timeseries/status/{analysis_id}` | GET | Poll until `status` is no longer `"processing"`. On success, returns real `dates`, `means_db`/`means_power` (power-scale-correct spatial means per date), `frames` (per-date animation frame URLs), and `gif_url`. |
| `/api/v2/timeseries/{id}/frame/{index}` | GET | One real per-date animation frame PNG. |
| `/api/v2/timeseries/{id}/animation.gif` | GET | The real animated GIF assembled from every per-date frame. |

See `backend/app_real_api.py` for the authoritative, fully-commented implementation of every endpoint above.

---

## Legacy v1 API (dormant — kept for backward compatibility, not used by the live frontend)

## Authentication

Currently, the API does not require authentication. This is suitable for local/closed deployments. For production deployments, implement API key or OAuth2 authentication.

## Endpoints

### 1. Search NISAR Scenes

Query available NISAR GCOV Level 2 products by location and date range.

**Endpoint:** `GET /api/search`

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `location` | string | No | Location name (e.g., "Houston, Texas"). Will be geocoded to coordinates. |
| `latitude` | float | No | Latitude in decimal degrees (-90 to 90). Use with `longitude` instead of `location`. |
| `longitude` | float | No | Longitude in decimal degrees (-180 to 180). Use with `latitude` instead of `location`. |
| `radius` | integer | No | Search radius in kilometers (5-100). Default: 50 km. |
| `start_date` | string | No | Start date in YYYY-MM-DD format. Default: 30 days ago. |
| `end_date` | string | No | End date in YYYY-MM-DD format. Default: today. |

**Example Request:**

```bash
curl "http://localhost:8000/api/search?location=Houston,Texas&radius=70&start_date=2026-08-22&end_date=2026-09-05"
```

Or with coordinates:

```bash
curl "http://localhost:8000/api/search?latitude=29.2241&longitude=-94.7623&radius=70&start_date=2026-08-22&end_date=2026-09-05"
```

**Response:**

```json
{
  "location": "Houston, Texas",
  "coordinates": [29.2241, -94.7623],
  "search_radius_km": 70,
  "date_range": {
    "start": "2026-08-22",
    "end": "2026-09-05"
  },
  "scenes_found": 12,
  "scenes": [
    {
      "id": "NISAR_L2_PR_GCOV_005_172_A_008_2005_DHDH_A_20251122T024618_20251122T024652_P05023_N_F_J_001",
      "datetime": "2026-08-25T10:30:00Z",
      "description": "NISAR L2 GCOV",
      "properties": {
        "relative_orbit": 172,
        "pass_direction": "A",
        "polarization": ["VV", "VH"],
        "gridlines": "DHDH"
      }
    },
    {
      "id": "...",
      "datetime": "2026-08-27T14:20:00Z",
      "description": "NISAR L2 GCOV",
      "properties": {}
    }
  ],
  "status": "success"
}
```

**Response Codes:**

| Code | Description |
|------|-------------|
| 200 | Success - scenes found |
| 400 | Bad request - invalid parameters |
| 404 | No scenes found for given parameters |
| 500 | Server error |

---

### 2. Generate Before-After Comparison

Generate synthetic SAR backscatter visualizations for before-and-after imagery.

**Endpoint:** `GET /api/imagery/comparison`

**Query Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `scene_id` | string | No | Scene ID to analyze. If not provided, uses mock/sample data. |
| `latitude` | float | No | Center latitude for visualization. |
| `longitude` | float | No | Center longitude for visualization. |
| `radius` | integer | No | Analysis radius in kilometers. Default: 30 km. |

**Example Request:**

```bash
curl "http://localhost:8000/api/imagery/comparison?latitude=29.2241&longitude=-94.7623&radius=30"
```

**Response:**

Returns two PNG images as a comparison object:

```json
{
  "before_image": "data:image/png;base64,...",
  "after_image": "data:image/png;base64,...",
  "difference_map": "data:image/png;base64,...",
  "backscatter_info": {
    "before_min_db": -25.5,
    "before_max_db": 2.3,
    "after_min_db": -28.1,
    "after_max_db": 0.8,
    "change_threshold_db": 3.0,
    "pixels_changed": 15420,
    "flooded_area_km2": 12.8
  },
  "status": "success"
}
```

**Image Details:**

- **Before Image:** Baseline SAR backscatter (grey/black = water, bright = vegetation/buildings)
- **After Image:** Post-event SAR backscatter
- **Difference Map:** Orange = detected change (potential inundation), grey = no significant change

**Response Codes:**

| Code | Description |
|------|-------------|
| 200 | Success - images generated |
| 400 | Bad request - invalid parameters |
| 500 | Server error - failed to generate |

---

### 3. Health Check

Verify API server is running and responsive.

**Endpoint:** `GET /api/health`

**Example Request:**

```bash
curl "http://localhost:8000/api/health"
```

**Response:**

```json
{
  "status": "healthy",
  "version": "2.0",
  "timestamp": "2026-11-15T10:30:00Z",
  "asf_api": "connected",
  "services": {
    "geocoding": "ready",
    "imagery_processing": "ready"
  }
}
```

**Response Codes:**

| Code | Description |
|------|-------------|
| 200 | API is healthy and ready |
| 503 | API is degraded or unavailable |

---

## Data Models

### Scene Object

```json
{
  "id": "NISAR_L2_PR_GCOV_005_172_A_008_2005_DHDH_A_20251122T024618_20251122T024652_P05023_N_F_J_001",
  "datetime": "2026-08-25T10:30:00Z",
  "description": "NISAR Level 2 GCOV Product",
  "url": "https://daac.asf.alaska.edu/...",
  "properties": {
    "relative_orbit": 172,
    "pass_direction": "A",
    "product_type": "GCOV",
    "processing_level": "L2",
    "polarization": ["VV", "VH"],
    "gridlines": "DHDH",
    "collection_date": "2026-08-25",
    "collection_time": "10:30:00Z"
  }
}
```

### Confidence Badge

```json
{
  "confidence_level": 85,
  "rating": "Good",
  "factors": {
    "coherence": 0.92,
    "atmospheric_effects": 0.78,
    "geometric_distortion": 0.88,
    "multi_temporal_consistency": 0.89
  },
  "caveats": [
    "Minor ionospheric distortion detected",
    "High coherence maintained across time baseline"
  ]
}
```

---

## Error Handling

### Common Error Responses

**400 Bad Request:**

```json
{
  "error": "Bad Request",
  "message": "Invalid latitude: must be between -90 and 90",
  "code": "INVALID_PARAMETER"
}
```

**404 Not Found:**

```json
{
  "error": "Not Found",
  "message": "No NISAR scenes found for the specified parameters",
  "code": "NO_SCENES_FOUND"
}
```

**500 Internal Server Error:**

```json
{
  "error": "Internal Server Error",
  "message": "Failed to connect to ASF API",
  "code": "API_CONNECTION_ERROR"
}
```

---

## Rate Limiting

Currently no rate limiting is enforced. For production deployments, implement:

- **1000 requests per hour** per IP
- **100 concurrent requests** maximum
- **Burst limit** of 10 requests per second

---

## Caching

The API implements server-side caching:

- Scene query results cached for **1 hour**
- Imagery generation cached for **4 hours**
- Geocoding results cached for **24 hours**

Clear cache by restarting the server.

---

## Performance Tips

1. **Use coordinates instead of location names** - Faster geocoding
2. **Smaller search radius** - Fewer scenes to query (typical: 30-70 km)
3. **Shorter date ranges** - Reduces API response time
4. **Batch multiple requests** - Better server utilization
5. **Cache response locally** - Avoid redundant queries

---

## Integration Examples

### Python Example

```python
import requests

API_BASE = "http://localhost:8000"

# Search for NISAR scenes
response = requests.get(
    f"{API_BASE}/api/search",
    params={
        "location": "Houston, Texas",
        "radius": 70,
        "start_date": "2026-08-22",
        "end_date": "2026-09-05"
    }
)

scenes = response.json()["scenes"]
print(f"Found {len(scenes)} scenes")

# Get imagery comparison for first scene
if scenes:
    scene_id = scenes[0]["id"]
    imagery = requests.get(
        f"{API_BASE}/api/imagery/comparison",
        params={"scene_id": scene_id}
    )
    print("Before image URL:", imagery.json()["before_image"][:50] + "...")
```

### JavaScript Example

```javascript
const API_BASE = "http://localhost:8000";

// Search for scenes
async function searchScenes(location, radius, startDate, endDate) {
    const params = new URLSearchParams({
        location,
        radius,
        start_date: startDate,
        end_date: endDate
    });
    
    const response = await fetch(`${API_BASE}/api/search?${params}`);
    return await response.json();
}

// Get imagery comparison
async function getComparison(sceneId) {
    const response = await fetch(
        `${API_BASE}/api/imagery/comparison?scene_id=${sceneId}`
    );
    return await response.json();
}

// Usage
const scenes = await searchScenes("Houston, Texas", 70, "2026-08-22", "2026-09-05");
console.log(`Found ${scenes.scenes_found} scenes`);
```

### cURL Examples

**Search scenes:**
```bash
curl -X GET "http://localhost:8000/api/search" \
  -G -d "location=Houston,Texas" \
  -d "radius=70" \
  -d "start_date=2026-08-22" \
  -d "end_date=2026-09-05"
```

**Get comparison imagery:**
```bash
curl -X GET "http://localhost:8000/api/imagery/comparison" \
  -G -d "latitude=29.2241" \
  -d "longitude=-94.7623" \
  -d "radius=30"
```

**Health check:**
```bash
curl http://localhost:8000/api/health
```

---

## Future Endpoints (v1 legacy roadmap — superseded)

These were originally planned for the legacy v1 API. All of them are **already implemented in the real v2 API** above instead: custom analysis parameters (`POST /api/v2/analyze` body), export (handled client-side in `index.html` from real v2 GeoJSON/summary data), and confidence-factors breakdown (`detection_confidence.quality_checks` in the `/api/v2/analyze` response).

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| v2 (current) | Nov 2026 | Real-data-only `/api/v2/*` API: NASA CMR discovery, real GCOV download/analysis, dual open-water + flooded-vegetation detection, real OpenStreetMap infrastructure impact, Featured Locations pre-seed cache. Legacy v1 endpoints below retained but dormant. |
| 1.5 | Oct 2026 | Added confidence scoring, infrastructure layers (legacy v1 API) |
| 1.0 | Sep 2026 | Initial MVP with basic search and comparison (legacy v1 API) |

---

## Support

For API issues:

1. Check server logs: `backend/logs/app.log`
2. Verify `.env` configuration
3. Ensure NISAR/ASF APIs are accessible
4. Test endpoint manually with cURL
5. Check browser developer console for frontend errors

---

Last Updated: November 2026
