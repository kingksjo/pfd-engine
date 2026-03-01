import threading
import time
import sys
from core.state import FlightState
from game_io.mock_sensor import MockSensor
from ui.renderer import PFDRenderer
from ui.instruments.horizon import ArtificialHorizon
from ui.instruments.tape import TapeInstrument

def sensor_loop(state: FlightState, stop_event: threading.Event):
    """
    Background thread acting as the 'Data Thread'.
    Polls the sensor at high frequency (100Hz) and updates the thread-safe state.
    """
    sensor = MockSensor()
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
        
        # Sleep remainder of interval
        elapsed = time.time() - start_time
        sleep_time = max(0.0, interval - elapsed)
        time.sleep(sleep_time)
    
    sensor.close()
    print("[INFO] Sensor thread stopped.")

def main():
    print("[INFO] Initializing PFD Engine...")
    
    # 1. Init Shared State
    state = FlightState()
    
    # 2. Start Data Thread
    stop_event = threading.Event()
    data_thread = threading.Thread(
        target=sensor_loop, 
        args=(state, stop_event), 
        daemon=True
    )
    data_thread.start()
    
    # 3. Start Renderer (Main Thread)
    # We run the GUI on the main thread to avoid OS-level windowing issues.
    renderer = PFDRenderer(state, width=1024, height=768)
    
    # Center: Artificial Horizon
    horizon = ArtificialHorizon(x=212, y=84, width=600, height=600)
    renderer.add_instrument(horizon)
    
    # Left: Airspeed Tape
    # 100px wide, same height as horizon
    speed_tape = TapeInstrument(
        x=110, y=84, width=100, height=600,
        label="IAS (KTS)", pixels_per_unit=4.0, 
        major_step=20, minor_step=10, is_altitude=False
    )
    renderer.add_instrument(speed_tape)
    
    # Right: Altitude Tape
    alt_tape = TapeInstrument(
        x=814, y=84, width=100, height=600,
        label="ALT (FT)", pixels_per_unit=0.2, 
        major_step=500, minor_step=100, is_altitude=True
    )
    renderer.add_instrument(alt_tape)
    
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
