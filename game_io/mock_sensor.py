import math
import time
from typing import Dict
from .sensor_interface import SensorInterface

class MockSensor(SensorInterface):
    """
    Simulates flight dynamics for testing without hardware.
    Generates smooth sine waves for attitude and altitude.
    """

    def __init__(self):
        self.start_time = 0.0
        self.connected = False

    def connect(self) -> bool:
        self.start_time = time.time()
        self.connected = True
        return True

    def read(self) -> Dict[str, float]:
        if not self.connected:
            return {}

        t = time.time() - self.start_time
        
        # Physics Simulation Logic
        # Pitch: Gentle oscillation +/- 5 degrees
        pitch = 5.0 * math.sin(t * 0.5)
        
        # Roll: Banking turn +/- 20 degrees
        roll = 20.0 * math.sin(t * 0.2)
        
        # Heading: Constant turn rate
        heading = (t * 5.0) % 360.0
        
        # Altitude: Slow climb/descent around 5000ft
        altitude = 5000.0 + (500.0 * math.sin(t * 0.1))
        
        # Airspeed: Fluctuation around 120 knots
        airspeed = 120.0 + (10.0 * math.cos(t * 0.3))
        
        # Vertical Speed: Derivative of altitude (approx)
        # d/dt(500sin(0.1t)) = 50 * cos(0.1t)
        # Scale for visibility
        vsi = 500.0 * math.cos(t * 0.1)

        return {
            "pitch": pitch,
            "roll": roll,
            "heading": heading,
            "altitude": altitude,
            "airspeed": airspeed,
            "vertical_speed": vsi,
            "slip": 0.0
        }

    def close(self) -> None:
        self.connected = False
