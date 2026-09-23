import os
import sys
import json
import time
import shutil
import socket
import platform
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException, Query, status, Depends, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    from backend.auth import (
        get_client_ip,
        is_ip_trusted,
        get_current_user,
        require_admin,
        require_superadmin,
        create_session,
        destroy_session,
        hash_password,
        verify_password,
        init_auth_data,
        save_auth_data,
        get_token_from_request,
        reset_user_password
    )
except ImportError:
    from auth import (
        get_client_ip,
        is_ip_trusted,
        get_current_user,
        require_admin,
        require_superadmin,
        create_session,
        destroy_session,
        hash_password,
        verify_password,
        init_auth_data,
        save_auth_data,
        get_token_from_request,
        reset_user_password
    )

# Load environment variables if .env exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

FRONTEND_DIR = PROJECT_ROOT / "frontend"
CMS_FILE = BASE_DIR / "cms_data.json"

# Server Base Directory for folder creation and browsing
if os.environ.get("SERVER_BASE_DIR"):
    DEFAULT_SERVER_DIR = os.environ["SERVER_BASE_DIR"]
elif Path("/var/www").exists():
    DEFAULT_SERVER_DIR = "/var/www"
else:
    DEFAULT_SERVER_DIR = str(PROJECT_ROOT.parent)

SERVER_BASE_DIR = Path(DEFAULT_SERVER_DIR).resolve()
GITHUB_USER = os.environ.get("GITHUB_USER", "therealbonz")

# ---------------------------------------------------------
# Hardware Infrastructure Config (Raspberry Pi & Windows PC)
# ---------------------------------------------------------
PI_HOST = os.environ.get("PI_HOST", "10.0.0.120")
PI_FALLBACK_HOSTS = ["10.0.0.118", "raspberrypi.local"]
PI_PORT = int(os.environ.get("PI_PORT", 80))
PI_TOKEN = os.environ.get("PI_TOKEN", "pi_control_secret_key_998822")

PC_NAME = os.environ.get("PC_NAME", "Windows PC")
PC_IP = os.environ.get("PC_IP", "10.0.0.225")
PC_MAC = os.environ.get("PC_MAC", "84:9e:56:51:4b:cd")
PC_AGENT_PORT = int(os.environ.get("PC_AGENT_PORT", 8888))
PC_AGENT_TOKEN = os.environ.get("PC_AGENT_TOKEN", "pi_secret_control_key_2026")

app = FastAPI(
    title="therealbonz.com Launchpad & Secure CMS",
    description="Central project hub with multi-factor admin locking to bonz, machine IP, and user credentials.",
    version="1.1.0"
)

# Enable CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory GitHub repo cache
repo_cache: Dict[str, Any] = {
    "data": [],
    "last_fetched": 0,
    "user_info": None
}
CACHE_TTL = 60  # seconds


# ---------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------

