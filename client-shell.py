import socks
import socket
import sys
import os
import struct


ONION_ADDRESS = "fe5eq4fk6rts4vztbawz2grey6ktcafzlxvk5jmxjqqjqglvm54bnaid.onion"
ONION_PORT    = 80
PROXY_IP      = "127.0.0.1"
PROXY_PORT    = 6781

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def send_frame(sock, data: bytes):
    sock.sendall(struct.pack('>I', len(data)) + data)

def recv_exact(sock, n: int) -> bytes:
    buf = b''
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed mid-read")
        buf += chunk
    return buf

def recv_frame(sock) -> bytes:
    raw_len = recv_exact(sock, 4)
    length = struct.unpack('>I', raw_len)[0]
    return recv_exact(sock, length)


def create_connection():
    s = socks.socksocket()
    s.set_proxy(socks.SOCKS5, PROXY_IP, PROXY_PORT, rdns=True)
    s.settimeout(60)
    s.connect((ONION_ADDRESS, ONION_PORT))
    return s


def print_progress(current, total, prefix='Progress', length=40):
    if total == 0:
        return
    percent = 100 * (current / float(total))
    filled = int(length * current // total)
    bar = '█' * filled + '-' * (length - filled)
    sys.stdout.write(f'\r{prefix} |{bar}| {percent:.1f}% ({current}/{total} bytes)')
    sys.stdout.flush()



def main():
    print(f"[*] Connecting to {ONION_ADDRESS}:{ONION_PORT} via Tor...")
    try:
        sock = create_connection()
    except Exception as e:
        print(f"[!] Connection failed: {e}")
        sys.exit(1)

    print("[+] Connected.")
    print("[*] Commands: cd <path>, upload <file>, download <file>, exit\n")

    def reconnect():
        nonlocal sock
        print("[*] Reconnecting...")
        try:
            sock.close()
        except Exception:
            pass
        try:
            sock = create_connection()
            print("[+] Reconnected.")
        except Exception as e:
            print(f"[!] Reconnect failed: {e}")
            sock = None

    while True:
        try:
            cmd = input("Shell> ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            break

        if not cmd:
            continue
        if cmd.lower() in ('exit', 'quit'):
            break

        if sock is None:
            reconnect()
            if sock is None:
                continue


        if cmd.startswith("upload "):
            filename = cmd[7:].strip()
            local_path = os.path.join(BASE_DIR, filename)

            if not os.path.isfile(local_path):
                print(f"[!] File not found: {local_path}")
                continue

            try:
                with open(local_path, "rb") as f:
                    file_data = f.read()
                filesize = len(file_data)

                send_frame(sock, cmd.encode())

                response = recv_frame(sock).decode(errors='ignore')
                if "READY" not in response:
                    print(f"[!] Unexpected server response: {response}")
                    continue

                print_progress(0, filesize, prefix='Uploading')
                send_frame(sock, file_data)
                print_progress(filesize, filesize, prefix='Uploading')
                print()

                result = recv_frame(sock).decode(errors='ignore')
                print(f"[+] {result}")

            except Exception as e:
                print(f"\n[!] Upload error: {e}")
                reconnect()


        elif cmd.startswith("download "):
            filename = cmd[9:].strip()

            try:
                send_frame(sock, cmd.encode())

                status = recv_frame(sock).decode(errors='ignore')
                if not status.startswith("EXISTS"):
                    print(f"[!] Server: {status}")
                    continue

                print("[*] Receiving file...")
                file_data = recv_frame(sock)
                filesize = len(file_data)
                print_progress(filesize, filesize, prefix='Downloading')
                print()

                dl_path = os.path.join(BASE_DIR, f"dl_{filename}")
                with open(dl_path, "wb") as f:
                    f.write(file_data)

                print(f"[+] Saved: {dl_path}  ({filesize} bytes)")

            except Exception as e:
                print(f"\n[!] Download error: {e}")
                reconnect()


        else:
            try:
                send_frame(sock, cmd.encode())
                response = recv_frame(sock).decode('utf-8', errors='ignore')
                print(response)
            except Exception as e:
                print(f"[!] Error: {e}")
                reconnect()

    try:
        sock.close()
    except Exception:
        pass
    print("[*] Disconnected.")


if __name__ == "__main__":
    main()
