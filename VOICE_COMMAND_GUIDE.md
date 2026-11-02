# 🎤 Voice Command Feature Guide

## Overview

The NISAR Flood & Wetland Change Mapping application now includes an innovative **voice command interface** that allows you to search for locations, set search radius, and specify analysis dates using natural speech. Simply click the microphone button and speak your command - the application will automatically parse your input and populate all fields.

---

## Quick Start

1. **Click the 🎤 Voice Button**
   - Located next to the "Location or Coordinates" input field
   - Button turns red with pulsing animation when listening
   - Status changes to "🎤 Listening..."

2. **Speak Your Command**
   - Example: "Search Venice Italy with 15 kilometers for January 1 to March 1 2025"
   - Speak naturally - the system will parse location, radius, and dates

3. **Form Auto-Fills**
   - Location input updates with your location
   - Radius sets to specified distance (in km)
   - Start and end dates populate automatically
   - Map updates with red circle at your location

4. **Discover Scenes**
   - Click "Discover Available Scenes" to search for satellite data
   - Results appear instantly

---

## Voice Command Examples

### Example 1: Basic Location Search
**Say:** "Venice Italy with 10 kilometers"

**Result:**
- Location: Venice, Italy
- Radius: 10 km
- Start Date: (today)
- End Date: (2 months from today)

---

### Example 2: Complete Search with Dates
**Say:** "Search Nile Delta Egypt with 25 kilometers for January 1 to March 1 2025"

**Result:**
- Location: Nile Delta, Egypt
- Radius: 25 km
- Start Date: 2025-01-01
- End Date: 2025-03-01

---

### Example 3: Using Coordinates
**Say:** "45.4408 comma 12.3155 with 20 kilometers from February to April"

**Result:**
- Location: 45.4408, 12.3155 (Venice)
- Radius: 20 km
- Start Date: 2025-02-01
- End Date: 2025-04-30

---

### Example 4: Month Names
**Say:** "Amazon Basin Brazil 50 kilometers January through June"

**Result:**
- Location: Amazon Basin, Brazil
- Radius: 50 km
- Start Date: 2025-01-01
- End Date: 2025-06-30

---

### Example 5: Multiple Radius Units
**Say:** "Cairo Egypt with 30 kilometers for May 1 to July 31"

**Result:**
- Location: Cairo, Egypt
- Radius: 30 km
- Start Date: 2025-05-01
- End Date: 2025-07-31

---

## Supported Input Formats

### Location Formats
```
✓ City name: "Venice"
✓ City, Country: "Venice, Italy"
✓ Coordinates: "45.4408, 12.3155"
✓ Decimal degrees: "45.4408, 12.3155"
✓ Negative coordinates: "-15.7942, -47.8822" (South/West)
```

### Radius Formats
```
✓ "10 km"
✓ "15 kilometers"
✓ "20 km radius"
✓ "with 25 km"
✓ Valid range: 5 to 100 km (auto-clamped)
```

### Date Formats
```
✓ Month names: "January 15", "Jan 15"
✓ Month abbreviations: "Jan", "Feb", "Mar", etc.
✓ Numeric format: "01/15/2025"
✓ Dash format: "01-15-2025", "2025-01-15"
✓ Natural language: "January to March", "from April to June"
```

---

## Advanced Usage

### Setting Specific Date Ranges

**Single Date Provided:**
- If you only specify one date, the system automatically sets the end date to 2 months later
- Example: "January 15" → Start: 2025-01-15, End: 2025-03-15

**Two Dates Provided:**
- The system uses the first date as start and second as end
- Example: "January 1 to March 1" → Start: 2025-01-01, End: 2025-03-01

**Month Range:**
- Specify months without specific dates
- Example: "January through April" → Uses first and last days of specified months

---

## Natural Language Processing

The voice command parser is designed to be flexible with natural speech patterns:

### What It Understands
- **"with"**: "Venice with 10 km" → sets radius
- **"for"**: "for January to March" → sets dates
- **"from...to"**: "from January to March" → sets date range
- **"comma"**: "45.4408 comma 12.3155" → separates coordinates
- **Variations**: "km", "kilometer", "kilometers" all recognized

### Example Complex Commands
```
"Find Venice Italy with 15 kilometers radius for January 1 2025 to March 31 2025"
"Search coordinates 30.9176 comma 31.2922 with 20 km from February to April"
"Nile Delta Egypt 25 km January through June 2025"
"Po Valley 10 kilometers for the period January 1 to March 1"
```

---

## Visual Feedback

### Button States

