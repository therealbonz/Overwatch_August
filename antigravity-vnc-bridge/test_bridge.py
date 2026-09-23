"""
Automated Verification Test Suite for Antigravity VNC Bridge & Controller
Tests screen capture, session discovery, VNC handshake, Web API, and MCP tools.
"""

import sys
import os
import json
import time
import socket
import struct
import unittest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure bridge directory is on sys.path
BRIDGE_DIR = Path(__file__).parent
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

import agent_bridge
from vnc_server import VNCServer
from web_server import app


class TestAntigravityVNCBridge(unittest.TestCase):

    def test_01_agent_bridge_sessions(self):
        """Test active conversation discovery and transcript access."""
        convs = agent_bridge.list_conversations(limit=5)
        self.assertIsInstance(convs, list)
        self.assertGreater(len(convs), 0, "Should discover at least one conversation")
        
        active_id = agent_bridge.get_active_conversation_id()
        self.assertIsNotNone(active_id)
        print(f"\n[PASS] Discovered {len(convs)} conversations. Active ID: {active_id}")

        # Check transcript
        entries = agent_bridge.get_recent_transcript(active_id, max_steps=5)
        self.assertIsInstance(entries, list)
        print(f"[PASS] Read {len(entries)} transcript entries for active session")

    def test_02_screen_capture(self):
        """Test capturing frame for Antigravity window and monitor."""
        frame = agent_bridge.capture_frame(mode="antigravity")
        self.assertIsNotNone(frame)
        self.assertGreater(frame.width, 100)
        self.assertGreater(frame.height, 100)
        print(f"[PASS] Captured screen frame: {frame.size}, mode={frame.mode}")

    def test_03_web_server_endpoints(self):
        """Test Web API endpoints using TestClient."""
        client = TestClient(app)

        # 1. Index dashboard
        res_idx = client.get("/")
        self.assertEqual(res_idx.status_code, 200)
        self.assertIn("Antigravity Overwatch", res_idx.text)

        # 2. Status API
        res_stat = client.get("/api/status")
        self.assertEqual(res_stat.status_code, 200)
        data = res_stat.json()
        self.assertEqual(data.get("status"), "online")
        self.assertIn("vnc_server", data)
        self.assertIn("web_server", data)

        # 3. Conversations API
        res_conv = client.get("/api/conversations")
        self.assertEqual(res_conv.status_code, 200)
        conv_data = res_conv.json()
        self.assertIn("conversations", conv_data)

        # 4. Screenshot API
        res_shot = client.get("/api/screenshot")
        self.assertEqual(res_shot.status_code, 200)
        self.assertEqual(res_shot.headers["content-type"], "image/jpeg")
        self.assertGreater(len(res_shot.content), 1000)
        print("[PASS] Web server endpoints verified: /, /api/status, /api/conversations, /api/screenshot")

    def test_04_vnc_rfb_handshake(self):
        """Test RFB VNC protocol handshake on port 5909 (test port)."""
        test_port = 5909
        vnc = VNCServer(port=test_port, capture_mode="antigravity", allow_input=False)
        vnc.start()
        time.sleep(0.3)

        try:
            # Connect TCP client
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2.0)
            sock.connect(("127.0.0.1", test_port))

            # Step 1: Read protocol version
            ver = sock.recv(12)
            self.assertEqual(ver, b"RFB 003.008\n")

            # Step 2: Send client version
            sock.sendall(b"RFB 003.008\n")

            # Step 3: Receive security types (1 count, type 1 = None)
            sec_count = sock.recv(1)[0]
            sec_types = sock.recv(sec_count)
            self.assertIn(1, sec_types)

            # Step 4: Choose None security
            sock.sendall(bytes([1]))

            # Step 5: SecurityResult
            res = struct.unpack(">I", sock.recv(4))[0]
            self.assertEqual(res, 0) # 0 = OK

            # Step 6: ClientInit (shared=1)
            sock.sendall(bytes([1]))

            # Step 7: ServerInit
            server_init_hdr = sock.recv(24) # 2 w + 2 h + 16 pixfmt + 4 namelen
            w, h = struct.unpack(">HH", server_init_hdr[:4])
            self.assertGreater(w, 0)
            self.assertGreater(h, 0)

            sock.close()
            print(f"[PASS] RFB VNC server handshake verified on port {test_port} ({w}x{h})")
        finally:
            vnc.stop()

    def test_05_mcp_server_protocol(self):
        """Test MCP JSON-RPC protocol initialization and tool listing."""
        mcp_path = Path(r"C:\Users\Brendhann\.gemini\config\plugins\vnc-plugin\mcp_server.py")
        self.assertTrue(mcp_path.exists())

        import subprocess
        p = subprocess.Popen(
            [sys.executable, str(mcp_path)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # 1. initialize
        init_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"}
        }) + "\n"
        p.stdin.write(init_req)
        p.stdin.flush()
        init_resp = json.loads(p.stdout.readline())
        self.assertEqual(init_resp.get("id"), 1)
        self.assertIn("capabilities", init_resp["result"])

        # 2. tools/list
        list_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }) + "\n"
        p.stdin.write(list_req)
        p.stdin.flush()
        list_resp = json.loads(p.stdout.readline())
        self.assertEqual(list_resp.get("id"), 2)
        tool_names = [t["name"] for t in list_resp["result"]["tools"]]
        self.assertIn("vnc_get_status", tool_names)
        self.assertIn("send_agent_command", tool_names)
        self.assertIn("vnc_capture_screen", tool_names)

        # 3. tools/call vnc_get_status
        call_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "vnc_get_status", "arguments": {}}
        }) + "\n"
        p.stdin.write(call_req)
        p.stdin.flush()
        call_resp = json.loads(p.stdout.readline())
        self.assertEqual(call_resp.get("id"), 3)
        self.assertIn("content", call_resp["result"])

        p.stdin.close()
        p.terminate()
        print(f"[PASS] MCP Server JSON-RPC verified with {len(tool_names)} tools")


if __name__ == "__main__":
    unittest.main()
