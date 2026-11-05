# 🚀 PHASE 2 ARCHITECTURE: OPERATIONAL IMPACT FEATURES
## NISAR Flood & Wetland Mapping Application

**Phase:** 2 - Operational Impact Features  
**Status:** ✅ Architecture Planning  
**Date:** November 5, 2026

---

## 🎯 PHASE 2 OBJECTIVES

Transform Phase 1 flood detection into **actionable emergency response intelligence** by adding:

1. **Affected Area Estimator** - Quantify the disaster scale
2. **Infrastructure Layer Toggles** - Show critical asset overlap
3. **Export Suite** - Enable field team handoff

---

## 📊 PHASE 2 FEATURES OVERVIEW

### Feature 1: Affected Area Estimator Display 📏

**Purpose:** Emergency managers need quantified disaster scale  
**User Story:** "As Derek, I need to know the flooded area in km² to prioritize resources"

**Components:**
```
┌─────────────────────────────────────────────┐
│  📊 AFFECTED AREA ANALYSIS                 │
├─────────────────────────────────────────────┤
│  Flooded Area:        45.2 km²             │
│  Affected Population: ~12,400 people       │
│  Critical Assets at Risk:                  │
│    🏥 Hospitals:      2                    │
│    🏘️  Settlements:    8                    │
│    🛣️  Roads (km):    23.5                  │
├─────────────────────────────────────────────┤
│  Damage Estimate:    $2.3M - $5.1M         │
│  Priority Level:     🔴 CRITICAL           │
└─────────────────────────────────────────────┘
```

**Technical Approach:**

1. **Polygon Area Calculation**
   - Extract inundation GeoJSON from swipe view
   - Calculate polygon area using Turf.js
   - Convert to km² (Web Mercator projection)
   - Formula: Area = geometry area / projection scale factor

2. **Population Estimation**
   - Query WorldPop dataset (gridded population)
   - Sum population within flood polygon
   - Provide confidence interval (±30%)

3. **Infrastructure Overlap**
   - Query OSM overpass API for hospitals, roads, settlements
   - Spatial join with inundation polygon
   - Count intersecting features

4. **Damage Estimation**
   - Use UNISDR damage curves (building loss vs inundation depth)
   - Estimate based on flood extent and land use
   - Provide low/mid/high confidence estimates

**Data Sources:**
- Inundation polygon: Phase 1 overlay
- Population: WorldPop dataset
- Infrastructure: OpenStreetMap
- Damage curves: UNISDR/World Bank

---

### Feature 2: Infrastructure Layer Toggles 🗺️

**Purpose:** Show where flooding impacts critical infrastructure  
**User Story:** "As Derek, I need to see which roads, hospitals, and settlements are affected"

**Components:**

```
Layer Stack (Visual Hierarchy):
┌──────────────────────────────────┐
│ 1. Inundation Overlay (Phase 1)  │ ← Highest priority
│    (Neon orange, 0.6 opacity)    │
├──────────────────────────────────┤
│ 2. Roads Layer                   │
│    (Yellow lines, 2px width)     │
├──────────────────────────────────┤
│ 3. Hospitals Layer               │
│    (🏥 Red cross icons, 24px)    │
├──────────────────────────────────┤
│ 4. Settlements Layer             │
│    (🏘️ Blue dots, 12px)          │
├──────────────────────────────────┤
│ 5. Basemap (OSM)                 │
│    (Gray tiles)                  │
└──────────────────────────────────┘

Layer Toggle Controls:
┌────────────────────────────────┐
│ Infrastructure Layers           │
├────────────────────────────────┤
│ ☐ Roads                        │
│ ☐ Hospitals                    │
│ ☑ Settlements                  │
│ ☐ Power Plants                 │
│ ☐ Water Treatment              │
└────────────────────────────────┘
```

**Technical Approach:**

1. **Data Loading Strategy**
   - Use Leaflet GeoJSON layer
   - Query Overpass API for each layer type
   - Cache results locally (1 hour TTL)
   - Lazy load on layer toggle

2. **Road Layer**
   ```
   Query: way["highway"~"primary|secondary|tertiary"]
   Style: Yellow (#FFD700), 2px width, opacity 0.7
   Interaction: Click → show road name + length
   Performance: Render limit 500 segments per viewport
   ```

