import threading
import time
import sys
from core.state import FlightState
from game_io.mock_sensor import MockSensor
from ui.renderer import PFDRenderer

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
