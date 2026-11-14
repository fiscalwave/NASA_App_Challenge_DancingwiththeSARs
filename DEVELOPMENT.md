# Development Guide

Guide for contributing to VAMIKA (the NISAR-based Flood & Wetland Mapping Application).

## Local Development Setup

### Prerequisites

- Python 3.8+
- Git
- Code editor (VS Code recommended)
- Modern web browser

### Installation

```bash
# Clone repository
git clone <repository-url>
cd NASA_App_Challenge_DancingwiththeSARs

# Setup backend
cd backend
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or
.\venv\Scripts\activate  # Windows

pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Edit .env with your configuration
```

### Starting Development Servers

**Terminal 1 - Backend:**
```bash
cd backend
source venv/bin/activate
python app_real_api.py
```

**Terminal 2 - Frontend:**
```bash
# From project root
python -m http.server 3000
```

Access application at `http://localhost:3000`

---

## Project Structure

```
.
├── index.html                    # Main frontend application
├── backend/
│   ├── app_real_api.py          # FastAPI server entry point
│   ├── imagery_handler.py       # SAR backscatter processing
│   ├── requirements.txt         # Python dependencies
│   ├── .env.example            # Environment template
│   └── app/                     # FastAPI route modules
│       ├── __init__.py
│       ├── routes.py           # API endpoint handlers
│       └── utils.py            # Utility functions
├── data/
│   └── scenes/                 # NISAR HDF5 scene files
├── README.md                   # User documentation
├── API_REFERENCE.md            # API documentation
├── DEPLOYMENT.md               # Deployment guide
├── DEVELOPMENT.md              # This file
└── SYSTEM_ARCHITECTURE.md      # Architecture documentation
```

---

## Code Style Guide

### Python (Backend)

Follow **PEP 8** standard:

```python
# Good
def calculate_backscatter_difference(before_array, after_array, threshold_db=3.0):
    """
    Calculate SAR backscatter difference for change detection.
    
    Args:
        before_array: Pre-event backscatter data
        after_array: Post-event backscatter data
        threshold_db: Change threshold in decibels
        
    Returns:
        Binary change mask with True where change exceeds threshold
    """
    difference = after_array - before_array
    return abs(difference) > threshold_db


# Bad
def calc_bs(b, a, t=3.0):
    d = a - b
    return abs(d) > t
```

### Naming Conventions

- **Functions:** snake_case
- **Classes:** PascalCase
- **Constants:** UPPER_SNAKE_CASE
- **Private methods:** _leading_underscore

### Comments

Only comment complex logic:

```python
# Good - explains why
if backscatter_vv < WATER_THRESHOLD_DB:
    # Standing water has very low backscatter due to specular reflection
    is_water = True

# Bad - redundant
# Check if value is less than threshold
if value < threshold:
    pass
```

### Type Hints

Use type hints for clarity:

```python
from typing import Tuple, List, Optional

def search_scenes(
    location: str,
    radius_km: int,
    start_date: str,
    end_date: str
) -> List[dict]:
    """Search for NISAR scenes."""
    pass

def geocode_location(location: str) -> Optional[Tuple[float, float]]:
    """Convert location name to coordinates."""
    pass
```

---

## JavaScript (Frontend)

Follow **ES6+** conventions:

```javascript
// Good - clear naming and structure
class FloodMapViewer {
    constructor(mapElement, apiBaseUrl) {
        this.map = L.map(mapElement);
        this.apiBaseUrl = apiBaseUrl;
        this.floodOverlay = null;
    }
    
    addFloodZone(latitude, longitude, radiusKm, color) {
        const circle = L.circle([latitude, longitude], {
            radius: radiusKm * 1000,
            color: color,
            fillOpacity: 0.3,
            dashArray: '5, 5'
        });
        circle.addTo(this.map);
        return circle;
    }
}

// Usage
const viewer = new FloodMapViewer('map', 'http://localhost:8000');
```

---

## API Endpoint Development

### Adding a New Endpoint

1. **Define in `backend/app/routes.py`:**

```python
from fastapi import APIRouter, Query
from typing import Optional

router = APIRouter(prefix="/api", tags=["analysis"])

@router.get("/analysis/{location}")
async def analyze_location(
    location: str,
    radius: int = Query(50, ge=5, le=100),
    confidence_threshold: Optional[float] = Query(None, ge=0, le=100)
) -> dict:
    """
    Analyze a location for flood risk.
    
    Parameters:
    - location: Location name or coordinates
    - radius: Search radius in km (5-100)
    - confidence_threshold: Optional confidence filter
    
    Returns:
    - Analysis results with confidence scoring
    """
    # Implementation
    return {"status": "success", "data": {...}}
```

2. **Register in `backend/app_real_api.py`:**

```python
from app.routes import router

app = FastAPI()
app.include_router(router)
```

3. **Test the endpoint:**

```bash
curl "http://localhost:8000/api/analysis/Houston?radius=70&confidence_threshold=85"
```

