# Helios Deck - BossCrafts Audio Interface Showdown Submission

A complete browser-based audio interface built with plain HTML, CSS, and JavaScript.
It runs by opening `index.html` directly, with no build tools or dependencies.

## Table of Contents

- [Run Instructions](#run-instructions)
- [Implemented Features](#implemented-features)
- [Nice-to-Have Features Included](#nice-to-have-features-included)
- [Implementation Notes](#implementation-notes)
- [Known Limitations](#known-limitations)

## Run Instructions
1. Open this folder.
2. Double-click `index.html` (or open it in any modern browser).
3. Use built-in tracks or load your own audio files by drag-and-drop.

## Implemented Features
- Play/pause control
- Stop control
- Previous/next track navigation
- Volume slider
- Mute toggle
- Seek/progress bar with real-time `current time` and `duration`
- Playlist with multiple tracks (preloaded built-in tracks + user-loaded files)
- Keyboard shortcuts:
  - `Space`: Play/Pause
  - `ArrowLeft`: Seek backward 5 seconds
  - `ArrowRight`: Seek forward 5 seconds
  - `M`: Mute/Unmute
- Visual audio feedback via animated spectrum bars (Web Audio analyser + canvas)
- Fully responsive layout for desktop and mobile
- Distinct visual theme with intentional typography, atmospheric gradients, and motion

## Nice-to-Have Features Included
- Loop toggle
- Shuffle toggle
- Playback speed selector (0.75x, 1.0x, 1.25x, 1.5x)
- Drag-and-drop audio file loading and file picker

## Implementation Notes
- Built-in starter tracks are procedurally generated WAV tones at runtime, so the app is fully self-contained.
- User audio files are loaded with object URLs and appended to the playlist.
- The visualizer responds to frequency data from the active track in real time.

## Known Limitations
- Browser autoplay restrictions require first interaction before guaranteed playback.
- Generated starter tracks are synthetic tones, intended as placeholders for demo/testing.
- On very old browsers, some Web Audio APIs may be limited.
