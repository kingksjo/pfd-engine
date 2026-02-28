from abc import ABC, abstractmethod
from typing import Dict

class SensorInterface(ABC):
    """
    Abstract Base Class for all flight data sensors.
    Enforces a common contract for both hardware drivers and simulation mocks.
    """
    
    @abstractmethod
    def connect(self) -> bool:
        """
        Establish connection to the physical or simulated device.
        Returns:
            bool: True if connection successful, False otherwise.
        """
        pass

    @abstractmethod
    def read(self) -> Dict[str, float]:
        """
        Poll the sensor for the latest data frame.
        Returns:
            Dict[str, float]: Key-value pairs matching FlightState fields.
        """
        pass

    @abstractmethod
    def close(self) -> None:
        """
        Cleanly close the connection.
        """
        pass
