import pygame
from abc import ABC, abstractmethod
from core.state import FlightState

class BaseInstrument(ABC):
    """
    Abstract Base Class for all PFD instruments (Horizon, Tapes, Compass).
    """
    
    def __init__(self, x: int, y: int, width: int, height: int):
        self.rect = pygame.Rect(x, y, width, height)
        # Create a dedicated surface for this instrument
        self.surface = pygame.Surface((width, height))

    @abstractmethod
    def update(self, state: FlightState) -> None:
        """
        Process the latest flight state and redraw the instrument's internal surface.
        This is where the instrument-specific logic lives.
        """
        pass

    def draw(self, screen: pygame.Surface) -> None:
        """
        Blit the instrument's surface onto the main screen.
        """
        screen.blit(self.surface, self.rect)
