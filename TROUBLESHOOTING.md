# Troubleshooting Guide

Common issues and solutions for VAMIKA (the NISAR-based Flood & Wetland Mapping Application).

## Backend Issues

### Issue: Backend won't start

**Error:** `python app_real_api.py` fails or crashes immediately

**Solutions:**

1. **Check Python version:**
   ```bash
   python --version
   # Should be 3.8 or higher
   ```

2. **Verify dependencies installed:**
   ```bash
   pip list | grep -E "fastapi|uvicorn|requests|pillow"
   ```

3. **Reinstall requirements:**
   ```bash
   cd backend
   pip install -r requirements.txt --force-reinstall
   ```

4. **Check for port conflicts:**
   ```bash
   # Windows
   netstat -ano | findstr :8000
   
   # Linux/macOS
   lsof -i :8000
   ```
   If port 8000 is in use, kill the process or change port in `app_real_api.py`

5. **Check logs:**
   ```bash
   tail -f backend/logs/app.log
   ```

### Issue: API connection errors

**Error:** `Cannot connect to ASF API` or `Geocoding failed`

**Solutions:**

1. **Check internet connectivity:**
   ```bash
   # Test ASF API
   curl https://api.daac.asf.alaska.edu/baseline
   
   # Test Nominatim
   curl "https://nominatim.openstreetmap.org/search?q=London&format=json"
   ```

2. **Verify .env file:**
   ```bash
   cat backend/.env
   # Should show ASF and Nominatim URLs
   ```

3. **Check firewall:**
   - Ensure outbound HTTPS (443) is allowed
   - Check corporate proxy settings if behind proxy

4. **Verify API availability:**
   - ASF status: https://status.asf.daac.asf.alaska.edu/
   - Nominatim status: https://nominatim.org/

5. **Check DNS:**
   ```bash
   nslookup api.daac.asf.alaska.edu
   nslookup nominatim.openstreetmap.org
   ```

### Issue: Memory errors or slowness

**Error:** `MemoryError` or slow responses

**Solutions:**

1. **Monitor memory usage:**
   ```bash
   # Linux/macOS
   top -p $(pgrep -f app_real_api.py)
   
   # Windows
   tasklist | findstr python
   taskmgr  # View process details
   ```

2. **Reduce concurrent requests:**
   - Modify `app_real_api.py` to reduce worker count
   - Use external load balancer to queue requests

3. **Optimize imagery processing:**
   - Reduce image resolution
   - Use smaller search radius
   - Enable caching

4. **Increase system resources:**
   - Add more RAM
   - Use SSD instead of HDD
   - Upgrade to faster CPU

### Issue: Scene files not loading

**Error:** `HDF5 file not found` or `Cannot read scene data`

**Solutions:**

1. **Check file location:**
   ```bash
   ls -la data/scenes/
   # Files should be *.h5
   ```

2. **Verify file permissions:**
   ```bash
   # Linux/macOS
   chmod 644 data/scenes/*.h5
   ```

3. **Check file size:**
   ```bash
   ls -lh data/scenes/
   # Should be 200+ MB each
   ```

4. **Validate HDF5 file:**
   ```bash
   # Install h5py if needed
   pip install h5py
   
   python -c "import h5py; f = h5py.File('data/scenes/file.h5', 'r'); print(list(f.keys()))"
   ```

---

## Frontend Issues

### Issue: Page won't load

**Error:** Blank white page or "Cannot GET /"

**Solutions:**

1. **Check server is running:**
   ```bash
   curl http://localhost:3000
   # Should return HTML content
   ```

2. **Verify correct URL:**
   - Should be `http://localhost:3000` (not :8000)
   - Check browser address bar

3. **Clear browser cache:**
   - Chrome: `Ctrl+Shift+R` (or `Cmd+Shift+R` on Mac)
   - Firefox: `Ctrl+Shift+R`
   - Safari: `Cmd+Option+E`

4. **Check browser console:**
   - Press `F12` to open DevTools
   - Go to Console tab
   - Look for error messages

5. **Try different browser:**
   - If error persists, may be backend issue

### Issue: Map not displaying

**Error:** Grey/white area where map should be

**Solutions:**

1. **Check Leaflet library loads:**
   ```
   Press F12 → Console tab
   Type: L
   Should return: ƒ newLatLng(lat, lng) {...}
   ```

2. **Verify Mapbox/Leaflet keys:**
   - Check if API keys are set correctly
   - Verify token hasn't expired

3. **Check browser console for errors:**
   ```
   F12 → Console tab
   Look for red error messages
   ```

4. **Enable JavaScript:**
   - Some browsers disable it by default
   - Settings → Privacy/Security

5. **Try without Leaflet plugins:**
   - Temporarily disable overlays
   - Check if base map displays

### Issue: Flood overlay not showing

**Error:** Map displays but no orange flood zones

**Solutions:**

