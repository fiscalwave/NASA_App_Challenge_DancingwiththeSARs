# VAMIKA

**Real NISAR-Based Flood & Wetland Change Mapping**

**NASA International Space Apps Challenge | Disaster Response Technology**

An open-source interactive web application for flood and wetland surface-change detection using real NASA-ISRO SAR (NISAR) satellite data — zero mock/synthetic/fabricated data anywhere in the pipeline. Every number, image, and polygon shown in the UI is derived from an actual downloaded NISAR L2 GCOV granule processed on demand.

## Try it now

| Deployment | URL | Notes |
|---|---|---|
| **GCP Compute Engine (primary)** | **http://34.31.239.90:8000** | Real persistent disk, fast NASA Earthdata throughput, pre-seeded instant demo locations. Share this link with anyone — no login required. |
| Render (fallback) | https://nisar-flood-wetland-mapping.onrender.com | Same code, auto-deploys from this repo. Free tier: no persistent disk, may take 30-60s to wake from idle. |

## Challenge Problem Statement

Earth's surface is an endless dance of natural processes and human activities, but these changes are often difficult to visualize, understand, and communicate. From wetland loss to forest wildfires, earthquakes, farming activities, glacier movement, and more, Earth is in a constant waltz of surface changes. Your challenge is to build an interactive application that uses radar remote sensing data from the NASA-ISRO Synthetic Aperture Radar (NISAR) mission to track and visualize one or more types of surface change at locations around the world.

## Overview

VAMIKA lets anyone — emergency managers, researchers, educators, or the public — search any location worldwide, pull the real NISAR acquisitions NASA's CMR catalog actually has for that area/date range, and run a genuine before/after L-band SAR backscatter change-detection analysis: no simulated imagery, no placeholder statistics, no synthetic scenes ever substituted when real data can't be found.

