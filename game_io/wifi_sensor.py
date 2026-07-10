import socket
import time
from typing import Dict, Optional

from .sensor_interface import SensorInterface

# Matches AbleTechPFDProject.ino -> txData():
#   "$PFD,IAS,TAS,Mach,alt_ft,VSI,roll,pitch,hdg,OAT,QNH,pres,ts_ms\n"
PACKET_PREFIX = "$PFD,"
PACKET_FIELD_COUNT = 12

# How long to wait with zero received packets before printing a diagnostic hint.
SILENCE_WARNING_SEC = 3.0


class WifiSensor(SensorInterface):
    """
    Reads live flight data from the AbleTechPFDProject ESP32 firmware over
    a Wi-Fi connection using UDP packets.

    When COMM_MODE in the firmware is set to COMM_WIFI, the ESP32 acts as a
    UDP client broadcasting telemetry packets to a specified IP:Port.
    This class binds a UDP server socket locally to listen on that Port.

    Fail-safe: if the socket cannot be bound, or reads time out/fail,
    read() returns an empty dict to activate the GUI Red X safety watchdogs.
    """

    def __init__(self, port: int = 5005, timeout: float = 0.2):
        self.port = port
        self.timeout = timeout
        self._sock: Optional[socket.socket] = None
        self._first_packet_seen = False
        self._last_packet_time = 0.0
        self._silence_warned = False

    def connect(self) -> bool:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Allow reusing the port to avoid "Address already in use" errors on restarts
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("0.0.0.0", self.port))
            self._sock.settimeout(self.timeout)
            self._last_packet_time = time.time()
            print(f"[INFO] WifiSensor: Bound to 0.0.0.0:{self.port} successfully. Waiting for ESP32 packets...")
            return True
        except Exception as e:
            print(f"[ERROR] WifiSensor: Failed to bind to port {self.port}: {e}")
            self._sock = None
            return False

    def read(self) -> Dict[str, float]:
        if self._sock is None:
            return {}

        try:
            # Buffer size of 1024 is plenty for a compact ~150 char CSV packet
            data, addr = self._sock.recvfrom(1024)
            raw = data.decode("ascii", errors="ignore").strip()
        except socket.timeout:
            # Normal if packet frequency is lower than timeout or during temporary disconnects.
            # But if we've NEVER received anything and it's been a while, the most likely causes
            # are: wrong UDP_HOST in the firmware, ESP32/PC on different networks, or a firewall
            # blocking inbound UDP to python.exe.
            if not self._first_packet_seen and not self._silence_warned:
                if time.time() - self._last_packet_time > SILENCE_WARNING_SEC:
                    self._silence_warned = True
                    print("[WARN] WifiSensor: no UDP packets received on port "
                          + str(self.port) + " yet. Check that: (1) firmware UDP_HOST "
                          "matches this PC's hotspot IP, (2) COMM_MODE is set to COMM_WIFI "
                          "and re-flashed, (3) Windows Firewall allows inbound UDP for python.exe.")
            return {}
        except Exception as e:
            print(f"[ERROR] WifiSensor: read failed: {e}")
            return {}

        if not self._first_packet_seen:
            self._first_packet_seen = True
            print(f"[INFO] WifiSensor: first packet received from {addr[0]}:{addr[1]}")

        if not raw.startswith(PACKET_PREFIX):
            return {}

        fields = raw[len(PACKET_PREFIX):].split(",")
        if len(fields) != PACKET_FIELD_COUNT:
            return {}

        try:
            ias, tas, mach, alt_ft, vsi_fpm, roll_deg, pitch_deg, hdg_deg, \
                oat_c, qnh_hpa, pres_hpa, ts_ms = (float(f) for f in fields)
        except ValueError:
            return {}

        return {
            "airspeed": ias,
            "altitude": alt_ft,
            "vertical_speed": vsi_fpm,
            "roll": roll_deg,
            "pitch": pitch_deg,
            "heading": hdg_deg,
        }

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
        self._sock = None
