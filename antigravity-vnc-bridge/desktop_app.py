"""
Antigravity Overwatch Desktop Application
Native Windows GUI for monitoring Antigravity, viewing the live window/screen,
and sending interactive commands directly to the running agent.
"""

import sys
import os
import time
import json
import socket
import subprocess
import threading
import webbrowser
import urllib.request
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from PIL import Image, ImageTk

try:
    from agent_bridge import (
        capture_frame,
        find_antigravity_window,
        focus_antigravity_window,
        list_conversations,
        get_active_conversation_id,
        get_recent_transcript,
        send_agent_command,
        new_agent_conversation
    )
    from vnc_server import VNCServer
    from web_server import start_servers, get_lan_ips, app
except ImportError:
    from .agent_bridge import (
        capture_frame,
        find_antigravity_window,
        focus_antigravity_window,
        list_conversations,
        get_active_conversation_id,
        get_recent_transcript,
        send_agent_command,
        new_agent_conversation
    )
    from .vnc_server import VNCServer
    from .web_server import start_servers, get_lan_ips, app


class AntigravityDesktopApp(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("Antigravity Overwatch - Desktop Controller")
        self.geometry("1180x760")
        self.minsize(980, 620)
        self.configure(bg="#0f111a")

        # Application state
        self.capture_mode = "antigravity"  # 'antigravity' or 'all'
        self.refresh_rate = 5  # FPS
        self.is_viewing = True
        self.active_conv_id = None
        self.conv_list = []
        self.vnc_server = None
        self.web_server_thread = None
        self.lan_ip = get_lan_ips()[0] if get_lan_ips() else "127.0.0.1"

        # Theme Colors
        self.c_bg = "#0f111a"
        self.c_panel = "#171926"
        self.c_card = "#1f2335"
        self.c_accent = "#7aa2f7"
        self.c_purple = "#bb9af7"
        self.c_success = "#9ece6a"
        self.c_warn = "#e0af68"
        self.c_danger = "#f7768e"
        self.c_text = "#c0caf5"
        self.c_muted = "#565f89"
        self.c_border = "#292e42"

        self._setup_styles()
        self._build_ui()

        # Start background workers
        self._refresh_sessions()
        self._start_viewport_loop()
        self._start_transcript_loop()

    def _setup_styles(self):
        style = ttk.Style(self)
        style.theme_use("clam")

        style.configure("TFrame", background=self.c_bg)
        style.configure("Panel.TFrame", background=self.c_panel)
        style.configure("Card.TFrame", background=self.c_card)

        style.configure("TLabel", background=self.c_panel, foreground=self.c_text, font=("Segoe UI", 10))
        style.configure("Title.TLabel", font=("Segoe UI", 12, "bold"), foreground=self.c_accent)
        style.configure("Muted.TLabel", font=("Segoe UI", 9), foreground=self.c_muted)
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"), foreground=self.c_success)

        style.configure("TCombobox", fieldbackground=self.c_card, background=self.c_card, foreground="#ffffff")
        style.map("TCombobox", fieldbackground=[("readonly", self.c_card)], foreground=[("readonly", "#ffffff")])

        style.configure("TNotebook", background=self.c_panel, borderwidth=0)
        style.configure("TNotebook.Tab", background=self.c_card, foreground=self.c_text, padding=[12, 6], font=("Segoe UI", 9, "bold"))
        style.map("TNotebook.Tab", background=[("selected", self.c_accent)], foreground=[("selected", "#0f111a")])

        style.configure("Action.TButton", font=("Segoe UI", 9, "bold"), background=self.c_card, foreground=self.c_text)
        style.map("Action.TButton", background=[("active", self.c_accent)], foreground=[("active", "#0f111a")])

        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background=self.c_accent, foreground="#0f111a")
        style.map("Primary.TButton", background=[("active", self.c_purple)])

    def _build_ui(self):
        # 1. Top Header Bar
        header = ttk.Frame(self, style="Panel.TFrame", padding=(16, 10))
        header.pack(fill=tk.X, side=tk.TOP)

        logo_frame = ttk.Frame(header, style="Panel.TFrame")
        logo_frame.pack(side=tk.LEFT, fill=tk.Y)

        lbl_logo = tk.Label(logo_frame, text="A", bg=self.c_accent, fg="#000", font=("Segoe UI", 13, "bold"), width=2, height=1)
        lbl_logo.pack(side=tk.LEFT, padx=(0, 10))

        title_box = ttk.Frame(logo_frame, style="Panel.TFrame")
        title_box.pack(side=tk.LEFT)
        ttk.Label(title_box, text="Antigravity Overwatch", style="Title.TLabel").pack(anchor=tk.W)
        ttk.Label(title_box, text="Remote Screen & Agent Command Controller", style="Muted.TLabel").pack(anchor=tk.W)

        # Right Header: Session Picker & Status
        session_box = ttk.Frame(header, style="Panel.TFrame")
        session_box.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(session_box, text="Session:", style="Muted.TLabel").pack(side=tk.LEFT, padx=(10, 4))
        self.combo_sessions = ttk.Combobox(session_box, width=38, state="readonly")
        self.combo_sessions.pack(side=tk.LEFT, padx=(0, 6))
        self.combo_sessions.bind("<<ComboboxSelected>>", self._on_session_selected)

        btn_refresh = ttk.Button(session_box, text="🔄", width=3, style="Action.TButton", command=self._refresh_sessions)
        btn_refresh.pack(side=tk.LEFT, padx=(0, 10))

        self.lbl_status = ttk.Label(session_box, text="● Connected", style="Status.TLabel")
        self.lbl_status.pack(side=tk.LEFT, padx=(6, 0))

        # 2. Main Content Split
        main_paned = tk.PanedWindow(self, orient=tk.HORIZONTAL, bg=self.c_border, sashwidth=4)
        main_paned.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        # Left Panel: Viewport Area
        viewport_panel = ttk.Frame(main_paned, style="Panel.TFrame", padding=10)
        main_paned.add(viewport_panel, minsize=480, stretch="always")

        # Viewport Header
        vp_header = ttk.Frame(viewport_panel, style="Panel.TFrame")
        vp_header.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(vp_header, text="LIVE MONITOR VIEW", style="Title.TLabel").pack(side=tk.LEFT)

        self.mode_var = tk.StringVar(value="antigravity")
        r1 = tk.Radiobutton(vp_header, text="Antigravity Window", variable=self.mode_var, value="antigravity",
                            bg=self.c_panel, fg=self.c_text, selectcolor=self.c_card,
                            activebackground=self.c_panel, activeforeground=self.c_accent,
                            command=self._on_mode_changed)
        r1.pack(side=tk.RIGHT, padx=4)
        r2 = tk.Radiobutton(vp_header, text="Full Screen", variable=self.mode_var, value="all",
                            bg=self.c_panel, fg=self.c_text, selectcolor=self.c_card,
                            activebackground=self.c_panel, activeforeground=self.c_accent,
                            command=self._on_mode_changed)
        r2.pack(side=tk.RIGHT, padx=4)

        # Canvas Viewport
        self.canvas_frame = tk.Frame(viewport_panel, bg="#000", highlightbackground=self.c_border, highlightthickness=1)
        self.canvas_frame.pack(fill=tk.BOTH, expand=True)

        self.lbl_viewport = tk.Label(self.canvas_frame, bg="#000", text="Initializing Screen Stream...", fg=self.c_muted)
        self.lbl_viewport.pack(fill=tk.BOTH, expand=True)
        self.lbl_viewport.bind("<Double-Button-1>", lambda e: focus_antigravity_window())

        # Viewport Controls Footer
        vp_footer = ttk.Frame(viewport_panel, style="Panel.TFrame", padding=(0, 8, 0, 0))
        vp_footer.pack(fill=tk.X)

        ttk.Button(vp_footer, text="🎯 Focus Antigravity", style="Action.TButton", command=focus_antigravity_window).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(vp_footer, text="📸 Save Snapshot", style="Action.TButton", command=self._save_snapshot).pack(side=tk.LEFT, padx=(0, 6))

        self.btn_pause = ttk.Button(vp_footer, text="⏸ Pause", style="Action.TButton", command=self._toggle_pause)
        self.btn_pause.pack(side=tk.LEFT)

        self.lbl_fps = ttk.Label(vp_footer, text="5 FPS", style="Muted.TLabel")
        self.lbl_fps.pack(side=tk.RIGHT)

        # Right Panel: Tabs for Command Console, Thoughts, & Servers
        right_panel = ttk.Frame(main_paned, style="Panel.TFrame", padding=10)
        main_paned.add(right_panel, minsize=420, stretch="never")

        notebook = ttk.Notebook(right_panel)
        notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: Command Console
        tab_console = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
        notebook.add(tab_console, text=" Agent Console ")

        ttk.Label(tab_console, text="COMMAND / INSTRUCTIONS TO AGENT:", style="Muted.TLabel").pack(anchor=tk.W, pady=(0, 4))
        self.txt_prompt = tk.Text(tab_console, height=6, bg=self.c_card, fg=self.c_text,
                                  insertbackground=self.c_accent, relief=tk.FLAT,
                                  highlightbackground=self.c_border, highlightthickness=1,
                                  font=("Segoe UI", 10), wrap=tk.WORD)
        self.txt_prompt.pack(fill=tk.X, pady=(0, 8))
        self.txt_prompt.bind("<Control-Return>", lambda e: self._send_command())

        # Quick Actions
        quick_frame = ttk.Frame(tab_console, style="Panel.TFrame")
        quick_frame.pack(fill=tk.X, pady=(0, 10))

        ttk.Button(quick_frame, text="📊 Status Summary", style="Action.TButton",
                   command=lambda: self._send_quick("Summarize current task status and next steps.")).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(quick_frame, text="🧪 Run Tests", style="Action.TButton",
                   command=lambda: self._send_quick("Run verification tests and report output.")).pack(side=tk.LEFT, padx=(0, 4))
        ttk.Button(quick_frame, text="▶ Proceed", style="Action.TButton",
                   command=lambda: self._send_quick("Proceed with current plan.")).pack(side=tk.LEFT)

        btn_send = ttk.Button(tab_console, text="🚀 Send Command to Running Agent", style="Primary.TButton", command=self._send_command)
        btn_send.pack(fill=tk.X, pady=(0, 6))

        self.lbl_cmd_status = tk.Label(tab_console, text="", bg=self.c_panel, fg=self.c_success, font=("Segoe UI", 9))
        self.lbl_cmd_status.pack(fill=tk.X, pady=(0, 8))

        # Recent Activity in Console Tab
        ttk.Label(tab_console, text="RECENT AGENT EVENTS:", style="Muted.TLabel").pack(anchor=tk.W, pady=(8, 4))
        self.txt_recent = tk.Text(tab_console, bg=self.c_card, fg=self.c_text,
                                  relief=tk.FLAT, highlightbackground=self.c_border, highlightthickness=1,
                                  font=("Consolas", 9), wrap=tk.WORD, state=tk.DISABLED)
        self.txt_recent.pack(fill=tk.BOTH, expand=True)

        # Tab 2: Live Agent Activity / Thinking
        tab_activity = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
        notebook.add(tab_activity, text=" Live Agent Activity ")

        self.txt_activity = tk.Text(tab_activity, bg=self.c_card, fg=self.c_text,
                                    relief=tk.FLAT, highlightbackground=self.c_border, highlightthickness=1,
                                    font=("Consolas", 9), wrap=tk.WORD)
        self.txt_activity.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        act_footer = ttk.Frame(tab_activity, style="Panel.TFrame")
        act_footer.pack(fill=tk.X)
        ttk.Button(act_footer, text="Clear Log", style="Action.TButton", command=lambda: self._clear_text(self.txt_activity)).pack(side=tk.RIGHT)

        # Tab 3: Remote VNC & Web Server Controls
        tab_servers = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
        notebook.add(tab_servers, text=" Remote / VNC Servers ")

        # VNC Box
        vnc_card = ttk.Frame(tab_servers, style="Card.TFrame", padding=12)
        vnc_card.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(vnc_card, text="RFB VNC SERVER (Port 5900)", style="Title.TLabel", background=self.c_card).pack(anchor=tk.W)
        ttk.Label(vnc_card, text="Allows standard VNC viewers to connect directly.", style="Muted.TLabel", background=self.c_card).pack(anchor=tk.W, pady=(0, 6))

        vnc_ctrls = ttk.Frame(vnc_card, style="Card.TFrame")
        vnc_ctrls.pack(fill=tk.X, pady=(4, 6))

        self.btn_vnc = ttk.Button(vnc_ctrls, text="▶ Start VNC Server", style="Action.TButton", command=self._toggle_vnc_server)
        self.btn_vnc.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_vnc_status = ttk.Label(vnc_ctrls, text="Status: Stopped", style="Muted.TLabel", background=self.c_card)
        self.lbl_vnc_status.pack(side=tk.LEFT)

        vnc_url_frame = ttk.Frame(vnc_card, style="Card.TFrame")
        vnc_url_frame.pack(fill=tk.X)
        ttk.Label(vnc_url_frame, text=f"URL: vnc://{self.lan_ip}:5900", font=("Consolas", 10), foreground=self.c_accent, background=self.c_card).pack(side=tk.LEFT)
        ttk.Button(vnc_url_frame, text="Copy", style="Action.TButton", command=lambda: self._copy_to_clip(f"vnc://{self.lan_ip}:5900")).pack(side=tk.RIGHT)

        # Web Server Box
        web_card = ttk.Frame(tab_servers, style="Card.TFrame", padding=12)
        web_card.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(web_card, text="WEB VNC & DASHBOARD (Port 5901)", style="Title.TLabel", background=self.c_card).pack(anchor=tk.W)
        ttk.Label(web_card, text="Access from any browser, tablet, or phone on the LAN.", style="Muted.TLabel", background=self.c_card).pack(anchor=tk.W, pady=(0, 6))

        web_ctrls = ttk.Frame(web_card, style="Card.TFrame")
        web_ctrls.pack(fill=tk.X, pady=(4, 6))

        self.btn_web = ttk.Button(web_ctrls, text="▶ Start Web Server", style="Action.TButton", command=self._toggle_web_server)
        self.btn_web.pack(side=tk.LEFT, padx=(0, 8))

        self.lbl_web_status = ttk.Label(web_ctrls, text="Status: Stopped", style="Muted.TLabel", background=self.c_card)
        self.lbl_web_status.pack(side=tk.LEFT)

        web_url_frame = ttk.Frame(web_card, style="Card.TFrame")
        web_url_frame.pack(fill=tk.X, pady=(4, 0))
        ttk.Label(web_url_frame, text=f"http://{self.lan_ip}:5901", font=("Consolas", 10), foreground=self.c_accent, background=self.c_card).pack(side=tk.LEFT)
        ttk.Button(web_url_frame, text="Open Browser", style="Action.TButton", command=lambda: webbrowser.open(f"http://localhost:5901")).pack(side=tk.RIGHT, padx=(4, 0))
        ttk.Button(web_url_frame, text="Copy", style="Action.TButton", command=lambda: self._copy_to_clip(f"http://{self.lan_ip}:5901")).pack(side=tk.RIGHT)

        # Tab 4: Pi & PC Control
        tab_pi = ttk.Frame(notebook, style="Panel.TFrame", padding=12)
        notebook.add(tab_pi, text=" Pi & PC Control ")

        # Pi Section Card
        pi_card = ttk.Frame(tab_pi, style="Card.TFrame", padding=12)
        pi_card.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(pi_card, text="🍓 RASPBERRY PI 5 (10.0.0.120)", style="Title.TLabel", foreground=self.c_danger, background=self.c_card).pack(anchor=tk.W)
        self.lbl_pi_info = ttk.Label(pi_card, text="Status: Checking telemetry...", style="Muted.TLabel", background=self.c_card)
        self.lbl_pi_info.pack(anchor=tk.W, pady=(2, 8))

        pi_btn_frame = ttk.Frame(pi_card, style="Card.TFrame")
        pi_btn_frame.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(pi_btn_frame, text="🔄 Reboot Pi", style="Action.TButton", command=self._reboot_pi).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(pi_btn_frame, text="🛑 Shutdown Pi", style="Action.TButton", command=self._shutdown_pi).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(pi_btn_frame, text="📊 Refresh", style="Action.TButton", command=self._refresh_pi_telemetry).pack(side=tk.LEFT)

        pi_links_frame = ttk.Frame(pi_card, style="Card.TFrame")
        pi_links_frame.pack(fill=tk.X, pady=(4, 0))
        ttk.Button(pi_links_frame, text="🌐 Open Pi Hub", style="Action.TButton", command=lambda: webbrowser.open("http://10.0.0.120/")).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(pi_links_frame, text="🖥️ Open noVNC (6080)", style="Action.TButton", command=lambda: webbrowser.open("http://10.0.0.120:6080/")).pack(side=tk.LEFT)

        # PC Section Card
        pc_card = ttk.Frame(tab_pi, style="Card.TFrame", padding=12)
        pc_card.pack(fill=tk.X, pady=(0, 10))

        ttk.Label(pc_card, text="💻 WINDOWS PC COMMAND", style="Title.TLabel", foreground=self.c_accent, background=self.c_card).pack(anchor=tk.W)
        self.lbl_pc_info = ttk.Label(pc_card, text="IP: 10.0.0.225 • MAC: 84:9e:56:51:4b:cd", style="Muted.TLabel", background=self.c_card)
        self.lbl_pc_info.pack(anchor=tk.W, pady=(2, 8))

        pc_btn_frame1 = ttk.Frame(pc_card, style="Card.TFrame")
        pc_btn_frame1.pack(fill=tk.X, pady=(0, 6))
        ttk.Button(pc_btn_frame1, text="🔄 Reboot PC", style="Action.TButton", command=self._reboot_pc).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(pc_btn_frame1, text="⚡ Wake PC (WoL)", style="Action.TButton", command=self._wake_pc).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(pc_btn_frame1, text="🛑 Abort Reboot", style="Action.TButton", command=self._abort_pc).pack(side=tk.LEFT)

        pc_btn_frame2 = ttk.Frame(pc_card, style="Card.TFrame")
        pc_btn_frame2.pack(fill=tk.X, pady=(0, 4))
        ttk.Button(pc_btn_frame2, text="🔒 Lock PC", style="Action.TButton", command=self._lock_pc).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(pc_btn_frame2, text="🌙 Sleep PC", style="Action.TButton", command=self._sleep_pc).pack(side=tk.LEFT, padx=(0, 6))
        ttk.Button(pc_btn_frame2, text="🛑 Shutdown PC", style="Action.TButton", command=self._shutdown_pc).pack(side=tk.LEFT)

        # Result status bar in Tab 4
        self.lbl_hardware_msg = ttk.Label(tab_pi, text="", style="Muted.TLabel")
        self.lbl_hardware_msg.pack(fill=tk.X, pady=(8, 0))

        # Start initial Pi telemetry check
        self._refresh_pi_telemetry()

    def _refresh_pi_telemetry(self):
        def worker():
            try:
                req = urllib.request.Request(
                    "http://10.0.0.120/api/server/stats",
                    headers={"Authorization": "Bearer pi_control_secret_key_998822"}
                )
                with urllib.request.urlopen(req, timeout=2.5) as resp:
                    data = json.loads(resp.read().decode())
                    temp = data.get("temperature_c", "--")
                    cpu = data.get("cpu", {}).get("percent", "--")
                    ram = data.get("memory", {}).get("percent", "--")
                    txt = f"Online • CPU: {cpu}% • RAM: {ram}% • Temp: {temp}°C"
                    self.after(0, lambda: self.lbl_pi_info.configure(text=txt, foreground=self.c_success))
            except Exception:
                self.after(0, lambda: self.lbl_pi_info.configure(text="Offline / Unreachable (10.0.0.120)", foreground=self.c_danger))
        threading.Thread(target=worker, daemon=True).start()

    def _reboot_pi(self):
        if not messagebox.askyesno("Reboot Pi", "Are you sure you want to REBOOT the Raspberry Pi 5?"):
            return
        def worker():
            try:
                req = urllib.request.Request(
                    "http://10.0.0.120/api/server/power/reboot",
                    data=b"{}",
                    headers={"Authorization": "Bearer pi_control_secret_key_998822", "Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    self.after(0, lambda: self.lbl_hardware_msg.configure(text="Pi reboot initiated.", foreground=self.c_warn))
            except Exception as e:
                self.after(0, lambda: self.lbl_hardware_msg.configure(text=f"Pi Reboot Error: {e}", foreground=self.c_danger))
        threading.Thread(target=worker, daemon=True).start()

    def _shutdown_pi(self):
        if not messagebox.askyesno("Shutdown Pi", "Are you sure you want to SHUT DOWN the Raspberry Pi 5?"):
            return
        def worker():
            try:
                req = urllib.request.Request(
                    "http://10.0.0.120/api/server/power/shutdown",
                    data=b"{}",
                    headers={"Authorization": "Bearer pi_control_secret_key_998822", "Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as resp:
                    self.after(0, lambda: self.lbl_hardware_msg.configure(text="Pi shutdown initiated.", foreground=self.c_danger))
            except Exception as e:
                self.after(0, lambda: self.lbl_hardware_msg.configure(text=f"Pi Shutdown Error: {e}", foreground=self.c_danger))
        threading.Thread(target=worker, daemon=True).start()

    def _reboot_pc(self):
        if not messagebox.askyesno("Reboot PC", "Are you sure you want to REBOOT the Windows PC?\nA 10-second timer will start."):
            return
        try:
            subprocess.Popen(["shutdown.exe", "/r", "/t", "10", "/c", "Restart requested from Desktop Controller"])
            self.lbl_hardware_msg.configure(text="PC Reboot scheduled (10s). Click 'Abort Reboot' to cancel.", foreground=self.c_warn)
        except Exception as e:
            self.lbl_hardware_msg.configure(text=f"Error: {e}", foreground=self.c_danger)

    def _shutdown_pc(self):
        if not messagebox.askyesno("Shutdown PC", "Are you sure you want to SHUT DOWN the Windows PC?\nA 10-second timer will start."):
            return
        try:
            subprocess.Popen(["shutdown.exe", "/s", "/t", "10", "/c", "Shutdown requested from Desktop Controller"])
            self.lbl_hardware_msg.configure(text="PC Shutdown scheduled (10s). Click 'Abort Reboot' to cancel.", foreground=self.c_danger)
        except Exception as e:
            self.lbl_hardware_msg.configure(text=f"Error: {e}", foreground=self.c_danger)

    def _abort_pc(self):
        try:
            subprocess.run(["shutdown.exe", "/a"], capture_output=True, text=True)
            self.lbl_hardware_msg.configure(text="PC Shutdown/Reboot aborted.", foreground=self.c_success)
        except Exception as e:
            self.lbl_hardware_msg.configure(text=f"Error: {e}", foreground=self.c_danger)

    def _wake_pc(self):
        try:
            mac_bytes = bytes.fromhex("849e56514bcd")
            magic = b"\xff" * 6 + mac_bytes * 16
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
                s.sendto(magic, ("255.255.255.255", 9))
                s.sendto(magic, ("10.0.0.255", 9))
            self.lbl_hardware_msg.configure(text="Wake-on-LAN magic packet sent to 84:9e:56:51:4b:cd.", foreground=self.c_success)
        except Exception as e:
            self.lbl_hardware_msg.configure(text=f"WoL Error: {e}", foreground=self.c_danger)

    def _lock_pc(self):
        try:
            subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
            self.lbl_hardware_msg.configure(text="Workstation locked.", foreground=self.c_success)
        except Exception as e:
            self.lbl_hardware_msg.configure(text=f"Error: {e}", foreground=self.c_danger)

    def _sleep_pc(self):
        try:
            subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
            self.lbl_hardware_msg.configure(text="PC sleep requested.", foreground=self.c_success)
        except Exception as e:
            self.lbl_hardware_msg.configure(text=f"Error: {e}", foreground=self.c_danger)

    def _refresh_sessions(self):
        try:
            self.conv_list = list_conversations(limit=20)
            active_id = get_active_conversation_id()
            titles = []
            selected_idx = 0

            for idx, c in enumerate(self.conv_list):
                label = f"[{c['modified_str'].split(' ')[1]}] {c['title'][:40]}"
                titles.append(label)
                if active_id and c["id"] == active_id:
                    selected_idx = idx

            self.combo_sessions["values"] = titles
            if titles:
                self.combo_sessions.current(selected_idx)
                self.active_conv_id = self.conv_list[selected_idx]["id"]
        except Exception as e:
            print(f"[DesktopApp] Refresh sessions error: {e}")

    def _on_session_selected(self, event):
        idx = self.combo_sessions.current()
        if 0 <= idx < len(self.conv_list):
            self.active_conv_id = self.conv_list[idx]["id"]
            self._update_transcript_view()

    def _on_mode_changed(self):
        self.capture_mode = self.mode_var.get()

    def _toggle_pause(self):
        self.is_viewing = not self.is_viewing
        self.btn_pause.configure(text="▶ Resume" if not self.is_viewing else "⏸ Pause")

    def _start_viewport_loop(self):
        def loop():
            while True:
                if self.is_viewing:
                    try:
                        frame = capture_frame(mode=self.capture_mode)
                        # Resize to fit viewport canvas
                        cw = max(200, self.canvas_frame.winfo_width())
                        ch = max(150, self.canvas_frame.winfo_height())
                        
                        # Preserve aspect ratio
                        fw, fh = frame.size
                        ratio = min(cw / fw, ch / fh)
                        nw, nh = max(1, int(fw * ratio)), max(1, int(fh * ratio))

                        resized = frame.resize((nw, nh), Image.Resampling.BILINEAR)
                        img_tk = ImageTk.PhotoImage(resized)

                        # Update GUI on main thread
                        self.after(0, self._render_viewport, img_tk)
                    except Exception as e:
                        pass
                time.sleep(1.0 / max(1, self.refresh_rate))

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _render_viewport(self, img_tk):
        self.lbl_viewport.configure(image=img_tk, text="")
        self.lbl_viewport.image = img_tk

    def _start_transcript_loop(self):
        def loop():
            while True:
                if self.active_conv_id:
                    self.after(0, self._update_transcript_view)
                time.sleep(2.5)

        t = threading.Thread(target=loop, daemon=True)
        t.start()

    def _update_transcript_view(self):
        if not self.active_conv_id:
            return
        entries = get_recent_transcript(self.active_conv_id, max_steps=25)
        if not entries:
            return

        # Format for display
        lines_activity = []
        lines_recent = []

        for e in entries:
            t = e.get("type", "MSG")
            ts = e.get("created_at", "")[11:19]
            content = e.get("content", "")
            thinking = e.get("thinking", "")
            tool_calls = e.get("tool_calls", [])

            if t == "USER_INPUT":
                lines_recent.append(f"[{ts}] USER: {content[:80]}")
                lines_activity.append(f"=== USER [{ts}] ===\n{content}\n")
            elif thinking:
                lines_recent.append(f"[{ts}] THINKING: {thinking[:60]}...")
                lines_activity.append(f"--- AGENT REASONING [{ts}] ---\n{thinking[:500]}\n")
            elif tool_calls:
                tc = tool_calls[0]
                lines_recent.append(f"[{ts}] TOOL: {tc.get('name')}")
                lines_activity.append(f"[TOOL] {tc.get('name')}({json.dumps(tc.get('args', {}))[:120]})\n")
            elif content:
                lines_recent.append(f"[{ts}] MODEL: {content[:80]}")
                lines_activity.append(f"=== MODEL [{ts}] ===\n{content[:400]}\n")

        # Update text boxes
        self.txt_recent.configure(state=tk.NORMAL)
        self.txt_recent.delete("1.0", tk.END)
        self.txt_recent.insert(tk.END, "\n".join(lines_recent[-12:]))
        self.txt_recent.configure(state=tk.DISABLED)
        self.txt_recent.see(tk.END)

        self.txt_activity.delete("1.0", tk.END)
        self.txt_activity.insert(tk.END, "\n".join(lines_activity))
        self.txt_activity.see(tk.END)

    def _send_command(self):
        prompt = self.txt_prompt.get("1.0", tk.END).strip()
        if not prompt:
            return
        if not self.active_conv_id:
            messagebox.showwarning("No Session", "Please select an active conversation session.")
            return

        self.lbl_cmd_status.configure(text="Dispatching command to agent...", fg=self.c_muted)

        def worker():
            res = send_agent_command(self.active_conv_id, prompt)
            if res.get("success"):
                self.after(0, lambda: self._on_cmd_success())
            else:
                err = res.get("error", "Failed")
                self.after(0, lambda: self.lbl_cmd_status.configure(text=f"Error: {err}", fg=self.c_danger))

        threading.Thread(target=worker, daemon=True).start()

    def _on_cmd_success(self):
        self.txt_prompt.delete("1.0", tk.END)
        self.lbl_cmd_status.configure(text="✓ Command dispatched to running agent!", fg=self.c_success)
        self.after(3000, lambda: self.lbl_cmd_status.configure(text=""))
        self._update_transcript_view()

    def _send_quick(self, text):
        self.txt_prompt.delete("1.0", tk.END)
        self.txt_prompt.insert(tk.END, text)
        self._send_command()

    def _save_snapshot(self):
        try:
            frame = capture_frame(mode=self.capture_mode)
            path = filedialog.asksaveasfilename(defaultextension=".png", filetypes=[("PNG Files", "*.png"), ("All Files", "*.*")])
            if path:
                frame.save(path)
                messagebox.showinfo("Saved", f"Snapshot saved to:\n{path}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save snapshot: {e}")

    def _toggle_vnc_server(self):
        if self.vnc_server and self.vnc_server.running:
            self.vnc_server.stop()
            self.vnc_server = None
            self.btn_vnc.configure(text="▶ Start VNC Server")
            self.lbl_vnc_status.configure(text="Status: Stopped", foreground=self.c_muted)
        else:
            self.vnc_server = VNCServer(port=5900, capture_mode=self.capture_mode, allow_input=True)
            self.vnc_server.start()
            self.btn_vnc.configure(text="⏹ Stop VNC Server")
            self.lbl_vnc_status.configure(text="Status: Running (Port 5900)", foreground=self.c_success)

    def _toggle_web_server(self):
        if self.web_server_thread and self.web_server_thread.is_alive():
            messagebox.showinfo("Web Server", "Web Server is already running in background.")
        else:
            def run_uvicorn():
                import uvicorn
                uvicorn.run(app, host="0.0.0.0", port=5901, log_level="warning")

            self.web_server_thread = threading.Thread(target=run_uvicorn, daemon=True)
            self.web_server_thread.start()
            self.btn_web.configure(state=tk.DISABLED, text="✓ Web Server Active")
            self.lbl_web_status.configure(text="Status: Running (Port 5901)", foreground=self.c_success)

    def _copy_to_clip(self, text):
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Copied", f"Copied to clipboard:\n{text}")

    def _clear_text(self, widget):
        widget.delete("1.0", tk.END)


if __name__ == "__main__":
    app = AntigravityDesktopApp()
    app.mainloop()