4. **Update `API_REFERENCE.md`** with endpoint documentation

---

## Frontend Component Development

### Creating a New Component

1. **Add to `index.html`:**

```html
<!-- Flood Analysis Panel -->
<div id="flood-analysis-panel" class="panel">
    <h3>Flood Analysis Results</h3>
    <div id="analysis-results"></div>
</div>
```

2. **Add JavaScript logic:**

```javascript
class FloodAnalysis {
    constructor(panelElementId) {
        this.panel = document.getElementById(panelElementId);
        this.results = null;
    }
    
    async analyze(location, radius, dates) {
        try {
            const response = await fetch(
                `/api/analysis/${location}?radius=${radius}`
            );
            this.results = await response.json();
            this.render();
        } catch (error) {
            console.error('Analysis failed:', error);
            this.showError(error.message);
        }
    }
    
    render() {
        const html = `
            <div class="results">
                <p>Flooded Area: ${this.results.area_km2} km²</p>
                <p>Confidence: ${this.results.confidence}%</p>
            </div>
        `;
        this.panel.innerHTML = html;
    }
    
    showError(message) {
        this.panel.innerHTML = `<p class="error">${message}</p>`;
    }
}

// Initialize
const analysis = new FloodAnalysis('flood-analysis-panel');
```

3. **Add CSS styling:**

```css
#flood-analysis-panel {
    background: #f5f5f5;
    border-radius: 8px;
    padding: 16px;
    margin: 12px 0;
}

#flood-analysis-panel .results {
    font-size: 14px;
    line-height: 1.6;
}

#flood-analysis-panel .error {
    color: #d32f2f;
    font-weight: 500;
}
```

---

## Feature Development Workflow

### 1. Plan the Feature

- Create an issue describing the feature
- Add acceptance criteria
- Estimate complexity
- Link to architecture diagram if needed

### 2. Create Feature Branch

```bash
git checkout -b feature/flood-area-calculator
```

### 3. Implement Feature

- Write code following style guide
- Add comments for complex logic
- Test locally thoroughly
- Commit with clear messages:

```bash
git commit -m "Add flood area estimation feature

- Calculate area from detected flood zones
- Display in metrics panel
- Support km² and square mile units
- Add confidence factors"
```

### 4. Test Feature

```bash
# Manual testing
# 1. Start backend and frontend
# 2. Test feature with multiple scenarios
# 3. Check browser console for errors
# 4. Verify API calls in network tab

# Automated testing (if applicable)
python -m pytest backend/tests/
```

### 5. Update Documentation

- Update README if user-facing
- Update API_REFERENCE.md if new endpoints
- Add code comments if complex
- Update SYSTEM_ARCHITECTURE.md if architecture changes

### 6. Submit Pull Request

```bash
git push origin feature/flood-area-calculator
```

Include in PR:
- Description of changes
- How to test
- Screenshots/videos if UI changes
- Links to related issues

---

## Testing

### Manual Testing Checklist

For any UI change:
- [ ] Functionality works in Chrome
- [ ] Functionality works in Firefox
- [ ] Functionality works in Safari
- [ ] Responsive on mobile (375px width)
- [ ] No console errors
- [ ] No visual glitches

For any API change:
- [ ] Endpoint returns expected data
- [ ] Error handling works
- [ ] All query parameters work
- [ ] Timeout handling works
- [ ] Caching works correctly

### Test Locations (Pre-validated)

Use these for consistent testing:

| Location | Coordinates | Expected Scenes | Notes |
|----------|-------------|-----------------|-------|
| Houston, TX | 29.2241, -94.7623 | 12+ | Hurricane storm surge |
| Venice, Italy | 45.4408, 12.3155 | 8+ | Seasonal flooding |
| Bangladesh | 23.6850, 90.3563 | 10+ | Monsoon flooding |
| Jakarta, Indonesia | -6.2088, 106.8456 | 6+ | Tidal/coastal |

### Writing Tests

```python
# backend/tests/test_imagery_handler.py
import pytest
from imagery_handler import calculate_difference_map

def test_calculate_difference_map():
    """Test backscatter difference calculation."""
    before = [[1.0, 2.0], [3.0, 4.0]]
    after = [[1.5, 2.5], [3.5, 4.5]]
    threshold = 1.0
    
    result = calculate_difference_map(before, after, threshold)
    
    assert result.shape == (2, 2)
    assert result[0, 0] == True  # Meets threshold
    assert all(result.flatten() == [True, True, True, True])

def test_calculate_difference_map_no_change():
    """Test when there's no change."""
    data = [[1.0, 2.0], [3.0, 4.0]]
    
    result = calculate_difference_map(data, data, 1.0)
    
    assert not result.any()  # All False
```

Run tests:
```bash
cd backend
python -m pytest tests/ -v
```

---

## Debugging

### Backend Debugging

```python
# Add debug logging
import logging
logger = logging.getLogger(__name__)

logger.debug(f"Searching for scenes in {location}")
logger.info(f"Found {len(scenes)} scenes")
logger.error(f"API request failed: {str(error)}")
```