**Core capability:** Real before-and-after SAR backscatter change detection, classifying two distinct, physically-documented flood signatures (see the [NASA/JPL "Floods" StoryMap](https://storymaps.arcgis.com/stories/c00d7691b8004b20a14f28df710d05fd)):
- **Open water** (backscatter decrease — specular/surface scattering)
- **Flooded vegetation** (backscatter increase — double-bounce scattering beneath canopy, often dominant in forested floodplains/wetlands and invisible to optical satellites)

## Quick Start

### Prerequisites
- Python 3.11+
- Real [NASA Earthdata](https://urs.earthdata.nasa.gov/) account (free) — required; there is no mock-data mode
- Modern web browser

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

3. **Configure real Earthdata credentials** — create `backend/.env` (see `backend/.env.example`):
   ```
   ASF_USERNAME=your_earthdata_username
   ASF_PASSWORD=your_earthdata_password
   ```

4. **Start the application**
   ```bash
   python app_real_api.py
   ```
   This single command serves both the API and the frontend together. Open your browser to `http://localhost:8000`

### Using the Application

1. **Click a Featured Location** for an instant pre-cached real result, or **search any location** — enter a city name or `lat, lon` coordinates
2. **Set search radius** (up to ~150 km, limited by real-data processing memory) and **date range**
3. **Choose a polarization channel** (HH recommended for flood detection; all 6 real NISAR GCOV channels supported)
4. Click **Discover Available Scenes** — this queries real NASA CMR directly; if more than one compatible before/after pair exists, a pair selector lets you pick which real dates to compare
5. The app downloads the real granules, runs real backscatter change detection, and displays:
   - A real before/after swipe comparison
   - A real flood-extent map overlay (open water + flooded vegetation, color-coded)
   - A transparent, rule-based confidence score (not a black-box probability)
   - Real OpenStreetMap-derived infrastructure impact (hospitals/settlements/roads intersecting the detected flood polygon), computed in the background so you aren't blocked waiting on it
6. **Export** real findings as PDF, GeoJSON, KML, or CSV

## Features

- **Real NASA CMR discovery** across NISAR's three data-maturity tiers (Validated/Provisional/Beta), honestly reporting zero results rather than ever substituting mock data
- **Real before/after SAR swipe comparison**, rendered server-side from actual downloaded GCOV HDF5 pixel data
- **Dual flood-signature detection**: open water (radar-dark) and flooded vegetation (radar-bright, double-bounce) — see [SYSTEM_ARCHITECTURE.md](./SYSTEM_ARCHITECTURE.md) for the science
- **Real infrastructure impact** (hospitals, settlements, roads, power plants) via live OpenStreetMap/Overpass spatial intersection, with an explainable, rule-based priority score
- **Featured Locations**: a curated set of real, globally diverse flood/wetland-significant places, pre-computed for instant loading (see `backend/scripts/preseed_featured_locations.py`)
- **Polarization selector** and **multi-date pair selector** when NASA CMR finds more than one compatible real acquisition pair
- **Honest confidence scoring** — a transparent, rule-based score derived from real statistics (acquisition geometry match, noise level, observation age, candidate-pixel count), explicitly not a fabricated probability
- **Export suite** — PDF, GeoJSON, KML, CSV, all built from real detected geometry (no circle-approximation placeholders)

## Architecture

### Technology Stack
- **Frontend:** Single-page vanilla JS + Leaflet.js (`index.html`) — no build step, no framework
- **Backend:** Python FastAPI + Uvicorn
- **Geospatial/SAR processing:** h5py, rasterio, pyproj, shapely, scipy, numpy
- **Data Source:** NASA CMR + ASF Earthdata Cloud, real NISAR L2 GCOV products only

### Directory Structure
```
.
├── index.html                       # Main frontend application (single file, no build step)
├── backend/
│   ├── app_real_api.py              # FastAPI server (live entrypoint)
│   ├── imagery_handler.py           # Real SAR backscatter -> PNG rendering
│   ├── requirements.txt             # Python dependencies
│   ├── .env.example                 # Environment configuration template
│   ├── scripts/
│   │   └── preseed_featured_locations.py  # Pre-computes the Featured Locations cache
│   ├── data/
│   │   └── featured_locations.json  # Curated real locations (version-controlled)
│   └── app/
│       ├── ingestion/                # NASA CMR discovery + download manager
│       ├── processing/               # GCOV reading, change detection, classification
│       ├── analysis/                 # Infrastructure impact + priority scoring
│       └── exports/                  # GeoTIFF/GeoJSON exporters
├── SYSTEM_ARCHITECTURE.md           # Technical architecture details
├── DEPLOYMENT.md                     # Deployment instructions (GCP VM, Render)
└── README.md                         # This file
```

### Key API Endpoints

**Base URL:** `http://34.31.239.90:8000` (or `http://localhost:8000` for local development)

- `POST /api/v2/discover` — Real NASA CMR discovery for an area/date range
- `GET /api/v2/featured` — List curated Featured Locations and their pre-seeded readiness
- `POST /api/v2/download/start` + `GET /api/v2/download/status/{granule_id}` — Real, resumable granule download
- `POST /api/v2/analyze` + `GET /api/v2/analyze/status/{id}` — Real change-detection analysis (background job + polling)
- `POST /api/v2/analyze/{id}/impact` + `GET /api/v2/analyze/{id}/impact/status` — Real OpenStreetMap infrastructure impact
- `GET /api/v2/analyze/{id}/visual/{before|after}` — Real rendered SAR backscatter PNG
- `GET /api/v2/analyze/{id}/geojson/{layer}` — Real detected flood polygon(s)
- See [API_REFERENCE.md](./API_REFERENCE.md) for the complete list
- See [API_REFERENCE.md](./API_REFERENCE.md) for the complete list

## NISAR Data Reference

**Mission:** NASA-ISRO Synthetic Aperture Radar (launched July 30, 2025; Science Operations Phase began January 2026)

**Product Type:** L2 GCOV (Geocoded Covariance Matrix), queried across all three real data-maturity tiers (Validated/Provisional/Beta) directly via NASA CMR

**Why L-band SAR?**
- Penetrates cloud cover and operates day or night (all-weather capability)
- Longer wavelength penetrates vegetation canopy further than C-band sensors, enabling detection of water *beneath* forest/vegetation (invisible to optical satellites)
- Produces two distinct, physically real flood signatures: open water (backscatter decrease) and flooded vegetation (backscatter increase, double-bounce)

## Environment Setup

Create `backend/.env` (see `backend/.env.example`):
```
ASF_USERNAME=your_earthdata_username
ASF_PASSWORD=your_earthdata_password
```

Real [NASA Earthdata](https://urs.earthdata.nasa.gov/) credentials (free account) are required — there is no mock-data fallback mode.

## Confidence Scoring

The confidence score shown for each analysis is a **transparent, rule-based score derived entirely from real Phase 5 change-detection statistics** — not a black-box ML probability and not derived from any atmospheric/layover model (which this project does not compute). It reflects four real, explainable checks:
- Acquisition geometry match (same track/frame/pass direction between before/after)
- Backscatter noise level (signal std. dev.)
- Observation age (how recently the "after" granule was acquired)
- Candidate change-pixel count

Each check's pass/fail state and underlying real value are shown directly in the UI — see `backend/app/analysis/priority.py` (`compute_detection_confidence`).

## Known Limitations (Stated Honestly)

- **Population exposure and monetary damage estimates are not provided** — no gridded population (e.g. WorldPop, GPW) or damage dataset is currently integrated; the UI reports these as "Not available" rather than inventing a figure.
- **Infrastructure impact (hospitals/settlements/roads) depends on the public OpenStreetMap Overpass API**, which has no uptime guarantee and is occasionally slow/unavailable; when this happens, the UI reports "Unavailable" and the rest of the analysis (flood detection, imagery, confidence) still completes normally.
- **A real AOI search radius is capped (~150 km on the current GCP VM)** to stay within safe in-memory processing limits for real multi-gigabyte GCOV files.
- **Not every real NISAR granule carries every polarization channel** — the polarization selector lets you try an alternate channel if your first choice isn't available for a given pair.

## Troubleshooting

### "No compatible before/after pairs found"
- **Issue:** Real acquisitions exist individually but none share the same track/frame/pass direction within the requested windows
- **Solutions:**
  - Widen the date range
  - Try a different location — NISAR's revisit cadence (6-12 days) means not every area has two compatible passes yet this early in the mission
  - Double-check your start/end dates aren't reversed

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

- **Featured Locations (pre-seeded):** results render within seconds — real analysis was already computed ahead of time and is replayed from cache, with no new download
- **Novel/live searches:** real multi-gigabyte NASA granule downloads and real backscatter processing take genuine time (download time depends on file size and network; analysis typically completes in seconds to low minutes once downloaded) — this cannot be made instant without fabricating data, which this project does not do
- Before/after granules download in parallel, not sequentially
- Infrastructure impact (OpenStreetMap) computes in the background after flood-detection results are already shown, so you are never blocked waiting on it

## Production Deployment

See [DEPLOYMENT.md](./DEPLOYMENT.md) for the full guide, including:
- The current live GCP Compute Engine deployment (primary) and how to share/manage it
- The Render.com fallback deployment (auto-deploys on every push)
- Local development setup

## Contributing Guidelines

- Follow PEP 8 for Python code
- Never introduce mock/synthetic/fabricated data as a fallback for a missing real result — report the real absence honestly instead
- Add comments for complex or non-obvious logic
- Test changes against real data before submitting
- Include documentation updates

## License

MIT License — see [LICENSE](./LICENSE). This project uses publicly available NASA NISAR data (via NASA Earthdata/ASF) and OpenStreetMap data (via Overpass); it is an independent project and is not endorsed by or affiliated with NASA, ISRO, or the OpenStreetMap Foundation.

## References

- [NISAR Mission](https://nisar.jpl.nasa.gov/)
- [NISAR Documentation](https://nisar-docs.asf.alaska.edu/)
- [ASF Search API](https://docs.asf.daac.asf.alaska.edu/api/)
- [NASA/JPL "Floods" StoryMap](https://storymaps.arcgis.com/stories/c00d7691b8004b20a14f28df710d05fd) — the scientific basis for this project's dual open-water/flooded-vegetation detection approach
- [SAR Fundamentals](https://www.usgs.gov/faqs/what-synthetic-aperture-radar)

## Support

For questions or issues:
1. Check the Troubleshooting section above and [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
2. Review system logs: `backend/logs/app.log`, or `sudo journalctl -u vamika.service -f` on the GCP VM
3. Check browser console for frontend errors
4. Verify all dependencies installed and real Earthdata credentials are configured

---

**Status:** Live, real-data-only production deployment  
**Version:** 2.0  
**NASA Space Apps Challenge Submission**
