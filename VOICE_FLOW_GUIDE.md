# 🎤 Step-by-Step Voice Flow Guide

## Overview

The NISAR application now features an **interactive step-by-step voice input system** that guides users through entering search parameters one at a time. This provides a much more intuitive and user-friendly experience compared to trying to say everything in one long sentence.

---

## How It Works

### The 4-Step Voice Flow

When you click the **microphone icon**, the application enters an interactive voice flow:

#### **Step 1: 🎤 Say Your Location**
```
Browser says/shows: "🎤 Listening... Please say your location 
(e.g., 'Venice Italy' or '45.4408, 12.3155')"
```
- You can say a place name (e.g., "Venice Italy", "Bangkok Thailand")
- Or say coordinates (e.g., "45.4408, 12.3155" for lat, long)
- Once you stop speaking, it automatically moves to Step 2

**What happens:**
- Your location is filled in the Location field
- Browser displays what it heard

---

#### **Step 2: 🎤 Say Search Radius**
```
Browser says/shows: "🎤 Listening... Please say the search radius 
in kilometers (e.g., '15' or '20 kilometers')"
```
- You can just say a number (e.g., "15", "20")
- Or say the full phrase (e.g., "15 kilometers", "20 km")
- Radius is limited to 5-100 km for optimal performance

**What happens:**
- Your radius is filled in the Search Radius field
- Browser displays what it heard

---

#### **Step 3: 🎤 Say Start Date**
```
Browser says/shows: "🎤 Listening... Please say the start date 
(e.g., 'January 15 2025' or '2025-01-15')"
```
- You can say it naturally (e.g., "January 15 2025")
- Or use ISO format (e.g., "2025-01-15")
- Or short format (e.g., "Jan 15 2025")
- Month names in English work best

**What happens:**
- Your date is parsed and filled in the Start Date field
- Browser displays what it heard

---

#### **Step 4: 🎤 Say End Date**
```
Browser says/shows: "🎤 Listening... Please say the end date 
(e.g., 'February 15 2025' or '2025-02-15')"
```
- Same format options as Start Date
- Should be after your Start Date for logical date ranges
- No validation prevents invalid ranges, but search results will be empty

**What happens:**
- Your date is parsed and filled in the End Date field
- Display shows: "✅ Search Parameters Set:" with all values
- Application automatically geocodes location
- Search executes automatically

---

## Example Usage

### Scenario 1: Natural Speech

```
User clicks microphone →

Step 1: Browser: "Say your location"
User: "Venice Italy"
✓ Location field filled with "Venice Italy"

Step 2: Browser: "Say the search radius"
User: "Fifteen kilometers"
✓ Radius field filled with "15"

Step 3: Browser: "Say the start date"
User: "January 15 2025"
✓ Start Date filled with "2025-01-15"

Step 4: Browser: "Say the end date"
User: "February 15 2025"
✓ End Date filled with "2025-02-15"
✓ Map updates with Venice location
✓ Search executes automatically
✓ Results appear below map
```

### Scenario 2: Coordinate Input

```
User clicks microphone →

Step 1: Browser: "Say your location"
User: "45.4408, 12.3155"
✓ Location field filled with "45.4408, 12.3155"

Step 2: Browser: "Say the search radius"
User: "20 km"
✓ Radius field filled with "20"

Step 3: Browser: "Say the start date"
User: "2025-01-01"
✓ Start Date filled with "2025-01-01"

Step 4: Browser: "Say the end date"
User: "2025-03-01"
✓ End Date filled with "2025-03-01"
✓ Automatic geocoding from coordinates
✓ Search executes
✓ Results displayed
```

---

## Supported Date Formats

The application recognizes various date formats:

### Month Names (English)
- ✅ "January 15 2025" → 2025-01-15
- ✅ "Jan 15 2025" → 2025-01-15
- ✅ "February 20" → 2025-02-20 (current year assumed)
- ✅ "Dec 31 2024" → 2024-12-31

### ISO Format
- ✅ "2025-01-15" → 2025-01-15
- ✅ "2025-01-15 exact" → 2025-01-15

### Numeric Formats
- ✅ "01/15/2025" → 2025-01-15
- ✅ "01-15-2025" → 2025-01-15
- ✅ "15/01/2025" → 2025-01-15 (European format)

---

## Supported Location Formats

### Place Names
- ✅ "Venice Italy" → Geocoded to Venice coordinates
- ✅ "Bangkok Thailand" → Geocoded to Bangkok
- ✅ "New York" → Geocoded to New York City
- ✅ "Tokyo" → Geocoded to Tokyo