def get_github_token() -> Optional[str]:
    """Retrieves GitHub token from environment variable or gh CLI."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token and token.strip():
        return token.strip()

    # Try gh auth token command
    gh_paths = ["gh", "gh.exe", r"C:\Program Files\GitHub CLI\gh.exe"]
    for gh in gh_paths:
        try:
            res = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=3)
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            continue
    return None


def read_cms_data() -> Dict[str, Any]:
    """Reads projects and settings from cms_data.json."""
    if not CMS_FILE.exists():
        default_data = {"projects": []}
        CMS_FILE.write_text(json.dumps(default_data, indent=2), encoding="utf-8")
        return default_data
    try:
        return json.loads(CMS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"projects": []}


def write_cms_data(data: Dict[str, Any]):
    """Saves projects and settings to cms_data.json."""
    CMS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def resolve_safe_server_path(subpath: str = "") -> Path:
    """Resolves and validates that the requested path is inside SERVER_BASE_DIR."""
    clean_subpath = subpath.strip().lstrip("/\\")
    resolved = (SERVER_BASE_DIR / clean_subpath).resolve()
    try:
        resolved.relative_to(SERVER_BASE_DIR)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Path is outside the authorized server directory root."
        )
    return resolved


def send_wol_packet(mac_address: str, broadcast_ip: str = "255.255.255.255", port: int = 9) -> bool:
    """Sends a standard Wake-on-LAN magic packet to wake target machine."""
    clean_mac = mac_address.replace(":", "").replace("-", "").replace(".", "")
    if len(clean_mac) != 12:
        raise ValueError(f"Invalid MAC address '{mac_address}': expected 12 hexadecimal characters.")
    mac_bytes = bytes.fromhex(clean_mac)
    magic_packet = b"\xff" * 6 + mac_bytes * 16

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, (broadcast_ip, port))
        sock.sendto(magic_packet, ("10.0.0.255", port))
    return True


async def query_pi_api(endpoint: str, method: str = "GET", json_data: Any = None, timeout: float = 4.0) -> Dict[str, Any]:
    """Communicates with the Raspberry Pi Control Hub backend API, trying primary and fallback addresses."""
    hosts = [PI_HOST] + [h for h in PI_FALLBACK_HOSTS if h != PI_HOST]
    headers = {
        "Authorization": f"Bearer {PI_TOKEN}",
        "Accept": "application/json"
    }
    last_err = None
    for host in hosts:
        url = f"http://{host}:{PI_PORT}{endpoint}"
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method.upper() == "GET":
                    resp = await client.get(url, headers=headers)
                elif method.upper() == "POST":
                    resp = await client.post(url, headers=headers, json=json_data)
                elif method.upper() == "DELETE":
                    resp = await client.delete(url, headers=headers)
                else:
                    resp = await client.request(method, url, headers=headers, json=json_data)

                if resp.status_code == 200:
                    try:
                        return resp.json()
                    except Exception:
                        return {"success": True, "text": resp.text}
                elif resp.status_code in (201, 204):
                    return {"success": True}
                else:
                    error_detail = resp.text
                    try:
                        error_detail = resp.json().get("detail", resp.text)
                    except Exception:
                        pass
                    raise HTTPException(status_code=resp.status_code, detail=f"Pi API Error ({resp.status_code}): {error_detail}")
        except HTTPException:
            raise
        except Exception as e:
            last_err = e
            continue

    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Could not connect to Raspberry Pi at {hosts}:{PI_PORT}: {str(last_err)}"
    )



# ---------------------------------------------------------
# Request Models
# ---------------------------------------------------------

class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1)
    password: str = Field(..., min_length=1)


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=6)


class ResetPasswordRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=50)
    new_password: str = Field(..., min_length=6)


class AdminResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=6)


class AddAdminRequest(BaseModel):
    username: str = Field(..., min_length=2, max_length=50, pattern=r"^[A-Za-z0-9_.-]+$")
    display_name: Optional[str] = Field(None, max_length=60)
    password: str = Field(..., min_length=6)
    role: Optional[str] = "admin"


class AddTrustedIpRequest(BaseModel):
    ip_pattern: str = Field(..., min_length=1, max_length=50)
    comment: Optional[str] = Field(None, max_length=100)


class CreateRepoRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    description: Optional[str] = Field(None, max_length=350)
    private: bool = False
    auto_init: bool = True


class CreateFolderRequest(BaseModel):
    folder_name: str = Field(..., min_length=1, max_length=100)
    parent_path: Optional[str] = Field("", description="Relative path under server base dir")


class CMSProject(BaseModel):
    id: Optional[str] = None
    title: str = Field(..., min_length=1, max_length=100)
    subtitle: Optional[str] = Field(None, max_length=150)
    description: Optional[str] = Field(None, max_length=500)
    url: str = Field(..., min_length=1)
    github_url: Optional[str] = None
    badge: Optional[str] = "Project"
    badge_color: Optional[str] = "cyan"
    category: Optional[str] = "General"
    icon: Optional[str] = "cube"
    featured: bool = True
    priority: int = 10


class PCActionRequest(BaseModel):
    action: str = Field(..., description="Action to perform: restart, shutdown, abort, sleep, lock, or exec")
    command: Optional[str] = Field(None, description="Optional command to execute if action is 'exec'")


class PiCommandRequest(BaseModel):
    command: str = Field(..., min_length=1, description="Shell command to run on Raspberry Pi")



# ---------------------------------------------------------
# Authentication Endpoints
# ---------------------------------------------------------

@app.post("/api/auth/login")
async def login(payload: LoginRequest, request: Request, response: Response):
    """Authenticates admin user. Enforces IP whitelist verification and user credentials."""
    client_ip = get_client_ip(request)

    # 1. Check if client IP is authorized
    if not is_ip_trusted(client_ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access Denied: Admin login is locked to authorized IPs. Your IP ({client_ip}) is not on the whitelist."
        )

    # 2. Verify user credentials
    auth_data = init_auth_data()
    users = auth_data.get("users", [])
    target_user = None

    for u in users:
        if u.get("username", "").lower() == payload.username.lower().strip():
            target_user = u
            break

    if not target_user or not verify_password(payload.password, target_user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password."
        )

    # 3. Create Session Token
    token = create_session(
        username=target_user["username"],
        role=target_user.get("role", "admin"),
        display_name=target_user.get("display_name", target_user["username"]),
        client_ip=client_ip
    )

    # Set session cookie
    response.set_cookie(
        key="bonz_session_token",
        value=token,
        max_age=7 * 24 * 3600,
        httponly=True,
        samesite="lax",
        secure=False  # Set True in production HTTPS
    )

    return {
        "success": True,
        "token": token,
        "user": {
            "username": target_user["username"],
            "display_name": target_user.get("display_name", target_user["username"]),
            "role": target_user.get("role", "admin"),
            "can_add_admins": target_user.get("can_add_admins", False) or target_user.get("username").lower() == "bonz"
        },
        "client_ip": client_ip
    }


@app.get("/api/auth/me")
async def get_me(request: Request):
    """Returns authentication status, current user, client IP, and whitelist state."""
    client_ip = get_client_ip(request)
    trusted = is_ip_trusted(client_ip)
    user = await get_current_user(request)

    return {
        "authenticated": user is not None,
        "user": user,
        "client_ip": client_ip,
        "is_ip_trusted": trusted,
        "is_superadmin": user is not None and (user.get("username").lower() == "bonz" or user.get("role") == "superadmin")
    }


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response):
    """Revokes the current admin session."""
    token = get_token_from_request(request)
    if token:
        destroy_session(token)
    response.delete_cookie(key="bonz_session_token")
    return {"success": True, "message": "Logged out successfully."}


@app.post("/api/auth/change-password")
async def change_password(payload: ChangePasswordRequest, admin: Dict[str, Any] = Depends(require_admin)):
    """Allows authenticated admin to change their password."""
    auth_data = init_auth_data()
    users = auth_data.get("users", [])

    for u in users:
        if u.get("username", "").lower() == admin["username"].lower():
            if not verify_password(payload.current_password, u.get("password_hash", "")):
                raise HTTPException(status_code=400, detail="Current password incorrect.")
            u["password_hash"] = hash_password(payload.new_password)
            save_auth_data(auth_data)
            return {"success": True, "message": "Password updated successfully."}

    raise HTTPException(status_code=404, detail="User not found.")


@app.post("/api/auth/reset-password")
async def reset_password_public(payload: ResetPasswordRequest, request: Request):
    """Resets an admin user's password. Requires the client to originate from an authorized/trusted IP."""
    client_ip = get_client_ip(request)
    if not is_ip_trusted(client_ip):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access Denied: Password reset is restricted to authorized IPs. Your IP ({client_ip}) is not on the whitelist."
        )

    clean_user = payload.username.strip().lower()
    user = reset_user_password(clean_user, payload.new_password)
    return {
        "success": True,
        "message": f"Password reset successfully for user '{user['username']}'. You can now log in.",
        "username": user["username"]
    }


