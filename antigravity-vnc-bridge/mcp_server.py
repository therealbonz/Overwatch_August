"""
VNC & Agent Bridge MCP Server (Stdio JSON-RPC 2.0)
Exposes tools to Antigravity for querying VNC status, capturing windows,
listing sessions, and sending commands to running agents.
"""

import sys
import os
import json
import traceback
import subprocess
from pathlib import Path

# Add bridge directory to path
BRIDGE_DIR = Path(r"d:\Overwatch\antigravity-vnc-bridge")
if str(BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(BRIDGE_DIR))

try:
    import agent_bridge
except ImportError:
    agent_bridge = None


TOOLS = [
    {
        "name": "vnc_get_status",
        "description": "Check the status of the VNC bridge, Antigravity window position, and active conversation ID.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        }
    },
    {
        "name": "vnc_capture_screen",
        "description": "Capture a screenshot of either the Antigravity window or the full desktop.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["antigravity", "all"],
                    "description": "Whether to capture 'antigravity' window or 'all' monitors.",
                    "default": "antigravity"
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional file path to save the screenshot image to. If omitted, saves to default temp location."
                }
            }
        }
    },
    {
        "name": "vnc_focus_window",
        "description": "Bring the Antigravity desktop window to the foreground.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "send_agent_command",
        "description": "Send a prompt or instructions to a running Antigravity conversation session.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "conversation_id": {
                    "type": "string",
                    "description": "The target conversation ID. If empty, uses active conversation."
                },
                "content": {
                    "type": "string",
                    "description": "The prompt or instructions to send to the agent."
                },
                "title": {
                    "type": "string",
                    "description": "Optional title for the message."
                }
            },
            "required": ["content"]
        }
    },
    {
        "name": "list_agent_sessions",
        "description": "List active and recent Antigravity conversation sessions with their IDs and titles.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of sessions to return.",
                    "default": 10
                }
            }
        }
    },
    {
        "name": "start_vnc_bridge",
        "description": "Launch the background VNC server (port 5900) and Web stream server (port 5901).",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    }
]


def handle_tool_call(name: str, args: dict) -> dict:
    if not agent_bridge:
        return {"error": "agent_bridge module could not be imported"}

    if name == "vnc_get_status":
        win = agent_bridge.find_antigravity_window()
        active_id = agent_bridge.get_active_conversation_id()
        return {
            "active_conversation_id": active_id,
            "antigravity_window": {
                "found": win is not None,
                "hwnd": win[0] if win else None,
                "rect": win[1] if win else None,
                "title": win[2] if win else None
            },
            "vnc_port": 5900,
            "web_port": 5901
        }

    elif name == "vnc_capture_screen":
        mode = args.get("mode", "antigravity")
        out_path = args.get("output_path")
        if not out_path:
            out_path = str(BRIDGE_DIR / "latest_screen_capture.png")
        img = agent_bridge.capture_frame(mode=mode)
        img.save(out_path)
        return {
            "status": "success",
            "saved_to": out_path,
            "dimensions": img.size,
            "mode": mode
        }

    elif name == "vnc_focus_window":
        res = agent_bridge.focus_antigravity_window()
        return {"success": res, "message": "Window focused" if res else "Window not found"}

    elif name == "send_agent_command":
        conv_id = args.get("conversation_id")
        if not conv_id:
            conv_id = agent_bridge.get_active_conversation_id()
        content = args.get("content", "")
        title = args.get("title")
        res = agent_bridge.send_agent_command(conv_id, content, title)
        return res

    elif name == "list_agent_sessions":
        limit = args.get("limit", 10)
        sessions = agent_bridge.list_conversations(limit=limit)
        return {"sessions": sessions}

    elif name == "start_vnc_bridge":
        bat_path = BRIDGE_DIR / "run_vnc_bridge.bat"
        proc = subprocess.Popen(["cmd.exe", "/c", str(bat_path)], creationflags=subprocess.CREATE_NEW_CONSOLE)
        return {"status": "started", "pid": proc.pid, "vnc_url": "vnc://localhost:5900", "web_url": "http://localhost:5901"}

    else:
        return {"error": f"Unknown tool: {name}"}


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue

        try:
            req = json.loads(line)
        except Exception:
            continue

        msg_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "vnc-bridge-mcp", "version": "1.0.0"}
                }
            }
        elif method == "notifications/initialized":
            continue
        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "result": {"tools": TOOLS}
            }
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                result_data = handle_tool_call(tool_name, tool_args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": json.dumps(result_data, indent=2)}
                        ]
                    }
                }
            except Exception as e:
                resp = {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Error executing {tool_name}: {str(e)}\n{traceback.format_exc()}"}
                        ],
                        "isError": True
                    }
                }
        else:
            resp = {
                "jsonrpc": "2.0",
                "id": msg_id,
                "error": {"code": -32601, "message": f"Method not found: {method}"}
            }

        sys.stdout.write(json.dumps(resp) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
