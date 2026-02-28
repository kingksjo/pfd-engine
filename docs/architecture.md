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
*   **Logic (`core/logic.py`):** Implements the **Complementary Filter** logic. This ensures that raw, noisy data from the `io` layer is smoothed before it reaches the `FlightState`.

## Future Extensions
*   **Hardware Integration:** Implement `io/serial_sensor.py` using `pyserial` to read from Arduino/IMU.
*   **New Instruments:** Create classes like `ui/instruments/horizon.py` implementing the `BaseInstrument` interface.