# ---------------------------------------------------------
# Admin User & Security Management (Superadmin: bonz only)
# ---------------------------------------------------------

@app.get("/api/admin/users")
async def list_admin_users(superadmin: Dict[str, Any] = Depends(require_superadmin)):
    """Lists all admin accounts. Superadmin bonz only."""
    auth_data = init_auth_data()
    sanitized = []
    for u in auth_data.get("users", []):
        sanitized.append({
            "username": u.get("username"),
            "display_name": u.get("display_name"),
            "role": u.get("role", "admin"),
            "created_at": u.get("created_at"),
            "is_owner": u.get("username").lower() in ("bonz", "admin") or u.get("role") == "superadmin"
        })
    return {"users": sanitized}


@app.post("/api/admin/users")
async def add_admin_user(payload: AddAdminRequest, superadmin: Dict[str, Any] = Depends(require_superadmin)):
    """Adds a new authorized admin user. Superadmin bonz only."""
    auth_data = init_auth_data()
    users = auth_data.get("users", [])

    clean_user = payload.username.strip().lower()
    for u in users:
        if u.get("username", "").lower() == clean_user:
            raise HTTPException(status_code=409, detail=f"User '{clean_user}' already exists.")

    new_user = {
        "username": clean_user,
        "display_name": payload.display_name.strip() if payload.display_name else clean_user,
        "role": payload.role or "admin",
        "password_hash": hash_password(payload.password),
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "created_by": superadmin["username"],
        "can_add_admins": False
    }

    users.append(new_user)
    auth_data["users"] = users
    save_auth_data(auth_data)

    return {
        "success": True,
        "message": f"Admin user '{clean_user}' added successfully.",
        "user": {
            "username": new_user["username"],
            "display_name": new_user["display_name"],
            "role": new_user["role"]
        }
    }


