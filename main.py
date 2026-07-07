import argparse
import threading
import time
import sys
from core.state import FlightState
from game_io.mock_sensor import MockSensor
from game_io.hardware_sensor import HardwareSensor
from game_io.sensor_interface import SensorInterface
from ui.renderer import PFDRenderer
from ui.instruments.horizon import ArtificialHorizon
from ui.instruments.tape import TapeInstrument
from ui.instruments.compass import CompassTape
from ui.instruments.vsi import VerticalSpeedIndicator

def sensor_loop(sensor: SensorInterface, state: FlightState, stop_event: threading.Event):
    """
    Background thread acting as the 'Data Thread'.
    Polls the sensor at high frequency (100Hz) and updates the thread-safe state.
    """
    if not sensor.connect():
        print("[ERROR] Failed to connect to sensor!")
        return

    print("[INFO] Sensor thread started (100Hz).")
    
    # Target 100Hz loop
    interval = 1.0 / 100.0
    
    while not stop_event.is_set():
        start_time = time.time()
        
        # Read & Update
        data = sensor.read()
        if data:
            state.update(**data)
        
        # Sleep remainder of interval regardless of whether a frame arrived.
        # Using stop_event.wait() allows instant shutdown responsiveness
        elapsed = time.time() - start_time
        sleep_time = max(0.0, interval - elapsed)
        stop_event.wait(sleep_time)
    
    sensor.close()
    print("[INFO] Sensor thread stopped.")

def build_sensor(args: argparse.Namespace) -> SensorInterface:
    """
    Selects the live hardware sensor (AbleTechPFDProject over serial) when
    --port is given, otherwise falls back to the simulated MockSensor.
    """
    if args.port:
        return HardwareSensor(port=args.port, baud=args.baud)
    return MockSensor()


def main():
    parser = argparse.ArgumentParser(description="Glass Cockpit PFD Engine")
    parser.add_argument(
        "--port", default=None,
        help="Serial port of the AbleTechPFDProject ESP32 (e.g. COM5 or /dev/ttyUSB0). "
             "Omit to run against the simulated MockSensor."
    )
    parser.add_argument(
        "--baud", type=int, default=921600,
        help="Serial baud rate. Must match SERIAL_BAUD in the firmware (default 921600)."
    )
    args = parser.parse_args()

    print("[INFO] Initializing PFD Engine...")
    if args.port:
        print(f"[INFO] Live hardware mode: {args.port} @ {args.baud} baud")
    else:
        print("[INFO] Simulation mode (MockSensor). Pass --port COMx for live hardware.")
    
    # 1. Init Shared State
    state = FlightState()
    sensor = build_sensor(args)
    
    # 2. Start Data Thread
    stop_event = threading.Event()
    data_thread = threading.Thread(
        target=sensor_loop, 
        args=(sensor, state, stop_event), 
        daemon=True
    )
    data_thread.start()
    
    # 3. Start Renderer (Main Thread)
    # Reduced height to 700 to fit within standard screen taskbars
    renderer = PFDRenderer(state, width=1024, height=700)
    
    # --- Instrument Layout (Adjusted for 700 height) ---
    y_top = 30
    instrument_h = 580
    
    # Center: Artificial Horizon
    horizon = ArtificialHorizon(x=212, y=y_top, width=600, height=instrument_h)
    renderer.add_instrument(horizon)
    
    # Left: Airspeed Tape
    speed_tape = TapeInstrument(
        x=110, y=y_top, width=100, height=instrument_h,
        label="ASI (KTS)", pixels_per_unit=4.0, 
        major_step=20, minor_step=10, is_altitude=False
    )
    renderer.add_instrument(speed_tape)
    
    # Right: Altitude Tape
    alt_tape = TapeInstrument(
        x=814, y=y_top, width=100, height=instrument_h,
        label="ALT (FT)", pixels_per_unit=0.2, 
        major_step=500, minor_step=100, is_altitude=True
    )
    renderer.add_instrument(alt_tape)
    
    # Far Right: Vertical Speed Indicator (VSI)
    vsi = VerticalSpeedIndicator(x=916, y=y_top + 100, width=40, height=400)
    renderer.add_instrument(vsi)
    
    # Bottom: Compass Tape
    compass = CompassTape(x=212, y=y_top + instrument_h + 5, width=600, height=60)
    renderer.add_instrument(compass)
    
    try:
        renderer.run()
    except KeyboardInterrupt:
        print("[INFO] KeyboardInterrupt received.")
    except Exception as e:
        print(f"[ERROR] Main loop crashed: {e}")
    finally:
        # Cleanup
        print("[INFO] Shutting down...")
        stop_event.set()
        data_thread.join(timeout=1.0)
        sys.exit(0)

if __name__ == "__main__":
    main()
