import threading
from dataclasses import dataclass, field

@dataclass
class FlightState:
    """
    The Single Source of Truth (SSOT) for the aircraft's flight data.
    
    Thread-safety is managed via the internal lock.
    Units:
        - pitch, roll, heading: Degrees (Standard for display logic, though internals might use radians)
        - altitude: Feet
        - airspeed: Knots
        - vertical_speed: Feet per minute
        - slip: Relative unit (-1.0 to 1.0)
    """
    pitch: float = 0.0
    roll: float = 0.0
    heading: float = 0.0
    altitude: float = 0.0
    airspeed: float = 0.0
    vertical_speed: float = 0.0
    slip: float = 0.0
    
    # Private lock for thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def update(self, **kwargs) -> None:
        """
        Safely updates flight parameters.
        
        Args:
            **kwargs: Key-value pairs of attributes to update.
        """
        with self._lock:
            for key, value in kwargs.items():
                if hasattr(self, key) and key != "_lock":
                    setattr(self, key, float(value))

    def get_snapshot(self) -> 'FlightState':
        """
        Returns a thread-safe copy of the current state for rendering.
        """
        with self._lock:
            return FlightState(
                pitch=self.pitch,
                roll=self.roll,
                heading=self.heading,
                altitude=self.altitude,
                airspeed=self.airspeed,
                vertical_speed=self.vertical_speed,
                slip=self.slip
            )
