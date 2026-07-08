## Plan: Wi-Fi UDP Telemetry Support

We will integrate a wireless UDP raw-packet telemetry receiver into the PFD engine. The ESP32 is already pre-configured to operate as a UDP Client transmitting packets when `COMM_MODE` is set to `COMM_WIFI`. The Python app will bind onto a local port as a UDP server to grab these signals.

**Steps**

### Phase 1: Hardware Abstraction Layer Extension
1. Create the wireless sensor listener in game_io/wifi_sensor.py. It will implement the common contract in sensor_interface.py.
2. Use standard socket libraries to bind a UDP socket to host 0.0.0.0 (subscribing to all interfaces) and the target port.
3. Decrypt and decode incoming messages, verifying the packet prefix and length exactly like the serial implementation.
4. Implement fail-safes so that socket timeouts or decoding exceptions return an empty frame, which automatically activates the Red X safety watchdogs in base_instrument.py.

### Phase 2: CLI Options & Mode Routing
5. Modify main.py to accept wireless ports.
6. Add the `--wifi` option to accept a numeric port (defaulting to 5005).
7. Update the sensor router: if `--wifi` is configured, build and attach the UDP sensor module. Otherwise, check for `--port` for serial mode, or fall back to mock emulation.
8. Make main.py write the active local IPs of the matching network adapters to the terminal on startup. This makes it easy to set the `UDP_HOST` parameter in the ESP32 code.

### Phase 3: Documentation Updates
9. Add Wi-Fi configuration details under "Hardware Integration" in system_architecture.md.
10. Update README.MD with instructions on installing dependencies, matching IP addresses, and starting the Python engine in Wi-Fi mode.

**Relevant files**
- game_io/wifi_sensor.py — Create a new sensor class inheriting from the default interface to listen to raw UDP datagrams.
- main.py — Add `--wifi` argument to the arguments parser and logic selection router.
- system_architecture.md — Document the network schema, UDP binding properties, and flow diagrams.
- README.MD — Add instructions on executing `--wifi`.

**Verification**
1. Run syntax verification checks on newly added files.
2. Inject mock UDP datagrams matching the telemetry packet layout in a loop from a clean console and verify the local UI picks up the movements smoothly.
3. Test receiving telemetry live over the local air network by toggling `COMM_MODE` to `COMM_WIFI` in AbleTechPFDProject.ino.

**Decisions**
- The ESP32 is a UDP sender (Client mode), which targets `UDP_HOST` and `UDP_PORT` via `udp.beginPacket`.
- The Python App acts as the UDP Receiver (Server mode), meaning it binds to a specific port on `0.0.0.0` (all interfaces) and listens for incoming datagrams. No explicit host IP has to be entered on the Python command line.
- Connectionless UDP handles dropped packets safely; missing datagrams trigger fail-safes cleanly.