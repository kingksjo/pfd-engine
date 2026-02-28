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
        self.instruments: List[BaseInstrument] = []

        # Pygame Setup
        pygame.init()
        self.screen = pygame.display.set_mode((self.width, self.height))
        pygame.display.set_caption("Glass Cockpit PFD - Aerospace Engine")
        self.clock = pygame.time.Clock()
        
        # Font for debug overlay
        self.debug_font = pygame.font.SysFont("Consolas", 14)

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
            f"FPS:   {self.clock.get_fps():.1f}"
        ]
        
        y_offset = 10
        for line in debug_text:
            text_surf = self.debug_font.render(line, Colors.GREEN, None)
            self.screen.blit(text_surf, (10, y_offset))
            y_offset += 20

    def run(self) -> None:
        """
        The Main Loop.
        Strict 60 FPS target.
        """
        self.running = True
        
        while self.running:
            # 1. Event Handling
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
            
            # 2. State Snapshot (Thread Safety)
            current_state = self.state.get_snapshot()
            
            # 3. Clear Screen
            self.screen.fill(Colors.BLACK) # Use constant
            
            # 4. Update & Draw Instruments
            for instrument in self.instruments:
                instrument.update(current_state)
                instrument.draw(self.screen)
                
            # 5. Debug Overlay
            self._draw_debug_overlay(current_state)

            # 6. Flip & Tick
            pygame.display.flip()
            self.clock.tick(60)
            
        pygame.quit()
