# 📍 How to Input Coordinates - Complete Guide

**Version**: 1.0  
**Last Updated**: November 2, 2026  
**Feature**: Coordinate and Location Name Input

---

## Quick Reference

### Input Format Examples

```
Format: latitude, longitude

Examples:
✅ 45.4408, 12.3155          (Venice, Italy)
✅ 30.9176, 31.2922           (Cairo, Egypt - near Nile Delta)
✅ 22.8456, 88.3676           (Kolkata, Bangladesh - near Ganges Delta)
✅ -15.7942, -47.8822         (Brasília, Brazil)
✅ 40.7128, -74.0060          (New York City, USA)
✅ 51.5074, -0.1278           (London, England)
```

---

## Two Ways to Define Your Analysis Area

### Option 1: Location Name (Easiest)

**What to Enter**: City, region, or landmark name

**Examples**:
- "Venice, Italy"
- "Nile Delta, Egypt"
- "Ganges Delta, Bangladesh"
- "Amazon Basin, Brazil"
- "Po Valley, Italy"

**How It Works**:
1. Type location name in the textbox
2. System searches OpenStreetMap database
3. Circle appears on map at that location
4. Bounds automatically calculated

**Advantages**:
- ✅ Intuitive and easy
- ✅ No need to know exact coordinates
- ✅ Works with city/region names
- ✅ Automatic geocoding

---

### Option 2: Coordinates (Precise)

**What to Enter**: Latitude and Longitude in decimal format

**Format**: `latitude, longitude`

**Example**: `45.4408, 12.3155`

**How It Works**:
1. Type coordinates in textbox
2. System parses the latitude and longitude
3. Validates coordinate ranges
4. Circle appears at exact coordinates
5. Bounds calculated from radius

**Advantages**:
- ✅ Precise location control
- ✅ No ambiguity
- ✅ Exact coordinates ready
- ✅ Useful for specific research sites

---

## Input Guide

### Location: Where is the Textbox?

Find the textbox labeled:

```
📍 Define Analysis Area
├─ LOCATION OR COORDINATES  ← THIS IS THE INPUT FIELD
│  ├─ Placeholder text: "Location: Po Valley, Italy OR Coordinates: 45.0, 12.5"
│  └─ Helper text: "📍 Enter location name OR coordinates (latitude, longitude)"
└─ SEARCH RADIUS (km)
```

### Textbox Placeholder Shows Examples

The textbox displays a helpful placeholder:

```
"Location: Po Valley, Italy OR Coordinates: 45.0, 12.5"
```

This shows you:
- **Location example**: "Po Valley, Italy"
- **Coordinate example**: "45.0, 12.5"

### Helper Text Below the Textbox

Below the input field, you'll see:

```
📍 Enter location name OR coordinates (latitude, longitude)
```

This reminds you of both input methods.

---

## Coordinate Format Rules

### Valid Formats

All of these will work:

| Format | Example | Status |
|--------|---------|--------|
| Latitude, Longitude | `45.4408, 12.3155` | ✅ Works |
| With spaces | `45.4408 , 12.3155` | ✅ Works |
| With extra spaces | `45.4408  ,  12.3155` | ✅ Works |
| Negative (South/West) | `-15.7942, -47.8822` | ✅ Works |
| Mixed signs | `22.8456, 88.3676` | ✅ Works |

### Invalid Formats

These will NOT work:

| Format | Example | Why It Fails |
|--------|---------|--------------|
| Wrong order | `12.3155, 45.4408` | Coordinates reversed |
| Missing comma | `45.4408 12.3155` | No comma separator |
| Wrong symbols | `45.4408; 12.3155` | Semicolon instead of comma |
| Text mixed in | `45.4408, Venice, 12.3155` | Extra text |
| Single number | `45.4408` | Missing longitude |

### Coordinate Ranges

**Latitude**: -90° to 90°
- Negative = South of equator
- Positive = North of equator

