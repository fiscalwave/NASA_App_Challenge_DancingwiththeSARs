# VAMIKA - NISAR Flood & Wetland Change Mapping Application - Refactored Architecture

**Phase 1: Working Dashboard and Map with FastAPI Backend**

## Overview

This is a comprehensive refactoring of the original Streamlit application into a modern, scalable **React + FastAPI** architecture for the NASA International Space Apps Challenge.

### What's Changed

| Aspect | Before (Streamlit) | After (React + FastAPI) |
|--------|-------------------|------------------------|
| **Frontend** | Streamlit (Python) | React + Vite + Tailwind |
| **Backend** | Monolithic script | Modular FastAPI services |
| **Architecture** | Single-tier | Microservices-ready |
| **Scalability** | Limited | Production-grade |
| **Code Organization** | Single file | Modular, documented |
| **Testing** | Limited | Built for unit/integration tests |
| **Deployment** | Streamlit Cloud only | Docker, cloud-native |

## Project Structure

```
NASA_App_Challenge_DancingwiththeSARs/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                      # FastAPI application
│   │   ├── config.py                    # Configuration management
│   │   ├── ingestion/                   # Data discovery & download
│   │   │   ├── asf_adapter.py           # ASF API integration
│   │   │   └── local_adapter.py         # Local file handling
│   │   ├── processing/                  # Scientific processing
│   │   │   ├── gcov_reader.py           # NISAR GCOV HDF5 reader
│   │   │   └── change_detection.py      # Backscatter analysis
│   │   ├── classification/              # Future: ML models
│   │   ├── exports/                     # GeoTIFF, GeoJSON export
│   │   │   ├── geotiff.py
│   │   │   └── geojson.py
│   │   ├── api/                         # FastAPI routes
│   │   │   ├── search.py                # Scene discovery
│   │   │   ├── process.py               # Analysis endpoints
│   │   │   └── export.py                # Export functionality
│   │   └── utils/
│   │       ├── errors.py                # Exception handling
│   │       └── logging.py               # Logging configuration
│   ├── tests/                           # Pytest suite
│   ├── requirements.txt
│   ├── .env.example
│   ├── run.sh (Linux/Mac)
│   └── run.bat (Windows)
│
├── frontend/
│   ├── src/
│   │   ├── main.jsx                     # React entry point
│   │   ├── App.jsx                      # Main app component
│   │   ├── index.css                    # Tailwind styles
│   │   ├── components/
│   │   │   ├── Header.jsx
│   │   │   ├── LocationSearch.jsx
│   │   │   ├── DateRangeSelector.jsx
│   │   │   └── MetricsPanel.jsx
│   │   ├── maps/
│   │   │   ├── LeafletMap.jsx           # Interactive map
│   │   │   └── LayerControl.jsx
│   │   ├── pages/
│   │   │   └── Dashboard.jsx            # Main dashboard page
│   │   ├── services/
│   │   │   └── api.js                   # API client
│   │   └── utils/
│   ├── public/
│   │   └── index.html
│   ├── package.json
│   └── vite.config.js
│
├── REFACTOR_PLAN.md                     # Detailed refactoring plan
└── ARCHITECTURE.md                      # This file
```

## Backend Architecture

### Core Modules

#### `ingestion/`
**Purpose**: Data discovery and retrieval

- **asf_adapter.py**: Searches and downloads NISAR GCOV from ASF
  - `search_gcov()`: Query NISAR scenes by location and date
  - `download_gcov()`: Download HDF5 files

- **local_adapter.py**: Manages local file discovery
  - `discover_gcov_files()`: Find HDF5 files
  - `validate_file()`: Check file integrity

#### `processing/`
**Purpose**: Scientific geospatial analysis

- **gcov_reader.py**: NISAR GCOV HDF5 file reader
  - `find_frequency_group()`: Locate SAR data in HDF5 structure
  - `list_polarizations()`: Get available channels
  - `load_gcov_subset()`: Extract geographic area with coordinate transformation

- **change_detection.py**: Flood detection algorithms
  - `align_and_compare()`: Spatial alignment + backscatter change computation
  - `create_flood_classification_masks()`: Classify water and flooded areas
  - `calculate_change_statistics()`: Generate metrics

#### `exports/`
**Purpose**: Output generation

- **geotiff.py**: Raster export
  - `export_to_geotiff()`: Single band GeoTIFF
  - `export_multiband_geotiff()`: Multi-band GeoTIFF

- **geojson.py**: Vector export
  - `raster_to_geojson()`: Convert masks to polygons
  - `geojson_from_metadata()`: Create metadata geometries

#### `api/`
**Purpose**: HTTP endpoints

- **search.py**: Data discovery endpoints
  - `POST /api/search/scenes`: Search available scenes
  - `GET /api/search/polarizations`: Get available channels

- **process.py**: Analysis endpoints
  - `POST /api/process/analyze`: Run flood detection analysis