3. **Hospital Layer**
   ```
   Query: node["amenity"="hospital"]
   Style: Red cross icon (#EF4444), 24px size
   Interaction: Click → show hospital name + bed count
   Performance: Render all (typically <20 per region)
   ```

4. **Settlements Layer**
   ```
   Query: node["place"~"village|town|city"]
   Style: Blue dots (#3B82F6), 12px size, halo effect
   Interaction: Click → show population estimate
   Performance: Render all (typically <50 per region)
   ```

5. **Flood Impact Calculation**
   - Spatial join: flood polygon intersects infrastructure
   - Mark affected features with 🔴 icon
   - Show distance to nearest affected area
   - Calculate impact metrics (e.g., "50% of roads blocked")

---

### Feature 3: Export Suite 💾

**Purpose:** Enable Derek to share findings with field teams  
**User Story:** "As Derek, I need to export this analysis for my field teams"

**Components:**

```
┌────────────────────────────────────────┐
│ EXPORT OPTIONS                         │
├────────────────────────────────────────┤
│ 📄 PDF Report                          │
│    └─ Summary dashboard + map image    │
│                                        │
│ 📍 GeoJSON Export                      │
│    └─ Inundation polygon + metadata    │
│                                        │
│ 🗺️  KML Export (Google Earth)          │
│    └─ Compatible with field teams      │
│                                        │
│ 📊 CSV Summary                         │
│    └─ Area, assets, damage stats       │
│                                        │
│ 🔗 Shareable Link                      │
│    └─ Pre-configured map view          │
└────────────────────────────────────────┘

PDF Report Layout:
┌──────────────────────────────────┐
│ NISAR FLOOD ANALYSIS REPORT      │ ← Header
├──────────────────────────────────┤
│ Location: Venice, Italy           │ ← Metadata
│ Date: 2025-01-15                 │
│ Confidence: 90%                  │
├──────────────────────────────────┤
│ [Map Image with Scale]            │ ← Map
├──────────────────────────────────┤
│ METRICS:                         │ ← Summary
│ • Area: 45.2 km²                │
│ • Population: ~12,400            │
│ • Critical Assets: 12            │
└──────────────────────────────────┘
```

**Technical Approach:**

1. **PDF Export**
   - Use jsPDF + html2canvas
   - Render summary dashboard to canvas
   - Include map screenshot, metrics, timestamp
   - Generate downloadable PDF

2. **GeoJSON Export**
   ```json
   {
     "type": "FeatureCollection",
     "features": [
       {
         "type": "Feature",
         "properties": {
           "type": "inundation",
           "confidence": 90,
           "area_km2": 45.2,
           "date": "2025-01-15T00:00:00Z",
           "affected_population": 12400
         },
         "geometry": {
           "type": "Polygon",
           "coordinates": [[[...], [...], ...]]
         }
       }
     ],
     "properties": {
       "source": "NISAR GCOV",
       "projection": "EPSG:4326"
     }
   }
   ```

3. **KML Export**
   - Convert GeoJSON to KML format
   - Include style (neon orange overlay)
   - Compatible with Google Earth, ArcGIS
   - Add ground overlay for basemap context

4. **CSV Summary**
   ```csv
   Metric,Value,Unit,Confidence
   Flooded Area,45.2,km²,90%
   Affected Population,12400,people,±30%
   Hospitals at Risk,2,count,100%
   Roads Blocked,23.5,km,85%
   Damage Estimate (Low),2300000,USD,75%
   Damage Estimate (High),5100000,USD,75%
   ```

5. **Shareable Link**
   - Encode search params in URL: `?location=Venice&bounds=45.1,-12.3,45.3,-12.1&date=2025-01-15`
   - Pre-load map with same search parameters
   - Generate shortened URL with QR code
   - Add expiration timestamp (24 hours)

---

## 🏗️ SYSTEM ARCHITECTURE UPDATE

### Data Flow with Phase 2