**Longitude**: -180° to 180°
- Negative = West of prime meridian
- Positive = East of prime meridian

**Examples**:
- North: Positive latitude (0 to 90)
- South: Negative latitude (-90 to 0)
- East: Positive longitude (0 to 180)
- West: Negative longitude (-180 to 0)

---

## Step-by-Step Examples

### Example 1: Using Location Name

**Goal**: Search for Venice, Italy

**Steps**:
1. Find the "LOCATION OR COORDINATES" textbox
2. Clear current text
3. Type: `Venice, Italy`
4. Wait 500ms for debounce
5. Watch the map update
6. Circle appears at Venice
7. Bounds display: "12.23°E, 45.35°N - 12.41°E, 45.53°N"

**Result**: ✅ Success

---

### Example 2: Using Coordinates

**Goal**: Search for Cairo, Egypt (near Nile Delta)

**Steps**:
1. Find the "LOCATION OR COORDINATES" textbox
2. Clear current text
3. Type: `30.9176, 31.2922`
4. Wait 500ms for debounce
5. Map centers on Cairo
6. Circle appears at coordinates
7. Bounds automatically calculated

**Result**: ✅ Success

---

### Example 3: Adjusting Search Area

**Goal**: Expand search area to 50 km

**Steps**:
1. Enter location: `45.4408, 12.3155` (Venice)
2. Circle appears (10 km default radius)
3. Locate "SEARCH RADIUS (km)" slider
4. Change value from 10 to 50
5. Circle expands to 50 km radius
6. Bounds recalculate automatically

**Result**: ✅ Success - Circle now covers 50 km area

---

## Common Locations with Coordinates

### Flood-Prone Deltas & Basins

| Location | Coordinates | Type |
|----------|-------------|------|
| **Po Valley, Italy** | 45.0°N, 12.5°E | River valley |
| **Nile Delta, Egypt** | 30.92°N, 31.29°E | River delta |
| **Ganges Delta, Bangladesh** | 22.85°N, 88.37°E | River delta |
| **Mekong Delta, Vietnam** | 10.33°N, 106.42°E | River delta |
| **Rhine River, Netherlands** | 51.90°N, 5.12°E | River area |
| **Amazon Basin, Brazil** | -3.00°S, -60.00°W | Basin area |
| **Venice Lagoon, Italy** | 45.44°N, 12.32°E | Lagoon |
| **New Orleans, USA** | 29.95°N, -90.07°W | Delta city |
| **Bangkok, Thailand** | 13.73°N, 100.50°E | Chao Phraya Delta |
| **Jakarta, Indonesia** | -6.21°S, 106.85°E | Jakarta Bay |

---

## Workflow: From Input to Analysis

```
1. ENTER LOCATION/COORDINATES
   ↓
   Textbox: "45.4408, 12.3155"
   Helper: "📍 Enter location name OR coordinates..."
   
2. SYSTEM PROCESSES INPUT
   ↓
   500ms debounce timer
   Parse coordinates OR
   Geocode location name
   
3. MAP UPDATES
   ↓
   Center on location
   Draw circle (default 10 km)
   Show center marker
   
4. BOUNDS CALCULATED
   ↓
   Convert radius to degrees
   Calculate geographic bounds
   Display: "12.23°E, 45.35°N - 12.41°E, 45.53°N"
   
5. READY FOR ANALYSIS
   ↓
   Adjust radius slider if needed
   Set date range
   Click "Discover Available Scenes"
   Analysis proceeds with calculated bounds
```

---

## Troubleshooting

### Problem: Circle Doesn't Appear

**Possible Causes**:
- Typo in location name → Try spelling check
- Invalid coordinate format → Use "latitude, longitude"
- Waiting for debounce → Wait 500ms after typing
- Network issue → Check internet connection

**Solutions**:
1. Check spelling of location name
2. Verify coordinate format (e.g., "45.4408, 12.3155")
3. Try a well-known location (e.g., "Venice, Italy")
4. Clear field and re-enter
5. Refresh page (F5)

