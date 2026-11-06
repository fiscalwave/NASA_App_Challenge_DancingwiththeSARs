# Voice Input Feature Guide

## Overview
The voice input system has been completely rebuilt with robust error handling, clear step-by-step feedback, and automatic field population.

## How It Works

### Step-by-Step Process
The voice system guides users through 4 sequential steps:

1. **Step 1: Location** - User speaks their location
   - Examples: "Venice Italy", "45.4408, 12.3155", "Houston Texas"
   - Input is automatically filled into the Location field
   
2. **Step 2: Radius** - User speaks the search radius
   - Examples: "15", "20 kilometers", "50 km"
   - Only numbers are extracted, clamped to 5-100 km range
   - Input is automatically filled into the Search Radius field
   
3. **Step 3: Start Date** - User speaks the start date
   - Examples: "January 15 2025", "15 January 2025", "2025-01-15", "01-15-2025"
   - Multiple date formats are supported
   - Input is automatically filled into the Start Date field
   
4. **Step 4: End Date** - User speaks the end date
   - Same format support as Step 3
   - Input is automatically filled into the End Date field

### After All Steps Complete
Once all 4 steps are successfully captured:
1. System shows: "All parameters set! Searching now..."
2. Auto-geocodes the location to find coordinates
3. Auto-clicks the "Discover Available Scenes" button
4. Search results are displayed automatically

## Key Features

### Real-Time Feedback
- Display shows current step number (e.g., "Step 1/4")
- Shows what the system is hearing in real-time
- Shows confirmation when step is processed
- Clear visual feedback with mic button color change

### Error Handling
- **No speech detected**: System retries up to 2 times automatically
- **Network error**: Displays error message and allows restart
- **Unrecognized input**: Step is retried with counter shown
- **Max retries reached**: User can manually enter data or restart voice input

### Robust State Management
- Prevents double-start of speech recognition
- Handles race conditions between recognition states
- Safely manages transitions between steps
- Graceful fallback to manual entry if voice fails

## User Interface

### Voice Input Display Box
Located at the top of the page, shows:
- Real-time transcript as user speaks
- Current step indicator (Step X/4)
- Status messages (Processing, Hearing, Confirmed, Error)

### Microphone Button
- **Idle**: Gray background, mic icon visible
- **Listening**: Blue background (listening class applied)
- **After Steps Complete**: Returns to gray

### Reset Button
- Clears all voice data and form fields
- Allows user to start fresh voice input

## Date Format Support
The system intelligently parses multiple date formats:

```
Supported formats:
✓ "January 15 2025"
✓ "15 January 2025"  
✓ "2025-01-15" (YYYY-MM-DD)
✓ "2025/01/15" (with slashes)
✓ "01-15-2025" (MM-DD-YYYY)
✓ "15-01-2025" (DD-MM-YYYY)

Month names:
January, February, March, April, May, June,
July, August, September, October, November, December
(and 3-letter abbreviations: Jan, Feb, Mar, etc.)
```

## Troubleshooting

### "No speech detected"
- Ensure microphone is working and permitted in browser
- Speak clearly at normal volume
- Wait for the step prompt to appear before speaking

### "Network error"
- Check internet connection
- Reload page and try again
- Some browsers/networks block speech recognition API

### Stuck on a step?
- Click the mic button to stop
- Manually enter the value in the form field
- Click mic button again to continue voice input

### Not filling fields correctly?
- Speak naturally and clearly
- Use the suggested examples from the prompts
- For dates, say month name or use YYYY-MM-DD format
- For locations, use known city names or coordinates

## Browser Compatibility
- Chrome/Edge: Full support
- Firefox: Partial support (requires flag enable)
- Safari: Full support (iOS 14.5+)
- Opera: Full support

## Technical Implementation

### Architecture
```
User clicks Mic
    ↓
startVoiceFlow() initializes state
    ↓
moveToNextStep() starts recognition for current step
    ↓
recognition.onresult() captures speech
    ↓
processCurrentStep() validates input
    ├─ Success: Move to next step
    └─ Failure: Retry with counter
    ↓
completeVoiceFlow() when all steps done
    ├─ Geocode location
    └─ Click search button
```

### State Variables
- `isListening`: Boolean flag for active listening state
- `voiceStep`: Current step key ('location', 'radius', 'startDate', 'endDate', null)
- `currentStepIndex`: 0-3 tracking which step we're on
- `retryCount`: Tracks retries for current step (max 2)
- `voiceData`: Object storing captured voice data
- `MAX_RETRIES`: Constant set to 2

### Error Handling Strategy
Each step has up to 2 retries before requiring manual input. Errors are caught at:
1. Speech recognition level (no-speech, network)
2. Parsing level (invalid date/radius format)
3. State management level (race conditions)

## Configuration
To adjust behavior, modify these constants in index.html:
```javascript
const MAX_RETRIES = 2;  // Change retry attempts
```

Voice step definitions can be customized in the `voiceSteps` array:
```javascript
const voiceSteps = [
    { key: 'location', prompt: '...', field: 'locationInput', processor: '...' },
    // ...
];
```

## Future Enhancements
- [ ] Support for continuous voice input (entire sentence)
- [ ] Custom wake words to start/stop recording
- [ ] Voice confirmation: "Please confirm..." before proceeding
- [ ] Fallback language support (Spanish, French, etc.)
- [ ] Voice playback of confirmations
- [ ] Accessibility improvements (ARIA labels, screen reader support)