```
USER INTERACTION (Derek's Emergency Workflow)
    │
    ├─→ Phase 1: Location Search + Swipe View
    │   ├─ Geocoding → Map display
    │   ├─ API search → Scene results
    │   ├─ Swipe view → Before/After comparison
    │   └─ Confidence badge → Quality metrics
    │
    ├─→ Phase 2A: Affected Area Calculation
    │   ├─ Extract inundation polygon from overlay
    │   ├─ Calculate area (Turf.js)
    │   ├─ Query population data (WorldPop)
    │   ├─ Count infrastructure features (OSM)
    │   └─ Estimate damage (UNISDR curves)
    │
    ├─→ Phase 2B: Infrastructure Visualization
    │   ├─ Toggle roads layer (OSM query)
    │   ├─ Toggle hospitals layer (OSM query)
    │   ├─ Toggle settlements layer (OSM query)
    │   ├─ Spatial join with inundation
    │   └─ Display affected features (red markers)
    │
    └─→ Phase 2C: Export & Share
        ├─ Generate PDF report
        ├─ Export GeoJSON polygon
        ├─ Export KML for Google Earth
        ├─ Generate CSV summary
        └─ Create shareable link with QR

BACKEND ARCHITECTURE (FastAPI)
    │
    ├─ /api/search (Phase 1)
    │  └─ Query ASF for NISAR scenes
    │
    ├─ /api/area (Phase 2A)
    │  ├─ Calculate polygon area
    │  ├─ Query WorldPop API
    │  └─ Count OSM features
    │
    ├─ /api/infrastructure (Phase 2B)
    │  ├─ Query Overpass API (roads, hospitals)
    │  ├─ Spatial join logic
    │  └─ Return GeoJSON layers
    │
    └─ /api/export (Phase 2C)
       ├─ Generate PDF
       ├─ Create GeoJSON/KML
       ├─ Generate CSV
       └─ Create shareable URL
```

---

## 🗃️ DATABASE SCHEMA (Future: PostgreSQL)

```sql
-- Scenes cache
CREATE TABLE scenes (
    id SERIAL PRIMARY KEY,
    scene_id VARCHAR(255) UNIQUE,
    search_location VARCHAR(255),
    bounds GEOMETRY(Polygon),
    inundation_polygon GEOMETRY(Polygon),
    area_km2 FLOAT,
    affected_population INT,
    confidence INT,
    created_at TIMESTAMP,
    INDEX idx_bounds (bounds)
);

-- Infrastructure cache
CREATE TABLE infrastructure (
    id SERIAL PRIMARY KEY,
    osm_id BIGINT,
    type VARCHAR(50), -- 'road', 'hospital', 'settlement'
    name VARCHAR(255),
    geometry GEOMETRY(Point),
    properties JSONB,
    cached_at TIMESTAMP,
    INDEX idx_type (type),
    INDEX idx_geometry (geometry)
);

-- Export history
CREATE TABLE exports (
    id SERIAL PRIMARY KEY,
    scene_id INT REFERENCES scenes(id),
    export_type VARCHAR(50), -- 'pdf', 'geojson', 'kml'
    file_path VARCHAR(512),
    created_at TIMESTAMP,
    expires_at TIMESTAMP
);

-- Share links
CREATE TABLE share_links (
    id SERIAL PRIMARY KEY,
    scene_id INT REFERENCES scenes(id),
    token VARCHAR(64) UNIQUE,
    query_params JSONB,
    created_at TIMESTAMP,
    accessed_count INT DEFAULT 0,
    expires_at TIMESTAMP
);
```

---

## 📦 EXTERNAL LIBRARIES REQUIRED

### Frontend Libraries
```json
{
  "turf": "^6.5.0",           // Polygon area calculation
  "jspdf": "^2.5.1",          // PDF generation
  "html2canvas": "^1.4.1",    // Canvas rendering for PDF
  "geojson": "^0.5.0",        // GeoJSON handling
  "qrcode": "^1.5.3",         // QR code generation
  "axios": "^1.6.0"           // HTTP client (existing)
}
```

### Backend Libraries
```python
# requirements.txt additions
shapely==2.0.1              # Polygon operations
geojson==3.0.1              # GeoJSON parsing
requests==2.31.0            # HTTP requests
folium==0.14.0              # Map rendering for PDF
reportlab==4.0.7            # PDF generation
```

---

## 🎨 UI COMPONENTS TO ADD

### Component 1: Area Estimator Card
```html
<div class="area-estimator-card">
  <h3>📊 Affected Area Analysis</h3>
  
  <div class="metric-row">
    <span class="label">Flooded Area:</span>
    <span class="value">45.2 km²</span>
  </div>
  
  <div class="metric-row">
    <span class="label">Affected Population:</span>
    <span class="value">~12,400 people</span>
  </div>
  
  <div class="infrastructure-summary">
    <div class="asset-count">
      <span class="icon">🏥</span>
      <span class="label">Hospitals:</span>
      <span class="value">2</span>
    </div>
    <!-- More assets -->
  </div>
</div>
```

