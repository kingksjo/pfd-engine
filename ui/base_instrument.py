import pygame
import time
from abc import ABC, abstractmethod
from typing import Tuple, Optional
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
        
        # Initialize Fonts (Verdana preferred, fallback to Arial)
        self.fonts = {}
        
    def _get_font(self, size: int, bold: bool = True) -> pygame.font.Font:
        """Cache and retrieve fonts."""
        key = (size, bold)
        if key not in self.fonts:
            try:
                self.fonts[key] = pygame.font.SysFont("Verdana", size, bold=bold)
            except:
                self.fonts[key] = pygame.font.SysFont("Arial", size, bold=bold)
        return self.fonts[key]

    def draw_text_with_shadow(self, surface: pygame.Surface, text: str, 
                              x: int, y: int, size: int = 16, 
                              color: Tuple[int, int, int] = Colors.TEXT,
                              align: str = "center") -> None:
        """
        Draws text with a black drop shadow for high readability.
        align: 'center', 'left', 'right', 'topleft', etc.
        """
        font = self._get_font(size)
        
        # Render Shadow (Black)
        shadow_surf = font.render(text, True, Colors.BLACK)
        shadow_rect = shadow_surf.get_rect()
        
        # Render Main Text
        text_surf = font.render(text, True, color)
        text_rect = text_surf.get_rect()
        
        # Calculate Position
        # We assume x, y is the anchor point based on 'align'
        if align == "center":
            text_rect.center = (x, y)
        elif align == "right":
            text_rect.right = x
            text_rect.centery = y
        elif align == "left":
            text_rect.left = x
            text_rect.centery = y
        elif align == "topleft":
            text_rect.topleft = (x, y)
            
        # Align shadow slightly offset
        shadow_rect.topleft = (text_rect.x + 2, text_rect.y + 2)
        
        # Blit
        surface.blit(shadow_surf, shadow_rect)
        surface.blit(text_surf, text_rect)

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
        self.draw_text_with_shadow(self.surface, "DATA FAIL", 
                                   self.rect.width // 2, self.rect.height // 2, 
                                   size=20, color=Colors.DANGER)
