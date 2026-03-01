import threading
import time
from dataclasses import dataclass, field

@dataclass
class FlightState:
    """
    The Single Source of Truth (SSOT) for the aircraft's flight data.
    """
    pitch: float = 0.0
    roll: float = 0.0
    heading: float = 0.0
    altitude: float = 0.0
    airspeed: float = 0.0
    vertical_speed: float = 0.0
    slip: float = 0.0
    last_update: float = field(default_factory=time.time)
    
    # Private lock for thread safety
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def update(self, **kwargs) -> None:
        """
        Safely updates flight parameters and the timestamp.
        """
        with self._lock:
            self.last_update = time.time()
            for key, value in kwargs.items():
                if hasattr(self, key) and key != "_lock":
                    setattr(self, key, float(value))

    def get_snapshot(self) -> 'FlightState':
        """
        Returns a thread-safe copy of the current state.
        """
        with self._lock:
            return FlightState(
                pitch=self.pitch,
                roll=self.roll,
                heading=self.heading,
                altitude=self.altitude,
                airspeed=self.airspeed,
                vertical_speed=self.vertical_speed,
                slip=self.slip,
                last_update=self.last_update
            )