**Normal State:**
- Purple gradient color (#8b5cf6 → #6d28d9)
- Shows "🎤 Voice"
- Ready to be clicked

**Listening State:**
- Red gradient color (#ef4444 → #dc2626)
- Shows "🎤 Listening..."
- Pulsing glow animation
- Click again to stop listening

**Hover State:**
- Brightness increases
- Shadow expands
- Slight upward movement
- Indicates interactive element

### Form Updates
- Location field updates with your specified location
- Radius updates to your specified distance
- Start date populates automatically
- End date populates automatically
- Map updates with red circle at location
- Visual confirmation alert shows parsed data

---

## Troubleshooting

### "Voice Error: not-allowed"
**Issue:** Browser permission denied for microphone access
**Solution:** 
1. Check browser permissions (look for microphone icon in address bar)
2. Click "Allow" when asked for microphone permission
3. Reload the page
4. Try voice command again

### "Voice Error: network-error"
**Issue:** Network connectivity problem
**Solution:**
1. Check your internet connection
2. Some browsers may have network restrictions
3. Try using Chrome or Edge browser
4. Disable VPN if you're using one

### "Voice Error: no-speech"
**Issue:** Microphone didn't pick up your speech
**Solution:**
1. Speak clearly and at normal volume
2. Wait longer after clicking the button
3. Reduce background noise
4. Move closer to your microphone
5. Try again

### Button Appears Disabled/Gray
**Issue:** Your browser doesn't support Web Speech API
**Solution:**
1. Update your browser to the latest version
2. Try Chrome, Edge, or Firefox (Safari may have limited support)
3. Use manual text input as alternative
4. See browser compatibility section

### Location Not Found
**Issue:** Spoken location not recognized
**Solution:**
1. Speak more clearly (avoid mumbling)
2. Use full location names: "Venice, Italy" instead of just "Venice"
3. Try coordinates instead: "45.4408, 12.3155"
4. Manually type if voice recognition fails
5. Use nearby major cities

### Dates Not Parsed
**Issue:** Spoken dates not being recognized
**Solution:**
1. Speak month names clearly: "January", "February" (not "Jan-u-ary")
2. Use standard date formats: "January 15" or "01/15/2025"
3. Say "to" between dates: "January to March"
4. Avoid complex phrasing like "mid-January"

---

## Browser Compatibility

| Browser | Support | Notes |
|---------|---------|-------|
| Chrome  | ✅ Full | Excellent native support |
| Edge    | ✅ Full | Excellent native support |
| Firefox | ✅ Full | Full support |
| Safari  | ✅ Full | WebKit prefix, may need permission |
| Mobile  | ✅ Full | Works on mobile browsers with permission |

**If Not Supported:**
- Voice button will be disabled (grayed out)
- Manual text input works normally
- All other features fully functional

---

## Privacy & Security

### Data Handling
- **Voice Input:** Only processed locally in your browser
- **No Cloud Transmission:** Speech recognition happens on-device
- **No Recording:** Audio is not saved or recorded
- **Temporary:** Voice data is discarded after parsing
- **Private:** No logs or tracking of voice commands

### Microphone Access
- Browser asks permission first
- You can deny access (voice button disables)
- You can revoke access anytime in browser settings
- Only active when you click the button

---

## Tips for Best Results

### 1. Clear Speech
- Speak clearly at normal volume
- Avoid mumbling or whispering
- Enunciate place names carefully

### 2. Standard Format
- Use recognized place names
- Say "comma" between coordinates
- Say "to" between dates
- Use "kilometers" or "km" for distance

### 3. Complete Information
- Include location, radius, and dates for best results
- If only location: dates default to today + 2 months
- If only dates: defaults to previous location
- Radius defaults to 10 km if not specified

### 4. Quiet Environment
- Minimize background noise
- Close other applications with sound
- Use a good quality microphone
- Test microphone in browser settings first

### 5. Natural Speaking
- Don't pause between words
- Speak as you would normally
- The system handles casual speech patterns
- Variations like "km", "kilometer", "kilometers" all work

---

## Common Commands Reference

### Flood Monitoring
```
"Venice Italy with 15 km for flood monitoring January to March"
"Nile Delta Egypt with 25 km from January 1 to March 31 2025"
```

### Wetland Analysis
```
"Amazon Basin Brazil with 50 km for wetland mapping February to August"
"Ganges Delta Bangladesh with 20 km January through December"
```

### Disaster Response
```
"Po Valley Italy with 10 km for emergency response May to September"
"Indus River Pakistan with 30 km March to May 2025"
```

### Research Sites
```
"45.4408 comma 12.3155 with 5 km for site-specific analysis"
"coordinates 30.9176 comma 31.2922 with 15 km January to June"
```

---

## Video Tutorial (if available)

For a visual guide, watch the voice command tutorial:
1. Click the 🎤 Voice button
2. Listen for the listening indicator
3. Speak your command clearly
4. Watch the form auto-fill
5. Review the confirmation alert
6. Click "Discover Available Scenes"

---

## Keyboard Alternatives

If voice isn't working:
- **Location:** Type manually in text box (supports names and coordinates)
- **Radius:** Use the number input field (5-100 km range)
- **Dates:** Use the date picker (click the calendar icon)
- **Map:** Click on map to set location manually

---

## Feature Request or Issues

Have suggestions for the voice feature?
- Report issues through the application
- Suggest new voice command formats
- Recommend additional location support
- Share your use cases

---

## Advanced: Command Syntax

### Core Structure
```
[Location] [with/radius] [Distance] [km/kilometer] [for/from] [Date] [to] [Date]
```

### Optional Components
```
Location: (required or defaults to last location)
Radius: (optional, defaults to 10 km)
Dates: (optional, defaults to today + 2 months)
```

### Examples of Valid Commands
```
✓ "Venice"
✓ "Venice with 10 km"
✓ "Venice with 10 km from January 1"
✓ "Venice with 10 km for January 1 to March 1 2025"
✓ "45.4408, 12.3155 with 20 km"
✓ "45.4408, 12.3155 with 20 km from January to March"
```

---

## Version History

**Version 1.0** (Current)
- ✅ Basic voice command support
- ✅ Location and coordinates parsing
- ✅ Radius extraction
- ✅ Date range parsing
- ✅ Auto-form filling
- ✅ Map integration
- ✅ Multi-language month names
- ✅ Browser fallback handling

**Planned Features**
- 🔜 Multi-language support (Spanish, Chinese, etc.)
- 🔜 Custom date formats
- 🔜 Saved command templates
- 🔜 Voice command history
- 🔜 Custom voice profiles

---

## Support

For technical support or questions:
1. Check the troubleshooting section above
2. Try clearing browser cache and reloading
3. Update your browser to latest version
4. Try a different browser (Chrome, Edge, Firefox)
5. Ensure microphone is working in other applications

---

**Enjoy hands-free satellite scene discovery with the NISAR application!** 🚀🎤
