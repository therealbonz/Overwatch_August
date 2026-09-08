#!/bin/bash
set -e

echo "=========================================================="
echo " Deploying therealbonz.com Homepage & CMS"
echo "=========================================================="

APP_DIR="/var/www/therealbonz"
if [ "$EUID" -ne 0 ]; then
  SUDO="sudo"
else
  SUDO=""
fi

# 1. Install prerequisites if missing
$SUDO apt-get update -y
$SUDO apt-get install -y python3 python3-venv python3-pip git nginx curl

# 2. Setup project directory
$SUDO mkdir -p /var/www
if [ ! -d "$APP_DIR/.git" ]; then
    echo "Cloning or initializing repository in $APP_DIR..."
    if git ls-remote https://github.com/therealbonz/Overwatch.git >/dev/null 2>&1; then
        $SUDO git clone https://github.com/therealbonz/Overwatch.git "$APP_DIR"
    else
        $SUDO mkdir -p "$APP_DIR"
        echo "Copying files to $APP_DIR..."
        $SUDO cp -r . "$APP_DIR/"
    fi
else
    echo "Pulling latest code from GitHub..."
    cd "$APP_DIR"
    $SUDO git fetch origin main || true
    $SUDO git reset --hard origin/main || true
fi

$SUDO chown -R bonz:bonz "$APP_DIR" 2>/dev/null || true

# 3. Create virtual environment & install requirements
cd "$APP_DIR/backend"
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt

# 4. Create Systemd Service for Homepage (:8080)
echo "Configuring systemd service for Homepage..."
$SUDO bash -c "cat << 'EOF' > /etc/systemd/system/therealbonz-homepage.service
[Unit]
Description=therealbonz.com Homepage and CMS Launchpad
After=network.target

[Service]
Type=simple
User=bonz
WorkingDirectory=$APP_DIR/backend
ExecStart=$APP_DIR/backend/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8080
Restart=always
RestartSec=5
Environment=PATH=$APP_DIR/backend/.venv/bin:/usr/bin:/bin
Environment=PYTHONPATH=$APP_DIR:$APP_DIR/backend
Environment=SERVER_BASE_DIR=/var/www
Environment=GITHUB_USER=therealbonz

[Install]
WantedBy=multi-user.target
EOF"

$SUDO systemctl daemon-reload
$SUDO systemctl enable --now therealbonz-homepage
$SUDO systemctl restart therealbonz-homepage

# Verify service is running
sleep 2
if ! systemctl is-active --quiet therealbonz-homepage; then
    echo "⚠️ Warning: therealbonz-homepage failed to start! Checking journal logs:"
    journalctl -u therealbonz-homepage -n 25 --no-pager
    exit 1
else
    echo "✓ therealbonz-homepage service is active and listening."
fi

# 5. Configure Nginx Reverse Proxy
echo "Configuring Nginx reverse proxy for root / ..."
DEFAULT_SITE="/etc/nginx/sites-available/default"

if [ -f "$DEFAULT_SITE" ]; then
    # Ensure backup of default site config
    if [ ! -f "$DEFAULT_SITE.bak" ]; then
        $SUDO cp "$DEFAULT_SITE" "$DEFAULT_SITE.bak"
    fi

    # Update root location / to proxy to port 8080
    if grep -q "proxy_pass http://127.0.0.1:8080" "$DEFAULT_SITE"; then
        echo "Root location block already points to 8080."
    else
        echo "Updating default site configuration..."
        $SUDO bash -c "cat << 'EOF' > /etc/nginx/sites-available/default
server {
    listen 80 default_server;
    listen [::]:80 default_server;

    server_name therealbonz.com www.therealbonz.com localhost;

    # Homepage & CMS Proxy (:8080)
    location / {
        proxy_pass http://127.0.0.1:8080/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    # Existing JsProject Proxy (:8000)
    location /JsProject/ {
        proxy_pass http://127.0.0.1:8000/JsProject/;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location = /JsProject {
        return 301 /JsProject/;
    }
}
EOF"
    fi
fi

$SUDO nginx -t && $SUDO systemctl reload nginx

echo ""
echo "=========================================================="
echo " SUCCESS! Deployment completed."
echo " Open Homepage: http://therealbonz.com"
echo " Open JsProject: http://therealbonz.com/JsProject"
echo "=========================================================="
