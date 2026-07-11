import pygame
import multiprocessing
from typing import List
from core.state import FlightState
from core.constants import Colors
from .base_instrument import BaseInstrument
from .telemetry import TelemetryScreen

def run_telemetry_window(queue: multiprocessing.Queue, sensor_type: str, stop_event: multiprocessing.Event) -> None:
    """
    Runs the telemetry dashboard in a separate OS window/process.
    This function must be at the module level so it can be pickled/spawned on Windows.
    """
    import pygame
    from ui.telemetry import TelemetryScreen
    from core.state import FlightState
    
    # Initialize pygame inside the new process
    pygame.init()
    width, height = 400, 700
    screen = pygame.display.set_mode((width, height))
    pygame.display.set_caption("Flight Telemetry Dashboard")
    clock = pygame.time.Clock()
    
    # Position telemetry panel at (0, 0) relative to its own window surface
    telemetry = TelemetryScreen(0, 0, width, height, sensor_type=sensor_type)
    local_state = FlightState()
    
    running = True
    while running and not stop_event.is_set():
        # Handle events for the telemetry window
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                
        # Drain queue to display latest updates
        new_data = None
        while not queue.empty():
            try:
                new_data = queue.get_nowait()
            except:
                break
                
        if new_data:
            local_state.update(**new_data)
            telemetry.record_state(local_state)
            
        screen.fill((0, 0, 0))
        telemetry.draw(screen)
        pygame.display.flip()
        
        # Keep loop running at 60 FPS
        clock.tick(60)
        
    pygame.quit()


class PFDRenderer:
    """
    The main rendering engine.
    Manages the PFD Pygame window, the event loop, and the collection of instruments.
    Optionally manages a secondary telemetry process/window.
    """
    
    def __init__(self, state: FlightState, width: int = 1024, height: int = 700,
                 sensor_type: str = "Simulation", show_telemetry: bool = False):
        self.state = state
        self.width = width
        self.height = height
        self.running = False
        self.show_vignette = True
        self.instruments: List[BaseInstrument] = []
        self.sensor_type = sensor_type

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
        
        # Create Glass Vignette Overlay (PFD size)
        self._create_vignette(self.width, self.height)
        
        # Create Metal Bezel Overlay (PFD size)
        self._create_bezel(self.width, self.height)
        
        # Backup telemetry object in main process to ensure continuous CSV logging
        self.telemetry = TelemetryScreen(
            x=0, y=0, width=400, height=self.height,
            sensor_type=self.sensor_type
        )
        
        # Telemetry process/window controls
        self.show_telemetry = show_telemetry
        self.telemetry_process = None
        self.telemetry_queue = None
        self.telemetry_stop_event = None

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

    def _start_telemetry_process(self) -> None:
        """Spawns the telemetry dashboard in a separate OS window/process."""
        self.telemetry_queue = multiprocessing.Queue()
        self.telemetry_stop_event = multiprocessing.Event()
        self.telemetry_process = multiprocessing.Process(
            target=run_telemetry_window,
            args=(self.telemetry_queue, self.sensor_type, self.telemetry_stop_event),
            daemon=True
        )
        self.telemetry_process.start()

    def _stop_telemetry_process(self) -> None:
        """Safely stops the telemetry dashboard process."""
        if self.telemetry_process and self.telemetry_process.is_alive():
            self.telemetry_stop_event.set()
            self.telemetry_process.join(timeout=1.0)
            if self.telemetry_process.is_alive():
                self.telemetry_process.terminate()
        self.telemetry_process = None
        self.telemetry_queue = None
        self.telemetry_stop_event = None

    def run(self) -> bool:
        """
        The Main Loop.
        Strict 60 FPS target.
        Returns:
            bool: False if the user requested to quit.
        """
        self.running = True
        
        if self.show_telemetry:
            self._start_telemetry_process()
        
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
                    # Recreate vignette and bezel for PFD size
                    self._create_vignette(self.width, self.height)
                    self._create_bezel(self.width, self.height)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self.running = False
                    elif event.key == pygame.K_g:
                        self.show_vignette = not self.show_vignette
                    elif event.key == pygame.K_t:
                        self.show_telemetry = not self.show_telemetry
                        if self.show_telemetry:
                            self._start_telemetry_process()
                        else:
                            self._stop_telemetry_process()
            
            # Check if telemetry window was closed by the user clicking "X" on it
            if self.show_telemetry and self.telemetry_process and not self.telemetry_process.is_alive():
                self.show_telemetry = False
                self._stop_telemetry_process()
            
            # 2. State Snapshot (Thread Safety)
            current_state = self.state.get_snapshot()
            
            # 3. Record snapshot to main-process telemetry database (always active in background for CSV logging)
            self.telemetry.record_state(current_state)
            
            # 4. Send telemetry data to the separate process if active
            if self.show_telemetry and self.telemetry_queue:
                state_dict = {
                    "pitch": current_state.pitch,
                    "roll": current_state.roll,
                    "heading": current_state.heading,
                    "altitude": current_state.altitude,
                    "airspeed": current_state.airspeed,
                    "vertical_speed": current_state.vertical_speed,
                    "slip": current_state.slip
                }
                try:
                    self.telemetry_queue.put_nowait(state_dict)
                except:
                    pass # Queue is full or closed
            
            # 5. Clear Screen
            self.screen.fill(Colors.BLACK)
            
            # 6. Update & Draw Instruments
            for instrument in self.instruments:
                instrument.update(current_state)
                instrument.draw(self.screen)
            
            # 7. Draw Glass Vignette (Optional)
            if self.show_vignette:
                self.screen.blit(self.vignette_surf, (0, 0))
                
            # 8. Draw Metal Bezel
            self.screen.blit(self.bezel_surf, (0, 0))
                
            # 9. Debug Overlay
            self._draw_debug_overlay(current_state)

            # 10. Flip & Tick
            pygame.display.flip()
            self.clock.tick(60)
            
        # Cleanup
        self._stop_telemetry_process()
        self.telemetry.export_csv()
        pygame.quit()
        return False


