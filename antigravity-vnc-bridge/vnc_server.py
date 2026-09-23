"""
Antigravity RFB VNC Server (RFC 6143 compliant)
Allows standard VNC viewers (RealVNC, TightVNC, TigerVNC, iOS/Android VNC, macOS Screen Sharing)
to connect directly to port 5900 and view Antigravity or the entire desktop.
"""

import sys
import os
import socket
import struct
import threading
import time
import ctypes
from ctypes import wintypes
from typing import Optional, Tuple
from PIL import Image

try:
    from agent_bridge import capture_frame, find_antigravity_window, attach_to_default_desktop
except ImportError:
    from .agent_bridge import capture_frame, find_antigravity_window, attach_to_default_desktop

# Win32 input injection
user32 = ctypes.windll.user32
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
KEYEVENTF_KEYUP = 0x0002


class RFBClientHandler(threading.Thread):
    def __init__(self, client_sock: socket.socket, addr: Tuple[str, int], server: "VNCServer"):
        super().__init__(daemon=True)
        self.sock = client_sock
        self.addr = addr
        self.server = server
        self.running = True
        self.shared = False
        self.encodings = []
        self.last_buttons = 0

    def send_all(self, data: bytes):
        self.sock.sendall(data)

    def recv_exact(self, n: int) -> bytes:
        data = bytearray()
        while len(data) < n:
            packet = self.sock.recv(n - len(data))
            if not packet:
                raise ConnectionResetError("Client disconnected")
            data.extend(packet)
        return bytes(data)

    def run(self):
        print(f"[VNC] Connection accepted from {self.addr}")
        try:
            # 1. ProtocolVersion Handshake
            self.send_all(b"RFB 003.008\n")
            client_version = self.recv_exact(12)
            print(f"[VNC] Client version: {client_version.strip()}")

            # 2. Security Handshake
            # 1 security type: Type 1 (None)
            self.send_all(bytes([1, 1]))
            chosen_security = self.recv_exact(1)[0]
            if chosen_security != 1:
                print(f"[VNC] Unsupported security type: {chosen_security}")
                return

            # SecurityResult: 0 = OK (uint32)
            self.send_all(struct.pack(">I", 0))

            # 3. ClientInit
            client_init = self.recv_exact(1)
            self.shared = bool(client_init[0])

            # 4. ServerInit
            # Grab initial frame to determine dimensions
            frame = self.server.get_current_frame()
            width, height = frame.size

            # Pixel Format: 32bpp, 24 depth, big-endian=0, true-color=1,
            # max(R)=255, max(G)=255, max(B)=255, shift(R)=16, shift(G)=8, shift(B)=0, 3 pad
            pix_format = struct.pack(
                ">BBBBHHHBBBxxx",
                32, 24, 0, 1,
                255, 255, 255,
                16, 8, 0
            )
            name = b"Antigravity Overwatch VNC"
            server_init = struct.pack(">HH", width, height) + pix_format + struct.pack(">I", len(name)) + name
            self.send_all(server_init)
            print(f"[VNC] Initialized session: {width}x{height}")

            # 5. Message Loop
            while self.running and self.server.running:
                msg_type_buf = self.recv_exact(1)
                msg_type = msg_type_buf[0]

                if msg_type == 0:
                    # SetPixelFormat: 3 pad + 16 bytes format
                    _ = self.recv_exact(19)

                elif msg_type == 2:
                    # SetEncodings: 1 pad + 2 bytes count + count*4 bytes
                    pad = self.recv_exact(1)
                    count = struct.unpack(">H", self.recv_exact(2))[0]
                    enc_data = self.recv_exact(count * 4)
                    self.encodings = [struct.unpack(">i", enc_data[i*4:(i+1)*4])[0] for i in range(count)]

                elif msg_type == 3:
                    # FramebufferUpdateRequest: 1 incremental + 2 x + 2 y + 2 w + 2 h
                    req = self.recv_exact(9)
                    incremental, rx, ry, rw, rh = struct.unpack(">BHHHH", req)
                    self.handle_framebuffer_update_request(incremental, rx, ry, rw, rh)

                elif msg_type == 4:
                    # KeyEvent: 1 down-flag, 2 pad, 4 key
                    key_data = self.recv_exact(7)
                    if self.server.allow_input:
                        down, _, key = struct.unpack(">B2sI", key_data)
                        self.handle_key_event(bool(down), key)

                elif msg_type == 5:
                    # PointerEvent: 1 button-mask, 2 x, 2 y
                    ptr_data = self.recv_exact(5)
                    if self.server.allow_input:
                        btn_mask, px, py = struct.unpack(">BHH", ptr_data)
                        self.handle_pointer_event(btn_mask, px, py)

                elif msg_type == 6:
                    # ClientCutText: 3 pad, 4 length, text
                    _ = self.recv_exact(3)
                    t_len = struct.unpack(">I", self.recv_exact(4))[0]
                    _ = self.recv_exact(t_len)

        except (ConnectionResetError, BrokenPipeError, socket.timeout):
            pass
        except Exception as e:
            print(f"[VNC] Client handler error: {e}")
        finally:
            self.running = False
            try:
                self.sock.close()
            except Exception:
                pass
            self.server.remove_client(self)
            print(f"[VNC] Connection closed for {self.addr}")

    def handle_framebuffer_update_request(self, incremental: int, rx: int, ry: int, rw: int, rh: int):
        frame = self.server.get_current_frame()
        fw, fh = frame.size

        # Clamp update area
        x = min(rx, fw - 1) if fw > 0 else 0
        y = min(ry, fh - 1) if fh > 0 else 0
        w = min(rw, fw - x) if fw > x else fw
        h = min(rh, fh - y) if fh > y else fh

        if w <= 0 or h <= 0:
            w, h = fw, fh
            x, y = 0, 0

        # Crop frame if partial rect requested
        if (x, y, w, h) != (0, 0, fw, fh):
            sub_img = frame.crop((x, y, x + w, y + h))
        else:
            sub_img = frame

        # Convert to 32bpp BGRA raw bytes
        # PIL 'RGBA' or 'RGB' conversion:
        if sub_img.mode != "RGBA":
            sub_img = sub_img.convert("RGBA")
        
        # Win32 GDI uses BGRA
        r, g, b, a = sub_img.split()
        bgra_img = Image.merge("RGBA", (b, g, r, a))
        pixel_bytes = bgra_img.tobytes()

        # FramebufferUpdate header:
        # msg_type=0, pad=0, num_rectangles=1
        header = struct.pack(">BxH", 0, 1)
        # Rect header: x, y, width, height, encoding=0 (Raw)
        rect_hdr = struct.pack(">HHHHl", x, y, w, h, 0)

        self.send_all(header + rect_hdr + pixel_bytes)

    def handle_pointer_event(self, btn_mask: int, px: int, py: int):
        """Translates VNC mouse events into Windows input."""
        try:
            # Offset position if capturing Antigravity window
            ox, oy = 0, 0
            if self.server.capture_mode == "antigravity":
                win = find_antigravity_window()
                if win:
                    ox, oy = win[1][0], win[1][1]
            
            target_x = ox + px
            target_y = oy + py
            user32.SetCursorPos(target_x, target_y)

            # Detect mouse button changes (bit 0: Left, bit 1: Middle, bit 2: Right)
            diff = btn_mask ^ self.last_buttons
            if diff & 1:
                flags = MOUSEEVENTF_LEFTDOWN if (btn_mask & 1) else MOUSEEVENTF_LEFTUP
                user32.mouse_event(flags, 0, 0, 0, 0)
            if diff & 2:
                flags = MOUSEEVENTF_MIDDLEDOWN if (btn_mask & 2) else MOUSEEVENTF_MIDDLEUP
                user32.mouse_event(flags, 0, 0, 0, 0)
            if diff & 4:
                flags = MOUSEEVENTF_RIGHTDOWN if (btn_mask & 4) else MOUSEEVENTF_RIGHTUP
                user32.mouse_event(flags, 0, 0, 0, 0)

            self.last_buttons = btn_mask
        except Exception as e:
            print(f"[VNC] Mouse event error: {e}")

    def handle_key_event(self, down: bool, key: int):
        """Translates basic keys to Windows virtual keys."""
        try:
            # Handle common ASCII and navigation keys
            vk = 0
            if 0x20 <= key <= 0x7E:
                # Direct char / VK
                vk = user32.VkKeyScanW(key) & 0xFF
            elif key == 0xFF08: # Backspace
                vk = 0x08
            elif key == 0xFF09: # Tab
                vk = 0x09
            elif key == 0xFF0D: # Return / Enter
                vk = 0x0D
            elif key == 0xFF1B: # Escape
                vk = 0x1B
            elif key == 0xFF51: # Left
                vk = 0x25
            elif key == 0xFF52: # Up
                vk = 0x26
            elif key == 0xFF53: # Right
                vk = 0x27
            elif key == 0xFF54: # Down
                vk = 0x28

            if vk > 0:
                flags = 0 if down else KEYEVENTF_KEYUP
                user32.keybd_event(vk, 0, flags, 0)
        except Exception as e:
            print(f"[VNC] Key event error: {e}")


