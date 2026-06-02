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
        # Using 80% of height for the active range so max limits aren't at the very edge
        self.usable_height = height * 0.8
        self.pixels_per_fpm = (self.usable_height / 2) / self.RANGE

    def _draw_scale(self) -> None:
        """Draws the static background scale for the VSI."""
        self.surface.fill(Colors.BEZEL)
        center_y = self.rect.height // 2
        font = pygame.font.SysFont("Arial", 14, bold=True)
        
        # Left border line (separating from altitude tape)
        pygame.draw.line(self.surface, Colors.TEXT, (0, 0), (0, self.rect.height), 2)
        
        # Center zero line
        pygame.draw.line(self.surface, Colors.TEXT, (0, center_y), (8, center_y), 3)
        
        # Scale markers
        for val in [-2000, -1500, -1000, -500, 500, 1000, 1500, 2000]:
            y = center_y - (val * self.pixels_per_fpm)
            tick_length = 8 if val % 1000 == 0 else 5
            
            pygame.draw.line(self.surface, Colors.TEXT, (0, y), (tick_length, y), 2)
            
            # Label only major ticks (1, 2)
            if val % 1000 == 0:
                label_val = abs(val) // 1000
                label = font.render(str(label_val), True, Colors.TEXT)
                # Position label to the right of the tick
                self.surface.blit(label, (14, y - label.get_height() // 2))

    def _update_logic(self, state: FlightState) -> None:
        """Draws the moving indicator based on current vertical speed."""
        self._draw_scale()
        center_y = self.rect.height // 2
        
        # Clamp VSI to range for display
        vsi = max(-self.RANGE, min(self.RANGE, state.vertical_speed))
        
        # Vertical Position
        target_y = center_y - (vsi * self.pixels_per_fpm)
        
        # Draw the Indicator Column (thin line from center to target)
        col_width = 3
        bar_rect = pygame.Rect(
            0, min(center_y, target_y), 
            col_width, abs(center_y - target_y)
        )
        pygame.draw.rect(self.surface, Colors.GREEN if vsi >= 0 else Colors.TEXT, bar_rect)
        
        # Pointer Triangle (Points left, base on the right)
        pygame.draw.polygon(self.surface, Colors.TEXT, [
            (0, target_y),
            (10, target_y - 8),
            (10, target_y + 8)
        ])
        
        # Digital Value Box at top or bottom (only if |VSI| >= 100)
        if abs(vsi) >= 100:
            font = pygame.font.SysFont("Consolas", 12, bold=True)
            v_str = f"{abs(int(vsi))}"
            val_surf = font.render(v_str, True, Colors.BLACK)
            
            # Box dimensions
            box_w = val_surf.get_width() + 4
            box_h = val_surf.get_height() + 4
            box_x = max(0, self.rect.width - box_w)
            
            # Position box above or below the pointer to not obstruct it
            if vsi > 0:
                box_y = max(0, target_y - box_h - 10)
            else:
                box_y = min(self.rect.height - box_h, target_y + 10)
                
            pygame.draw.rect(self.surface, Colors.TEXT, (box_x, box_y, box_w, box_h))
            self.surface.blit(val_surf, (box_x + 2, box_y + 2))
