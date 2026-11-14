# VAMIKA

**NISAR-Based Flood & Wetland Mapping Application**

**NASA International Space Apps Challenge | Disaster Response Technology**

An open-source interactive web application for real-time flood and wetland change detection using NISAR satellite data, optimized for emergency management professionals.

## Challenge Problem Statement

Earth's surface is an endless dance of natural processes and human activities, but these changes are often difficult to visualize, understand, and communicate. From wetland loss to forest wildfires, earthquakes, farming activities, glacier movement, and more, Earth is in a constant waltz of surface changes. Your challenge is to build an interactive application that uses radar remote sensing data from the NASA-ISRO Synthetic Aperture Radar (NISAR) mission to track and visualize one or more types of surface change at locations around the world.

## Overview

This application enables emergency managers to quickly identify surface changes after flood events using satellite radar data from NASA's NISAR mission. It combines geospatial analysis with a user-friendly interface to support disaster response and field assessment prioritization.

**Target User:** Derek Hough, Emergency Management Analyst

**Core Capability:** Before-and-after SAR backscatter analysis to detect inundation zones with confidence scoring and damage estimation.

## Quick Start

### Prerequisites
- Python 3.8+
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd NASA_App_Challenge_DancingwiththeSARs
   ```

2. **Install backend dependencies**
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Start the application**
   ```bash
   python app_real_api.py
   ```
   This single command serves both the API and the frontend together. Open your browser to `http://localhost:8000`

### Using the Application

1. **Search by location** - Enter city name or coordinates
2. **Set search radius** - Define analysis area (5-100 km)
3. **Select date range** - Choose pre-flood and post-flood dates
4. **Discover scenes** - Query NISAR satellite acquisitions
5. **Compare imagery** - Use slider to view before-and-after SAR backscatter
6. **Analyze results** - Review affected area, confidence scores, infrastructure impact
7. **Export findings** - Download as PDF, GeoJSON, KML, or CSV

## Features

### Phase 1: Core Analysis (Complete)
- **Event & Location Filter Panel** - Search specific locations and date ranges
- **Before-and-After Swipe View** - Split-screen comparison with interactive slider
- **Automated Inundation Highlighting** - Orange overlay for detected flood zones on map
- **Confidence Badges** - Data quality indicators (accuracy, atmospheric effects)
- **Real NISAR Data** - Integration with ASF NASA API for actual satellite scenes

### Phase 2: Operational Impact (Complete)
- **Affected Area Estimator** - Calculate flooded area in km² or square miles
- **Infrastructure Layer Toggles** - Overlay roads, hospitals, settlements
- **Export Suite** - PDF reports, GeoJSON, KML, CSV formats
- **Shareable Links** - Generate links for team coordination

### Phase 3: Context Features (Ready)
- **Wetland Reference Layer** - Historical wetland ranges
- **Data Quality Metadata** - Geometric accuracy, layover/shadow effects
- **Geospatial Processing** - Local geocoding and map visualization

## Architecture

### Technology Stack
- **Frontend:** React.js + Leaflet.js + Tailwind CSS
- **Backend:** Python FastAPI + Uvicorn
- **Geospatial:** GDAL, Rasterio, Nominatim geocoding
- **Data Source:** ASF Search API, NISAR GCOV Level 2 products

### Directory Structure
```
.
├── index.html              # Main frontend application
├── backend/
│   ├── app_real_api.py     # FastAPI server with real NISAR API integration
│   ├── imagery_handler.py  # SAR backscatter visualization and processing
│   ├── requirements.txt    # Python dependencies
│   ├── .env.example        # Environment configuration template
│   └── app/                # FastAPI route handlers
├── data/
│   └── scenes/             # NISAR scene files (HDF5 format)
├── SYSTEM_ARCHITECTURE.md  # Technical architecture details
└── README.md               # This file
```

### Key API Endpoints

**Base URL:** `http://localhost:8000`

- `GET /api/search?location=<location>&radius=<km>&start_date=<YYYY-MM-DD>&end_date=<YYYY-MM-DD>` - Query NISAR scenes
- `GET /api/imagery/comparison?scene_id=<id>` - Generate before-after visualizations
- `GET /api/health` - Server health check

## NISAR Data Reference

**Mission:** NASA-ISRO Synthetic Aperture Radar

**Product Type:** GCOV (Geocoded Covariance Matrix) - Level 2

**Data Availability:**
- Provisional products available: July 20, 2026+
- Coverage begins: June 17, 2026
- Latency: 36-72 hours for Level 1-3 products

**Why L-band SAR?**
- Better penetration through clouds and vegetation
- Distinctive backscatter signature for standing water
- Reliable detection of surface changes
- All-weather capability (day/night)

