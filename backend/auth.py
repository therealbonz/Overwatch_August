import os
import json
import time
import secrets
import hashlib
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import Request, HTTPException, status, Depends
from pydantic import BaseModel, Field

AUTH_FILE = Path(__file__).resolve().parent / "auth_data.json"
SESSIONS_FILE = Path(__file__).resolve().parent / "sessions.json"

# In-memory active sessions: token -> { username, role, ip, expires_at }
active_sessions: Dict[str, Dict[str, Any]] = {}
SESSION_DURATION_HOURS = 24 * 7  # 7 days


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hashes password with SHA-256 and a cryptographic salt."""
    if not salt:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
    return f"{salt}${hashed}"


def verify_password(password: str, hashed_str: str) -> bool:
    """Verifies a plaintext password against a salt$hash string."""
    try:
        salt, expected_hash = hashed_str.split("$", 1)
        actual_hash = hashlib.sha256((salt + password).encode("utf-8")).hexdigest()
        return secrets.compare_digest(expected_hash, actual_hash)
    except Exception:
        return False


def get_client_ip(request: Request) -> str:
    """Extracts client IP, respecting Nginx reverse proxy headers."""
    # Nginx X-Forwarded-For can be a comma-separated list of IPs
    x_forwarded = request.headers.get("x-forwarded-for")
    if x_forwarded:
        parts = [p.strip() for p in x_forwarded.split(",")]
        if parts and parts[0]:
            return parts[0]

    x_real_ip = request.headers.get("x-real-ip")
    if x_real_ip:
        return x_real_ip.strip()

    if request.client and request.client.host:
        return request.client.host.strip()

    return "127.0.0.1"


def init_auth_data() -> Dict[str, Any]:
    """Initializes auth_data.json with bonz superadmin and trusted IPs."""
    if AUTH_FILE.exists():
        try:
            return json.loads(AUTH_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Default initial password for bonz: 'bonzadmin2026'
    initial_password = "bonzadmin2026"
    password_hash = hash_password(initial_password)

    default_data = {
        "users": [
            {
                "username": "bonz",
                "display_name": "Bonz (Superadmin)",
                "role": "superadmin",
                "password_hash": password_hash,
                "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "can_add_admins": True
            }
        ],
        "security": {
            "require_ip_whitelist": True,
            "trusted_ips": [
                "127.0.0.1",
                "::1",
                "68.146.118.91",      # User's current external IP
                "10.0.0.*",           # Local home LAN
                "172.27.208.*",       # WSL / Virtual network
                "localhost"
            ]
        }
    }

    AUTH_FILE.write_text(json.dumps(default_data, indent=2), encoding="utf-8")
    return default_data


def save_auth_data(data: Dict[str, Any]):
    AUTH_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_sessions():
    """Loads persisted sessions from disk."""
    global active_sessions
    if SESSIONS_FILE.exists():
        try:
            active_sessions = json.loads(SESSIONS_FILE.read_text(encoding="utf-8"))
        except Exception:
            active_sessions = {}


def save_sessions():
    """Saves active sessions to disk."""
    SESSIONS_FILE.write_text(json.dumps(active_sessions, indent=2), encoding="utf-8")


# Initialize on import
init_auth_data()
load_sessions()


def is_ip_trusted(client_ip: str) -> bool:
    """Checks whether the client IP matches any trusted IP or wildcard."""
    data = init_auth_data()
    security = data.get("security", {})
    if not security.get("require_ip_whitelist", True):
        return True

    trusted_list = security.get("trusted_ips", ["127.0.0.1", "::1"])
    clean_ip = client_ip.strip()

    # Local loopback equivalents
    if clean_ip in ("127.0.0.1", "::1", "localhost", "testclient"):
        return True

    for pattern in trusted_list:
        pattern = pattern.strip()
        if pattern == "*" or pattern == clean_ip:
            return True
        if pattern.endswith("*"):
            prefix = pattern[:-1]
            if clean_ip.startswith(prefix):
                return True
    return False


def get_token_from_request(request: Request) -> Optional[str]:
    """Retrieves session token from Authorization header, X-Admin-Token, or cookie."""
    auth_header = request.headers.get("authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:].strip()

    header_token = request.headers.get("x-admin-token")
    if header_token and header_token.strip():
        return header_token.strip()

    cookie_token = request.cookies.get("bonz_session_token")
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()

    return None


async def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """Returns current authenticated admin user or None if guest."""
    token = get_token_from_request(request)
    if not token or token not in active_sessions:
        return None

    session = active_sessions[token]
    now = time.time()
    if session.get("expires_at", 0) < now:
        del active_sessions[token]
        save_sessions()
        return None

    return {
        "username": session["username"],
        "role": session.get("role", "admin"),
        "display_name": session.get("display_name", session["username"]),
        "client_ip": get_client_ip(request),
        "is_trusted_ip": is_ip_trusted(get_client_ip(request))
    }


async def require_admin(request: Request) -> Dict[str, Any]:
    """FastAPI Dependency: requires authenticated admin and trusted IP."""
    client_ip = get_client_ip(request)

    # 1. IP Whitelist check
    if not is_ip_trusted(client_ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access Denied: Your IP address ({client_ip}) is not on the admin authorized whitelist."
        )

    # 2. Authentication check
    user = await get_current_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin authentication required. Please log in through the admin panel."
        )

    return user


async def require_superadmin(request: Request) -> Dict[str, Any]:
    """FastAPI Dependency: requires user bonz or superadmin role."""
    user = await require_admin(request)
    if user["username"].lower() != "bonz" and user.get("role") != "superadmin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Superadmin privilege required for this operation."
        )
    return user


def create_session(username: str, role: str, display_name: str, client_ip: str) -> str:
    """Generates a secure session token and registers it."""
    token = secrets.token_hex(32)
    active_sessions[token] = {
        "username": username,
        "role": role,
        "display_name": display_name,
        "client_ip": client_ip,
        "created_at": time.time(),
        "expires_at": time.time() + (SESSION_DURATION_HOURS * 3600)
    }
    save_sessions()
    return token


def destroy_session(token: str):
    if token in active_sessions:
        del active_sessions[token]
        save_sessions()
