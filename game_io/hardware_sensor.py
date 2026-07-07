import time
from typing import Dict, Optional

import serial

from .sensor_interface import SensorInterface

# Matches AbleTechPFDProject.ino -> txData():
#   "$PFD,IAS,TAS,Mach,alt_ft,VSI,roll,pitch,hdg,OAT,QNH,pres,ts_ms\n"
PACKET_PREFIX = "$PFD,"
PACKET_FIELD_COUNT = 12

# Baud rate must match SERIAL_BAUD in the firmware.
DEFAULT_BAUD = 921600


class HardwareSensor(SensorInterface):
    """
    Reads live flight data from the AbleTechPFDProject ESP32 firmware over
    a serial (USB) connection.

    The firmware's Core-1 display task transmits one ASCII CSV line per
    frame (~50 Hz):

        $PFD,IAS_kts,TAS_kts,Mach,alt_ft,VSI_fpm,roll_deg,pitch_deg,
             hdg_deg,OAT_C,QNH_hPa,pres_hPa,ts_ms

    Only the fields present in FlightState are mapped through; the rest
    (TAS, Mach, OAT, QNH, static pressure, device uptime) are parsed but
    currently unused by the UI.

    Fail-safe: if the serial port cannot be opened, or a read/parse
    fails, `read()` returns an empty dict so the caller's FlightState is
    left untouched. `base_instrument.py` already flags instruments as
    invalid once `state.last_update` goes stale, so no frozen/misleading
    values are ever displayed.
    """

    def __init__(self, port: str, baud: int = DEFAULT_BAUD, timeout: float = 0.2):
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self._ser: Optional[serial.Serial] = None

    def connect(self) -> bool:
        try:
            self._ser = serial.Serial(self.port, self.baud, timeout=self.timeout)
            # Let the ESP32 finish any boot/reset triggered by DTR toggle.
            time.sleep(2.0)
            self._ser.reset_input_buffer()
            return True
        except serial.SerialException as e:
            print(f"[ERROR] HardwareSensor: could not open {self.port}: {e}")
            self._ser = None
            return False

    def read(self) -> Dict[str, float]:
        if self._ser is None or not self._ser.is_open:
            return {}

        try:
            raw = self._ser.readline().decode("ascii", errors="ignore").strip()
        except serial.SerialException as e:
            print(f"[ERROR] HardwareSensor: read failed: {e}")
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
        if self._ser is not None and self._ser.is_open:
            self._ser.close()
        self._ser = None
