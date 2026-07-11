import pygame
from typing import List
from core.state import FlightState
from core.constants import Colors
from .base_instrument import BaseInstrument
from .telemetry import TelemetryScreen

class PFDRenderer:
    """
    The main rendering engine.
    Manages the Pygame window, the event loop, the collection of instruments,
    and the real-time telemetry panel.
    """
    
    def __init__(self, state: FlightState, width: int = 1024, height: int = 700,
                 sensor_type: str = "Simulation", show_telemetry: bool = True):
        self.state = state
        self.pfd_width = width
        self.pfd_height = height
        self.height = height
        self.show_telemetry = show_telemetry
        self.sensor_type = sensor_type
        
        # Calculate actual window width including telemetry side panel if enabled
        self.width = self.pfd_width + 400 if self.show_telemetry else self.pfd_width
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
        
        # Create Glass Vignette Overlay (sized to cover PFD only)
        self._create_vignette(self.pfd_width, self.pfd_height)
        
        # Create Metal Bezel Overlay (sized to cover PFD only)
        self._create_bezel(self.pfd_width, self.pfd_height)
        
        # Initialize Telemetry Panel
        self.telemetry = TelemetryScreen(
            x=self.pfd_width, y=0, width=400, height=self.height,
            sensor_type=self.sensor_type
        )

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

    def _create_bezel(self, width: int, height: int) -> None:
        """Creates a metal-looking bezel overlay with 3D bevels and screws."""
        self.bezel_surf = pygame.Surface((width, height), pygame.SRCALPHA)
        self.bezel_surf.fill((0, 0, 0, 0))
        
        thickness = 35
        base_color = (120, 130, 140)
        highlight = (180, 190, 200)
        shadow = (60, 70, 80)
        
        # 1. Fill borders
        pygame.draw.rect(self.bezel_surf, base_color, (0, 0, width, thickness)) # Top
        pygame.draw.rect(self.bezel_surf, base_color, (0, height - thickness, width, thickness)) # Bottom
        pygame.draw.rect(self.bezel_surf, base_color, (0, 0, thickness, height)) # Left
        pygame.draw.rect(self.bezel_surf, base_color, (width - thickness, 0, thickness, height)) # Right
        
        # 2. Bevels (Highlights)
        pygame.draw.line(self.bezel_surf, highlight, (0, 0), (width, 0), 2) # Top outer
        pygame.draw.line(self.bezel_surf, highlight, (0, 0), (0, height), 2) # Left outer
        pygame.draw.line(self.bezel_surf, highlight, (thickness, height - thickness), (width - thickness, height - thickness), 2) # Bottom inner
        pygame.draw.line(self.bezel_surf, highlight, (width - thickness, thickness), (width - thickness, height - thickness), 2) # Right inner
        
        # 3. Bevels (Shadows)
        pygame.draw.line(self.bezel_surf, shadow, (0, height - 2), (width, height - 2), 2) # Bottom outer
        pygame.draw.line(self.bezel_surf, shadow, (width - 2, 0), (width - 2, height), 2) # Right outer
        pygame.draw.line(self.bezel_surf, shadow, (thickness, thickness), (width - thickness, thickness), 2) # Top inner
        pygame.draw.line(self.bezel_surf, shadow, (thickness, thickness), (thickness, height - thickness), 2) # Left inner
        
        # 4. Screws
        screw_base = (100, 110, 120)
        screw_shadow = (40, 45, 50)
        screw_hl = (160, 170, 180)
        centers = [
            (thickness // 2, thickness // 2),
            (width - thickness // 2, thickness // 2),
            (thickness // 2, height - thickness // 2),
            (width - thickness // 2, height - thickness // 2)
        ]
        for cx, cy in centers:
            # Shadow
            pygame.draw.circle(self.bezel_surf, screw_shadow, (cx + 1, cy + 1), 7)
            # Base
            pygame.draw.circle(self.bezel_surf, screw_base, (cx, cy), 7)
            # Slot
            pygame.draw.line(self.bezel_surf, screw_shadow, (cx - 4, cy - 4), (cx + 4, cy + 4), 2)
            pygame.draw.line(self.bezel_surf, screw_hl, (cx - 4, cy - 3), (cx + 4, cy + 5), 1)

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
            f"VIGNETTE: {'ON' if self.show_vignette else 'OFF'} (Toggle 'G')",
            f"TELEMETRY: {'ON' if self.show_telemetry else 'OFF'} (Toggle 'T')"
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
                    # Re-adjust telemetry panel dimensions
                    self.telemetry.rect.x = self.width - 400
                    self.telemetry.rect.height = self.height
                    self.telemetry.surface = pygame.Surface((self.telemetry.rect.width, self.height))
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_g:
                        self.show_vignette = not self.show_vignette
                    elif event.key == pygame.K_t:
                        self.show_telemetry = not self.show_telemetry
                        # Update window width dynamically
                        self.width = self.pfd_width + 400 if self.show_telemetry else self.pfd_width
                        self.screen = pygame.display.set_mode(
                            (self.width, self.height),
                            pygame.RESIZABLE | pygame.DOUBLEBUF
                        )
                        self.telemetry.rect.x = self.pfd_width
            
            # 2. State Snapshot (Thread Safety)
            current_state = self.state.get_snapshot()
            
            # 3. Record snapshot to telemetry database (even if panel is hidden)
            self.telemetry.record_state(current_state)
            
            # 4. Clear Screen
            self.screen.fill(Colors.BLACK)
            
            # 5. Update & Draw Instruments
            for instrument in self.instruments:
                instrument.update(current_state)
                instrument.draw(self.screen)
            
            # 6. Draw Glass Vignette (Optional, over PFD only)
            if self.show_vignette:
                self.screen.blit(self.vignette_surf, (0, 0))
                
            # 7. Draw Metal Bezel (over PFD only)
            self.screen.blit(self.bezel_surf, (0, 0))
                
            # 8. Debug Overlay
            self._draw_debug_overlay(current_state)

            # 9. Draw Telemetry Dashboard (if enabled)
            if self.show_telemetry:
                self.telemetry.draw(self.screen)

            # 10. Flip & Tick
            pygame.display.flip()
            self.clock.tick(60)
            
        # Export CSV data at the end of the session
        self.telemetry.export_csv()
        pygame.quit()
        return False

