# Quick Start Guide - NISAR Flood & Wetland Monitor (Refactored)

## TL;DR - Get Running in 5 Minutes

### Terminal 1: Backend

```bash
cd backend
# Windows:
run.bat
# Linux/Mac:
./run.sh
```

Server starts at: http://localhost:8000

### Terminal 2: Frontend

```bash
cd frontend
npm install
npm run dev
```

App opens at: http://localhost:5173

---

## Detailed Setup

### Prerequisites Check

```bash
# Check Python
python --version  # Need 3.9+

# Check Node
node --version    # Need 18+
npm --version
```

### Step 1: Backend Setup (Windows)

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv .venv

# Activate it
.venv\Scripts\activate.bat

# Install dependencies
pip install -r requirements.txt

# Configure (optional, uses MOCK mode by default)
copy .env.example .env
# Edit .env if needed

# Start server
run.bat
```

### Step 1: Backend Setup (Linux/Mac)

```bash
# Navigate to backend
cd backend

# Create virtual environment
python -m venv .venv

# Activate it
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure (optional)
cp .env.example .env
# Edit .env if needed

# Start server
chmod +x run.sh
./run.sh
```

### Step 2: Frontend Setup

```bash
# In new terminal, navigate to frontend
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

### Step 3: Open Application

Open browser: **http://localhost:5173**

---

## First Workflow

The app comes with **MOCK data** (no credentials needed):

### 1. **View the map**
   - Interactive Leaflet map on the right
   - Bounds displayed as blue rectangle
   - Adjust by dragging map or editing coordinates

### 2. **Set timeline**
   - Default: Oct 1 - Nov 1, 2024
   - Change dates as desired

### 3. **Search scenes**
   - Click "Search Available Scenes"
   - In MOCK mode: Returns 2 simulated NISAR scenes
   - In LOCAL mode: Lists .h5 files from `data/` directory
   - In API mode: Queries ASF (requires credentials)

### 4. **Select scenes**
   - Click first scene → becomes "Before" scene (green)
   - Click second scene → becomes "After" scene (red)

### 5. **Analyze**
   - Click "Analyze Change"
   - Backend processes scenes
   - Results show in Results panel

### 6. **View statistics**
   - Possible new inundation area (km²)
   - Persistent water area (km²)

---

## Troubleshooting

### Backend Issues

**Port already in use**
```bash
# Find process on port 8000
# Windows:
netstat -ano | findstr :8000
taskkill /PID <PID> /F

# Linux/Mac:
lsof -i :8000
kill -9 <PID>

# Then restart
```

**Module import errors**
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

**GDAL/rasterio installation fails**
```bash
# May need system libraries
# Windows: Use conda instead
conda create -n nisar python=3.11
conda activate nisar
conda install -c conda-forge gdal rasterio

# Linux: Install dev packages
sudo apt-get install libgdal-dev python3-dev

# Mac: Use Homebrew
brew install gdal
```

### Frontend Issues

**Port already in use**
```bash
# Kill process
# Windows:
netstat -ano | findstr :5173
taskkill /PID <PID> /F

# Linux/Mac:
lsof -i :5173
kill -9 <PID>
```

**npm install fails**
```bash
# Clear cache
npm cache clean --force
rm -rf node_modules package-lock.json
npm install
```

### API Connection Issues

**"Failed to fetch" errors**
- Ensure backend is running (`http://localhost:8000/health`)
- Check proxy settings in `frontend/vite.config.js`
- Check CORS settings in `backend/app/main.py`

---

## Data Modes

### MOCK (Default - Recommended for first run)

```env
DATA_MODE=MOCK
```

✅ No credentials needed
✅ Returns simulated scenes
✅ Tests full workflow
⚠️ Data not real

### LOCAL

```env
DATA_MODE=LOCAL
DATA_DIR=./data
```

✅ Works with downloaded GCOV files
⚠️ Requires .h5 files in `DATA_DIR`

**To add data:**
1. Place NISAR GCOV .h5 files in `backend/data/` directory
2. Restart backend
3. Scenes will appear in search results

### API

```env
DATA_MODE=API
ASF_USERNAME=your_username
ASF_PASSWORD=your_password
```

✅ Access real NISAR data
⚠️ Requires Earthdata login
⚠️ Downloads can be slow (files are large)

**Get credentials:**
1. Register at https://earthdata.nasa.gov
2. Add to `.env` file
3. Restart backend

---

## API Endpoints (for testing)

### Health Check
```bash
curl http://localhost:8000/health
```

### Search Scenes (MOCK)
```bash
curl -X POST http://localhost:8000/api/search/scenes \
  -H "Content-Type: application/json" \
  -d '{
    "bounds": {"west": 41.30, "south": 12.70, "east": 41.35, "north": 12.75},
    "start_date": "2024-10-01",
    "end_date": "2024-11-01"
  }'
```

### API Docs
Open in browser: **http://localhost:8000/docs**

Swagger UI for interactive testing

---

## Next Steps

After getting the basic app running:

1. **Explore the code**
   - Read `backend/ARCHITECTURE.md` for technical details
   - Review module docstrings

2. **Test with real data**
   - Switch to LOCAL or API mode
   - Download sample NISAR GCOV files
   - Run analysis on real data

3. **Contribute**
   - Review REFACTOR_PLAN.md for Phase 2 tasks
   - Set up development environment
   - Run tests

4. **Customize**
   - Adjust flood detection thresholds
   - Modify UI colors/layout
   - Add new features

---

## Useful Commands

```bash
# Backend tests
cd backend
pytest tests/
pytest tests/ -v  # Verbose
pytest tests/ --cov=app  # With coverage

# Frontend linting
cd frontend
npm run lint

# View API documentation
# Open http://localhost:8000/docs in browser

# Check backend logs
# Linux/Mac: tail -f logs/app.log
# Windows: type logs\app.log

# Monitor processes
# Windows: tasklist
# Linux/Mac: ps aux | grep python
```

---

## Common Questions

**Q: Can I use this without Earthdata login?**
A: Yes! Start in MOCK mode (default). No credentials needed.

**Q: Where's the original Streamlit app?**
A: It's still in `app.py` at root for reference. New code is in `backend/` and `frontend/`.

**Q: Can I process large areas?**
A: Yes, but there's a limit of 15 million pixels per scene to avoid memory issues.

**Q: How do I add more features?**
A: See REFACTOR_PLAN.md for Phase 2/3 roadmap and contribution guidelines.

**Q: Is this production-ready?**
A: Phase 1 is feature-complete for basic flood detection. See ARCHITECTURE.md for deployment guide.

---

## Getting Help

- **Documentation**: `backend/ARCHITECTURE.md`
- **API Docs**: http://localhost:8000/docs
- **Code Comments**: Each module has detailed docstrings
- **Issues**: Check GitHub Issues or create new one
- **Questions**: GitHub Discussions

---

Happy mapping! 🛰️
