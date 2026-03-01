# Instrument Reference

This document details the rendering logic, mathematical models, and visual implementation of the "Six-Pack" instruments.

## 1. Artificial Horizon (Attitude Indicator)
Located in `ui/instruments/horizon.py`.

### Rendering Model: "Moving World"
Instead of moving a line or an aircraft symbol, we transform a large **2000x2000 pixel "World Surface"**.
1.  **Vertical Shift (Pitch):** The world surface is offset vertically by `pitch * PIXELS_PER_DEGREE` (5px/deg).
2.  **Rotation (Roll):** The entire offset surface is rotated by `-roll` degrees around its center.
3.  **Centering:** A trigonometric calculation ensures the pivot point remains centered in the viewport, regardless of pitch/roll combination.

### Visual Features
*   **Sky/Ground Gradient:** A vertical gradient simulates atmospheric depth (Deep Blue -> Light Blue -> Horizon -> Light Brown -> Dark Brown).
*   **Pitch Ladder:** Pre-rendered anti-aliased degree markings every 5°.
*   **Slip/Skid Indicator:** An inclinometer ("The Ball") integrated at the bottom of the display reacts to lateral acceleration (simulated via `slip` state).

## 2. Vertical Tape Instruments
Located in `ui/instruments/tape.py`.

### Rendering Model: "Sliding Window"
1.  **Pre-Rendering:** A very tall surface (e.g., 50,000 pixels for Altitude) is generated once during initialization. It contains all tick marks and numbers.
2.  **Viewport Clipping:** During each frame, we calculate a `blit_y` offset based on the current value. The tall surface is blitted at this negative offset, creating the illusion of a sliding scale.

### Airspeed Indicator (ASI)
*   **Scale:** 0 to 500 Knots.
*   **Resolution:** 4.0 pixels per knot.
*   **Safety Bands:**
    *   **Red (0-45):** Stall Range.
    *   **Green (45-120):** Normal Operating Range.
    *   **Yellow (120-150):** Caution Range.
    *   **Red Line (150):** Never Exceed Speed (Vne).

### Altimeter (ALT)
*   **Scale:** 0 to 50,000 Feet.
*   **Resolution:** 0.2 pixels per foot.
*   **Visual:** Right-aligned tick marks.

## 3. Compass Tape (Heading Indicator)
Located in `ui/instruments/compass.py`.

### Rendering Model: "Wrapping Scale"
*   **Scale:** A horizontal strip 1440 pixels wide (360 degrees * 4px/degree).
*   **Wrapping Logic:** A buffer of the start (0-360) is appended to the end of the surface. This allows the viewport to seamlessly slide from 359° back to 0° without visual interruption.
*   **Cardinals:** Displays 'N', 'E', 'S', 'W' instead of numbers at 0, 90, 180, 270.

## 4. Vertical Speed Indicator (VSI)
Located in `ui/instruments/vsi.py`.

### Rendering Model: "Dynamic Bar"
*   **Concept:** A rate-of-change indicator, not a position indicator.
*   **Scale:** Linear mapping from -2000 to +2000 Feet Per Minute (FPM).
*   **Visual:** A colored bar grows from the center zero-point. Green for climb (positive), Red for descent (negative).

## 5. Visual Effects
Located in `ui/renderer.py`.

### Glass Vignette Overlay
*   **Purpose:** Simulates the physical glass screen and bezel of an avionics unit.
*   **Implementation:** A radial gradient surface (transparent center -> dark corners) is blitted over the entire screen at the end of the render pass.
*   **Toggle:** Can be enabled/disabled at runtime with the **'G'** key.