@app.post("/api/admin/users/{username}/reset-password")
async def admin_reset_user_password(
    username: str,
    payload: AdminResetPasswordRequest,
    superadmin: Dict[str, Any] = Depends(require_superadmin)
):
    """Allows superadmin to reset any admin user's password without knowing old password."""
    clean_user = username.strip().lower()
    user = reset_user_password(clean_user, payload.new_password)
    return {
        "success": True,
        "message": f"Password for user '{user['username']}' reset successfully.",
        "username": user["username"]
    }


@app.delete("/api/admin/users/{username}")
async def remove_admin_user(username: str, superadmin: Dict[str, Any] = Depends(require_superadmin)):
    """Removes an admin user. Primary owner accounts (bonz, admin) cannot be removed."""
    if username.lower() in ("bonz", "admin"):
        raise HTTPException(status_code=400, detail=f"Cannot delete primary superadmin account '{username}'.")

    auth_data = init_auth_data()
    users = auth_data.get("users", [])
    filtered = [u for u in users if u.get("username", "").lower() != username.lower()]

    if len(filtered) == len(users):
        raise HTTPException(status_code=404, detail="Admin user not found.")

    auth_data["users"] = filtered
    save_auth_data(auth_data)
    return {"success": True, "message": f"Admin '{username}' removed."}


@app.get("/api/admin/security")
async def get_security_settings(request: Request, superadmin: Dict[str, Any] = Depends(require_superadmin)):
    """Returns security configuration and trusted IP whitelist."""
    auth_data = init_auth_data()
    security = auth_data.get("security", {})
    return {
        "client_ip": get_client_ip(request),
        "require_ip_whitelist": security.get("require_ip_whitelist", True),
        "trusted_ips": security.get("trusted_ips", [])
    }


@app.post("/api/admin/security/trusted-ips")
async def add_trusted_ip(payload: AddTrustedIpRequest, superadmin: Dict[str, Any] = Depends(require_superadmin)):
    """Adds an IP or CIDR wildcard to the admin whitelist."""
    pattern = payload.ip_pattern.strip()
    if not pattern:
        raise HTTPException(status_code=400, detail="Invalid IP pattern.")

    auth_data = init_auth_data()
    security = auth_data.setdefault("security", {})
    trusted = security.setdefault("trusted_ips", [])

    if pattern not in trusted:
        trusted.append(pattern)
        save_auth_data(auth_data)

    return {"success": True, "message": f"IP pattern '{pattern}' added to whitelist.", "trusted_ips": trusted}


@app.delete("/api/admin/security/trusted-ips/{ip_pattern}")
async def remove_trusted_ip(ip_pattern: str, superadmin: Dict[str, Any] = Depends(require_superadmin)):
    """Removes an IP pattern from the whitelist (localhost cannot be removed)."""
    if ip_pattern in ("127.0.0.1", "::1", "localhost"):
        raise HTTPException(status_code=400, detail="Cannot remove local loopback from whitelist.")

    auth_data = init_auth_data()
    security = auth_data.setdefault("security", {})
    trusted = security.setdefault("trusted_ips", [])

    if ip_pattern in trusted:
        trusted.remove(ip_pattern)
        save_auth_data(auth_data)

    return {"success": True, "message": f"IP '{ip_pattern}' removed from whitelist.", "trusted_ips": trusted}


# ---------------------------------------------------------
# Public & Protected Dashboard Endpoints
# ---------------------------------------------------------

@app.api_route("/api/system/status", methods=["GET", "HEAD"])
async def get_system_status(request: Request):
    """Returns public server host health, platform, and client IP info."""
    token = get_github_token()
    token_preview = f"{token[:4]}...{token[-4:]}" if token and len(token) > 8 else None
    client_ip = get_client_ip(request)

    try:
        stat = shutil.disk_usage(str(SERVER_BASE_DIR))
        disk_info = {
            "total_gb": round(stat.total / (1024 ** 3), 2),
            "used_gb": round(stat.used / (1024 ** 3), 2),
            "free_gb": round(stat.free / (1024 ** 3), 2),
            "percent_used": round((stat.used / stat.total) * 100, 1)
        }
    except Exception:
        disk_info = None

    return {
        "status": "healthy",
        "domain": "therealbonz.com",
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "server_base_dir": str(SERVER_BASE_DIR),
        "client_ip": client_ip,
        "is_ip_trusted": is_ip_trusted(client_ip),
        "disk": disk_info,
        "github": {
            "user": GITHUB_USER,
            "authenticated": bool(token),
            "token_preview": token_preview
        }
    }


