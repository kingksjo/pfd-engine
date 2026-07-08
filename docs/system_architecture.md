# System Architecture

## High-Level Overview

The **Glass Cockpit PFD Engine** is a high-performance, multithreaded avionics display system. It decouples **Sensor Data Acquisition** (Producer) from **Graphical Rendering** (Consumer) to ensure fluid 60 FPS visualization regardless of sensor jitter or latency.

## Core Components

### 1. The Single Source of Truth (SSOT)
Located in `core/state.py`, the `FlightState` class is the central nervous system.
*   **Thread Safety:** Uses a `threading.Lock` to ensure atomic updates. This prevents "tearing" (e.g., displaying Pitch from Frame N and Roll from Frame N-1).
*   **Data Integrity:** Tracks a `last_update` timestamp for health monitoring.
*   **Snapshot Pattern:** The Renderer requests a read-only copy (`get_snapshot()`) at the start of every frame to ensure consistency during the drawing phase.

### 2. The Data Thread (Producer)
Located in `main.py` -> `sensor_loop`.
*   **Frequency:** Runs at a precise **100Hz**.
*   **Responsibility:** Polls the active sensor driver updating the `FlightState` atomically.
*   **Modes:** Supports three operational modes configured via command-line arguments:
    *   **Simulation Mode:** Polls a local physics-based `MockSensor` generating smooth, coherent motion waves.
    *   **Serial Hardware Mode (`--port`):** Connects to the ESP32 flight computer running the custom Arduino firmware via `pyserial` at 921600 Baud (default) to process live sensory feeds from IMUs, barometers, and pitot sensors.
    *   **Wi-Fi UDP Mode (`--wifi [port]`):** Activates a local UDP socket bound to port `5005` (default) to subscribe to incoming wireless broadcast datagrams from the ESP32 chip over the local network.
*   **Timing:** Uses `stop_event.wait(timeout)` for deterministic timing and instant shutdown responsiveness.

### 3. The Render Thread (Consumer)
Located in `ui/renderer.py`.
*   **Frequency:** Runs at **60Hz** (VSync locked).
*   **Responsibility:** Reads the state snapshot and orchestrates the drawing of all instruments.
*   **Window Management:** Handles resizing, fullscreen toggles, and input events (like the 'G' key for glass overlay).

## Hardware Integration & Telemetry Protocols

When interacting with the physical ESP32 avionics board, the engine supports two connection protocols:

### 1. Serial (USB) Protocol (`--port [port]`)
The system activates `HardwareSensor` inside [game_io/hardware_sensor.py](../game_io/hardware_sensor.py), which listens directly to the board's serial UART stream at **921600 baud**:
```text
$PFD,IAS_kts,TAS_kts,Mach,alt_ft,VSI_fpm,roll_deg,pitch_deg,hdg_deg,OAT_C,QNH_hPa,pres_hPa,ts_ms\n
```

### 2. Wi-Fi (UDP) Protocol (`--wifi [port]`)
By changing `#define COMM_MODE COMM_WIFI` in `AbleTechPFDProject.ino`, the ESP32 acts as a wireless client communicating over a local network.
*   **Packet Stream:** The ESP32 targets the Python client's machine IP (`UDP_HOST`) and specified port (`UDP_PORT`, default `5005`) pushing raw ASCII-CSV packets with the same `$PFD` schema over the air.
*   **Sensor Interface:** The python backend activates `WifiSensor` inside [game_io/wifi_sensor.py](../game_io/wifi_sensor.py) binding a standard UDP socket to `0.0.0.0` at the selected port to grab these incoming datagrams.

### Telemetry Mapping to GUI state:
| Telemetry Field Index | Value Name | FlightState Map Target | Range / Unit |
|---|---|---|---|
| `fields[0]` | $PFD Prefix | *Packet Recognition* | String Constant |
| `fields[1]` | IAS (Indicated Airspeed) | `airspeed` | Knots |
| `fields[2]` | TAS (True Airspeed) | *Pre-rendered / Ignored* | Knots |
| `fields[3]` | Mach Number | *Pre-rendered / Ignored* | Dimensionless |
| `fields[4]` | Barometric Altitude | `altitude` | Feet |
| `fields[5]`| VSI (Vertical Speed) | `vertical_speed` | Feet/Minute (FPM) |
| `fields[6]`| IMU Filtered Roll | `roll` | Degrees |
| `fields[7]`| IMU Filtered Pitch | `pitch` | Degrees |
| `fields[8]`| Magnetic Heading | `heading` | Degrees |
| `fields[9]`| Outer Air Temp (OAT) | *Pre-rendered / Ignored* | Celsius |
| `fields[10]`| Ground QNH Settings | *Pre-rendered / Ignored* | hPa |
| `fields[11]`| BMP Station Pressure | *Pre-rendered / Ignored* | hPa |
| `fields[12]`| Device TS Uptime | *Pre-rendered / Ignored* | Milliseconds |

## Safety Systems

### Sensor Watchdog
To prevent the display of "frozen" (and thus dangerous) flight data, the system includes an automatic watchdog.
1.  **Tracking:** The Data Thread updates `FlightState.last_update` on every valid packet.
2.  **Detection:** The `BaseInstrument` class checks this timestamp during every render cycle.
3.  **Action:** If `current_time - last_update > 0.5s`, the instrument aborts its normal drawing routine and calls `draw_failure_flag()`.
4.  **Visual:** A large **Red X** and **"DATA FAIL"** warning appear on the instrument.

## Data Flow Diagram
```mermaid
graph TD
    subgraph Hardware Setup (Live)
        HW_Serial[ESP32 Flight Computer] -->|Serial UART (921600 Baud)| HS[HardwareSensor]
        HW_Wifi[ESP32 Flight Computer] -->|Wi-Fi UDP Broadcast| WS[WifiSensor]
    end
    subgraph Local Simulation (Fallback)
        MS[MockSensor]
    end
    HS -->|Telemetry dict| DT[Data Thread - 100Hz]
    WS -->|Telemetry dict| DT
    MS -->|Simulated dict| DT
    DT -->|Atomic Update| C{FlightState (SSOT)}
    D[Render Thread (60Hz)] -->|Request Snapshot| C
    C -->|Thread-Safe Copy| D
    D -->|Draw| E[Artificial Horizon]
    D -->|Draw| F[Airspeed Tape]
    D -->|Draw| G[Altitude Tape]
    D -->|Draw| H[Compass]
```
