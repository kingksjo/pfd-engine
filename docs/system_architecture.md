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
*   **Responsibility:** Polls the hardware/mock sensor, applies signal filtering (future), and updates the `FlightState`.
*   **Timing:** Uses `stop_event.wait(timeout)` for deterministic timing and instant shutdown responsiveness.

### 3. The Render Thread (Consumer)
Located in `ui/renderer.py`.
*   **Frequency:** Runs at **60Hz** (VSync locked).
*   **Responsibility:** Reads the state snapshot and orchestrates the drawing of all instruments.
*   **Window Management:** Handles resizing, fullscreen toggles, and input events (like the 'G' key for glass overlay).

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
    A[Sensor/IMU] -->|Raw Data (100Hz)| B(Data Thread)
    B -->|Atomic Update| C{FlightState (SSOT)}
    D[Render Thread (60Hz)] -->|Request Snapshot| C
    C -->|Thread-Safe Copy| D
    D -->|Draw| E[Artificial Horizon]
    D -->|Draw| F[Airspeed Tape]
    D -->|Draw| G[Altitude Tape]
    D -->|Draw| H[Compass]
```
