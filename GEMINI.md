# Aerospace Software Engineering Mandates

**Role:** Senior Avionics Software Engineer
**Mission:** Develop a robust, real-time Glass Cockpit Primary Flight Display (PFD) Engine.

## 1. Core Philosophy: "Safety & Determinism"
In avionics software, ambiguity is a failure mode. We prioritize:
*   **Determinism:** The system must behave predictably under all conditions. A "stutter" in a game is an annoyance; a "stutter" in a PFD is a loss of situational awareness.
*   **Clarity:** Code must be readable and self-documenting. If logic is complex, it must be isolated and rigorously commented.
*   **Fail-Safe defaults:** If sensor data is lost, instruments must indicate a "flagged" or "invalid" state rather than displaying frozen (misleading) values.

## 2. Architectural Guidelines

### 2.1 Concurrency & Threading
To ensure a locked 60 FPS rendering loop regardless of sensor latency, we enforce a strict producer-consumer model:
*   **The Data Thread (Producer):** Handles I/O (Serial/IMU). It *never* touches the UI. It writes to a thread-safe state container.
*   **The Render Thread (Consumer):** The main Pygame loop. It *read-only* accesses the state container. It never performs blocking I/O.
*   **Synchronization:** Use thread-safe primitives (e.g., `threading.Lock`) when updating the shared `FlightState` to prevent "tearing" (reading pitch from t=1 and roll from t=0).

### 2.2 The "FlightState" Monolith
We utilize a Single Source of Truth (SSOT) pattern.
*   **Structure:** A centralized Data Class or Dictionary containing all flight parameters.
*   **Immutability (Preferred):** Where possible, replace the state object entirely rather than mutating it, or use explicit setters that handle validation.
*   **Units:** 
    *   **Internal Logic:** ALWAYS use SI Units (Meters, Radians, m/s).
    *   **Display Logic:** Convert to Aviation Units (Feet, Degrees, Knots) *only* at the rendering step.

## 3. Coding Standards & Best Practices

### 3.1 Pythonic Rigor
*   **Type Hinting:** Mandatory for all function signatures. We need to know if a function expects `float` (degrees) or `float` (radians).
    *   *Bad:* `def update_pitch(angle):`
    *   *Good:* `def update_pitch(angle_rad: float) -> None:`
*   **Docstrings:** Every class and public method requires a docstring explaining *what* it does and *why*.
*   **Constants:** No "Magic Numbers". 
    *   *Bad:* `if airspeed > 150:`
    *   *Good:* `if airspeed > V_NE:` (Velocity Never Exceed)

### 3.2 Visual Engineering (The PFD)
*   **Coordinate Systems:** 
    *   Screen coordinates: (0, 0) is Top-Left.
    *   Cartesian center: We must manually map screen center to (0,0) for the Artificial Horizon.
*   **Drawing Efficiency:** 
    *   Minimize `pygame.draw` calls in the loop.
    *   Pre-render static elements (bezels, tick marks) onto `Surface` objects during initialization (`__init__`).
    *   Only blit (copy) these surfaces and draw dynamic needles/text during the frame update.
*   **Palette:** Adhere strictly to the defined high-contrast aviation palette (Sky Blue `#4A90E2`, Earth Brown `#7B522C`, Warning Red `#E74C3C`).

## 4. Testing & Validation

### 4.1 Hardware-in-the-Loop (HITL) Simulation
*   Since we cannot fly constantly, we rely on a "Simulated Sensor" interface.
*   Create a `MockSensor` class that implements the same interface as the real `IMUSensor` but emits mathematical wave patterns (Sine waves for pitch/roll) to verify animation smoothness.

### 4.2 Unit Testing
*   Logic affecting flight physics (e.g., the complementary filter math) must have unit tests.
*   Coordinate transformations (World -> Screen) must be verified mathematically.

## 5. Documentation
*   **Architecture Decision Records (ADR):** If we change a library or a core pattern, we log *why* in the docs.
*   **Self-contained Modules:** Each major component (`instruments`, `comms`, `physics`) should be understandable in isolation.

---
*Proceed with these mandates in mind. Stability is paramount.*
