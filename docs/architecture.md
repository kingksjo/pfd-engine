# System Architecture: Glass Cockpit PFD Engine

## Overview
This project implements a high-performance, thread-safe Primary Flight Display (PFD) engine using Python and Pygame. It is designed to decouple sensor data acquisition from graphical rendering to ensure fluid 60 FPS performance regardless of sensor latency.

## Directory Structure
```
pfd-engine/
├── core/           # Core logic and shared state
│   ├── state.py     # FlightState (Single Source of Truth)
│   ├── logic.py     # Signal Processing (Filters, Math)
│   └── constants.py # Aviation Units & Color Palette
├── game_io/        # Input/Output and Hardware Abstraction
│   ├── sensor_interface.py  # Abstract Base Class
│   └── mock_sensor.py       # Simulation Logic
├── ui/             # Graphical User Interface
│   ├── base_instrument.py   # Abstract Instrument Class
│   ├── renderer.py          # Main Pygame Render Loop
│   └── instruments/         # Individual Instrument Modules
├── docs/           # Technical Documentation
└── main.py         # Application Entry Point
```

## Core Engineering Patterns

### 1. Producer-Consumer Threading
*   **Data Thread (`main.py` -> `sensor_loop`):** 
    *   Runs at a precise **100Hz**.
    *   Uses `stop_event.wait(timeout)` instead of `time.sleep()` for deterministic timing and instant shutdown responsiveness.
    *   Updates `FlightState` with a high-resolution timestamp for health monitoring.
*   **Render Thread (`ui.renderer.PFDRenderer`):**
    *   Runs at 60Hz (VSync).
    *   Features a **Resizable Viewport** to ensure visibility on all display resolutions.
    *   Gracefully handles window close events (`pygame.QUIT`) and `ESC` key interrupts.

### 2. Sensor Watchdog & Safety
*   **Heartbeat Monitor:** The `FlightState` tracks `last_update` time.
*   **Automatic Failure Detection:** The `BaseInstrument` class implements a watchdog. If `current_time - last_update > 500ms`, instruments automatically enter a **Failure State**.
*   **Visual Warning:** Failed instruments render a large **Red X** and a **"DATA FAIL"** flag, preventing the display of stale or frozen flight data.

### 3. Instrument Abstraction (Template Method Pattern)
All instruments inherit from `BaseInstrument`, which enforces a separation between system-level updates and instrument-specific drawing:
*   `update(state)`: Handles the watchdog and system health check.
*   `_update_logic(state)`: (Abstract) Implemented by children to render specific visuals (Horizon, Tapes, etc.).

## Implemented Instruments

### 1. Artificial Horizon (`ui/instruments/horizon.py`)
*   **Moving World Pattern:** Transforms a 2000x2000 "World Surface".
*   **Pitch & Roll Integration:** Uses trigonometric rotation vectors to ensure the pitch ladder remains aligned with the horizon during high-bank turns.
*   **Slip/Skid Indicator:** Integrated inclinometer at the bottom of the attitude indicator.

### 2. Vertical Tape Instruments (`ui/instruments/tape.py`)
*   **Sliding Window Pattern:** Uses tall pre-rendered scales for Airspeed and Altitude.
*   **Dynamic Readouts:** Features center-aligned digital pointer boxes with high-contrast green text.

### 3. Compass Tape (`ui/instruments/compass.py`)
*   **360-Degree Wrapping:** Uses a mirrored buffer at the end of a 1440-pixel scale to allow seamless transitions between 359° and 0°.

### 4. Vertical Speed Indicator (`ui/instruments/vsi.py`)
*   **Rate Scale:** Visualizes feet-per-minute (FPM) using a center-zero bar.

## Development Checkpoints

### Phase 1-3: Core Foundation [DONE]
- [x] **SSOT Architecture**: Thread-safe `FlightState` with locking mechanisms.
- [x] **Renderer Engine**: 60 FPS capped loop with Pygame.
- [x] **Artificial Horizon**: Pitch/Roll transformation logic with pre-rendered ladder.
- [x] **Vertical Tapes**: Reusable `TapeInstrument` for Airspeed and Altitude.

### Phase 4: Full Six-Pack Integration [DONE]
- [x] **Heading Indicator**: Horizontal compass tape with 360° wrapping.
- [x] **VSI**: Vertical Speed Indicator with dynamic bar logic.
- [x] **Inclinometer**: Slip/Skid ball integrated into the Horizon display.
- [x] **Layout Optimization**: Coordinated instrument positioning for 1024x700 resolution.

### Phase 5: Reliability & Refinement [IN PROGRESS]
- [x] **Graceful Shutdown**: Instant thread termination using `stop_event.wait()`.
- [x] **Watchdog System**: Automatic "DATA FAIL" Red X flags on sensor timeout.
- [x] **Windowing QoL**: Resizable window support and title bar visibility fixes.
- [ ] **Visual Polish**: Anti-aliasing and smoother font rendering.
- [ ] **Aviation Logic**: V-speed limit warnings (Redline/Stall).

### Phase 6: Hardware-in-the-Loop [TODO]
- [ ] **Serial Driver**: Implementation of `pyserial` interface for IMU data.
- [ ] **Signal Filtering**: Complementary or Kalman filter integration.
- [ ] **Calibration**: Offset and drift compensation logic.