1. **Verify scenes were found:**
   - Check "Scenes Found" counter
   - If 0, adjust search parameters

2. **Check scene data loaded:**
   - Press F12 → Network tab
   - Search for scenes
   - Look for `/api/search` response
   - Expand response to verify scene data

3. **Inspect map layers:**
   - Press F12 → Console tab
   - Type: `map.eachLayer(l => console.log(l))`
   - Should show multiple layers including flood overlay

4. **Adjust map zoom:**
   - Zoom in/out to see if overlay is at different scale
   - Overlay circles drawn at specific radius

5. **Check coordinates:**
   - Verify location was geocoded correctly
   - Check console for geocoding results

### Issue: Search hangs or timeouts

**Error:** Search button stuck spinning or times out after 30s

**Solutions:**

1. **Check backend is running:**
   ```bash
   curl http://localhost:8000/api/health
   # Should return JSON response
   ```

2. **Try different search:**
   - Reduce search radius
   - Use shorter date range
   - Try major city (e.g., "Houston")

3. **Check network tab:**
   - Press F12 → Network tab
   - Perform search
   - Look for `/api/search` request
   - Right-click → "Copy as cURL"
   - Run in terminal to test directly

4. **Check browser logs:**
   - F12 → Console tab
   - Look for timeout or network errors

5. **Increase timeout:**
   - In `index.html` search: `timeout: 30000`
   - Change to `60000` for longer timeout

### Issue: Before-after swipe not working

**Error:** Slider frozen or images not loading

**Solutions:**

1. **Check images generated:**
   - F12 → Network tab
   - Look for `/api/imagery/comparison` request
   - Verify it returns 200 status

2. **Check image data:**
   - Response should contain base64 image data
   - If empty, backend couldn't generate images

3. **Try different location:**
   - Some locations may not have sufficient data
   - Try Houston or Venice (tested locations)

4. **Refresh page:**
   - Clear cache and reload
   - May have cached incomplete data

5. **Check backend logs:**
   - `tail -f backend/logs/app.log`
   - Look for errors in imagery generation

---

## API Issues

### Issue: API returns 404 Not Found

**Error:** `GET /api/search` returns 404

**Solutions:**

1. **Check endpoint URL:**
   ```bash
   curl http://localhost:8000/api/search?location=Houston&radius=50
   # Note: location must be URL-encoded
   ```

2. **Verify backend running:**
   ```bash
   curl http://localhost:8000/api/health
   ```

3. **Check URL encoding:**
   ```bash
   # Spaces should be %20 or +
   curl "http://localhost:8000/api/search?location=Houston,Texas&radius=50"
   ```

4. **Verify API routes loaded:**
   - Check `backend/app_real_api.py`
   - Verify routes are imported
   - Restart backend

### Issue: API returns 400 Bad Request

**Error:** `GET /api/search?invalid_param=value` returns 400

**Solutions:**

1. **Check parameter names:**
   ```bash
   # Correct:
   curl "http://localhost:8000/api/search?location=Houston&radius=50&start_date=2026-08-22&end_date=2026-09-05"
   
   # Wrong:
   curl "http://localhost:8000/api/search?loc=Houston"  # 'loc' invalid
   ```

2. **Validate parameter values:**
   - Dates must be YYYY-MM-DD
   - Radius must be 5-100
   - Location must not be empty

3. **Check date format:**
   ```bash
   # Correct: 2026-08-22
   # Wrong: 08-22-2026 or 2026/08/22
   ```

4. **Use browser test:**
   - F12 → Console tab
   - Test with JavaScript fetch
   - Verify parameters match API spec

### Issue: API returns 500 Internal Server Error

**Error:** `GET /api/search` returns 500

**Solutions:**

1. **Check backend logs:**
   ```bash
   tail -100 backend/logs/app.log
   # Look for stack trace
   ```

2. **Verify dependencies:**
   ```bash
   python -c "import fastapi; import numpy; import PIL"
   # Should not error
   ```

3. **Check external APIs:**
   ```bash
   curl https://api.daac.asf.alaska.edu/baseline
   curl "https://nominatim.openstreetmap.org/search?q=Houston&format=json"
   # Both should respond
   ```

4. **Test with simple request:**
   ```bash
   curl http://localhost:8000/api/health
   # If this works, issue is with specific endpoint
   ```

5. **Restart backend:**
   ```bash
   # Stop current process (Ctrl+C)
   # Restart: python app_real_api.py
   ```

---

## Data Issues

### Issue: "No scenes found" for valid location/date

**Error:** Search returns 0 scenes

**Solutions:**

1. **Check date range:**
   - NISAR data available from June 17, 2026
   - Provisional products from July 20, 2026
   - Check if dates are before this

2. **Verify location:**
   - Use major city names
   - Try coordinates instead
   - Avoid very small locations

3. **Increase search radius:**
   - Try 50-70 km instead of 5 km
   - Larger area more likely to have coverage

