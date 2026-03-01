import pygame
import math
from ui.base_instrument import BaseInstrument
from core.state import FlightState
from core.constants import Colors

class ArtificialHorizon(BaseInstrument):
    """
    The primary attitude indicator.
    Renders pitch and roll by transforming a large sky/ground surface.
    """
    
    # Configuration Constants
    PIXELS_PER_DEGREE = 5
    HORIZON_SIZE = 2000  # Large enough to cover all rotations/pitches
    
    def __init__(self, x: int, y: int, width: int, height: int):
        super().__init__(x, y, width, height)
        
        # 1. Create the static background (Sky & Ground)
        self.bg_surface = pygame.Surface((self.HORIZON_SIZE, self.HORIZON_SIZE))
        
        # Draw Gradients
        self._draw_background_gradients()
        
        # Anti-aliased Horizon Line (Multiple lines for weight)
        for i in range(-1, 2):
            pygame.draw.aaline(
                self.bg_surface, 
                Colors.TEXT, 
                (0, self.HORIZON_SIZE // 2 + i), 
                (self.HORIZON_SIZE, self.HORIZON_SIZE // 2 + i)
            )

        # 2. Pre-render Pitch Ladder on the bg_surface
        self._draw_pitch_ladder()

    def _draw_background_gradients(self) -> None:
        """Draws professional sky and ground gradients."""
        # Sky Colors
        SKY_TOP = (30, 60, 120)      # Deep Blue
        SKY_HORIZON = (100, 160, 240) # Light Blue
        
        # Ground Colors
        GROUND_HORIZON = (120, 80, 40) # Light Brown
        GROUND_BOTTOM = (40, 30, 20)   # Dark Brown
        
        half = self.HORIZON_SIZE // 2
        
        # Draw Sky Gradient (Top to Horizon)
        for y in range(half):
            ratio = y / half
            # Interpolate
            r = int(SKY_TOP[0] + (SKY_HORIZON[0] - SKY_TOP[0]) * ratio)
            g = int(SKY_TOP[1] + (SKY_HORIZON[1] - SKY_TOP[1]) * ratio)
            b = int(SKY_TOP[2] + (SKY_HORIZON[2] - SKY_TOP[2]) * ratio)
            pygame.draw.line(self.bg_surface, (r, g, b), (0, y), (self.HORIZON_SIZE, y))
            
        # Draw Ground Gradient (Horizon to Bottom)
        for y in range(half, self.HORIZON_SIZE):
            ratio = (y - half) / half
            # Interpolate
            r = int(GROUND_HORIZON[0] + (GROUND_BOTTOM[0] - GROUND_HORIZON[0]) * ratio)
            g = int(GROUND_HORIZON[1] + (GROUND_BOTTOM[1] - GROUND_HORIZON[1]) * ratio)
            b = int(GROUND_HORIZON[2] + (GROUND_BOTTOM[2] - GROUND_HORIZON[2]) * ratio)
            pygame.draw.line(self.bg_surface, (r, g, b), (0, y), (self.HORIZON_SIZE, y))

    def _draw_pitch_ladder(self) -> None:
        """Draws the degree markings on the background surface using anti-aliasing."""
        center_x = self.HORIZON_SIZE // 2
        center_y = self.HORIZON_SIZE // 2
        
        # Draw every 5 degrees
        for deg in range(-90, 95, 5):
            if deg == 0: continue # Skip horizon line
            
            y = center_y - (deg * self.PIXELS_PER_DEGREE)
            width = 40 if deg % 10 == 0 else 20
            
            # Draw Anti-aliased Line (Double weight)
            pygame.draw.aaline(self.bg_surface, Colors.TEXT, (center_x - width, y), (center_x + width, y))
            pygame.draw.aaline(self.bg_surface, Colors.TEXT, (center_x - width, y + 1), (center_x + width, y + 1))
            
            # Draw Labels for 10-degree increments
            if deg % 10 == 0:
                self.draw_text_with_shadow(
                    self.bg_surface, str(abs(deg)), 
                    center_x + width + 10, y, 
                    size=16, align="left"
                )
                self.draw_text_with_shadow(
                    self.bg_surface, str(abs(deg)), 
                    center_x - width - 10, y, 
                    size=16, align="right"
                )

    def _draw_aircraft_symbol(self) -> None:
        """Draws the fixed yellow 'W' aircraft reference with anti-aliasing."""
        center_x, center_y = self.rect.width // 2, self.rect.height // 2
        wing_len = 40
        gap = 20
        yellow = (255, 255, 0)
        
        # Left Wing (Thick AA wings)
        for i in range(-1, 2):
            pygame.draw.aaline(self.surface, yellow, (center_x - wing_len - gap, center_y + i), (center_x - gap, center_y + i))
        
        # Right Wing
        for i in range(-1, 2):
            pygame.draw.aaline(self.surface, yellow, (center_x + gap, center_y + i), (center_x + wing_len + gap, center_y + i))
        
        # Center 'Nose' Square
        pygame.draw.rect(self.surface, yellow, (center_x - 4, center_y - 4, 8, 8))

    def _draw_slip_indicator(self, slip: float) -> None:
        """Draws the slip/skid indicator with anti-aliasing."""
        center_x = self.rect.width // 2
        bottom_y = self.rect.height - 40
        width = 80
        
        # Draw background scale
        pygame.draw.aaline(self.surface, Colors.TEXT, (center_x - width//2, bottom_y), (center_x + width//2, bottom_y))
        pygame.draw.aaline(self.surface, Colors.TEXT, (center_x - 5, bottom_y - 10), (center_x - 5, bottom_y + 10))
        pygame.draw.aaline(self.surface, Colors.TEXT, (center_x + 5, bottom_y - 10), (center_x + 5, bottom_y + 10))
        
        # Calculate Ball Position (Clamped to scale)
        ball_x = center_x + (slip * (width // 2))
        ball_x = max(center_x - width//2, min(center_x + width//2, ball_x))
        
        # Draw the Ball
        pygame.draw.rect(self.surface, Colors.TEXT, (ball_x - 4, bottom_y - 4, 8, 8))

    def _update_logic(self, state: FlightState) -> None:
        """
        Rotates and shifts the horizon based on state.
        """
        # 1. Clear instrument surface
        self.surface.fill(Colors.BLACK)
        
        # 2. Calculate Pitch Offset
        pitch_offset = state.pitch * self.PIXELS_PER_DEGREE
        
        # 3. Rotate the background
        rotated_bg = pygame.transform.rotate(self.bg_surface, -state.roll)
        
        # 4. Calculate blit position to keep rotation centered
        rot_rect = rotated_bg.get_rect()
        
        rad_roll = math.radians(state.roll)
        off_x = pitch_offset * math.sin(rad_roll)
        off_y = pitch_offset * math.cos(rad_roll)
        
        dest_x = (self.rect.width // 2) - (rot_rect.width // 2) + off_x
        dest_y = (self.rect.height // 2) - (rot_rect.height // 2) + off_y
        
        # 5. Blit the world
        self.surface.blit(rotated_bg, (dest_x, dest_y))
        
        # 6. Draw fixed overlays
        self._draw_aircraft_symbol()
        self._draw_slip_indicator(state.slip)