---

### Problem: Circle in Wrong Location

**Possible Causes**:
- Coordinates reversed → Latitude should be first
- Ambiguous location name → Use more specific name
- Wrong region → Try with country name

**Solutions**:
1. Double-check coordinate order (lat, lon)
2. Use full location name: "Venice, Veneto, Italy"
3. Try exact coordinates if available
4. Click map to manually reposition circle

---

### Problem: "Invalid Coordinates" Error

**What It Means**:
- Latitude is outside -90 to 90°
- Longitude is outside -180 to 180°

**Solutions**:
1. Check latitude range: -90 ≤ lat ≤ 90
2. Check longitude range: -180 ≤ lon ≤ 180
3. Verify you didn't swap latitude and longitude
4. Use online coordinate validator

---

## Pro Tips

### Tip 1: Use Full Location Names
```
❌ Bad:  "Venice"
✅ Good: "Venice, Italy"
✅ Better: "Venice, Veneto, Italy"
```

### Tip 2: Know Your Coordinate Format
```
Format: Latitude (North/South), Longitude (East/West)

Example: 45.4408, 12.3155
         ↑       ↑
       Latitude Longitude
       (North)  (East)
```

### Tip 3: Find Coordinates Online
1. Go to Google Maps
2. Right-click on location
3. Coordinates appear in popup
4. Copy and paste into textbox

### Tip 4: Verify Before Analysis
1. Check that circle appears on correct location
2. Verify bounds make sense
3. Adjust radius if needed
4. Then proceed with scene discovery

### Tip 5: Use Decimal Degrees
```
✅ Recommended: 45.4408 (decimal)
❌ Not supported: 45°26'26" (DMS format)
```

---

## Supported Coordinate Systems

### Decimal Degrees (Supported) ✅

Format: `±DD.DDDD`

Example: `45.4408, 12.3155`

```javascript
// How the system interprets it:
const latitude = 45.4408;    // Degrees decimal
const longitude = 12.3155;   // Degrees decimal
```

### NOT Supported: DMS (Degrees, Minutes, Seconds)

Format: `DD°MM'SS"` (Not supported)

Example: `45°26'26", 12°18'56"` (Will NOT work)

**Workaround**: Convert DMS to decimal first

```
Formula: Decimal = Degrees + (Minutes/60) + (Seconds/3600)

Example:
45°26'26" = 45 + (26/60) + (26/3600) = 45.4408
```

---

## API Integration

When you enter coordinates or location, the bounds are automatically calculated and sent to the backend:

```json
{
  "bounds": {
    "west": 12.23,
    "south": 45.35,
    "east": 12.41,
    "north": 45.53
  },
  "start_date": "2025-01-01T00:00:00Z",
  "end_date": "2025-03-01T00:00:00Z",
  "polarization": "VVVV"
}
```

The backend uses these bounds to search the NISAR satellite archive for scenes covering your analysis area.

---

## Summary

| Aspect | Details |
|--------|---------|
| **Input Field** | "Location or Coordinates" textbox |
| **Location Format** | City, region name (e.g., "Venice, Italy") |
| **Coordinate Format** | Latitude, Longitude in decimals (e.g., "45.4408, 12.3155") |
| **Debounce Time** | 500ms (waits for you to stop typing) |
| **Latitude Range** | -90° to +90° |
| **Longitude Range** | -180° to +180° |
| **Supported Systems** | Decimal degrees only |
| **Case Sensitivity** | No (case-insensitive) |
| **Result** | Circle on map + calculated bounds |

---

## Support

For issues or questions:
1. Check the helper text below the textbox
2. Review this guide's troubleshooting section
3. Try a known location (e.g., "Po Valley, Italy")
4. Verify coordinate format
5. Refresh the page

---

**Ready to search? Start by entering a location or coordinates!** 🗺️