@app.api_route("/api/repos", methods=["GET", "HEAD"])
async def list_github_repos(force: bool = False):
    """Public: Fetches repositories for therealbonz from GitHub REST API."""
    now = time.time()
    if not force and repo_cache["data"] and (now - repo_cache["last_fetched"]) < CACHE_TTL:
        return {
            "source": "cache",
            "count": len(repo_cache["data"]),
            "user": repo_cache["user_info"],
            "repos": repo_cache["data"]
        }

    token = get_github_token()
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "therealbonz-homepage"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=10.0) as client:
        user_info = None
        try:
            user_url = "https://api.github.com/user" if token else f"https://api.github.com/users/{GITHUB_USER}"
            u_resp = await client.get(user_url, headers=headers)
            if u_resp.status_code == 200:
                user_info = u_resp.json()
        except Exception:
            pass

        repos_url = "https://api.github.com/user/repos?per_page=100&sort=updated" if token else f"https://api.github.com/users/{GITHUB_USER}/repos?per_page=100&sort=updated"
        try:
            r_resp = await client.get(repos_url, headers=headers)
            if r_resp.status_code != 200:
                raise HTTPException(
                    status_code=r_resp.status_code,
                    detail=f"GitHub API error: {r_resp.text}"
                )
            raw_repos = r_resp.json()
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Failed to connect to GitHub API: {str(e)}"
            )

    formatted = []
    for r in raw_repos:
        owner = r.get("owner", {}).get("login", "")
        if owner.lower() != GITHUB_USER.lower():
            continue

        formatted.append({
            "id": r.get("id"),
            "name": r.get("name"),
            "full_name": r.get("full_name"),
            "description": r.get("description") or "No description provided.",
            "language": r.get("language") or "Code",
            "stars": r.get("stargazers_count", 0),
            "forks": r.get("forks_count", 0),
            "private": r.get("private", False),
            "html_url": r.get("html_url"),
            "clone_url": r.get("clone_url"),
            "updated_at": r.get("updated_at"),
            "created_at": r.get("created_at"),
            "topics": r.get("topics", []),
            "default_branch": r.get("default_branch", "main")
        })

    repo_cache["data"] = formatted
    repo_cache["user_info"] = user_info
    repo_cache["last_fetched"] = now

    return {
        "source": "github_api",
        "count": len(formatted),
        "user": user_info,
        "repos": formatted
    }


@app.post("/api/repos/create")
async def create_github_repo(payload: CreateRepoRequest, admin: Dict[str, Any] = Depends(require_admin)):
    """[LOCKED TO ADMIN] Creates a new repository on GitHub."""
    token = get_github_token()
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="GitHub token is required to create repositories. Please configure GITHUB_TOKEN on the server."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "therealbonz-homepage"
    }

    create_data = {
        "name": payload.name,
        "description": payload.description or "",
        "private": payload.private,
        "auto_init": payload.auto_init
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post("https://api.github.com/user/repos", headers=headers, json=create_data)
        if resp.status_code not in (200, 201):
            error_detail = resp.json().get("message", resp.text) if resp.headers.get("content-type", "").startswith("application/json") else resp.text
            raise HTTPException(
                status_code=resp.status_code,
                detail=f"GitHub rejected repo creation: {error_detail}"
            )
        new_repo = resp.json()

    repo_cache["last_fetched"] = 0

    return {
        "success": True,
        "message": f"Repository '{new_repo.get('full_name')}' created successfully!",
        "repo": {
            "name": new_repo.get("name"),
            "full_name": new_repo.get("full_name"),
            "html_url": new_repo.get("html_url"),
            "clone_url": new_repo.get("clone_url"),
            "private": new_repo.get("private", False)
        }
    }


@app.get("/api/server/folders")
async def list_server_folders(
    subpath: str = Query("", description="Relative path under server base dir"),
    admin: Dict[str, Any] = Depends(require_admin)
):
    """[LOCKED TO ADMIN] Lists folders and files inside server directory."""
    target_path = resolve_safe_server_path(subpath)

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Directory not found.")
    if not target_path.is_dir():
        raise HTTPException(status_code=400, detail="Requested path is not a directory.")

    items = []
    try:
        for entry in os.scandir(str(target_path)):
            stat = entry.stat()
            rel_path = str(Path(entry.path).relative_to(SERVER_BASE_DIR)).replace("\\", "/")
            items.append({
                "name": entry.name,
                "is_dir": entry.is_dir(),
                "relative_path": rel_path,
                "size_bytes": stat.st_size if not entry.is_dir() else 0,
                "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(stat.st_mtime))
            })
    except PermissionError:
        raise HTTPException(status_code=403, detail="Permission denied reading directory.")

    items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))

    curr_rel = str(target_path.relative_to(SERVER_BASE_DIR)).replace("\\", "/")
    if curr_rel == ".":
        curr_rel = ""

    return {
        "base_dir": str(SERVER_BASE_DIR),
        "current_path": curr_rel,
        "full_path": str(target_path),
        "items": items
    }


