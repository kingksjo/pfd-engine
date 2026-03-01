import pygame
import time
from abc import ABC, abstractmethod
from core.state import FlightState
from core.constants import Colors, Timing

class BaseInstrument(ABC):
    """
    Abstract Base Class for all PFD instruments (Horizon, Tapes, Compass).
    """
    
    def __init__(self, x: int, y: int, width: int, height: int):
        self.rect = pygame.Rect(x, y, width, height)
        # Create a dedicated surface for this instrument
        self.surface = pygame.Surface((width, height))

    @abstractmethod
    def _update_logic(self, state: FlightState) -> None:
        """Instrument-specific update logic."""
        pass

    def update(self, state: FlightState) -> None:
        """
        Check for sensor timeout before running update logic.
        """
        if time.time() - state.last_update > Timing.SENSOR_TIMEOUT:
            self.draw_failure_flag()
        else:
            self._update_logic(state)

    def draw(self, screen: pygame.Surface) -> None:
        """
        Blit the instrument's surface onto the main screen.
        """
        screen.blit(self.surface, self.rect)

    def draw_failure_flag(self) -> None:
        """
        Draws a large Red X across the instrument to indicate data timeout.
        """
        self.surface.fill(Colors.BLACK)
        
        # Draw Red X
        pygame.draw.line(self.surface, Colors.DANGER, (0, 0), (self.rect.width, self.rect.height), 3)
        pygame.draw.line(self.surface, Colors.DANGER, (self.rect.width, 0), (0, self.rect.height), 3)
        
        # Add "DATA FAIL" Text
        font = pygame.font.SysFont("Arial", 16, bold=True)
        text = font.render("DATA FAIL", True, Colors.DANGER)
        text_rect = text.get_rect(center=(self.rect.width // 2, self.rect.height // 2))
        self.surface.blit(text, text_rect)
