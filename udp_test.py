"""
Minimal UDP listener — confirms whether ANY packets arrive on port 5005.
Run this INSTEAD of main.py to isolate whether the problem is
network/firewall or something in the PFD code.

Press Ctrl+C to stop.
"""
import socket

PORT = 5005

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.bind(("0.0.0.0", PORT))
sock.settimeout(5.0)

print(f"[TEST] Listening on 0.0.0.0:{PORT} ...")
print("[TEST] Waiting for any UDP packet (Ctrl+C to quit)...\n")

while True:
    try:
        data, addr = sock.recvfrom(1024)
        print(f"[RECV] From {addr[0]}:{addr[1]} -> {data[:120]}")
    except socket.timeout:
        print("[....] No packet in last 5s — still waiting...")
    except KeyboardInterrupt:
        print("\n[TEST] Stopped.")
        break

sock.close()