### Component 2: Layer Controls
```html
<div class="layer-controls">
  <h4>Infrastructure Layers</h4>
  <label class="toggle-switch">
    <input type="checkbox" id="roads-toggle" />
    <span class="label">🛣️ Roads</span>
  </label>
  <label class="toggle-switch">
    <input type="checkbox" id="hospitals-toggle" />
    <span class="label">🏥 Hospitals</span>
  </label>
  <!-- More layers -->
</div>
```

### Component 3: Export Menu
```html
<div class="export-menu">
  <h4>Export Results</h4>
  <button class="export-btn" data-format="pdf">
    <span class="icon">📄</span> PDF Report
  </button>
  <button class="export-btn" data-format="geojson">
    <span class="icon">📍</span> GeoJSON
  </button>
  <!-- More export options -->
</div>
```

---

## 🧪 TESTING STRATEGY

### Unit Tests
- Polygon area calculation (known geometries)
- Area conversion (meters² → km²)
- Damage estimation (test vectors)
- Export format validation (valid GeoJSON/KML)

### Integration Tests
- OSM API query + result parsing
- Population data lookup
- Spatial join logic (flood vs infrastructure)
- PDF generation with map image

### E2E Tests
- Complete workflow: Search → Analyze → Export
- Layer toggle functionality
- Export file downloads
- Shareable link generation

### Performance Tests
- Large polygon area calculation (<100ms)
- OSM API response time (<2s)
- PDF generation (<5s)
- Layer rendering with 1000+ features

---

## 📈 PERFORMANCE TARGETS - PHASE 2

| Operation | Target | Approach |
|-----------|--------|----------|
| Area Calc | <100ms | Turf.js (optimized) |
| Population Query | <500ms | Cache + local query |
| Infrastructure | <1s | Overpass API batch query |
| PDF Generation | <5s | html2canvas + jsPDF |
| KML Export | <500ms | Client-side conversion |
| Layer Render | <200ms | Lazy load + clustering |

---

## 🔐 SECURITY CONSIDERATIONS

1. **Export Files**
   - No raw sensor data (only aggregated statistics)
   - Timestamps on all exports
   - Rate limiting (1 export per 5 seconds)

2. **Share Links**
   - Token-based access (64-char random)
   - 24-hour expiration
   - Access tracking (for audit)

3. **Data Privacy**
   - Anonymize population data (grid-level, not individual)
   - No personal infrastructure details
   - GDPR-compliant (no user tracking)

4. **API Security**
   - Overpass API: Rate limiting
   - WorldPop: Cache results
   - No authentication required (public data)

---

## 🚀 IMPLEMENTATION ROADMAP

### Week 1: Affected Area Estimator
- [ ] Implement polygon area calculation (Turf.js)
- [ ] Add population query logic
- [ ] Create area metrics UI
- [ ] Test with 10+ regions

### Week 2: Infrastructure Layers
- [ ] Implement OSM API queries
- [ ] Build layer toggle controls
- [ ] Add spatial join logic
- [ ] Style layer rendering

### Week 3: Export Suite
- [ ] Implement PDF export
- [ ] Create GeoJSON export
- [ ] Add KML conversion
- [ ] Implement shareable links

### Week 4: Integration & Testing
- [ ] E2E testing
- [ ] Performance optimization
- [ ] User acceptance testing
- [ ] Documentation

---

## 📚 DOCUMENTATION TO CREATE

- [ ] PHASE_2_IMPLEMENTATION_GUIDE.md
- [ ] PHASE_2_API_REFERENCE.md
- [ ] PHASE_2_USER_GUIDE.md
- [ ] INFRASTRUCTURE_LAYER_GUIDE.md
- [ ] EXPORT_FORMAT_SPECS.md

---

## ✨ SUCCESS CRITERIA

- [x] Architecture designed
- [ ] Affected area calculator implemented & tested
- [ ] Infrastructure layers functional with 4+ layer types
- [ ] Export suite supporting 4 formats (PDF/GeoJSON/KML/CSV)
- [ ] Performance targets met (<5s for all operations)
- [ ] Comprehensive documentation
- [ ] Full E2E testing
- [ ] Ready for user acceptance test

---

**Next Step:** Begin implementation of Affected Area Estimator (Feature 2A)

