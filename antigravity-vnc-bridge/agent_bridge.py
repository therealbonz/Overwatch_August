"""
Antigravity Agent Bridge
Provides screen capture (full desktop or Antigravity window), session discovery,
live transcript streaming, and command dispatching via agentapi.
"""

import os
import sys
import json
import time
import subprocess
import glob
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
import ctypes
from ctypes import wintypes
from PIL import Image
import mss

# Win32 definitions
user32 = ctypes.windll.user32
gdi32 = ctypes.windll.gdi32
kernel32 = ctypes.windll.kernel32

DESKTOP_ALL = 0x01FF
SW_RESTORE = 9

user32.OpenDesktopW.restype = wintypes.HDESK
user32.OpenDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
user32.SetThreadDesktop.restype = wintypes.BOOL
user32.SetThreadDesktop.argtypes = [wintypes.HDESK]

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long),
    ]

user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(RECT)]
user32.GetWindowRect.restype = wintypes.BOOL

user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL

user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL

# Paths
HOME_DIR = Path.home()
GEMINI_DIR = HOME_DIR / ".gemini"
ANTIGRAVITY_DATA_DIR = GEMINI_DIR / "antigravity"
CONVERSATIONS_DIR = ANTIGRAVITY_DATA_DIR / "conversations"
BRAIN_DIR = ANTIGRAVITY_DATA_DIR / "brain"
AGENTAPI_BAT = ANTIGRAVITY_DATA_DIR / "bin" / "agentapi.bat"
DEFAULT_LANGUAGE_SERVER = Path(r"C:\Users\Brendhann\AppData\Local\Programs\Antigravity\resources\bin\language_server.exe")


def attach_to_default_desktop():
    """Ensure the current thread is attached to the interactive Default desktop."""
    try:
        hdesk = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
            return True
    except Exception as e:
        print(f"[AgentBridge] Warning: Could not attach to Default desktop: {e}")
    return False


def get_antigravity_pids() -> List[int]:
    """Retrieve PIDs of running Antigravity instances."""
    pids = []
    try:
        cmd = ["tasklist", "/FI", "IMAGENAME eq Antigravity.exe", "/FO", "CSV", "/NH"]
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        for line in res.stdout.strip().splitlines():
            parts = [p.strip(' "') for p in line.split(",")]
            if len(parts) >= 2 and parts[0].lower().startswith("antigravity"):
                try:
                    pids.append(int(parts[1]))
                except ValueError:
                    pass
    except Exception as e:
        print(f"[AgentBridge] tasklist error: {e}")
    return pids


def find_antigravity_window() -> Optional[Tuple[int, Tuple[int, int, int, int], str]]:
    """
    Locates the primary Antigravity interactive window on the desktop.
    Returns (hwnd, (left, top, right, bottom), title) or None.
    """
    attach_to_default_desktop()
    pids = set(get_antigravity_pids())
    hdesk = user32.OpenDesktopW("Default", 0, False, DESKTOP_ALL)
    
    candidates = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def enum_cb(hwnd, lparam):
        if user32.IsWindowVisible(hwnd):
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            if not pids or pid.value in pids:
                rect = RECT()
                if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    w = rect.right - rect.left
                    h = rect.bottom - rect.top
                    # Filter out zero-size or tiny helper windows
                    if w > 300 and h > 200:
                        length = user32.GetWindowTextLengthW(hwnd)
                        title = ""
                        if length > 0:
                            buf = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buf, length + 1)
                            title = buf.value
                        candidates.append((hwnd, (rect.left, rect.top, rect.right, rect.bottom), title, w * h))
        return True

    if hdesk:
        user32.EnumDesktopWindows(hdesk, enum_cb, 0)
    else:
        user32.EnumWindows(enum_cb, 0)

    if not candidates:
        return None

    # Pick the largest window (main UI window)
    candidates.sort(key=lambda c: c[3], reverse=True)
    best = candidates[0]
    return (best[0], best[1], best[2])


def focus_antigravity_window() -> bool:
    """Brings the Antigravity window to the front."""
    win = find_antigravity_window()
    if not win:
        return False
    hwnd = win[0]
    attach_to_default_desktop()
    user32.ShowWindow(hwnd, SW_RESTORE)
    return bool(user32.SetForegroundWindow(hwnd))


def capture_frame(mode: str = "antigravity", monitor_index: int = 1) -> Image.Image:
    """
    Captures a frame:
      - mode='antigravity': Captures the Antigravity window bounding box.
      - mode='monitor': Captures specific monitor (1-based index).
      - mode='all': Captures all combined monitors.
    Returns a PIL Image (RGB).
    """
    attach_to_default_desktop()

    with mss.MSS() as sct:
        if mode == "antigravity":
            win = find_antigravity_window()
            if win:
                left, top, right, bottom = win[1]
                # Ensure width and height are positive
                w = max(1, right - left)
                h = max(1, bottom - top)
                bbox = {"left": left, "top": top, "width": w, "height": h}
                try:
                    raw = sct.grab(bbox)
                    return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")
                except Exception as e:
                    print(f"[AgentBridge] Window grab error: {e}, falling back to monitor")
        
        # Monitor fallback
        if mode == "all" or len(sct.monitors) <= 1:
            target = sct.monitors[0]
        else:
            idx = min(monitor_index, len(sct.monitors) - 1)
            target = sct.monitors[idx]

        raw = sct.grab(target)
        return Image.frombytes("RGB", raw.size, raw.bgra, "raw", "BGRX")