- **export.py**: Export endpoints
  - `GET /api/export/geotiff/{type}`: Download GeoTIFF
  - `GET /api/export/geojson/{type}`: Download GeoJSON

### Data Mode Configuration

The backend supports multiple data sourcing modes via `config.py`:

```python
DATA_MODE = "MOCK"  # Options: MOCK, LOCAL, API, CLOUD
```

| Mode | Use Case | Requirements |
|------|----------|--------------|
| **MOCK** | Development, demos | None - returns simulated data |
| **LOCAL** | Testing with local files | HDF5 files in DATA_DIR |
| **API** | Production with live data | Earthdata credentials |
| **CLOUD** | Scalable cloud processing | Future implementation |

### Processing Pipeline

```
Input: Two GCOV scenes
  ↓
[GCOVReader]
  ├─ Parse HDF5 structure
  ├─ Extract polarimetric data
  ├─ Reproject to common grid
  └─ Output: Backscatter arrays in dB

  ↓
[ChangeDetectionEngine]
  ├─ Spatial alignment (bilinear resampling)
  ├─ Calculate Δσ⁰ = σ⁰_post - σ⁰_pre
  ├─ Classify pixels:
  │   ├─ Possible flood: Δσ⁰ ≤ -2dB AND σ⁰_post ≤ -15dB
  │   ├─ Persistent water: σ⁰_pre ≤ -15dB AND σ⁰_post ≤ -15dB
  │   └─ Other: No change or outside thresholds
  └─ Output: Classification masks + statistics

  ↓
[Exporters]
  ├─ GeoTIFFExporter: Create cloud-optimized GeoTIFF
  └─ GeoJSONExporter: Convert masks to vector polygons

Output: Raster and vector products ready for mapping
```

## Frontend Architecture

### Component Hierarchy

```
App
 └─ Header
    └─ Dashboard
       ├─ LeafletMap (right panel)
       ├─ Sidebar (left panel)
       │  ├─ LocationSearch
       │  ├─ DateRangeSelector
       │  ├─ SceneList
       │  └─ AnalysisResults
```

### State Management

Uses React hooks and local state:

```javascript
// Location bounds
const [bounds, setBounds] = useState([41.30, 12.70, 41.35, 12.75])

// Date range
const [dateRange, setDateRange] = useState({ start: '2024-10-01', end: '2024-11-01' })

// Available scenes from API
const [scenes, setScenes] = useState([])

// Selected scenes for comparison
const [selectedBefore, setSelectedBefore] = useState(null)
const [selectedAfter, setSelectedAfter] = useState(null)

// Analysis results
const [analysisResults, setAnalysisResults] = useState(null)
```

### API Integration

`services/api.js` provides client methods:

```javascript
// Search for scenes
searchAPI.searchScenes(bounds, startDate, endDate, username, password)

// Get available polarizations
searchAPI.getPolarizations(scenePath)

// Run analysis
processAPI.analyzeFloodChange(beforeScene, afterScene, bounds, polarization, thresholds)

// Export data
exportAPI.downloadGeoTIFF(fileType)
exportAPI.downloadGeoJSON(layerType)
```

### Styling

Uses Tailwind CSS with custom dark theme CSS variables:

```css
--primary: #007AFF
--success: #34C759
--warning: #FF9500
--danger: #FF3B30
--background: #07090d
--surface: #11161e
--border: #282e37
--text-primary: #f4f6f8
--text-secondary: #9da7b2
```

## Getting Started

### Prerequisites

- **Backend**: Python 3.9+, pip
- **Frontend**: Node.js 18+, npm
- **Optional**: Docker for containerized deployment
- **Data**: Earthdata account for ASF API access (API mode only)

### Backend Setup

**1. Navigate to backend directory:**
```bash
cd backend
```

**2. Create and activate virtual environment:**
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# OR
.venv\Scripts\activate.bat  # Windows
```

**3. Install dependencies:**
```bash
pip install -r requirements.txt
```

**4. Configure environment:**
```bash
cp .env.example .env
# Edit .env to set DATA_MODE, credentials, etc.
```

**5. Run the server:**
```bash
# Linux/Mac
./run.sh

# Windows
run.bat

# OR manually
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Server will be available at: **http://localhost:8000**

API docs at: **http://localhost:8000/docs** (Swagger UI)

### Frontend Setup

**1. Navigate to frontend directory:**
```bash
cd frontend
```

**2. Install dependencies:**
```bash
npm install
```

**3. Configure API proxy (if needed):**
Edit `vite.config.js` proxy settings

**4. Run development server:**
```bash
npm run dev
```

Application will be available at: **http://localhost:5173**

## Phase 1 Workflow

### Three-Click Rule

The application follows the master prompt's "three-click rule":

**Click 1: Select Location**
- Adjust map bounds or enter coordinates
- Optionally search by location name

**Click 2: Select Timeline**
- Choose start and end dates
- Search for available scenes in that period

**Click 3: View Results**
- Select before and after scenes
- Run analysis
- View flood extent on map

### Example Workflow

