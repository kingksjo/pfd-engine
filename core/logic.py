import math

class ComplementaryFilter:
    """
    Implements a Complementary Filter for sensor fusion.
    Combines high-pass filtered gyroscope data (fast response)
    with low-pass filtered accelerometer data (stable baseline).
    
    Formula: angle = alpha * (angle + gyro * dt) + (1 - alpha) * accel
    """
    
    def __init__(self, alpha: float = 0.98):
        self.alpha = alpha
        self.current_value = 0.0

    def filter(self, raw_accel: float, gyro_rate: float, dt: float) -> float:
        """
        Updates the filter and returns the smoothed value.
        
        Args:
            raw_accel: The absolute angle from accelerometer/magnetometer.
            gyro_rate: The rate of change from the gyroscope.
            dt: Time delta since last update.
        """
        self.current_value = (self.alpha * (self.current_value + gyro_rate * dt) +
                              (1.0 - self.alpha) * raw_accel)
        return self.current_value

def normalize_heading(heading: float) -> float:
    """Ensures heading stays within [0, 360)."""
    return heading % 360.0

def calculate_vsi(alt_change: float, dt: float) -> float:
    """Calculates Vertical Speed in Feet Per Minute."""
    if dt <= 0:
        return 0.0
    # alt_change (ft) / dt (sec) * 60 (sec/min)
    return (alt_change / dt) * 60.0
