import pygame
from ui.base_instrument import BaseInstrument
from core.state import FlightState
from core.constants import Colors

class CompassTape(BaseInstrument):
    """
    A horizontal sliding compass tape for the bottom of the PFD.
    Handles 360-degree wrapping logic.
    """
    
    PIXELS_PER_DEGREE = 4
    
    def __init__(self, x: int, y: int, width: int, height: int):
        super().__init__(x, y, width, height)
        
        # Pre-render a 360-degree scale + extra width for seamless wrapping
        # We render 0 to 360, then append a bit of the start at the end.
        self.tape_width = 360 * self.PIXELS_PER_DEGREE
        self.full_tape = pygame.Surface((self.tape_width + width, height))
        self.full_tape.fill(Colors.BEZEL)
        
        self._draw_scale()

    def _draw_scale(self) -> None:
        """Draws the degree markings and cardinal points."""
        font = pygame.font.SysFont("Arial", 16, bold=True)
        cardinals = {0: "N", 90: "E", 180: "S", 270: "W"}
        
        # Draw 0 to 360 degrees
        for deg in range(361):
            x = deg * self.PIXELS_PER_DEGREE
            
            # Major ticks every 10 degrees, minor every 5
            if deg % 10 == 0:
                pygame.draw.line(self.full_tape, Colors.TEXT, (x, 0), (x, 15), 2)
                
                # Labels
                label_text = cardinals.get(deg % 360, str(deg % 360))
                label_surf = font.render(label_text, True, Colors.TEXT)
                label_rect = label_surf.get_rect(centerx=x, top=18)
                self.full_tape.blit(label_surf, label_rect)
            elif deg % 5 == 0:
                pygame.draw.line(self.full_tape, Colors.TEXT, (x, 0), (x, 8), 1)

        # Mirror the start of the tape at the end for seamless wrapping
        # This allows us to blit a window starting at 359 and still see 0, 1, 2...
        end_buffer = self.full_tape.subsurface((0, 0, self.rect.width, self.rect.height)).copy()
        self.full_tape.blit(end_buffer, (self.tape_width, 0))

    def _draw_pointer(self) -> None:
        """Draws the fixed center lubber line/pointer."""
        center_x = self.rect.width // 2
        # Yellow triangle pointer
        points = [(center_x - 10, 0), (center_x + 10, 0), (center_x, 15)]
        pygame.draw.polygon(self.surface, (255, 255, 0), points)
        
        # Digital Heading Box
        font = pygame.font.SysFont("Arial", 18, bold=True)
        pygame.draw.rect(self.surface, Colors.BLACK, (center_x - 25, self.rect.height - 25, 50, 22))
        pygame.draw.rect(self.surface, Colors.TEXT, (center_x - 25, self.rect.height - 25, 50, 22), 1)

    def _update_logic(self, state: FlightState) -> None:
        """Slides the compass tape based on current heading."""
        self.surface.fill(Colors.BEZEL)
        
        # 1. Normalize heading
        heading = state.heading % 360
        
        # 2. Calculate blit position
        # We want 'heading' to be at the center of our width.
        # target_x_on_tape = heading * PIXELS_PER_DEGREE
        # blit_x = (width / 2) - target_x_on_tape
        blit_x = (self.rect.width // 2) - (heading * self.PIXELS_PER_DEGREE)
        
        # 3. Blit the tape
        self.surface.blit(self.full_tape, (blit_x, 0))
        
        # 4. Static elements
        self._draw_pointer()
        
        # Digital value
        font = pygame.font.SysFont("Arial", 18, bold=True)
        h_str = f"{int(heading):03d}"
        val_surf = font.render(h_str, True, Colors.GREEN)
        val_rect = val_surf.get_rect(center=(self.rect.width // 2, self.rect.height - 14))
        self.surface.blit(val_surf, val_rect)
