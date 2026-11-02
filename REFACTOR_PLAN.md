# REFACTOR PLAN: Streamlit → React + FastAPI Architecture

## Overview
Refactoring the existing Streamlit application into a modern, scalable **React + FastAPI** stack following NASA Space Apps Challenge master prompt specifications.

## Current State Analysis

### Existing app.py Functionality
- **Data Ingestion**: ASF Search API, NISAR GCOV download, HDF5 parsing
- **Processing**: Backscatter comparison, change detection, SAR screening
- **Visualization**: Folium maps, matplotlib plots, GeoTIFF export
- **UI**: Streamlit-based tabs (Search ASF, Analyze)

### Libraries Used
- `asf_search`: NISAR data discovery and download
- `h5py`: HDF5 file reading
- `rasterio`: Raster processing
- `numpy/scipy`: Numerical analysis
- `folium`: Interactive mapping
- `matplotlib`: Scientific visualization

## Refactored Architecture

### Backend (FastAPI)
```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry point
│   ├── config.py               # Configuration management
│   ├── dependencies.py         # Shared dependencies
│   ├── ingestion/              # Data discovery & download
│   │   ├── __init__.py
│   │   ├── asf_adapter.py      # ASF Search API adapter
│   │   ├── nisar_handler.py    # NISAR-specific logic
│   │   └── local_adapter.py    # Local file handling
│   ├── processing/             # Scientific processing
│   │   ├── __init__.py
│   │   ├── gcov_reader.py      # NISAR GCOV HDF5 reading
│   │   ├── preprocessing.py    # Raster alignment, validation
│   │   └── change_detection.py # Backscatter analysis
│   ├── classification/         # Flood/water classification
│   │   ├── __init__.py
│   │   ├── water_classifier.py # Water/flood detection
│   │   └── confidence.py       # Confidence assessment
│   ├── exports/                # Output generation
│   │   ├── __init__.py
│   │   ├── geotiff.py          # GeoTIFF generation
│   │   └── geojson.py          # GeoJSON export
│   ├── api/                    # API routes
│   │   ├── __init__.py
│   │   ├── search.py           # Data search endpoints
│   │   ├── process.py          # Processing endpoints
│   │   └── export.py           # Export endpoints
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── errors.py
├── tests/
│   ├── __init__.py
│   ├── test_gcov_reader.py
│   ├── test_change_detection.py
│   └── test_api.py
├── requirements.txt
└── .env.example

```

### Frontend (React + Vite)
```
frontend/
├── src/
│   ├── main.jsx                # React entry point
│   ├── App.jsx                 # Main app component
│   ├── index.css               # Global styles
│   ├── components/
│   │   ├── Header.jsx
│   │   ├── Sidebar.jsx
│   │   ├── LocationSearch.jsx
│   │   ├── DateRangeSelector.jsx
│   │   └── MetricsPanel.jsx
│   ├── maps/
│   │   ├── LeafletMap.jsx      # Main map component
│   │   ├── BeforeAfterSlider.jsx
│   │   └── LayerControl.jsx
│   ├── pages/
│   │   ├── Dashboard.jsx       # Main page
│   │   └── Analysis.jsx        # Analysis results
│   ├── services/
│   │   ├── api.js              # API client
│   │   └── mapService.js       # Map utilities
│   ├── hooks/
│   │   ├── useMap.js
│   │   └── useAnalysis.js
│   └── utils/
│       ├── constants.js
│       └── helpers.js
├── public/
│   └── index.html
├── package.json
└── vite.config.js
```

## Phase 1 Deliverables

### Backend
1. **FastAPI application skeleton** with CORS, error handling
2. **Data ingestion layer** with ASF Search adapter
3. **GCOV reader** (extracted from app.py)
4. **Change detection engine** (extracted from app.py)
5. **API endpoints** for search, process, export
6. **Configuration management** (mock/local/API modes)

### Frontend
1. **React + Vite setup**
2. **Professional dashboard layout**
3. **Interactive Leaflet map**
4. **Location search component**
5. **Date range selector**
6. **Before/after slider**
7. **Layer controls**
8. **Metrics panel**

### Integration
1. **API client** connecting frontend to backend
2. **End-to-end workflow** (search → select → process → visualize)
3. **Environment configuration** (.env setup)
4. **Docker configuration** (optional, for deployment)

## Implementation Strategy

### Step 1: Backend Foundation
- Create FastAPI app structure
- Move GCOV reader logic from app.py
- Move change detection logic from app.py
- Create API endpoints
- Setup environment management

### Step 2: Frontend Foundation
- Initialize React + Vite project
- Create layout components
- Setup Leaflet integration
- Create map and controls

### Step 3: Integration
- Connect frontend to backend
- Test end-to-end workflow
- Add error handling
- Setup development environment

## Acceptance Criteria (Phase 1)

✅ Application starts successfully
✅ Users can select a study area via map or coordinates
✅ Users can select observation dates
✅ Frontend fetches available NISAR scenes from backend
✅ Users can download a scene pair
✅ Backend processes the pair and generates raster outputs
✅ Frontend visualizes the results on an interactive map
✅ Before/after comparison works
✅ Exports (GeoTIFF, GeoJSON) are available

## Notes

- Keep existing Streamlit app for reference during refactoring
- Preserve all scientific logic and algorithms
- Ensure same processing accuracy
- Mock data will be used initially (MOCK mode in config)
- All numerical calculations remain unchanged
