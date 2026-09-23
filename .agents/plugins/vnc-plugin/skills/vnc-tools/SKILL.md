---
name: vnc-tools
description: Instructions and tools for running, monitoring, and interacting with the Antigravity VNC screen streaming bridge and companion desktop controller.
---

# Antigravity VNC Bridge & Remote Controller Skill

This skill teaches the agent how to monitor, start, and interface with the VNC and Web streaming servers and the native companion desktop app.

## Capabilities

1. **RFB VNC Server (Port 5900)**:
   - Connect using any native VNC client (e.g. TightVNC, RealVNC, TigerVNC, Apple Screen Sharing, mobile VNC viewers).
   - Address: `vnc://<host>:5900` or `vnc://localhost:5900`.
   - Security: None (standard local network access).

2. **Web VNC & REST/WebSocket Dashboard (Port 5901)**:
   - Connect using any web browser on desktop, phone, or tablet.
   - Address: `http://localhost:5901` or `http://<LAN-IP>:5901`.
   - Features: Live viewport canvas, active conversation selector, prompt input bar with instant dispatch, and real-time agent thought streaming.

3. **Desktop Companion Controller**:
   - Location: `d:\Overwatch\antigravity-vnc-bridge\desktop_app.py`
   - Launch: Double click `d:\Overwatch\antigravity-vnc-bridge\run_desktop_app.bat`
   - Features: Native Windows dark-themed GUI for viewing the Antigravity window or full desktop, viewing agent reasoning/tool activity, and typing commands directly to the running agent.

## Available MCP Tools (via `vnc-bridge` MCP Server)

- `vnc_get_status`: Inspect whether VNC/Web streaming is running, get Antigravity window details (HWND, bounds), and active conversation ID.
- `vnc_capture_screen`: Capture a screenshot of the Antigravity window or full desktop.
- `vnc_focus_window`: Bring the Antigravity window to the foreground.
- `send_agent_command`: Inject a message into an active conversation via `agentapi.bat send-message`.
- `list_agent_sessions`: List active and past conversations.
- `start_vnc_bridge`: Start the background VNC and Web streaming service.

## Command Line Scripts

- `d:\Overwatch\antigravity-vnc-bridge\run_desktop_app.bat`: Starts the Desktop GUI app.
- `d:\Overwatch\antigravity-vnc-bridge\run_vnc_bridge.bat`: Starts headless VNC and Web servers.
