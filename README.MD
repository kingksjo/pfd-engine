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

You can run the engine using either the **A320 Ground Station GUI** (`pfd_gui.py` built with PyQt5) or the **Pygame Six-Pack Display** (`main.py`). Both support all three operational modes:

### A320 Ground Station GUI (`pfd_gui.py` — Recommended)
Features a complete Airbus A320 PFD alongside an interactive side panel for configuring FCU targets (Speed, Altitude, Heading), QNH baro settings, and aircraft state (Weight, Flaps, Gear).
```bash
python pfd_gui.py --mode demo    # Run simulated A320 flight sector
python pfd_gui.py --mode serial  # Connect over USB serial
python pfd_gui.py --mode udp     # Connect over Wi-Fi UDP
```

### Pygame Six-Pack Display (`main.py`)
Runs the classic 60 FPS capped Pygame rendering loop with VSpeed bands and attitude watchdogs.

#### 1. Simulation Mode (Default)
Runs a local physics simulation using smooth sine waves for attitude and altitude (useful for testing without hardware).
```bash
python main.py
```

#### 2. Live Serial Mode (USB Cable)
Connects directly to your dual-core ESP32 board over a USB cable.
```bash
python main.py --port COM5
```
*   **--port**: Serial/USB port (e.g. `COM5` on Windows, `/dev/ttyUSB0` or `/dev/tty.usbserial-xxx` on Unix).
*   **--baud**: Serial baud rate. Must match `SERIAL_BAUD` in the firmware (defaults to `921600`).

#### 3. Live Wi-Fi Mode (Over-the-Air UDP)
Listens for wireless UDP telemetry packets sent by the ESP32 over your local network.
```bash
python main.py --wifi 5005
```
*   **--wifi**: Sets up a local UDP server listening on the specified port (defaults to `5005`).
*   **Firmware Configuration:** In `AbleTechPFDProject.ino`, set `#define COMM_MODE COMM_WIFI` and configure `UDP_HOST` to your PC's IP address (`192.168.137.1` when using Windows Mobile Hotspot, or your local LAN IP). Ensure both devices are on the same 2.4 GHz network.
*   **Alias IP Quick-Fix:** If the ESP32 firmware was pre-flashed with a hardcoded destination IP (such as `192.168.1.100`) while connected to your PC's Mobile Hotspot (`192.168.137.1`), you can add that IP as a secondary address on your PC without re-flashing the board:
    ```powershell
    # Run in Administrator PowerShell (replace 'Local Area Connection* 2' with your Hotspot adapter name)
    netsh interface ipv4 add address "Local Area Connection* 2" 192.168.1.100 255.255.255.0
    ```

### Controls & Key Bindings

| Key | Action |
| :--- | :--- |
| **ESC** | Graceful Shutdown (Stops all threads/subprocesses safely & exports CSV) |
| **G** | Toggle "Glass Vignette" overlay (On/Off) |
| **T** | Toggle secondary "Flight Telemetry Dashboard" window (On/Off) |

## Project Structure

*   `main.py`: Entry point. Starts the Data Thread and Render Thread.
*   `core/`: Shared state (`FlightState`), constants, and logic.
*   `ui/`: Pygame rendering engine and instrument classes.
*   `ui/telemetry.py`: Telemetry dashboard implementation (charts, grids, CSV export).
*   `ui/instruments/`: Individual gauge implementations (Horizon, Tape, Compass).
*   `game_io/`: Hardware abstraction layer (Mock Sensor vs. Real Sensor).
*   `telemetry_logs/`: Automatically generated folder containing exported session logs in CSV format.
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
