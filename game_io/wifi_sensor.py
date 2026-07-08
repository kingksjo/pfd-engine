import socket
from typing import Dict, Optional

from .sensor_interface import SensorInterface

# Matches AbleTechPFDProject.ino -> txData():
#   "$PFD,IAS,TAS,Mach,alt_ft,VSI,roll,pitch,hdg,OAT,QNH,pres,ts_ms\n"
PACKET_PREFIX = "$PFD,"
PACKET_FIELD_COUNT = 12


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

    def connect(self) -> bool:
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Allow reusing the port to avoid "Address already in use" errors on restarts
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("0.0.0.0", self.port))
            self._sock.settimeout(self.timeout)
            print(f"[INFO] WifiSensor: Bound to 0.0.0.0:{self.port} successfully.")
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
            # Normal if packet frequency is lower than timeout or during temporary disconnects
            return {}
        except Exception as e:
            print(f"[ERROR] WifiSensor: read failed: {e}")
            return {}

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
