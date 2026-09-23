"""
Antigravity Web VNC & Remote Agent Dashboard
FastAPI + WebSocket server providing:
  - Real-time HTML5 Canvas desktop/window streaming (Web VNC)
  - Interactive mouse/keyboard actuation
  - Live agent thought & activity monitor (transcript streaming)
  - Prompt & command dispatch console
  - REST API for status, sessions, and command dispatch
"""

import sys
import os
import json
import time
import asyncio
import io
import socket
from pathlib import Path
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Query, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from PIL import Image

try:
    from agent_bridge import (
        capture_frame,
        find_antigravity_window,
        list_conversations,
        get_active_conversation_id,
        get_recent_transcript,
        send_agent_command,
        new_agent_conversation,
        focus_antigravity_window
    )
    from vnc_server import VNCServer
except ImportError:
    from .agent_bridge import (
        capture_frame,
        find_antigravity_window,
        list_conversations,
        get_active_conversation_id,
        get_recent_transcript,
        send_agent_command,
        new_agent_conversation,
        focus_antigravity_window
    )
    from .vnc_server import VNCServer

app = FastAPI(title="Antigravity Overwatch VNC Bridge")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State
global_vnc_server: Optional[VNCServer] = None
capture_mode = "antigravity"  # 'antigravity' or 'all'
allow_remote_input = True


def get_lan_ips() -> List[str]:
    """Finds all non-loopback local IPv4 addresses."""
    ips = []
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbynameex(hostname)[2]:
            if not ip.startswith("127.") and not ip.startswith("169.254."):
                ips.append(ip)
    except Exception:
        pass
    return ips if ips else ["127.0.0.1"]


class CommandRequest(BaseModel):
    conversation_id: str
    content: str
    title: Optional[str] = None


class NewConversationRequest(BaseModel):
    prompt: str
    model: str = "flash"
    title: Optional[str] = None


