# therealbonz.com - Central Project Launchpad & CMS

A high-performance, dark-themed developer portal and Content Management System for **therealbonz.com**.

## Features

- **Project Launchpad**: Quick access cards for core applications and services:
  - **3D Cube Project**: Interactive 3D graphics studio and reactive wallpaper engine.
  - **JsProject**: AI Sales Automation & Cold Calling Platform (`http://therealbonz.com/JsProject/`).
  - **Bonz2D**: Unity 2D action game repository and builds.
  - **Media Gallery Suite**: Cross-platform gallery applications.
- **Interactive 3D Physics Viewport**:
  - Real-time 3D cube rendered with CSS 3D transforms and inertia decay physics.
  - Drag with mouse or swipe touch to rotate; click any face to launch projects.
- **GitHub Repositories Hub**:
  - Real-time sync with GitHub account `therealbonz`.
  - Filter by language and live text search.
  - One-click clone URL copier and direct links.
  - **Create New GitHub Repo**: Direct creation via modal using GitHub API.
- **Server Folder & Storage Manager (CMS)**:
  - Browse directory structures on the server.
  - Create new project directories and web roots directly from the browser.
- **Customizable Launchpad Cards (CMS)**:
  - Add, edit, or remove custom project bookmarks and external links.

---

## Local Development (Windows)

To run the application locally:

```powershell
# Using PowerShell
.\run_local.ps1

# Or double-click run_local.bat
```

Once running, visit [http://127.0.0.1:8080](http://127.0.0.1:8080) in your browser.

---

## Production Deployment (Ubuntu / Nginx)

Run the automated deployment script on your server:

```bash
chmod +x deploy_server.sh
./deploy_server.sh
```

The script configures:
1. Python virtual environment at `/var/www/therealbonz/backend/.venv`.
2. Systemd service `therealbonz-homepage.service` running on port `8080`.
3. Nginx reverse proxy so `http://therealbonz.com` serves the homepage while preserving `http://therealbonz.com/JsProject/` on port `8000`.
