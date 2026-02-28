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
        self.bg_surface.fill(Colors.SKY)
        # Draw ground on the bottom half
        pygame.draw.rect(
            self.bg_surface, 
            Colors.GROUND, 
            (0, self.HORIZON_SIZE // 2, self.HORIZON_SIZE, self.HORIZON_SIZE // 2)
        )
        # Horizon Line
        pygame.draw.line(
            self.bg_surface, 
            Colors.TEXT, 
            (0, self.HORIZON_SIZE // 2), 
            (self.HORIZON_SIZE, self.HORIZON_SIZE // 2), 
            3
        )

        # 2. Pre-render Pitch Ladder on the bg_surface
        self._draw_pitch_ladder()

    def _draw_pitch_ladder(self) -> None:
        """Draws the degree markings on the background surface."""
        center_x = self.HORIZON_SIZE // 2
        center_y = self.HORIZON_SIZE // 2
        font = pygame.font.SysFont("Arial", 16, bold=True)
        
        # Draw every 5 degrees
        for deg in range(-90, 95, 5):
            if deg == 0: continue # Skip horizon line
            
            y = center_y - (deg * self.PIXELS_PER_DEGREE)
            width = 40 if deg % 10 == 0 else 20
            
            # Draw Line
            pygame.draw.line(self.bg_surface, Colors.TEXT, (center_x - width, y), (center_x + width, y), 2)
            
            # Draw Labels for 10-degree increments
            if deg % 10 == 0:
                label = font.render(str(abs(deg)), True, Colors.TEXT)
                self.bg_surface.blit(label, (center_x + width + 5, y - 10))
                self.bg_surface.blit(label, (center_x - width - 25, y - 10))

    def _draw_aircraft_symbol(self) -> None:
        """Draws the fixed yellow 'W' aircraft reference."""
        center_x, center_y = self.rect.width // 2, self.rect.height // 2
        wing_len = 40
        gap = 20
        thickness = 4
        yellow = (255, 255, 0)
        
        # Left Wing
        pygame.draw.line(self.surface, yellow, (center_x - wing_len - gap, center_y), (center_x - gap, center_y), thickness)
        # Right Wing
        pygame.draw.line(self.surface, yellow, (center_x + gap, center_y), (center_x + wing_len + gap, center_y), thickness)
        # Center 'Nose'
        pygame.draw.rect(self.surface, yellow, (center_x - 4, center_y - 4, 8, 8))

    def update(self, state: FlightState) -> None:
        """
        Rotates and shifts the horizon based on state.
        """
        # 1. Clear instrument surface
        self.surface.fill(Colors.BLACK)
        
        # 2. Calculate Pitch Offset
        # A positive pitch (nose up) means the horizon moves DOWN relative to the plane.
        pitch_offset = state.pitch * self.PIXELS_PER_DEGREE
        
        # 3. Rotate the background
        # Note: We rotate by -roll because if the plane banks right, the world appears to tilt left.
        rotated_bg = pygame.transform.rotate(self.bg_surface, -state.roll)
        
        # 4. Calculate blit position to keep rotation centered
        # This is the tricky part: Pygame's rotate expands the surface.
        rot_rect = rotated_bg.get_rect()
        
        # Center of the rotated surface needs to align with the PFD center,
        # but offset by the pitch.
        # We need to rotate the pitch offset vector as well!
        # In a real PFD, the pitch scale is often locked to the horizon's rotation.
        
        # Simplified Pitch + Roll integration:
        # We blit the center of the rotated_bg at (center_x, center_y + pitch_offset)
        dest_x = (self.rect.width // 2) - (rot_rect.width // 2)
        
        # Rotation math for the pitch offset:
        # The pitch shift happens ALONG the vertical axis of the rotated world.
        rad_roll = math.radians(state.roll)
        off_x = pitch_offset * math.sin(rad_roll)
        off_y = pitch_offset * math.cos(rad_roll)
        
        dest_y = (self.rect.height // 2) - (rot_rect.height // 2) + off_y
        dest_x += off_x
        
        # 5. Blit the world
        self.surface.blit(rotated_bg, (dest_x, dest_y))
        
        # 6. Draw fixed overlays
        self._draw_aircraft_symbol()
