from dataclasses import dataclass

@dataclass(frozen=True)
class Colors:
    """Aviation-standard high-contrast color palette."""
    SKY = (74, 144, 226)    # #4A90E2
    GROUND = (123, 82, 44)   # #7B522C
    TEXT = (255, 255, 255)   # #FFFFFF
    WARNING = (241, 196, 15) # #F1C40F (Yellow)
    DANGER = (231, 76, 60)   # #E74C3C (Red)
    BEZEL = (28, 28, 28)     # #1C1C1C
    BLACK = (0, 0, 0)
    GREEN = (0, 255, 0)

@dataclass(frozen=True)
class AviationUnits:
    """Conversion factors for standard aviation units."""
    # Internal SI -> External Display
    MPS_TO_KNOTS = 1.94384
    METERS_TO_FEET = 3.28084
    PA_TO_INHG = 0.0002953  # Barometric pressure
    
@dataclass(frozen=True)
class FlightLimits:
    """V-speeds and structural limits (Example values)."""
    V_NE = 150.0  # Velocity Never Exceed (Knots)
    V_NO = 120.0  # Structural Cruising Speed
    V_S = 45.0    # Stall Speed

@dataclass(frozen=True)
class Timing:
    """System timing and watchdog thresholds."""
    SENSOR_TIMEOUT = 0.5  # Seconds before data is considered invalid
