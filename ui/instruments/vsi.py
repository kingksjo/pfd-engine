import pygame
from ui.base_instrument import BaseInstrument
from core.state import FlightState
from core.constants import Colors

class VerticalSpeedIndicator(BaseInstrument):
    """
    Vertical Speed Indicator (VSI).
    Displays climb/descent rate in feet per minute (FPM).
    Scale: -2000 to +2000 FPM.
    """
    
    RANGE = 2000.0
    
    def __init__(self, x: int, y: int, width: int, height: int):
        super().__init__(x, y, width, height)
        self.pixels_per_fpm = (height / 2) / self.RANGE

    def _draw_scale(self) -> None:
        """Draws the static background scale for the VSI."""
        self.surface.fill(Colors.BEZEL)
        center_y = self.rect.height // 2
        font = pygame.font.SysFont("Arial", 12, bold=True)
        
        # Scale markers
        for val in [-2000, -1000, -500, 0, 500, 1000, 2000]:
            y = center_y - (val * self.pixels_per_fpm)
            pygame.draw.line(self.surface, Colors.TEXT, (0, y), (10, y), 2)
            
            # Label
            if val != 0:
                label = font.render(str(abs(val // 100)), True, Colors.TEXT)
                self.surface.blit(label, (12, y - 6))

    def _update_logic(self, state: FlightState) -> None:
        """Draws the moving bar based on current vertical speed."""
        self._draw_scale()
        center_y = self.rect.height // 2
        
        # Clamp VSI to range for display
        vsi = max(-self.RANGE, min(self.RANGE, state.vertical_speed))
        
        # Vertical Position
        target_y = center_y - (vsi * self.pixels_per_fpm)
        
        # Draw the Indicator Bar
        bar_color = Colors.GREEN if vsi >= 0 else Colors.DANGER
        pygame.draw.rect(
            self.surface, 
            bar_color, 
            (0, min(center_y, target_y), self.rect.width // 2, abs(center_y - target_y))
        )
        
        # Pointer Triangle
        pygame.draw.polygon(self.surface, Colors.TEXT, [
            (self.rect.width, target_y),
            (self.rect.width - 10, target_y - 8),
            (self.rect.width - 10, target_y + 8)
        ])
        
        # Digital Value at the bottom
        font = pygame.font.SysFont("Arial", 14, bold=True)
        v_str = f"{int(abs(vsi))}"
        val_surf = font.render(v_str, True, Colors.TEXT)
        self.surface.blit(val_surf, (self.rect.width // 2 - 10, self.rect.height - 20))
