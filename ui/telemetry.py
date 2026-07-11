import pygame
import time
import os
import csv
import math
from typing import List, Dict, Any, Tuple
from core.state import FlightState
from core.constants import Colors

# Colors for telemetry dashboard
BG_COLOR = (15, 20, 28)       # Deep slate black/obsidian
PANEL_BG = (22, 28, 38)       # Slightly lighter blue-grey for panels
BORDER_COLOR = (45, 55, 72)   # Distinct borders
GRID_COLOR = (30, 40, 55)     # Subdued grid lines
MUTE_TEXT = (140, 150, 165)   # Muted grey-blue for labels
TEXT_COLOR = (240, 245, 255)  # Bright off-white for normal text
CYAN = (0, 230, 230)          # Tech accent color

class TelemetryScreen:
    """
    Manages and renders the flight telemetry panel.
    Tracks flight parameters, displays real-time rolling charts,
    and handles exporting flight data to CSV on shutdown.
    """
    
    def __init__(self, x: int, y: int, width: int, height: int, sensor_type: str = "Simulation"):
        """
        Initializes the telemetry screen panel.
        
        Args:
            x: X-coordinate of the panel's left edge on the screen.
            y: Y-coordinate of the panel's top edge.
            width: Width of the telemetry panel.
            height: Height of the telemetry panel.
            sensor_type: Name/type of the connected sensor (e.g. "Mock", "Serial", "Wi-Fi").
        """
        self.rect = pygame.Rect(x, y, width, height)
        self.surface = pygame.Surface((width, height))
        self.sensor_type = sensor_type
        
        # Flight state history for charting and export
        self.session_data: List[Dict[str, float]] = []
        self.start_time: float = time.time()
        
        # Performance calculation (Hz)
        self.last_hz_time: float = time.time()
        self.samples_since_last_hz: int = 0
        self.current_hz: float = 0.0
        
        # Load fonts
        try:
            self.header_font = pygame.font.SysFont("Verdana", 15, bold=True)
            self.title_font = pygame.font.SysFont("Verdana", 11, bold=True)
            self.label_font = pygame.font.SysFont("Arial", 12, bold=False)
            self.value_font = pygame.font.SysFont("Consolas", 13, bold=True)
            self.big_value_font = pygame.font.SysFont("Consolas", 16, bold=True)
        except Exception:
            # Fallbacks
            self.header_font = pygame.font.SysFont("Arial", 15, bold=True)
            self.title_font = pygame.font.SysFont("Arial", 11, bold=True)
            self.label_font = pygame.font.SysFont("Arial", 12, bold=False)
            self.value_font = pygame.font.SysFont("Arial", 13, bold=True)
            self.big_value_font = pygame.font.SysFont("Arial", 16, bold=True)

    def record_state(self, state: FlightState) -> None:
        """
        Records a new flight state snapshot.
        Tracks execution rate (Hz) and appends data to session log.
        """
        now = time.time()
        elapsed = now - self.start_time
        
        # Calculate update rate (Hz)
        self.samples_since_last_hz += 1
        if now - self.last_hz_time >= 1.0:
            self.current_hz = self.samples_since_last_hz / (now - self.last_hz_time)
            self.samples_since_last_hz = 0
            self.last_hz_time = now

        # Add data snapshot (convert state to dictionary)
        record = {
            "timestamp_unix": now,
            "timestamp_relative": elapsed,
            "pitch": state.pitch,
            "roll": state.roll,
            "heading": state.heading,
            "altitude": state.altitude,
            "airspeed": state.airspeed,
            "vertical_speed": state.vertical_speed,
            "slip": state.slip
        }
        self.session_data.append(record)

    def _draw_chart(self, title: str, y_top: int, height: int,
                    keys: List[str], colors: List[Tuple[int, int, int]],
                    labels: List[str], min_val_default: float, max_val_default: float,
                    dual_axis: bool = False, min_val_default_2: float = 0.0,
                    max_val_default_2: float = 0.0) -> None:
        """
        Helper method to render a rolling telemetry line chart.
        Supports single axis or dual-axis (keys[0] on left axis, keys[1] on right axis).
        """
        x_left = 20
        x_right = self.rect.width - 20
        width = x_right - x_left
        y_bottom = y_top + height
        
        # Draw chart panel
        pygame.draw.rect(self.surface, PANEL_BG, (x_left, y_top, width, height))
        pygame.draw.rect(self.surface, BORDER_COLOR, (x_left, y_top, width, height), 1)
        
        # Draw title
        title_surf = self.title_font.render(title, True, MUTE_TEXT)
        self.surface.blit(title_surf, (x_left, y_top - 17))
        
        # Extract last 150 points for rolling display
        samples = self.session_data[-150:] if len(self.session_data) > 0 else []
        if not samples:
            # Draw placeholder text
            no_data = self.label_font.render("WAITING FOR TELEMETRY DATA...", True, MUTE_TEXT)
            self.surface.blit(no_data, (x_left + width // 2 - no_data.get_width() // 2, y_top + height // 2 - 6))
            return
            
        num_pts = len(samples)
        x_step = width / 150.0  # Align to right side of chart
        
        if not dual_axis:
            # Single-axis logic (Pitch/Roll or Airspeed)
            min_val = min_val_default
            max_val = max_val_default
            
            # Find min/max in current sample buffer
            for key in keys:
                vals = [s[key] for s in samples]
                if vals:
                    min_val = min(min_val, min(vals))
                    max_val = max(max_val, max(vals))
            
            # Pad the range slightly
            val_range = max_val - min_val
            if val_range == 0:
                val_range = 1.0
            min_val -= val_range * 0.05
            max_val += val_range * 0.05
            val_range = max_val - min_val
            
            # Draw horizontal gridlines (25%, 50%, 75%)
            for pct in [0.25, 0.5, 0.75]:
                grid_y = y_top + int(height * pct)
                pygame.draw.line(self.surface, GRID_COLOR, (x_left + 1, grid_y), (x_right - 1, grid_y), 1)
                
            # Draw axis range labels (on the left side)
            min_label = self.value_font.render(f"{int(min_val)}", True, MUTE_TEXT)
            max_label = self.value_font.render(f"{int(max_val)}", True, MUTE_TEXT)
            self.surface.blit(max_label, (x_left + 5, y_top + 2))
            self.surface.blit(min_label, (x_left + 5, y_bottom - min_label.get_height() - 2))
            
            # Plot each key
            for key, color in zip(keys, colors):
                points = []
                for i, s in enumerate(samples):
                    x = x_left + (150 - num_pts + i) * x_step
                    val = s[key]
                    y = y_bottom - ((val - min_val) / val_range) * height
                    points.append((x, y))
                    
                if len(points) >= 2:
                    pygame.draw.aalines(self.surface, color, False, points)
                    
        else:
            # Dual-axis logic (Altitude & VSI)
            key0, key1 = keys[0], keys[1]
            color0, color1 = colors[0], colors[1]
            
            # Key 0 range (Altitude)
            min0 = min_val_default
            max0 = max_val_default
            vals0 = [s[key0] for s in samples]
            if vals0:
                min0 = min(min0, min(vals0))
                max0 = max(max0, max(vals0))
            range0 = max0 - min0
            if range0 == 0: range0 = 1.0
            min0 -= range0 * 0.05
            max0 += range0 * 0.05
            range0 = max0 - min0
            
            # Key 1 range (VSI)
            min1 = min_val_default_2
            max1 = max_val_default_2
            vals1 = [s[key1] for s in samples]
            if vals1:
                min1 = min(min1, min(vals1))
                max1 = max(max1, max(vals1))
            range1 = max1 - min1
            if range1 == 0: range1 = 1.0
            min1 -= range1 * 0.05
            max1 += range1 * 0.05
            range1 = max1 - min1
            
            # Draw horizontal gridlines (25%, 50%, 75%)
            for pct in [0.25, 0.5, 0.75]:
                grid_y = y_top + int(height * pct)
                pygame.draw.line(self.surface, GRID_COLOR, (x_left + 1, grid_y), (x_right - 1, grid_y), 1)
                
            # Draw Key 0 axis range labels (on the left side)
            max0_label = self.value_font.render(f"{int(max0)}ft", True, color0)
            min0_label = self.value_font.render(f"{int(min0)}ft", True, color0)
            self.surface.blit(max0_label, (x_left + 5, y_top + 2))
            self.surface.blit(min0_label, (x_left + 5, y_bottom - min0_label.get_height() - 2))
            
            # Draw Key 1 axis range labels (on the right side)
            max1_label = self.value_font.render(f"{int(max1)}fpm", True, color1)
            min1_label = self.value_font.render(f"{int(min1)}fpm", True, color1)
            self.surface.blit(max1_label, (x_right - max1_label.get_width() - 5, y_top + 2))
            self.surface.blit(min1_label, (x_right - min1_label.get_width() - 5, y_bottom - min1_label.get_height() - 2))
            
            # Plot Key 0 (Altitude)
            points0 = []
            for i, s in enumerate(samples):
                x = x_left + (150 - num_pts + i) * x_step
                val = s[key0]
                y = y_bottom - ((val - min0) / range0) * height
                points0.append((x, y))
            if len(points0) >= 2:
                pygame.draw.aalines(self.surface, color0, False, points0)
                
            # Plot Key 1 (VSI)
            points1 = []
            for i, s in enumerate(samples):
                x = x_left + (150 - num_pts + i) * x_step
                val = s[key1]
                y = y_bottom - ((val - min1) / range1) * height
                points1.append((x, y))
            if len(points1) >= 2:
                pygame.draw.aalines(self.surface, color1, False, points1)

        # Draw legend in the upper-left
        legend_x = x_left + 50 if not dual_axis else x_left + 75
        legend_y = y_top + 5
        for label, color in zip(labels, colors):
            # Legend indicator dot
            pygame.draw.circle(self.surface, color, (legend_x + 4, legend_y + 7), 4)
            # Text
            leg_surf = self.label_font.render(label, True, TEXT_COLOR)
            self.surface.blit(leg_surf, (legend_x + 12, legend_y))
            legend_x += leg_surf.get_width() + 25

    def draw(self, screen: pygame.Surface) -> None:
        """
        Renders the telemetry dashboard layout onto its surface and blits it to the screen.
        """
        # 1. Clear surface
        self.surface.fill(BG_COLOR)
        
        # 2. Draw outer border & left divider line
        pygame.draw.line(self.surface, BORDER_COLOR, (0, 0), (0, self.rect.height), 2)
        
        # 3. Draw Header Title
        hdr_surf = self.header_font.render("FLIGHT TELEMETRY SYSTEM", True, CYAN)
        self.surface.blit(hdr_surf, (20, 15))
        
        # 4. Draw Status Block (Recording indicator + Pulsing dot)
        rec_label = self.label_font.render("RECORDING", True, Colors.GREEN)
        rec_x = self.rect.width - rec_label.get_width() - 35
        self.surface.blit(rec_label, (rec_x, 18))
        
        # Pulsing heartbeat indicator
        pulse_val = math.sin(time.time() * 6.0)
        dot_radius = 4 + int(2 * abs(pulse_val))
        dot_color = (0, 200, 0)
        dot_center = (self.rect.width - 25, 24)
        
        # Outer glow
        pygame.draw.circle(self.surface, (0, 100, 0), dot_center, dot_radius + 2, 1)
        # Inner solid dot
        pygame.draw.circle(self.surface, dot_color, dot_center, 4)
        
        # Divider line under header
        pygame.draw.line(self.surface, BORDER_COLOR, (20, 42), (self.rect.width - 20, 42), 1)
        
        # 5. Session Info Block (2 columns)
        elapsed_sec = time.time() - self.start_time
        mins = int(elapsed_sec // 60)
        secs = elapsed_sec % 60
        
        # Column 1
        self.surface.blit(self.label_font.render("Time Elapsed:", True, MUTE_TEXT), (20, 52))
        time_str = f"{mins:02d}:{secs:04.1f}"
        self.surface.blit(self.value_font.render(time_str, True, TEXT_COLOR), (115, 52))
        
        self.surface.blit(self.label_font.render("Data Samples:", True, MUTE_TEXT), (20, 72))
        samples_str = f"{len(self.session_data)}"
        self.surface.blit(self.value_font.render(samples_str, True, TEXT_COLOR), (115, 72))

        self.surface.blit(self.label_font.render("Log Target:", True, MUTE_TEXT), (20, 92))
        self.surface.blit(self.value_font.render("60 Hz CSV", True, TEXT_COLOR), (115, 92))
        
        # Column 2
        self.surface.blit(self.label_font.render("Sensor Mode:", True, MUTE_TEXT), (210, 52))
        self.surface.blit(self.value_font.render(self.sensor_type, True, CYAN), (300, 52))
        
        self.surface.blit(self.label_font.render("Sample Rate:", True, MUTE_TEXT), (210, 72))
        rate_str = f"{self.current_hz:.1f} FPS"
        self.surface.blit(self.value_font.render(rate_str, True, TEXT_COLOR), (300, 72))
        
        self.surface.blit(self.label_font.render("Log Status:", True, MUTE_TEXT), (210, 92))
        self.surface.blit(self.value_font.render("OK", True, Colors.GREEN), (300, 92))
        
        # 6. Current Values Panel (Grid)
        grid_y = 120
        grid_h = 100
        pygame.draw.rect(self.surface, PANEL_BG, (20, grid_y, self.rect.width - 40, grid_h))
        pygame.draw.rect(self.surface, BORDER_COLOR, (20, grid_y, self.rect.width - 40, grid_h), 1)
        
        # Get latest state if we have data
        latest = self.session_data[-1] if self.session_data else None
        
        if latest:
            # Col 1: Attitude
            self.surface.blit(self.label_font.render("PITCH:", True, MUTE_TEXT), (35, grid_y + 12))
            pitch_surf = self.big_value_font.render(f"{latest['pitch']:+5.1f}°", True, Colors.SKY)
            self.surface.blit(pitch_surf, (90, grid_y + 10))
            
            self.surface.blit(self.label_font.render("ROLL:", True, MUTE_TEXT), (35, grid_y + 34))
            roll_surf = self.big_value_font.render(f"{latest['roll']:+5.1f}°", True, Colors.WARNING)
            self.surface.blit(roll_surf, (90, grid_y + 32))
            
            self.surface.blit(self.label_font.render("HEADING:", True, MUTE_TEXT), (35, grid_y + 56))
            hdg_surf = self.big_value_font.render(f"{latest['heading']:03.0f}°", True, TEXT_COLOR)
            self.surface.blit(hdg_surf, (90, grid_y + 54))

            self.surface.blit(self.label_font.render("SLIP:", True, MUTE_TEXT), (35, grid_y + 78))
            slip_surf = self.big_value_font.render(f"{latest['slip']:+.2f}", True, TEXT_COLOR)
            self.surface.blit(slip_surf, (90, grid_y + 76))
            
            # Col 2: Physics
            self.surface.blit(self.label_font.render("ALTITUDE:", True, MUTE_TEXT), (210, grid_y + 12))
            alt_surf = self.big_value_font.render(f"{int(latest['altitude']):,} ft", True, Colors.GREEN)
            self.surface.blit(alt_surf, (290, grid_y + 10))
            
            self.surface.blit(self.label_font.render("AIRSPEED:", True, MUTE_TEXT), (210, grid_y + 34))
            spd_surf = self.big_value_font.render(f"{int(latest['airspeed'])} kts", True, CYAN)
            self.surface.blit(spd_surf, (290, grid_y + 32))
            
            self.surface.blit(self.label_font.render("VERT SPD:", True, MUTE_TEXT), (210, grid_y + 56))
            vsi_surf = self.big_value_font.render(f"{int(latest['vertical_speed']):+d}", True, TEXT_COLOR)
            self.surface.blit(vsi_surf, (290, grid_y + 54))
        else:
            wait_surf = self.header_font.render("CONNECTING SENSORS...", True, MUTE_TEXT)
            self.surface.blit(wait_surf, (self.rect.width // 2 - wait_surf.get_width() // 2, grid_y + grid_h // 2 - 10))

        # 7. Render Charts
        # Chart 1: Attitude (Pitch / Roll)
        self._draw_chart(
            title="ATTITUDE DYNAMICS (PITCH/ROLL)",
            y_top=255, height=115,
            keys=["pitch", "roll"],
            colors=[Colors.SKY, Colors.WARNING],
            labels=["Pitch", "Roll"],
            min_val_default=-15.0, max_val_default=15.0,
            dual_axis=False
        )
        
        # Chart 2: Altitude & VSI (Dual axis)
        self._draw_chart(
            title="ALTITUDE & CLIMB RATE (FPM)",
            y_top=400, height=115,
            keys=["altitude", "vertical_speed"],
            colors=[Colors.GREEN, TEXT_COLOR],
            labels=["Alt", "VSI"],
            min_val_default=0.0, max_val_default=5000.0,
            dual_axis=True,
            min_val_default_2=-1000.0, max_val_default_2=1000.0
        )
        
        # Chart 3: Airspeed
        self._draw_chart(
            title="AIRSPEED (KNOTS)",
            y_top=545, height=115,
            keys=["airspeed"],
            colors=[CYAN],
            labels=["IAS"],
            min_val_default=0.0, max_val_default=150.0,
            dual_axis=False
        )
        
        # Footer / instruction
        footer_font = pygame.font.SysFont("Arial", 11, italic=True)
        footer_surf = footer_font.render("Press 'T' to toggle Telemetry panel. ESC to exit and export.", True, MUTE_TEXT)
        self.surface.blit(footer_surf, (self.rect.width // 2 - footer_surf.get_width() // 2, self.rect.height - 20))
        
        # 8. Blit panel surface onto the main screen
        screen.blit(self.surface, self.rect)

    def export_csv(self) -> None:
        """
        Exports the recorded session telemetry data to a CSV file.
        Saves files inside a folder named 'telemetry_logs' in the project directory.
        """
        if not self.session_data:
            print("[INFO] Telemetry: No data collected to export.")
            return

        log_dir = "telemetry_logs"
        os.makedirs(log_dir, exist_ok=True)
        
        # Generate filename using local timestamp
        time_str = time.strftime("%Y%m%d_%H%M%S")
        filename = f"telemetry_{time_str}.csv"
        filepath = os.path.join(log_dir, filename)
        
        print(f"[INFO] Telemetry: Exporting {len(self.session_data)} data points to '{filepath}'...")
        
        try:
            with open(filepath, "w", newline="") as csvfile:
                fieldnames = [
                    "Timestamp_Unix",
                    "Timestamp_Relative_Sec",
                    "Pitch_Deg",
                    "Roll_Deg",
                    "Heading_Deg",
                    "Altitude_Ft",
                    "Airspeed_Kts",
                    "Vertical_Speed_Fpm",
                    "Slip"
                ]
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                
                for row in self.session_data:
                    writer.writerow({
                        "Timestamp_Unix": row["timestamp_unix"],
                        "Timestamp_Relative_Sec": round(row["timestamp_relative"], 3),
                        "Pitch_Deg": round(row["pitch"], 3),
                        "Roll_Deg": round(row["roll"], 3),
                        "Heading_Deg": round(row["heading"], 1),
                        "Altitude_Ft": round(row["altitude"], 1),
                        "Airspeed_Kts": round(row["airspeed"], 1),
                        "Vertical_Speed_Fpm": round(row["vertical_speed"], 1),
                        "Slip": round(row["slip"], 3)
                    })
            print(f"[INFO] Telemetry: Successfully exported {len(self.session_data)} rows to '{filepath}'.")
        except Exception as e:
            print(f"[ERROR] Telemetry: Failed to export CSV: {e}")