class VNCServer(threading.Thread):
    def __init__(self, host: str = "0.0.0.0", port: int = 5900, capture_mode: str = "antigravity", allow_input: bool = True):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.capture_mode = capture_mode
        self.allow_input = allow_input
        self.running = False
        self.clients = []
        self._lock = threading.Lock()
        self._cached_frame = None
        self._cached_time = 0
        self._cache_ttl = 0.05 # 20 FPS max capture rate

    def get_current_frame(self) -> Image.Image:
        now = time.time()
        if self._cached_frame is None or (now - self._cached_time) > self._cache_ttl:
            self._cached_frame = capture_frame(mode=self.capture_mode)
            self._cached_time = now
        return self._cached_frame

    def remove_client(self, client: RFBClientHandler):
        with self._lock:
            if client in self.clients:
                self.clients.remove(client)

    def run(self):
        self.running = True
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            server_sock.bind((self.host, self.port))
            server_sock.listen(5)
            server_sock.settimeout(1.0)
            print(f"[VNC] Server listening on {self.host}:{self.port} (mode: {self.capture_mode}, input: {self.allow_input})")

            while self.running:
                try:
                    client_sock, addr = server_sock.accept()
                    handler = RFBClientHandler(client_sock, addr, self)
                    with self._lock:
                        self.clients.append(handler)
                    handler.start()
                except socket.timeout:
                    continue
                except Exception as e:
                    if self.running:
                        print(f"[VNC] Accept error: {e}")
                    break
        except Exception as e:
            print(f"[VNC] Server failed to bind: {e}")
        finally:
            self.running = False
            try:
                server_sock.close()
            except Exception:
                pass
            with self._lock:
                for c in self.clients:
                    c.running = False
            print("[VNC] Server stopped.")

    def stop(self):
        self.running = False


if __name__ == "__main__":
    server = VNCServer(port=5900, capture_mode="antigravity", allow_input=True)
    server.start()
    print("VNC Server is running in background. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