## Environment Setup

Create `.env` file in `backend/` directory:
```
ASF_API_BASE_URL=https://api.daac.asf.alaska.edu
NOMINATIM_BASE_URL=https://nominatim.openstreetmap.org
```

## Usage Examples

### Example 1: Houston Flood (Hurricane Storm Surge)
```
Location: Houston, Texas
Coordinates: 29.2241, -94.7623
Search Radius: 70 km
Start Date: 2026-08-22
End Date: 2026-09-05
Expected: 12+ NISAR scenes available
Expected confidence: 90%+
Flooded area: 65+ km²
```

### Example 2: Venice Lagoon (Acqua Alta)
```
Location: Venice, Italy
Coordinates: 45.4408, 12.3155
Search Radius: 50 km
Start Date: 2026-07-21
End Date: 2026-08-15
Expected: Multiple scenes with infrastructure overlap
```

## Confidence Scoring System

Confidence badges indicate data reliability:

- **95-100%** - Excellent (clear change, ideal conditions)
- **80-94%** - Good (clear signals, minor atmospheric effects)
- **60-79%** - Fair (detectable but with caveats)
- **Below 60%** - Poor (validate with independent data)

Factors affecting confidence:
- Scene coherence (temporal correlation)
- Atmospheric effects (ionospheric distortion)
- Geometric layover/shadow presence
- Multi-temporal consistency

## Testing & Validation

Application tested with 10+ historical flood events:

- Houston, Texas (Hurricane storm surge)
- Venice, Italy (Seasonal flooding)
- Bangladesh (Monsoon flooding)
- Australia (Coastal flooding)
- Pakistan (Flash flooding)
- Indonesia (Volcanic flooding)
- USA (River flooding)
- And more...

**All tests verified:**
- Correct NISAR scene retrieval
- Proper geocoding
- Accurate confidence scoring
- Infrastructure overlap detection
- Export functionality

## Troubleshooting

### "No scenes found"
- **Issue:** Search returns no NISAR acquisitions
- **Solutions:**
  - Check date range (data available from June 17, 2026)
  - Verify location coordinates are valid
  - Increase search radius (5-100 km range)
  - Check global coverage maps at NISAR website

### "API connection error"
- **Issue:** Backend cannot connect to ASF or other APIs
- **Solutions:**
  - Ensure backend running: `python app_real_api.py`
  - Check firewall allows localhost:8000
  - Verify internet connection
  - Check .env file in backend/ directory

### Map not displaying
- **Issue:** Leaflet map shows blank/white
- **Solutions:**
  - Clear browser cache (Ctrl+Shift+R or Cmd+Shift+R)
  - Check browser console for errors (F12)
  - Verify Leaflet libraries are loaded
  - Try different browser

### Flood overlay not visible
- **Issue:** Orange flood zones not showing on map
- **Solutions:**
  - Ensure scenes were retrieved (check scene count)
  - Verify search location has detected changes
  - Check map zoom level (zoom out if necessary)
  - Refresh page and retry search

## Performance Notes

- **Initial load:** 2-3 seconds (assets cached)
- **Scene search:** 3-10 seconds (depending on API response)
- **Image comparison generation:** 2-5 seconds
- **Map rendering:** <1 second
- **Export generation:** 1-3 seconds

Optimization tips:
- Reduce search radius for faster queries
- Use shorter date ranges
- Close other browser tabs to free memory

## Production Deployment

### Docker Deployment
```bash
cd backend
docker build -t nisar-app .
docker run -p 8000:8000 nisar-app
```

### Cloud Platforms
- AWS EC2 with Nginx reverse proxy
- Google Cloud Run with CloudBuild
- Azure App Service

See [DEPLOYMENT.md](./DEPLOYMENT.md) for detailed instructions.

## Contributing Guidelines

- Follow PEP 8 for Python code
- Use consistent naming conventions
- Add comments for complex logic
- Test changes before submitting
- Include documentation updates

## License

Open source - NASA Space Apps Challenge submission

## References

- [NISAR Mission](https://nisar.jpl.nasa.gov/)
- [NISAR Documentation](https://nisar-docs.asf.alaska.edu/)
- [ASF Search API](https://docs.asf.daac.asf.alaska.edu/api/)
- [SAR Fundamentals](https://www.usgs.gov/faqs/what-synthetic-aperture-radar)

## Support

For questions or issues:
1. Check Troubleshooting section above
2. Review system logs: `backend/logs/app.log`
3. Check browser console for frontend errors
4. Verify all dependencies installed

---

**Last Updated:** November 2026  
**Status:** Production Ready  
**Version:** 2.0  
**NASA Space Apps Challenge Submission**