4. **Check ASF coverage:**
   - https://nisar-docs.asf.alaska.edu/availability-overview/
   - Verify location is in acquisition plan

5. **Different date range:**
   - Try dates 30-90 days apart
   - Recent dates more likely to have data

### Issue: Confidence score seems wrong

**Error:** Scene marked as "Poor confidence" but looks good

**Solutions:**

1. **Understand confidence factors:**
   - Coherence (40%): Temporal correlation
   - Atmospheric (35%): Ionospheric effects
   - Geometric (25%): Layover/shadow effects

2. **Check scene metadata:**
   - Hover over scene in list
   - View individual factors
   - May be valid reasons for low score

3. **Validate with ground truth:**
   - Compare with weather data
   - Check satellite overpass timing
   - Verify scene time

4. **Report low confidence:**
   - Document the case
   - Help improve scoring algorithm

---

## Export Issues

### Issue: PDF export not generating

**Error:** PDF download fails or creates blank file

**Solutions:**

1. **Check scene data loaded:**
   - PDF requires scene/analysis data
   - Must perform search first

2. **Check file permissions:**
   ```bash
   ls -l backend/
   # Should be writable
   ```

3. **Verify PDF library:**
   ```bash
   pip list | grep -i report
   pip install reportlab  # If needed
   ```

4. **Try GeoJSON instead:**
   - Simpler export format
   - More reliable
   - Can open in QGIS

### Issue: Export file too large

**Error:** Export takes very long or creates huge file

**Solutions:**

1. **Reduce search area:**
   - Smaller radius = smaller export
   - Fewer features = smaller file

2. **Use different format:**
   - CSV smaller than GeoJSON
   - GeoJSON smaller than KML

3. **Compress before download:**
   - Files are gzipped by default
   - Should be manageable size

---

## Performance Issues

### Issue: Application very slow

**Error:** UI sluggish, long delays between clicks

**Solutions:**

1. **Check network tab:**
   - F12 → Network tab
   - See which requests are slow
   - Focus on slowest request

2. **Reduce search complexity:**
   - Smaller radius
   - Shorter date range
   - More specific location

3. **Clear browser cache:**
   - Ctrl+Shift+R to hard refresh

4. **Close other tabs:**
   - Reduces browser memory usage
   - Frees up resources

5. **Restart browser:**
   - Clear browser cache
   - Kill background processes

### Issue: High memory usage

**Error:** Browser becomes unresponsive

**Solutions:**

1. **Reduce image resolution:**
   - Backend can generate smaller images
   - Saves memory and bandwidth

2. **Close imagery panel:**
   - Images consume memory
   - Close comparison to free up

3. **Reduce zoom level:**
   - Leaflet uses more memory at high zoom
   - Zoom out if needed

4. **Use different browser:**
   - Chrome uses more memory than Firefox
   - Safari more efficient on Mac

---

## Uncommon Issues

### Issue: Localhost unreachable from other machines

**Error:** Can access from local machine, but not from network

**Solution:**

Backend server only binds to localhost by default. To access from other machines:

1. Edit `backend/app_real_api.py`:
   ```python
   # Change from:
   uvicorn.run(app, host="127.0.0.1", port=8000)
   
   # To:
   uvicorn.run(app, host="0.0.0.0", port=8000)
   ```

2. Restart backend

3. Access from other machine:
   ```
   http://<your-machine-ip>:3000
   ```

### Issue: Voice input not working

**Error:** Microphone button does nothing

**Solutions:**

1. **Check browser support:**
   - Chrome/Edge: Full support
   - Firefox: Requires flag enabled
   - Safari: iOS 14.5+ only
   - Check console for "SpeechRecognition not supported"

2. **Check microphone permissions:**
   - Browser should ask for permission
   - Allow access when prompted
   - Check system audio settings

3. **Test Web Speech API:**
   ```javascript
   // In browser console
   console.log(typeof webkitSpeechRecognition)
   // Should be 'function' if supported
   ```

4. **Use alternative:**
   - Type location manually
   - Web Speech optional feature

---

## Getting Help

If issues persist:

1. **Check documentation:**
   - README.md for quick start
   - API_REFERENCE.md for endpoints
   - DEVELOPMENT.md for debugging

2. **Review logs:**
   ```bash
   # Backend logs
   tail -200 backend/logs/app.log
   
   # Browser console (F12)
   # Network tab for API requests
   ```

3. **Verify environment:**
   ```bash
   python --version  # Should be 3.8+
   pip list          # Check dependencies
   cat backend/.env  # Verify config
   ```

4. **Create test case:**
   - Use known working location (Houston)
   - Use known working date range
   - Isolate the problem

5. **Contact support:**
   - Document the issue
   - Include error messages
   - Attach relevant logs
   - Describe steps to reproduce

---

Last Updated: November 2026