# Embedded HTML/JS Single-Page Application
INDEX_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Antigravity Overwatch - Remote VNC & Controller</title>
    <style>
        :root {
            --bg-primary: #0f111a;
            --bg-secondary: #171926;
            --bg-tertiary: #1f2335;
            --accent: #7aa2f7;
            --accent-glow: rgba(122, 162, 247, 0.3);
            --accent-success: #9ece6a;
            --accent-warn: #e0af68;
            --accent-danger: #f7768e;
            --text-main: #c0caf5;
            --text-muted: #565f89;
            --border: #292e42;
            --card-radius: 12px;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg-primary);
            color: var(--text-main);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            overflow-x: hidden;
        }

        header {
            background-color: var(--bg-secondary);
            border-bottom: 1px solid var(--border);
            padding: 12px 24px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 12px;
        }

        .logo-box {
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .logo-icon {
            width: 32px;
            height: 32px;
            background: linear-gradient(135deg, #bb9af7, #7aa2f7);
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: #000;
            font-size: 18px;
            box-shadow: 0 0 15px var(--accent-glow);
        }

        h1 {
            font-size: 18px;
            font-weight: 600;
            letter-spacing: 0.5px;
        }

        .badges {
            display: flex;
            align-items: center;
            gap: 10px;
            flex-wrap: wrap;
        }

        .badge {
            font-size: 12px;
            padding: 4px 10px;
            border-radius: 20px;
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border);
            display: flex;
            align-items: center;
            gap: 6px;
        }

        .status-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: var(--accent-success);
            box-shadow: 0 0 8px var(--accent-success);
        }

        .main-layout {
            display: grid;
            grid-template-columns: 1fr 440px;
            gap: 20px;
            padding: 20px;
            flex: 1;
        }

        @media (max-width: 1024px) {
            .main-layout {
                grid-template-columns: 1fr;
            }
        }

        .card {
            background-color: var(--bg-secondary);
            border: 1px solid var(--border);
            border-radius: var(--card-radius);
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }

        .card-header {
            padding: 14px 18px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
            background-color: rgba(255, 255, 255, 0.02);
        }

        .card-title {
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--text-muted);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .viewport-container {
            position: relative;
            background-color: #000;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 480px;
            flex: 1;
            overflow: hidden;
            cursor: crosshair;
        }

        #viewportCanvas {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
            display: block;
        }

        .viewport-overlay {
            position: absolute;
            top: 12px;
            right: 12px;
            display: flex;
            gap: 8px;
            background: rgba(15, 17, 26, 0.85);
            backdrop-filter: blur(8px);
            padding: 6px 10px;
            border-radius: 8px;
            border: 1px solid var(--border);
        }

        .btn-small {
            background: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .btn-small:hover {
            border-color: var(--accent);
            color: #fff;
        }

        .btn-small.active {
            background-color: var(--accent);
            color: #000;
            font-weight: bold;
        }

        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }

        .console-box {
            display: flex;
            flex-direction: column;
            gap: 12px;
            padding: 16px;
        }

        .form-group {
            display: flex;
            flex-direction: column;
            gap: 6px;
        }

        label {
            font-size: 12px;
            color: var(--text-muted);
            font-weight: 500;
        }

        select, textarea, input {
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-main);
            border-radius: 8px;
            padding: 10px;
            font-size: 13px;
            outline: none;
            transition: border-color 0.2s;
        }

        select:focus, textarea:focus, input:focus {
            border-color: var(--accent);
        }

        textarea {
            resize: vertical;
            min-height: 80px;
            line-height: 1.5;
        }

        .btn-primary {
            background: linear-gradient(135deg, #7aa2f7, #bb9af7);
            color: #0f111a;
            font-weight: 600;
            padding: 12px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            font-size: 13px;
            transition: opacity 0.2s, transform 0.1s;
        }

        .btn-primary:hover {
            opacity: 0.95;
            transform: translateY(-1px);
        }

        .quick-actions {
            display: flex;
            gap: 6px;
            flex-wrap: wrap;
        }

        .pill-btn {
            background-color: var(--bg-tertiary);
            border: 1px solid var(--border);
            color: var(--text-main);
            padding: 4px 10px;
            border-radius: 14px;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.2s;
        }

        .pill-btn:hover {
            border-color: var(--accent);
            color: #fff;
        }

        .feed-container {
            padding: 12px 16px;
            max-height: 360px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 10px;
        }

        .feed-entry {
            background-color: var(--bg-tertiary);
            border-radius: 8px;
            padding: 10px;
            font-size: 12px;
            border-left: 3px solid var(--border);
        }

        .feed-entry.user {
            border-left-color: var(--accent);
        }

        .feed-entry.thinking {
            border-left-color: #bb9af7;
            background: rgba(187, 154, 247, 0.05);
            font-style: italic;
        }

        .feed-entry.tool {
            border-left-color: var(--accent-warn);
            font-family: monospace;
            font-size: 11px;
        }

        .feed-meta {
            display: flex;
            justify-content: space-between;
            color: var(--text-muted);
            font-size: 10px;
            margin-bottom: 4px;
        }

        .vnc-details {
            padding: 12px 16px;
            font-size: 12px;
            display: flex;
            flex-direction: column;
            gap: 8px;
        }

        .code-snippet {
            background: #000;
            padding: 6px 10px;
            border-radius: 6px;
            font-family: monospace;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
    </style>
</head>
<body>
    <header>
        <div class="logo-box">
            <div class="logo-icon">A</div>
            <div>
                <h1>Antigravity Overwatch</h1>
                <div style="font-size: 11px; color: var(--text-muted);">Remote VNC & Agent Control Center</div>
            </div>
        </div>

        <div class="badges">
            <div class="badge">
                <div class="status-dot" id="statusDot"></div>
                <span id="statusText">Stream Connecting...</span>
            </div>
            <button class="btn-small" style="background:#f59e0b;color:#0f172a;font-weight:bold;cursor:pointer;border:none;" onclick="rebootPi()" title="Reboot Raspberry Pi 5 remotely">🔄 Reboot Pi</button>
            <button class="btn-small" style="background:#38bdf8;color:#0f172a;font-weight:bold;cursor:pointer;border:none;" onclick="rebootPC()" title="Reboot Windows PC">💻 Reboot PC</button>
            <div class="badge">
                <span>VNC Port:</span> <strong style="color:var(--accent);">5900</strong>
            </div>
            <div class="badge">
                <span>Web Port:</span> <strong style="color:var(--accent);">5901</strong>
            </div>
        </div>
    </header>

    <div class="main-layout">
        <!-- Viewport Area -->
        <div class="card">
            <div class="card-header">
                <div class="card-title">Live Remote View</div>
                <div style="display: flex; gap: 8px; align-items: center;">
                    <button class="btn-small active" id="btnModeAntigravity" onclick="setMode('antigravity')">Antigravity Window</button>
                    <button class="btn-small" id="btnModeAll" onclick="setMode('all')">Full Desktop</button>
                    <button class="btn-small" id="btnFocus" onclick="focusAntigravity()">Focus Window</button>
                </div>
            </div>
            <div class="viewport-container" id="viewportContainer">
                <canvas id="viewportCanvas"></canvas>
                <div class="viewport-overlay">
                    <span style="font-size: 11px; color: var(--text-muted); align-self: center;" id="fpsCounter">0 FPS</span>
                    <button class="btn-small" onclick="toggleFullscreen()">Fullscreen</button>
                </div>
            </div>
        </div>

        <!-- Sidebar Area -->
        <div class="sidebar">
            <!-- Command Console -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Send Agent Command</div>
                    <button class="btn-small" onclick="refreshSessions()">Refresh</button>
                </div>
                <div class="console-box">
                    <div class="form-group">
                        <label>Target Conversation Session:</label>
                        <select id="conversationSelect" onchange="onSessionChange()"></select>
                    </div>

                    <div class="form-group">
                        <label>Command / Instructions:</label>
                        <textarea id="commandInput" placeholder="Enter instructions or prompt to inject into running agent (Ctrl+Enter to send)..."></textarea>
                    </div>

                    <div class="quick-actions">
                        <button class="pill-btn" onclick="sendQuick('Summarize your current progress and status.')">Status Summary</button>
                        <button class="pill-btn" onclick="sendQuick('Run tests and verify the code.')">Run Tests</button>
                        <button class="pill-btn" onclick="sendQuick('Proceed with next implementation step.')">Proceed</button>
                    </div>

                    <button class="btn-primary" id="btnSend" onclick="sendCommand()">
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z"/></svg>
                        Send to Running Agent
                    </button>
                    <div id="cmdResult" style="font-size: 11px; text-align: center; color: var(--accent-success); min-height: 16px;"></div>
                </div>
            </div>

            <!-- Live Agent Feed -->
            <div class="card" style="flex: 1;">
                <div class="card-header">
                    <div class="card-title">Live Agent Activity</div>
                    <span style="font-size: 11px; color: var(--text-muted);" id="feedStatus">Tracking</span>
                </div>
                <div class="feed-container" id="feedContainer">
                    <div style="color: var(--text-muted); font-size: 12px; text-align: center; padding: 20px;">
                        Loading agent transcripts...
                    </div>
                </div>
            </div>

            <!-- Connection Guide -->
            <div class="card">
                <div class="card-header">
                    <div class="card-title">Remote Access Links</div>
                </div>
                <div class="vnc-details">
                    <div>Standard VNC Client (RFB):</div>
                    <div class="code-snippet">
                        <span id="vncUrl">vnc://localhost:5900</span>
                        <button class="btn-small" onclick="copyText('vncUrl')">Copy</button>
                    </div>
                    <div>Browser / Mobile Web VNC:</div>
                    <div class="code-snippet">
                        <span id="webUrl">http://localhost:5901</span>
                        <button class="btn-small" onclick="copyText('webUrl')">Copy</button>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        const canvas = document.getElementById("viewportCanvas");
        const ctx = canvas.getContext("2d");
        let wsStream = null;
        let wsAgent = null;
        let frameCount = 0;
        let lastFpsTime = Date.now();
        let currentConvId = "";

        function connectStream() {
            const loc = window.location;
            const wsUri = (loc.protocol === "https:" ? "wss://" : "ws://") + loc.host + "/ws/stream";
            wsStream = new WebSocket(wsUri);
            wsStream.binaryType = "blob";

            wsStream.onopen = () => {
                document.getElementById("statusDot").style.backgroundColor = "var(--accent-success)";
                document.getElementById("statusText").innerText = "Stream Connected";
            };

            wsStream.onmessage = async (event) => {
                const blob = event.data;
                const bmp = await createImageBitmap(blob);
                if (canvas.width !== bmp.width || canvas.height !== bmp.height) {
                    canvas.width = bmp.width;
                    canvas.height = bmp.height;
                }
                ctx.drawImage(bmp, 0, 0);
                frameCount++;
                const now = Date.now();
                if (now - lastFpsTime >= 1000) {
                    document.getElementById("fpsCounter").innerText = `${frameCount} FPS`;
                    frameCount = 0;
                    lastFpsTime = now;
                }
            };

            wsStream.onclose = () => {
                document.getElementById("statusDot").style.backgroundColor = "var(--accent-danger)";
                document.getElementById("statusText").innerText = "Stream Disconnected (Reconnecting...)";
                setTimeout(connectStream, 2000);
            };
        }

        function setMode(mode) {
            fetch(`/api/mode?mode=${mode}`, { method: "POST" })
                .then(() => {
                    document.getElementById("btnModeAntigravity").classList.toggle("active", mode === "antigravity");
                    document.getElementById("btnModeAll").classList.toggle("active", mode === "all");
                });
        }

        function focusAntigravity() {
            fetch("/api/focus", { method: "POST" });
        }

        function toggleFullscreen() {
            const container = document.getElementById("viewportContainer");
            if (!document.fullscreenElement) {
                container.requestFullscreen();
            } else {
                document.exitFullscreen();
            }
        }

        async function refreshSessions() {
            try {
                const res = await fetch("/api/conversations");
                const data = await res.json();
                const sel = document.getElementById("conversationSelect");
                sel.innerHTML = "";
                data.conversations.forEach((c, idx) => {
                    const opt = document.createElement("option");
                    opt.value = c.id;
                    opt.innerText = `[${c.modified_str.split(" ")[1]}] ${c.title.substring(0, 50)}`;
                    sel.appendChild(opt);
                });
                if (data.active_id) {
                    sel.value = data.active_id;
                    currentConvId = data.active_id;
                }
                loadTranscript();
            } catch (e) {
                console.error(e);
            }
        }

        function onSessionChange() {
            currentConvId = document.getElementById("conversationSelect").value;
            loadTranscript();
        }

        async function loadTranscript() {
            if (!currentConvId) return;
            try {
                const res = await fetch(`/api/transcript/${currentConvId}`);
                const data = await res.json();
                const feed = document.getElementById("feedContainer");
                feed.innerHTML = "";
                data.entries.forEach(entry => {
                    const div = document.createElement("div");
                    const type = entry.type || "GENERIC";
                    let cls = "feed-entry";
                    let title = type;
                    let text = entry.content || "";

                    if (type === "USER_INPUT") {
                        cls += " user";
                        title = "User Input";
                    } else if (entry.thinking) {
                        cls += " thinking";
                        title = "Agent Reasoning / Thinking";
                        text = entry.thinking;
                    } else if (entry.tool_calls && entry.tool_calls.length > 0) {
                        cls += " tool";
                        title = `Tool Call: ${entry.tool_calls[0].name}`;
                        text = JSON.stringify(entry.tool_calls[0].args, null, 2);
                    }

                    div.className = cls;
                    div.innerHTML = `
                        <div class="feed-meta">
                            <span>${title}</span>
                            <span>${entry.created_at ? entry.created_at.substring(11, 19) : ""}</span>
                        </div>
                        <div style="white-space: pre-wrap; word-break: break-word;">${escapeHtml(text.substring(0, 400))}</div>
                    `;
                    feed.appendChild(div);
                });
                feed.scrollTop = feed.scrollHeight;
            } catch (e) {
                console.error(e);
            }
        }

        function escapeHtml(str) {
            return (str || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        async function sendCommand() {
            const prompt = document.getElementById("commandInput").value.trim();
            const convId = document.getElementById("conversationSelect").value;
            const resBox = document.getElementById("cmdResult");
            if (!prompt) return;

            resBox.style.color = "var(--text-muted)";
            resBox.innerText = "Dispatching command to agent...";

            try {
                const res = await fetch("/api/send", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ conversation_id: convId, content: prompt })
                });
                const data = await res.json();
                if (data.success) {
                    resBox.style.color = "var(--accent-success)";
                    resBox.innerText = "Command dispatched successfully!";
                    document.getElementById("commandInput").value = "";
                    setTimeout(() => { resBox.innerText = ""; loadTranscript(); }, 2500);
                } else {
                    resBox.style.color = "var(--accent-danger)";
                    resBox.innerText = `Error: ${data.error || "Failed"}`;
                }
            } catch (e) {
                resBox.style.color = "var(--accent-danger)";
                resBox.innerText = `Error: ${e.message}`;
            }
        }

        function sendQuick(txt) {
            document.getElementById("commandInput").value = txt;
            sendCommand();
        }

        document.getElementById("commandInput").addEventListener("keydown", (e) => {
            if (e.key === "Enter" && e.ctrlKey) {
                e.preventDefault();
                sendCommand();
            }
        });

        function copyText(id) {
            const t = document.getElementById(id).innerText;
            navigator.clipboard.writeText(t);
        }

        async function rebootPi() {
            if (confirm("Are you sure you want to REBOOT the Raspberry Pi 5?")) {
                try {
                    const res = await fetch("/api/reboot_pi", { method: "POST" });
                    const data = await res.json();
                    alert(data.message || "Reboot command dispatched to Pi.");
                } catch (e) {
                    alert("Error rebooting Pi: " + e);
                }
            }
        }

        async function rebootPC() {
            if (confirm("Are you sure you want to REBOOT the Windows PC? A 10-second timer will start.")) {
                try {
                    const res = await fetch("/api/reboot_pc", { method: "POST" });
                    const data = await res.json();
                    alert(data.message || "PC reboot initiated.");
                } catch (e) {
                    alert("Error rebooting PC: " + e);
                }
            }
        }

        // Initialize
        window.addEventListener("DOMContentLoaded", () => {
            connectStream();
            refreshSessions();
            setInterval(loadTranscript, 3000);

            // Update URLs with current host
            const host = window.location.hostname;
            document.getElementById("vncUrl").innerText = `vnc://${host}:5900`;
            document.getElementById("webUrl").innerText = `http://${host}:5901`;
        });
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(INDEX_HTML)


@app.get("/api/status")
async def get_status():
    global global_vnc_server, capture_mode, allow_remote_input
    win = find_antigravity_window()
    vnc_active = global_vnc_server is not None and global_vnc_server.running
    vnc_clients = len(global_vnc_server.clients) if vnc_active and global_vnc_server else 0
    active_id = get_active_conversation_id()

    return {
        "status": "online",
        "vnc_server": {
            "active": vnc_active,
            "port": 5900,
            "connected_clients": vnc_clients,
        },
        "web_server": {
            "port": 5901,
            "lan_ips": get_lan_ips(),
        },
        "capture_mode": capture_mode,
        "antigravity_window": {
            "found": win is not None,
            "hwnd": win[0] if win else None,
            "rect": win[1] if win else None,
            "title": win[2] if win else None,
        },
        "active_conversation_id": active_id,
    }


@app.get("/api/conversations")
async def get_conversations(limit: int = 15):
    convs = list_conversations(limit=limit)
    active_id = get_active_conversation_id()
    return {
        "active_id": active_id,
        "conversations": convs,
    }


@app.get("/api/transcript/{conversation_id}")
async def get_transcript_endpoint(conversation_id: str, max_steps: int = 30):
    entries = get_recent_transcript(conversation_id, max_steps=max_steps)
    return {
        "conversation_id": conversation_id,
        "count": len(entries),
        "entries": entries,
    }


@app.post("/api/send")
async def post_command(cmd: CommandRequest):
    res = send_agent_command(cmd.conversation_id, cmd.content, cmd.title)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error", "Dispatch failed"))
    return res


@app.post("/api/new_conversation")
async def post_new_conversation(req: NewConversationRequest):
    res = new_agent_conversation(req.prompt, req.model, req.title)
    return res


@app.post("/api/mode")
async def set_capture_mode(mode: str = Query("antigravity")):
    global capture_mode, global_vnc_server
    if mode in ["antigravity", "all", "monitor"]:
        capture_mode = mode
        if global_vnc_server:
            global_vnc_server.capture_mode = mode
        return {"status": "ok", "capture_mode": capture_mode}
    return {"status": "error", "message": "Invalid mode"}


@app.post("/api/focus")
async def focus_window_endpoint():
    res = focus_antigravity_window()
    return {"status": "ok", "focused": res}


@app.post("/api/reboot_pi")
async def web_reboot_pi():
    try:
        import urllib.request
        req = urllib.request.Request(
            "http://10.0.0.120/api/server/power/reboot",
            data=b"{}",
            headers={"Authorization": "Bearer pi_control_secret_key_998822", "Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            return {"status": "ok", "message": "Pi reboot initiated"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/reboot_pc")
async def web_reboot_pc():
    try:
        import subprocess
        subprocess.Popen(["shutdown.exe", "/r", "/t", "10", "/c", "Restart requested from Web VNC"])
        return {"status": "ok", "message": "PC reboot initiated (10s delay)"}
    except Exception as e:
        return {"status": "error", "message": str(e)}



@app.get("/api/screenshot")
async def screenshot_endpoint(mode: Optional[str] = None):
    m = mode or capture_mode
    img = capture_frame(mode=m)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return Response(content=buf.getvalue(), media_type="image/jpeg")


APK_PATH = Path(r"d:\Overwatch\android-app\app\build\outputs\apk\debug\app-debug.apk")

@app.get("/api/app/version")
async def get_app_version():
    build_time = APK_PATH.stat().st_mtime if APK_PATH.exists() else 0
    return {
        "versionCode": 2,
        "versionName": "1.1",
        "downloadUrl": "/api/app/latest.apk",
        "changelog": "Added Antigravity Remote VNC & Controller with auto-update",
        "buildTime": build_time,
        "apkAvailable": APK_PATH.exists()
    }


@app.get("/api/app/latest.apk")
async def get_latest_apk():
    if not APK_PATH.exists():
        raise HTTPException(status_code=404, detail="APK build not found")
    return FileResponse(
        path=str(APK_PATH),
        media_type="application/vnd.android.package-archive",
        filename="overwatch-latest.apk"
    )


@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    global capture_mode
    await websocket.accept()
    try:
        while True:
            # Capture frame and send as JPEG bytes
            img = capture_frame(mode=capture_mode)
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=80)
            await websocket.send_bytes(buf.getvalue())
            # Maintain ~15 FPS
            await asyncio.sleep(0.065)
    except (WebSocketDisconnect, ConnectionResetError):
        pass
    except Exception as e:
        print(f"[WebSocket] Stream error: {e}")


def start_servers(vnc_port: int = 5900, web_port: int = 5901, launch_vnc: bool = True):
    global global_vnc_server
    if launch_vnc:
        global_vnc_server = VNCServer(port=vnc_port, capture_mode=capture_mode, allow_input=True)
        global_vnc_server.start()
        print(f"[Overwatch] RFB VNC Server started on port {vnc_port}")

    lan_ip = get_lan_ips()[0]
    print(f"[Overwatch] Web VNC Dashboard available at:")
    print(f"  -> Local: http://localhost:{web_port}")
    print(f"  -> LAN:   http://{lan_ip}:{web_port}")
    uvicorn.run(app, host="0.0.0.0", port=web_port, log_level="warning")


if __name__ == "__main__":
    start_servers()
