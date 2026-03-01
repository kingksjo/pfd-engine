import pygame
from typing import List
from core.state import FlightState
from core.constants import Colors
from .base_instrument import BaseInstrument

class PFDRenderer:
    """
    The main rendering engine.
    Manages the Pygame window, the event loop, and the collection of instruments.
    """
    
    def __init__(self, state: FlightState, width: int = 800, height: int = 600):
        self.state = state
        self.width = width
        self.height = height
        self.running = False
        self.show_vignette = True
        self.instruments: List[BaseInstrument] = []

        # Pygame Setup
        pygame.init()
        # Use RESIZABLE and DOUBLEBUF for better window compatibility
        self.screen = pygame.display.set_mode(
            (self.width, self.height), 
            pygame.RESIZABLE | pygame.DOUBLEBUF
        )
        pygame.display.set_caption("Glass Cockpit PFD - Aerospace Engine")
        self.clock = pygame.time.Clock()
        
        # Font for debug overlay
        self.debug_font = pygame.font.SysFont("Consolas", 14)
        
        # Create Glass Vignette Overlay
        self._create_vignette(self.width, self.height)

    def _create_vignette(self, width: int, height: int) -> None:
        """Creates a radial gradient surface for the glass effect."""
        self.vignette_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        center_x, center_y = width // 2, height // 2
        max_dist = (center_x**2 + center_y**2) ** 0.5
        
        # Faster approach: Create a small gradient and scale it up
        grad_size = 256
        grad_surf = pygame.Surface((grad_size, grad_size), pygame.SRCALPHA)
        for y in range(grad_size):
            for x in range(grad_size):
                # Distance from center (0 to 1)
                dx = (x - grad_size/2) / (grad_size/2)
                dy = (y - grad_size/2) / (grad_size/2)
                dist = (dx*dx + dy*dy) ** 0.5
                
                if dist > 0.7:
                    alpha = min(255, int((dist - 0.7) * 3 * 255))
                    grad_surf.set_at((x, y), (0, 0, 0, alpha))
        
        self.vignette_surf = pygame.transform.smoothscale(grad_surf, (width, height))

    def add_instrument(self, instrument: BaseInstrument) -> None:
        self.instruments.append(instrument)

    def _draw_debug_overlay(self, state: FlightState) -> None:
        """Helper to verify data flow before graphics are perfect."""
        debug_text = [
            f"PITCH: {state.pitch:.2f}",
            f"ROLL:  {state.roll:.2f}",
            f"HDG:   {state.heading:.0f}",
            f"ALT:   {state.altitude:.0f} ft",
            f"IAS:   {state.airspeed:.0f} kts",
            f"FPS:   {self.clock.get_fps():.1f}",
            f"VIGNETTE: {'ON' if self.show_vignette else 'OFF'} (Toggle 'G')"
        ]
        
        y_offset = 10
        for line in debug_text:
            text_surf = self.debug_font.render(line, True, Colors.GREEN)
            self.screen.blit(text_surf, (10, y_offset))
            y_offset += 20

    def run(self) -> bool:
        """
        The Main Loop.
        Strict 60 FPS target.
        Returns:
            bool: False if the user requested to quit.
        """
        self.running = True
        
        while self.running:
            # 1. Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.VIDEORESIZE:
                    # Update screen size if user drags window
                    self.width, self.height = event.w, event.h
                    self.screen = pygame.display.set_mode(
                        (self.width, self.height), 
                        pygame.RESIZABLE | pygame.DOUBLEBUF
                    )
                    # Recreate vignette for new size
                    self._create_vignette(self.width, self.height)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_g:
                        self.show_vignette = not self.show_vignette
            
            # 2. State Snapshot (Thread Safety)
            current_state = self.state.get_snapshot()
            
            # 3. Clear Screen
            self.screen.fill(Colors.BLACK)
            
            # 4. Update & Draw Instruments
            for instrument in self.instruments:
                instrument.update(current_state)
                instrument.draw(self.screen)
            
            # 5. Draw Glass Vignette (Optional)
            if self.show_vignette:
                self.screen.blit(self.vignette_surf, (0, 0))
                
            # 6. Debug Overlay
            self._draw_debug_overlay(current_state)

            # 7. Flip & Tick
            pygame.display.flip()
            self.clock.tick(60)
            
        pygame.quit()
        return False