```
1. Set bounds: [41.30, 12.70, 41.35, 12.75] (Rome area)
2. Set dates: 2024-10-01 to 2024-11-01
3. Click "Search Available Scenes"
   → API returns NISAR GCOV scenes in that area/time
4. Select before scene: NISAR_...2024_10_25...
5. Select after scene: NISAR_...2024_11_01...
6. Click "Analyze Change"
   → Backend processes scenes
   → Computes flood masks
   → Returns statistics & GeoTIFF
7. View results on interactive map
   → Possible new inundation (cyan)
   → Permanent water (blue)
   → Statistics panel shows areas
```

## Scientific Accuracy

### Validation Criteria

All original algorithms preserved:

✅ **GCOV Reading**: Identical HDF5 parsing, coordinate handling, projection management
✅ **Change Detection**: Same backscatter difference calculation (Δσ⁰)
✅ **Water Classification**: Identical threshold logic and pixel masking
✅ **Spatial Alignment**: Bilinear resampling preserved
✅ **Export**: Same GeoTIFF generation and metadata

### Data Quality

- Handles missing/invalid pixels (NaN masking)
- Validates coordinate arrays
- Checks subset size limits (max 15M pixels)
- Reports data completeness statistics
- Distinguishes real observations from simulated data

## Error Handling

Custom exception hierarchy:

```python
ApplicationError
 ├─ DataIngestionError      # Download/discovery failures
 ├─ ProcessingError          # Algorithm failures
 ├─ ValidationError          # Data validation issues
 ├─ FileNotFoundError        # Missing files
 └─ ConfigurationError       # Config issues
```

All errors logged and returned to frontend with user-friendly messages.

## Testing

### Backend Tests (pytest)

```bash
cd backend
pytest tests/
pytest --cov=app tests/  # With coverage
```

Test structure:
- `test_gcov_reader.py`: GCOV file reading and validation
- `test_change_detection.py`: Algorithm correctness
- `test_api.py`: Endpoint functionality

### Frontend Tests (Vitest)

```bash
cd frontend
npm run test
npm run test:coverage
```

### Manual Testing

1. **MOCK mode**: Test full workflow without Earthdata
2. **LOCAL mode**: Test with sample HDF5 files
3. **API mode**: Test with real NISAR data

## Deployment

### Docker (Recommended)

```dockerfile
# Backend
FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install -r requirements.txt
COPY backend/app ./app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Frontend
FROM node:18-alpine
WORKDIR /app
COPY frontend/package*.json .
RUN npm ci
COPY frontend .
RUN npm run build
CMD ["npm", "run", "preview"]
```

### Cloud Deployment

- **Backend**: AWS EC2, Google Cloud Run, Azure Container Instances
- **Frontend**: Netlify, Vercel, AWS S3 + CloudFront
- **Database**: PostgreSQL for analysis caching (future)
- **Storage**: S3/GCS for GeoTIFF storage

## Performance Considerations

### Backend Optimization
- Bilinear resampling for alignment
- Vectorized NumPy operations
- Memory-efficient float32 arrays
- Streaming GeoTIFF exports

### Frontend Optimization
- Vite bundling and code splitting
- Lazy-loaded components
- WebWorkers for heavy map operations
- Image compression for raster display

### Caching Strategy
- Cache GCOV file metadata
- Cache polarization lists
- Cache analysis results (by hash of inputs)
- Future: Redis caching layer

## Limitations & Future Work

### Phase 1 (Current)
✅ Basic flood detection
✅ NISAR GCOV support
✅ Interactive mapping
✅ GeoTIFF/GeoJSON export

### Phase 2 (Planned)
- [ ] Infrastructure exposure analysis
- [ ] Wetland change detection
- [ ] Historical comparison
- [ ] Multi-temporal analysis

### Phase 3 (Planned)
- [ ] Machine learning classification
- [ ] Sentinel-1 integration
- [ ] AWS/GCS cloud processing
- [ ] Database-backed storage
- [ ] User accounts & saved analyses
- [ ] PDF report generation

### Known Limitations
- Requires > 1GB RAM for processing large areas
- No offline support yet
- Single-threaded processing
- Limited to NISAR GCOV (Sentinel-1 planned)

## Contributing

### Code Standards
- Python: PEP 8, type hints
- JavaScript: ESLint, Prettier
- Documentation: Markdown + docstrings
- Tests: Minimum 70% coverage

### Adding Features
1. Create feature branch: `git checkout -b feature/name`
2. Implement with tests
3. Update documentation
4. Submit pull request
5. Review & merge

## License

NASA Space Apps Challenge - Open Source

See [LICENSE](../LICENSE) for details

## Support

- **Issues**: GitHub Issues
- **Discussions**: GitHub Discussions
- **Documentation**: This guide + API docs at `/docs`

## Acknowledgments

- NASA NISAR team for data specifications
- OpenStreetMap contributors
- ASF (Alaska Satellite Facility)
- NASA Earthdata program