def list_conversations(limit: int = 20) -> List[Dict[str, Any]]:
    """
    Returns a list of conversation sessions sorted by most recent activity.
    """
    conv_files = glob.glob(str(CONVERSATIONS_DIR / "*.db"))
    results = []
    
    for f in conv_files:
        p = Path(f)
        conv_id = p.stem
        mtime = p.stat().st_mtime
        
        # Check transcript log for prompt / title
        title = ""
        transcript_path = BRAIN_DIR / conv_id / ".system_generated" / "logs" / "transcript.jsonl"
        first_prompt = ""
        last_activity = ""
        
        if transcript_path.exists():
            try:
                with open(transcript_path, "r", encoding="utf-8", errors="ignore") as tf:
                    for line in tf:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            obj = json.loads(line)
                            if not first_prompt and obj.get("type") == "USER_INPUT":
                                first_prompt = obj.get("content", "")
                            if obj.get("type") == "USER_INPUT":
                                last_activity = obj.get("created_at", "")
                        except json.JSONDecodeError:
                            pass
            except Exception:
                pass
        
        if first_prompt:
            clean_title = first_prompt.replace("<USER_REQUEST>", "").replace("</USER_REQUEST>", "").strip()
            # If multiple lines, take first non-empty line
            lines = [l.strip() for l in clean_title.splitlines() if l.strip() and not l.strip().startswith("<")]
            title = lines[0][:80] if lines else f"Conversation {conv_id[:8]}"
        else:
            title = f"Conversation {conv_id[:8]}"
        
        results.append({
            "id": conv_id,
            "title": title,
            "modified": mtime,
            "modified_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime)),
            "last_activity": last_activity,
            "has_transcript": transcript_path.exists(),
        })

    results.sort(key=lambda x: x["modified"], reverse=True)
    return results[:limit]


def get_active_conversation_id() -> Optional[str]:
    """Returns the most recently modified conversation ID."""
    convs = list_conversations(limit=1)
    if convs:
        return convs[0]["id"]
    return None


def get_recent_transcript(conversation_id: str, max_steps: int = 30) -> List[Dict[str, Any]]:
    """
    Parses recent entries from transcript.jsonl for the given conversation ID.
    """
    transcript_path = BRAIN_DIR / conversation_id / ".system_generated" / "logs" / "transcript.jsonl"
    if not transcript_path.exists():
        return []

    entries = []
    try:
        with open(transcript_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            for line in lines[-max_steps:]:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    entries.append(obj)
                except json.JSONDecodeError:
                    pass
    except Exception as e:
        print(f"[AgentBridge] Error reading transcript: {e}")
    return entries


def send_agent_command(conversation_id: str, content: str, title: Optional[str] = None) -> Dict[str, Any]:
    """
    Dispatches a prompt/command to the specified conversation using agentapi.bat.
    """
    if not conversation_id:
        return {"success": False, "error": "No conversation ID provided"}
    if not content:
        return {"success": False, "error": "Empty command content"}

    # Resolve executable
    if AGENTAPI_BAT.exists():
        cmd = [str(AGENTAPI_BAT), "send-message"]
    elif DEFAULT_LANGUAGE_SERVER.exists():
        cmd = [str(DEFAULT_LANGUAGE_SERVER), "agentapi", "send-message"]
    else:
        return {"success": False, "error": "agentapi executable not found"}

    if title:
        cmd.append(f"--title={title}")
    cmd.extend([conversation_id, content])

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if res.returncode == 0:
            try:
                data = json.loads(res.stdout)
                return {"success": True, "data": data, "raw": res.stdout}
            except json.JSONDecodeError:
                return {"success": True, "raw": res.stdout}
        else:
            return {"success": False, "error": res.stderr or res.stdout, "code": res.returncode}
    except Exception as e:
        return {"success": False, "error": str(e)}


def new_agent_conversation(prompt: str, model: str = "flash", title: Optional[str] = None) -> Dict[str, Any]:
    """
    Spawns a new conversation session via agentapi.
    """
    if AGENTAPI_BAT.exists():
        cmd = [str(AGENTAPI_BAT), "new-conversation", f"--model={model}"]
    elif DEFAULT_LANGUAGE_SERVER.exists():
        cmd = [str(DEFAULT_LANGUAGE_SERVER), "agentapi", "new-conversation", f"--model={model}"]
    else:
        return {"success": False, "error": "agentapi executable not found"}

    if title:
        cmd.append(f"--title={title}")
    cmd.append(prompt)

    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=False)
        return {"success": res.returncode == 0, "output": res.stdout, "error": res.stderr}
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    print("Testing Agent Bridge...")
    active_id = get_active_conversation_id()
    print(f"Active Conversation ID: {active_id}")
    convs = list_conversations(limit=5)
    print(f"Discovered {len(convs)} conversations:")
    for c in convs:
        print(f" - [{c['id'][:8]}] {c['modified_str']}: {c['title']}")
    
    win = find_antigravity_window()
    if win:
        print(f"Found Antigravity Window: HWND={win[0]}, Rect={win[1]}, Title='{win[2]}'")
    else:
        print("Antigravity window not found by bounds, monitor fallback active.")
    
    frame = capture_frame(mode="antigravity")
    print(f"Captured frame: size={frame.size}, mode={frame.mode}")
