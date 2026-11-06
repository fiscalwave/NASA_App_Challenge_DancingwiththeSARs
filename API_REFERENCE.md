# API Reference

## Base URL

```
http://localhost:8000
```

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

## Future Endpoints

Planned for Phase 3:

- `POST /api/analysis` - Custom analysis parameters
- `GET /api/export/{format}` - Export results (GeoJSON, KML, GeoTIFF)
- `POST /api/analysis/save` - Save analysis for later retrieval
- `GET /api/historical/{location}` - Historical flood/wetland statistics
- `GET /api/confidence-factors` - Detailed confidence scoring breakdown

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | Nov 2026 | Production ready, real NISAR data integration |
| 1.5 | Oct 2026 | Added confidence scoring, infrastructure layers |
| 1.0 | Sep 2026 | Initial MVP with basic search and comparison |

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
