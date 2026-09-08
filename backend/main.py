import os
import sys
import json
import time
import shutil
import platform
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

import httpx
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

# Load environment variables if .env exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
CMS_FILE = BASE_DIR / "cms_data.json"

# Server Base Directory for folder creation and browsing
# Production default: /var/www, Development fallback: parent of PROJECT_ROOT or BASE_DIR
if os.name == "nt":
    DEFAULT_SERVER_DIR = str(PROJECT_ROOT.parent)
else:
    DEFAULT_SERVER_DIR = "/var/www"

SERVER_BASE_DIR = Path(os.environ.get("SERVER_BASE_DIR", DEFAULT_SERVER_DIR)).resolve()
GITHUB_USER = os.environ.get("GITHUB_USER", "therealbonz")

app = FastAPI(
    title="therealbonz.com Launchpad & CMS",
    description="Central project hub, GitHub integration, server manager, and 3D studio.",
    version="1.0.0"
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
    # Strip any leading slashes or Windows drive specifiers from relative subpath
    clean_subpath = subpath.strip().lstrip("/\\")
    resolved = (SERVER_BASE_DIR / clean_subpath).resolve()
    
    # Check if resolved path is within SERVER_BASE_DIR
    try:
        resolved.relative_to(SERVER_BASE_DIR)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Path is outside the authorized server directory root."
        )
    return resolved


# ---------------------------------------------------------
# Models
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# API Endpoints
# ---------------------------------------------------------

@app.get("/api/system/status")
async def get_system_status():
    """Returns server host health, platform details, and GitHub authentication state."""
    token = get_github_token()
    token_preview = f"{token[:4]}...{token[-4:]}" if token and len(token) > 8 else None

    # Disk usage for server base directory
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
        "disk": disk_info,
        "github": {
            "user": GITHUB_USER,
            "authenticated": bool(token),
            "token_preview": token_preview
        }
    }


@app.get("/api/repos")
async def list_github_repos(force: bool = False):
    """Fetches all repositories for therealbonz from GitHub REST API."""
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
        # Fetch user info
        user_info = None
        try:
            user_url = "https://api.github.com/user" if token else f"https://api.github.com/users/{GITHUB_USER}"
            u_resp = await client.get(user_url, headers=headers)
            if u_resp.status_code == 200:
                user_info = u_resp.json()
        except Exception:
            pass

        # Fetch repositories
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

    # Format repo objects
    formatted = []
    for r in raw_repos:
        # Ensure repo belongs to user if authenticated
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
async def create_github_repo(payload: CreateRepoRequest):
    """Creates a new repository on GitHub under therealbonz account."""
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

    # Invalidate cache so new repo shows up immediately
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
async def list_server_folders(subpath: str = Query("", description="Relative path under server base dir")):
    """Lists folders and files inside the specified server directory path."""
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

    # Sort directories first, then alphabetically
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
async def create_server_folder(payload: CreateFolderRequest):
    """Creates a new folder on the server in the designated directory root."""
    name = payload.folder_name.strip()
    # Ensure no path traversal in folder_name
    if not name or "/" in name or "\\" in name or name in (".", ".."):
        raise HTTPException(
            status_code=400,
            detail="Invalid folder name. Folder name cannot contain path separators or parent directory references."
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


@app.get("/api/cms/projects")
async def get_cms_projects():
    """Returns the list of launchpad items."""
    data = read_cms_data()
    projects = data.get("projects", [])
    projects.sort(key=lambda p: p.get("priority", 99))
    return {"projects": projects}


@app.post("/api/cms/projects")
async def add_cms_project(project: CMSProject):
    """Adds a new launchpad item to the CMS."""
    data = read_cms_data()
    projects = data.get("projects", [])

    # Generate an ID if omitted
    proj_id = project.id or project.title.lower().replace(" ", "-")
    clean_id = "".join(c for c in proj_id if c.isalnum() or c in "-_")

    # Check for existing
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
async def update_cms_project(project_id: str, project: CMSProject):
    """Updates an existing launchpad project item."""
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
async def delete_cms_project(project_id: str):
    """Deletes a launchpad project item."""
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
        # If API route not found, let FastAPI handle 404
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