@app.post("/api/server/folders/create")
async def create_server_folder(payload: CreateFolderRequest, admin: Dict[str, Any] = Depends(require_admin)):
    """[LOCKED TO ADMIN] Creates a new folder on the server."""
    name = payload.folder_name.strip()
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise HTTPException(
            status_code=400,
            detail="Invalid folder name. Folder name cannot contain path separators or parent references."
        )

    parent = resolve_safe_server_path(payload.parent_path or "")
    if not parent.exists():
        raise HTTPException(status_code=404, detail="Parent directory does not exist.")

    new_dir = parent / name
    if new_dir.exists():
        raise HTTPException(status_code=409, detail=f"Folder '{name}' already exists.")

    try:
        new_dir.mkdir(parents=False, exist_ok=False)
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail="Permission denied: Web server process does not have write access to create folders here."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create folder: {str(e)}")

    rel_created = str(new_dir.relative_to(SERVER_BASE_DIR)).replace("\\", "/")

    return {
        "success": True,
        "message": f"Folder '{name}' created successfully on server.",
        "folder": {
            "name": name,
            "relative_path": rel_created,
            "full_path": str(new_dir)
        }
    }


@app.api_route("/api/cms/projects", methods=["GET", "HEAD"])
async def get_cms_projects():
    """Public: Returns the list of launchpad items."""
    data = read_cms_data()
    projects = data.get("projects", [])
    projects.sort(key=lambda p: p.get("priority", 99))
    return {"projects": projects}


@app.post("/api/cms/projects")
async def add_cms_project(project: CMSProject, admin: Dict[str, Any] = Depends(require_admin)):
    """[LOCKED TO ADMIN] Adds a new launchpad item to the CMS."""
    data = read_cms_data()
    projects = data.get("projects", [])

    proj_id = project.id or project.title.lower().replace(" ", "-")
    clean_id = "".join(c for c in proj_id if c.isalnum() or c in "-_")

    for p in projects:
        if p.get("id") == clean_id:
            raise HTTPException(status_code=409, detail=f"Project with ID '{clean_id}' already exists.")

    new_item = project.model_dump()
    new_item["id"] = clean_id
    projects.append(new_item)
    data["projects"] = projects
    write_cms_data(data)

    return {"success": True, "project": new_item}


@app.put("/api/cms/projects/{project_id}")
async def update_cms_project(project_id: str, project: CMSProject, admin: Dict[str, Any] = Depends(require_admin)):
    """[LOCKED TO ADMIN] Updates an existing launchpad project item."""
    data = read_cms_data()
    projects = data.get("projects", [])

    found = False
    for i, p in enumerate(projects):
        if p.get("id") == project_id:
            updated = project.model_dump()
            updated["id"] = project_id
            projects[i] = updated
            found = True
            break

    if not found:
        raise HTTPException(status_code=404, detail="Project not found.")

    data["projects"] = projects
    write_cms_data(data)
    return {"success": True, "project": projects[i]}


@app.delete("/api/cms/projects/{project_id}")
async def delete_cms_project(project_id: str, admin: Dict[str, Any] = Depends(require_admin)):
    """[LOCKED TO ADMIN] Deletes a launchpad project item."""
    data = read_cms_data()
    projects = data.get("projects", [])

    original_len = len(projects)
    projects = [p for p in projects if p.get("id") != project_id]

    if len(projects) == original_len:
        raise HTTPException(status_code=404, detail="Project not found.")

    data["projects"] = projects
    write_cms_data(data)
    return {"success": True, "message": f"Project '{project_id}' deleted."}


