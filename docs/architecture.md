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
├── io/             # Input/Output and Hardware Abstraction
│   ├── sensor_interface.py  # Abstract Base Class
│   └── mock_sensor.py       # Simulation Logic
├── ui/             # Graphical User Interface
│   ├── base_instrument.py   # Abstract Instrument Class
│   └── renderer.py          # Main Pygame Render Loop
├── docs/           # Technical Documentation
├── tests/          # Unit and Integration Tests
└── main.py         # Application Entry Point
```

## Core Patterns

### 1. Producer-Consumer Threading
*   **Data Thread (`main.py` -> `sensor_loop`):** 
    *   Runs at ~100Hz.
    *   Polls the `SensorInterface`.
    *   Updates `FlightState` using a thread-safe lock.
*   **Render Thread (`ui.renderer.PFDRenderer`):**
    *   Runs at 60Hz (VSync).
    *   Reads a snapshot of `FlightState`.
    *   Draws instruments based on that snapshot.

### 2. Single Source of Truth
The `FlightState` class in `core/state.py` holds all flight parameters (pitch, roll, altitude, etc.). It uses a `threading.Lock` to ensure atomic updates, preventing "tearing" where the display might show pitch from frame N and roll from frame N-1.

### 3. Instrument Abstraction
All instruments (Horizon, Tapes, Compass) will inherit from `ui.base_instrument.BaseInstrument`. This enforces a standard `update(state)` and `draw(screen)` interface, making the renderer agnostic to the specific instruments being displayed.

### 4. Signal Processing & Logic Layer
To handle real-world sensor "jitter" and unit conversions:
*   **Constants (`core/constants.py`):** Centralizes all magic numbers, colors, and aviation conversion factors (e.g., Meters to Feet).
*   **Logic (`core/logic.py`):** Implements the **Complementary Filter** logic. This ensures that raw, noisy data from the `game_io` layer is smoothed before it reaches the `FlightState`.

## Implemented Instruments

### 1. Artificial Horizon (`ui/instruments/horizon.py`)
The most complex instrument in the PFD.
*   **Moving World Pattern:** Instead of moving a line, we transform a 2000x2000 "World Surface" (Sky/Ground).
*   **Transformation Flow:**
    1.  **Pitch Shift:** The world surface is offset vertically by `pitch * PIXELS_PER_DEGREE`.
    2.  **Roll Rotation:** The offset surface is rotated by `-roll` using Pygame's `transform.rotate`.
    3.  **Centered Blit:** A specialized algorithm ensures the rotation pivot stays centered in the PFD viewport while maintaining the pitch offset along the rotated vertical axis.
*   **Optimization:** The **Pitch Ladder** (degree markings) is pre-rendered onto the world surface during initialization to minimize per-frame drawing calls.

### 2. Tape Instruments (`ui/instruments/tape.py`)
A reusable component for vertical scales like Airspeed and Altitude.
*   **Sliding Window Pattern:** Pre-renders a very tall surface (e.g., 10,000 pixels for altitude) containing all tick marks and labels.
*   **Clipping Viewport:** The `TapeInstrument` surface acts as a window; the tall scale surface is blitted at a negative Y-offset calculated from the current flight value.
*   **Fixed Readout:** A "Pointer Box" is drawn statically in the center to show the exact digital value over the moving tape.

## Future Extensions
*   **Hardware Integration:** Implement `game_io/serial_sensor.py` using `pyserial` to read from Arduino/IMU.
*   **Tape Instruments:** Implement `ui/instruments/tapes.py` for Airspeed and Altitude using a vertical sliding window pattern.