### Coordinates
- ✅ "45.4408, 12.3155" → Direct lat/lon (Venice)
- ✅ "35.6892, 139.6917" → Direct lat/lon (Tokyo)
- ✅ "13.7563, 100.5018" → Direct lat/lon (Bangkok)

---

## Supported Radius Formats

The application accepts radius in kilometers:

### Simple Numbers
- ✅ "15" → 15 km
- ✅ "20" → 20 km
- ✅ "50" → 50 km

### With Unit Names
- ✅ "15 kilometers" → 15 km
- ✅ "20 km" → 20 km
- ✅ "10 kilometre" → 10 km

### Constraints
- Minimum: 5 km (values below are set to 5)
- Maximum: 100 km (values above are set to 100)

---

## What Happens After All Steps

Once you complete Step 4 (End Date), the application automatically:

1. **Updates the display** with a summary:
   ```
   ✅ Search Parameters Set:
   📍 Venice Italy
   📏 15 km
   📅 2025-01-15 to 2025-02-15
   
   🔍 Searching...
   ```

2. **Geocodes the location** if it's a place name:
   - Converts "Venice Italy" to coordinates
   - Updates the map

3. **Performs the search**:
   - Sends request to backend with all parameters
   - Retrieves available NISAR satellite scenes

4. **Displays results**:
   - Shows map with location circle
   - Displays latitude/longitude bounds
   - Shows search radius
   - Lists available scenes in table below

5. **Clears microphone state**:
   - Stops listening
   - Microphone button returns to normal (not pulsing)

---

## Important Tips

### 🎯 Best Practices

1. **Speak clearly** - Especially place names
   - Say "Venice Italy" not "V-E-N-I-C-E"
   - Proper pronunciation helps accuracy

2. **Use simple language** - No need for complex phrases
   - Just say the location, not "my location is Venice"
   - Just say the number, not "I need a radius of"

3. **Complete each step** - Wait for browser to move to next step
   - Don't skip steps
   - Pause before moving to next

4. **Reasonable dates** - Use realistic date ranges
   - NISAR satellite data starts from certain dates
   - Future dates will return no results

### ⚠️ Troubleshooting

**Problem**: Voice recognition not starting
- Solution: Check browser microphone permissions
- Make sure microphone button pulses red
- Try clicking microphone again

**Problem**: Wrong location recognized
- Solution: Speak more clearly with proper pronunciation
- Try using coordinates instead of place names
- Or manually type in the location field

**Problem**: Date not recognized
- Solution: Use clearer date format (month name is best)
- Say "January 15" not "Jan fifteen"
- Try ISO format: "2025-01-15"

**Problem**: Radius not recognized
- Solution: Just say the number clearly ("15")
- Or say "15 kilometers"
- Don't use fractions (say "15" not "15 point 5")

**Problem**: Application stops listening after Step 1
- Solution: This means browser permission was denied
- Allow microphone permission in browser settings
- Refresh page and try again

---

## Manual Alternative

If voice input isn't working:

1. **Manually fill in fields**:
   - Click Location field and type your location
   - Enter a radius (5-100 km)
   - Select Start Date and End Date from calendar

2. **Then click Search**:
   - "Discover Available Scenes" button
   - Application works the same way
   - Results display automatically

---

## Technical Details

### Voice Recognition Technology
- Uses **Web Speech API** (built into most modern browsers)
- Supports continuous voice input
- Recognizes interim results as you speak

### Browser Support
- ✅ Chrome/Chromium (best support)
- ✅ Firefox (good support)
- ✅ Safari (requires HTTPS in production)
- ✅ Edge (full support)

### Language
- Default: English (US)
- Can be changed in code to other languages
- Month names: English only (by design)

### Privacy
- Voice data processed locally by browser
- No data sent to third parties for recognition
- Backend only receives final text results

---

## Reset Button

Click the **refresh icon** to:
- Clear all form fields
- Reset to default values
- Clear map display
- Hide results table
- Stop listening if in progress
- Ready for new search

---

## Advanced Options

### Manual Editing
After voice input fills fields, you can:
1. Click any field to edit manually
2. Change values as needed
3. Click "Discover Available Scenes" to search with new values

### Combining Methods
- Start with voice (Steps 1-4)
- Manually edit any field
- Click search to execute with modified parameters

---

## Summary

The **step-by-step voice flow** makes searching for NISAR satellite scenes as easy as:

1. 🎤 Click microphone
2. 📍 Say location
3. 📏 Say radius
4. 📅 Say start date
5. 📅 Say end date
6. ✅ Automatic search and results!

**No complex commands needed. Just speak naturally, one step at a time.**

---

**For questions or issues, use the manual input fields as an alternative to voice input.**