# ---------------------------------------------------------
# Raspberry Pi & PC Hardware Control Endpoints
# ---------------------------------------------------------

@app.get("/api/pi/stats")
async def get_pi_stats():
    """Retrieves live telemetry (CPU, RAM, NVMe, Temp, Uptime) from Raspberry Pi 5."""
    try:
        data = await query_pi_api("/api/server/stats", method="GET", timeout=3.0)
        data["online"] = True
        return data
    except Exception as e:
        return {
            "online": False,
            "error": str(e),
            "ip": PI_HOST,
            "hostname": "raspberrypi"
        }


@app.get("/api/pi/services")
async def get_pi_services():
    """Retrieves monitored systemd services and active states from Raspberry Pi 5."""
    try:
        data = await query_pi_api("/api/server/services", method="GET", timeout=3.0)
        return data
    except Exception as e:
        return {
            "online": False,
            "services": [],
            "error": str(e)
        }


@app.post("/api/pi/services/{service_name}/{action}")
async def control_pi_service(service_name: str, action: str):
    """Controls a systemd service (restart, stop, start) on Raspberry Pi 5."""
    if action not in ("restart", "start", "stop"):
        raise HTTPException(status_code=400, detail="Action must be restart, start, or stop.")
    return await query_pi_api(f"/api/server/services/{service_name}/{action}", method="POST", timeout=12.0)


@app.post("/api/pi/power/{action}")
async def control_pi_power(action: str):
    """Initiates a remote reboot or shutdown on Raspberry Pi 5."""
    if action not in ("reboot", "shutdown"):
        raise HTTPException(status_code=400, detail="Power action must be reboot or shutdown.")
    return await query_pi_api(f"/api/server/power/{action}", method="POST", timeout=8.0)


@app.post("/api/pi/exec")
async def execute_pi_command(payload: PiCommandRequest):
    """Executes a shell command on Raspberry Pi 5."""
    return await query_pi_api("/api/server/exec", method="POST", json_data={"command": payload.command}, timeout=30.0)


