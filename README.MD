# Glass Cockpit PFD Engine

A high-performance, multithreaded Primary Flight Display (PFD) engine built with Python and Pygame. Designed for real-time avionics simulation and hardware integration.

## Features

*   **Real-Time Rendering:** 60 FPS capped loop with VSync.
*   **Multithreading:** Decoupled Data Thread (100Hz) and Render Thread (60Hz).
*   **Safety Systems:** Automatic "Data Timeout" watchdog (Red X) on sensor failure.
*   **Complete Six-Pack:** Artificial Horizon, Airspeed, Altitude, Compass, VSI, and Slip/Skid.
*   **Professional Visuals:** Anti-aliasing, Sky/Ground gradients, Drop Shadows, and V-Speed bands.
*   **Mock Sensor:** Physics-based simulation mode for testing without hardware.

## Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/pfd-engine.git
    cd pfd-engine
    ```

2.  **Create a Virtual Environment (Recommended):**
    ```bash
    python -m venv .venv
    source .venv/bin/activate  # On Windows: .venv\Scripts\activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Engine

You can run the engine in two modes:

### 1. Simulation Mode (Default)
Runs a local physics simulation using smooth sine waves for attitude and altitude (useful for testing without hardware).
```bash
python main.py
```

### 2. Live Hardware Mode
Connects directly to your dual-core ESP32 avionics board running the `AbleTechPFDProject.ino` firmware.
```bash
python main.py --port COM5
```
*   **--port**: Serial/USB port (e.g. `COM5` on Windows, `/dev/ttyUSB0` or `/dev/tty.usbserial-xxx` on Unix).
*   **--baud**: Serial baud rate. Must match `SERIAL_BAUD` in the firmware (defaults to `921600`).

### Controls & Key Bindings

| Key | Action |
| :--- | :--- |
| **ESC** | Graceful Shutdown (Stops all threads safely) |
| **G** | Toggle "Glass Vignette" overlay (On/Off) |

## Project Structure

*   `main.py`: Entry point. Starts the Data Thread and Render Thread.
*   `core/`: Shared state (`FlightState`), constants, and logic.
*   `ui/`: Pygame rendering engine and instrument classes.
*   `ui/instruments/`: Individual gauge implementations (Horizon, Tape, Compass).
*   `game_io/`: Hardware abstraction layer (Mock Sensor vs. Real Sensor).
*   `docs/`: Detailed technical documentation.

## Extending the Engine

### Adding a New Instrument
1.  Create a new file in `ui/instruments/`.
2.  Inherit from `ui.base_instrument.BaseInstrument`.
3.  Implement `_update_logic(self, state: FlightState)`.
    *   *Note: Do not override `update()`; the base class handles the safety watchdog.*
4.  Add the instrument to `main.py` using `renderer.add_instrument()`.

### Connecting Real Hardware
1.  Create a new class in `game_io/` (e.g., `SerialSensor`).
2.  Inherit from `SensorInterface`.
3.  Implement `connect()`, `read()`, and `close()`.
4.  Swap `MockSensor` with `SerialSensor` in `main.py`.

## Documentation

*   [System Architecture](docs/system_architecture.md) - Threading model & Data flow.
*   [Instrument Reference](docs/instrument_reference.md) - Rendering logic & Math.