View logs:
```bash
tail -f backend/logs/app.log
```

### Frontend Debugging

```javascript
// Use console for debugging
console.log('Scene data:', sceneData);
console.warn('No imagery generated');
console.error('API error:', error);

// Use browser DevTools
// 1. Press F12 to open DevTools
// 2. Go to Console tab for errors/logs
// 3. Go to Network tab to inspect API calls
// 4. Go to Elements tab to inspect HTML
```

### Common Issues & Solutions

**Issue: "No scenes found"**
- Check date range (must be after June 17, 2026)
- Verify location spelling
- Try increasing radius
- Check ASF API availability

**Issue: Imagery not generating**
- Verify HDF5 files exist in `data/scenes/`
- Check file permissions
- Review backend logs for specific errors
- Verify imagery_handler.py imports

**Issue: API timeout**
- Check network connectivity
- Verify ASF/Nominatim APIs are responsive
- Reduce search radius
- Check server logs for slow queries

---

## Performance Optimization

### Backend Optimization

```python
# Use async/await for I/O operations
async def search_scenes(location: str) -> List[dict]:
    # Async API calls instead of blocking
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            return await response.json()

# Cache results
from functools import lru_cache

@lru_cache(maxsize=128)
def geocode_location(location: str) -> Tuple[float, float]:
    # Results cached for repeated requests
    pass

# Use database indexes for frequent queries
# Covered in SYSTEM_ARCHITECTURE.md
```

### Frontend Optimization

```javascript
// Debounce search input
function debounce(func, wait) {
    let timeout;
    return function(...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func(...args), wait);
    };
}

// Lazy load images
const lazyImages = document.querySelectorAll('img[loading="lazy"]');

// Minimize DOM reflows
// Batch DOM updates instead of individual updates
const fragment = document.createDocumentFragment();
items.forEach(item => {
    fragment.appendChild(createItem(item));
});
container.appendChild(fragment);
```

---

## Version Control

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat` - New feature
- `fix` - Bug fix
- `docs` - Documentation
- `style` - Formatting
- `refactor` - Code reorganization
- `perf` - Performance
- `test` - Tests
- `chore` - Dependencies

Examples:
```
feat(search): Add coordinate input support

- Allow latitude/longitude input in addition to location names
- Validate coordinate ranges
- Update API endpoint to handle both formats

Fixes #42
```

```
fix(imagery): Fix backscatter visualization

- Correct colormap scaling for dB values
- Handle missing data pixels
- Improve rendering performance

Closes #38
```

---

## Documentation

### Code Documentation

All functions should have docstrings:

```python
def calculate_confidence_score(
    coherence: float,
    atmospheric_effects: float,
    geometric_distortion: float
) -> float:
    """
    Calculate overall confidence score for analysis.
    
    Combines multiple factors to produce a single confidence metric
    ranging from 0 to 100. Higher scores indicate more reliable results.
    
    Args:
        coherence: Temporal coherence (0-1)
        atmospheric_effects: Atmospheric distortion factor (0-1)
        geometric_distortion: Geometric accuracy factor (0-1)
        
    Returns:
        Confidence score 0-100, rounded to nearest integer
        
    Example:
        >>> score = calculate_confidence_score(0.92, 0.78, 0.88)
        >>> print(score)
        85
        
    Note:
        Weights are: coherence=40%, atmospheric=35%, geometric=25%
    """
    weights = {
        'coherence': 0.40,
        'atmospheric': 0.35,
        'geometric': 0.25
    }
    
    score = (
        coherence * weights['coherence'] +
        atmospheric_effects * weights['atmospheric'] +
        geometric_distortion * weights['geometric']
    ) * 100
    
    return round(score)
```

### README Updates

When adding new features, update:
1. Feature list in main README
2. Usage examples if user-facing
3. Architecture diagram if affects system design
4. API_REFERENCE.md if new endpoints

---

## Release Process

### Version Numbering

Use **Semantic Versioning**: MAJOR.MINOR.PATCH

- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes

### Release Checklist

- [ ] Update VERSION in code/docs
- [ ] Update CHANGELOG
- [ ] Run full test suite
- [ ] Update README
- [ ] Create git tag: `git tag v2.0.0`
- [ ] Push tag: `git push origin v2.0.0`
- [ ] Create GitHub release with notes

---

## Resources

- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Leaflet.js Docs:** https://leafletjs.com/
- **PEP 8 Style Guide:** https://pep8.org/
- **NASA NISAR Docs:** https://nisar-docs.asf.alaska.edu/
- **ASF Search API:** https://docs.asf.daac.asf.alaska.edu/

---

## Getting Help

1. Check existing GitHub issues
2. Review SYSTEM_ARCHITECTURE.md for design questions
3. Check API_REFERENCE.md for endpoint details
4. Review code comments for implementation details
5. Ask in project discussions/issues

---

Last Updated: November 2026