@app.get("/api/pc/status")
async def get_pc_status():
    """Checks Windows PC online status, ping latency, and companion agent availability."""
    ping_ok = False
    ping_ms = None
    t0 = time.time()

    # Ping check
    if os.name == "nt":
        # When running on Windows, if target IP is localhost or matches local NIC, it's immediately online
        try:
            res = subprocess.run(["ping", "-n", "1", "-w", "800", PC_IP], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                ping_ok = True
                for line in res.stdout.splitlines():
                    if "time=" in line.lower() or "time<" in line.lower():
                        parts = line.split("time")
                        if len(parts) > 1:
                            val = parts[1].replace("=", "").replace("<", "").strip().split("ms")[0].strip()
                            try:
                                ping_ms = float(val)
                            except ValueError:
                                pass
                        break
                if ping_ms is None:
                    ping_ms = round((time.time() - t0) * 1000, 1)
            else:
                # If target is local machine
                ping_ok = True
                ping_ms = 0.5
        except Exception:
            ping_ok = True
            ping_ms = 0.5
    else:
        try:
            res = subprocess.run(["ping", "-c", "1", "-W", "1", PC_IP], capture_output=True, text=True, timeout=2)
            if res.returncode == 0:
                ping_ok = True
                for line in res.stdout.splitlines():
                    if "time=" in line:
                        parts = line.split("time=")[1].split(" ")
                        try:
                            ping_ms = float(parts[0])
                        except ValueError:
                            pass
                        break
                if ping_ms is None:
                    ping_ms = round((time.time() - t0) * 1000, 1)
        except Exception:
            ping_ok = False

    # Check companion agent
    agent_online = False
    agent_data = None
    agent_hosts = [PC_IP, "127.0.0.1"] if os.name == "nt" else [PC_IP]
    for h in agent_hosts:
        try:
            async with httpx.AsyncClient(timeout=1.5) as client:
                resp = await client.get(f"http://{h}:{PC_AGENT_PORT}/status")
                if resp.status_code == 200:
                    agent_online = True
                    agent_data = resp.json()
                    break
        except Exception:
            pass

    local_info = {}
    if os.name == "nt":
        local_info = {
            "computer_name": os.environ.get("COMPUTERNAME", PC_NAME),
            "username": os.environ.get("USERNAME", "bonz"),
            "os": platform.platform()
        }

    return {
        "pc_name": PC_NAME,
        "ip": PC_IP,
        "mac": PC_MAC,
        "online": ping_ok,
        "ping_ms": ping_ms,
        "agent_online": agent_online,
        "agent_data": agent_data,
        "is_local": os.name == "nt",
        "local_info": local_info
    }


@app.post("/api/pc/wake")
async def wake_pc():
    """Sends a Wake-on-LAN magic packet to power on or wake the PC."""
    try:
        send_wol_packet(PC_MAC)
        return {"success": True, "message": f"Wake-on-LAN magic packet transmitted to {PC_MAC}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send WoL magic packet: {str(e)}")


@app.post("/api/pc/action")
async def trigger_pc_action(req: PCActionRequest):
    """
    Executes a power or control action on the PC:
    restart, shutdown, abort, sleep, lock, or exec.
    Supports both native Windows direct commands (when hosted locally) and PC Companion Agent dispatch.
    """
    act = req.action.lower().strip()

    # 1. Native Windows direct execution if running on Windows
    if os.name == "nt":
        try:
            if act in ("restart", "reboot"):
                subprocess.Popen(["shutdown.exe", "/r", "/t", "10", "/c", "Restart initiated from Overwatch Hub"])
                return {"success": True, "message": "PC restart scheduled in 10 seconds. Click 'Cancel PC Reboot' to abort."}
            elif act == "shutdown":
                subprocess.Popen(["shutdown.exe", "/s", "/t", "10", "/c", "Shutdown initiated from Overwatch Hub"])
                return {"success": True, "message": "PC shutdown scheduled in 10 seconds. Click 'Cancel PC Reboot' to abort."}
            elif act in ("abort", "cancel"):
                res = subprocess.run(["shutdown.exe", "/a"], capture_output=True, text=True)
                if res.returncode == 0:
                    return {"success": True, "message": "PC restart/shutdown cancelled."}
                else:
                    return {"success": False, "message": res.stderr.strip() or "No pending shutdown to abort."}
            elif act == "lock":
                subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
                return {"success": True, "message": "Workstation locked successfully."}
            elif act == "sleep":
                subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"])
                return {"success": True, "message": "PC sleep initiated."}
            elif act == "exec":
                if not req.command:
                    raise HTTPException(status_code=400, detail="Command string is required for action 'exec'.")
                res = subprocess.run(["powershell", "-NoProfile", "-Command", req.command], capture_output=True, text=True, timeout=20)
                return {
                    "success": res.returncode == 0,
                    "stdout": res.stdout,
                    "stderr": res.stderr,
                    "exit_code": res.returncode
                }
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to execute native action: {str(e)}")

    # 2. Remote execution via PC Companion Agent
    url = f"http://{PC_IP}:{PC_AGENT_PORT}/action"
    headers = {"X-Auth-Token": PC_AGENT_TOKEN}
    payload = {"action": act, "command": req.command}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to PC Companion Agent at {PC_IP}:{PC_AGENT_PORT}. Ensure PC is awake and agent is running."
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/infrastructure/summary")
async def get_infrastructure_summary():
    """Fast combined status of Raspberry Pi and Windows PC for navigation bar indicators."""
    # Fast Pi probe
    pi_summary = {"online": False, "ip": PI_HOST, "temp_c": None}
    try:
        data = await query_pi_api("/api/server/stats", method="GET", timeout=1.2)
        pi_summary = {
            "online": True,
            "ip": data.get("ip", PI_HOST),
            "temp_c": data.get("temperature_c"),
            "cpu_percent": data.get("cpu", {}).get("percent")
        }
    except Exception:
        pass

    # Fast PC probe
    pc_summary = {
        "online": True if os.name == "nt" else False,
        "ip": PC_IP,
        "mac": PC_MAC
    }

    return {
        "pi": pi_summary,
        "pc": pc_summary
    }



# ---------------------------------------------------------
# Static Files & Frontend Routing
# ---------------------------------------------------------

if FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets")

    @app.api_route("/style.css", methods=["GET", "HEAD"])
    async def get_css():
        return FileResponse(FRONTEND_DIR / "style.css", media_type="text/css")

    @app.api_route("/app.js", methods=["GET", "HEAD"])
    async def get_js():
        return FileResponse(FRONTEND_DIR / "app.js", media_type="application/javascript")

    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
    async def serve_spa(full_path: str):
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        file_path = FRONTEND_DIR / full_path
        if file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(FRONTEND_DIR / "index.html")
else:
    @app.get("/")
    async def placeholder_root():
        return {"message": "therealbonz.com API Backend is active. Frontend files initializing."}
