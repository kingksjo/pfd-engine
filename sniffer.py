"""
Raw IP sniffer on Windows Mobile Hotspot adapter (192.168.137.1)
Captures ALL incoming IP packets to see where the ESP32 (192.168.137.248)
is actually sending its UDP telemetry packets right now.
"""
import socket
import struct
import time

HOST = "192.168.137.1"

def main():
    print(f"[SNIFFER] Binding raw socket to {HOST}...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_IP)
        s.bind((HOST, 0))
        s.setsockopt(socket.IPPROTO_IP, socket.IP_HDRINCL, 1)
        # Turn on promiscuous mode on Windows
        s.ioctl(socket.SIO_RCVALL, socket.RCVALL_ON)
        print("[SNIFFER] Promiscuous mode ON. Listening for packets from 192.168.137.248 (Ctrl+C to stop)...")
    except Exception as e:
        print(f"[SNIFFER ERROR] Could not start raw socket (might require Administrator): {e}")
        return

    start_time = time.time()
    packet_count = 0
    try:
        while time.time() - start_time < 8.0:
            raw_data, addr = s.recvfrom(65535)
            if addr[0] == "192.168.137.248":
                packet_count += 1
                # Parse IP header
                ip_header = raw_data[0:20]
                iph = struct.unpack('!BBHHHBBH4s4s', ip_header)
                version_ihl = iph[0]
                ihl = version_ihl & 0xF
                iph_length = ihl * 4
                protocol = iph[6]
                s_addr = socket.inet_ntoa(iph[8])
                d_addr = socket.inet_ntoa(iph[9])
                
                if protocol == 17: # UDP
                    u = raw_data[iph_length:iph_length+8]
                    udph = struct.unpack('!HHHH', u)
                    source_port = udph[0]
                    dest_port = udph[1]
                    payload = raw_data[iph_length+8:]
                    preview = payload[:80].decode('ascii', errors='ignore').strip()
                    print(f"[UDP PACKET #{packet_count}] {s_addr}:{source_port} -> {d_addr}:{dest_port} | Payload: {preview}")
                    if packet_count >= 10:
                        break
    except KeyboardInterrupt:
        pass
    finally:
        try:
            s.ioctl(socket.SIO_RCVALL, socket.RCVALL_OFF)
            s.close()
        except Exception:
            pass
    print(f"[SNIFFER] Done. Total packets from ESP32 captured: {packet_count}")

if __name__ == "__main__":
    main()
