import pygame
from ui.base_instrument import BaseInstrument
from core.state import FlightState
from core.constants import Colors, FlightLimits

class TapeInstrument(BaseInstrument):
    """
    A reusable vertical sliding tape for Airspeed or Altitude.
    """
    
    def __init__(self, x: int, y: int, width: int, height: int, 
                 label: str, pixels_per_unit: float, 
                 major_step: int, minor_step: int, 
                 is_altitude: bool = False):
        super().__init__(x, y, width, height)
        self.label = label
        self.pixels_per_unit = pixels_per_unit
        self.major_step = major_step
        self.minor_step = minor_step
        self.is_altitude = is_altitude
        
        # Determine the range to pre-render
        # For Altitude: 0 to 50,000 ft
        # For Airspeed: 0 to 400 knots
        self.max_val = 50000 if is_altitude else 500
        self.tape_height = self.max_val * self.pixels_per_unit + height
        
        # 1. Create the long tape surface
        self.tape_surface = pygame.Surface((width, self.tape_height))
        self.tape_surface.fill(Colors.BEZEL)
        
        # 2. Pre-render the scale
        self._draw_scale()
        
        # 3. Draw Color Bands (Airspeed Only)
        if not self.is_altitude:
            self._draw_speed_bands()

    def _draw_speed_bands(self) -> None:
        """Draws V-speed color bands on the airspeed tape."""
        band_width = 6
        x_start = self.rect.width - band_width
        
        # Helper to draw a band from speed_min to speed_max
        def draw_band(min_spd, max_spd, color):
            # Calculate Y positions (remember Y is inverted on our tape surface)
            # Top of band (higher speed) corresponds to SMALLER Y value
            y_top = self.tape_height - (max_spd * self.pixels_per_unit) - (self.rect.height // 2)
            y_bottom = self.tape_height - (min_spd * self.pixels_per_unit) - (self.rect.height // 2)
            height = y_bottom - y_top
            
            pygame.draw.rect(self.tape_surface, color, (x_start, y_top, band_width, height))
            
        # Stall Range (0 to Vs) - Red
        draw_band(0, FlightLimits.V_S, Colors.DANGER)
        
        # Normal Range (Vs to Vno) - Green
        draw_band(FlightLimits.V_S, FlightLimits.V_NO, Colors.GREEN)
        
        # Caution Range (Vno to Vne) - Yellow
        draw_band(FlightLimits.V_NO, FlightLimits.V_NE, Colors.WARNING)
        
        # Never Exceed Line (Vne) - Thick Red Line
        y_vne = self.tape_height - (FlightLimits.V_NE * self.pixels_per_unit) - (self.rect.height // 2)
        pygame.draw.rect(self.tape_surface, Colors.DANGER, (x_start, y_vne, band_width, 4))

    def _draw_scale(self) -> None:
        """Draws tick marks and numbers onto the long tape surface."""
        font = pygame.font.SysFont("Arial", 18, bold=True)
        center_x = self.rect.width // 2
        
        # Draw from bottom (0) to top (max)
        # In Pygame, Y increases downward. So 0 is at the bottom of the surface.
        for val in range(0, self.max_val + self.minor_step, self.minor_step):
            # Calculate Y position relative to the bottom of the tape
            y = self.tape_height - (val * self.pixels_per_unit) - (self.rect.height // 2)
            
            is_major = (val % self.major_step == 0)
            tick_width = 20 if is_major else 10
            
            # Align ticks to the side (Left for Airspeed, Right for Altitude)
            if not self.is_altitude: # Left side tape, ticks on the right
                x_start = self.rect.width - tick_width
                x_end = self.rect.width
            else: # Right side tape, ticks on the left
                x_start = 0
                x_end = tick_width
            
            pygame.draw.line(self.tape_surface, Colors.TEXT, (x_start, y), (x_end, y), 2)
            
            # Draw Numbers for Major Steps
            if is_major:
                label_surf = font.render(str(val), True, Colors.TEXT)
                label_rect = label_surf.get_rect()
                if not self.is_altitude:
                    label_rect.right = self.rect.width - 25
                else:
                    label_rect.left = 25
                label_rect.centery = y
                self.tape_surface.blit(label_surf, label_rect)

    def _draw_pointer(self, current_val: float) -> None:
        """Draws the fixed readout box in the center."""
        center_y = self.rect.height // 2
        box_h = 40
        box_w = self.rect.width
        
        # Draw background box
        pygame.draw.rect(self.surface, Colors.BLACK, (0, center_y - box_h//2, box_w, box_h))
        pygame.draw.rect(self.surface, Colors.TEXT, (0, center_y - box_h//2, box_w, box_h), 2)
        
        # Draw the text
        font = pygame.font.SysFont("Arial", 22, bold=True)
        val_str = f"{int(current_val)}"
        text_surf = font.render(val_str, True, Colors.GREEN)
        text_rect = text_surf.get_rect(center=(self.rect.width // 2, center_y))
        self.surface.blit(text_surf, text_rect)

    def _update_logic(self, state: FlightState) -> None:
        """
        Slides the tape based on current airspeed/altitude.
        """
        # 1. Get current value
        current_val = state.altitude if self.is_altitude else state.airspeed
        
        # 2. Clear instrument surface
        self.surface.fill(Colors.BEZEL)
        
        # 3. Calculate blit position
        # We want current_val to be at the center_y of our instrument.
        target_pos_on_tape = self.tape_height - (current_val * self.pixels_per_unit) - (self.rect.height // 2)
        
        # We want this target_pos to appear at y = self.rect.height // 2
        blit_y = (self.rect.height // 2) - target_pos_on_tape
        
        self.surface.blit(self.tape_surface, (0, blit_y))
        
        # 4. Draw static pointer box
        self._draw_pointer(current_val)
        
        # 5. Draw Top Label (Label for the tape)
        font = pygame.font.SysFont("Arial", 14, bold=True)
        label_surf = font.render(self.label, True, Colors.TEXT)
        self.surface.blit(label_surf, (5, 5))
