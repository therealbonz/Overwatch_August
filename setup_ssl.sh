#!/bin/bash
set -e

echo "=========================================================="
echo " Setting up Free Let's Encrypt SSL Certificate"
echo " Domains: therealbonz.com, www.therealbonz.com"
echo "=========================================================="

if [ "$EUID" -ne 0 ]; then
  SUDO="sudo"
else
  SUDO=""
fi

# 1. Install certbot and the Nginx plugin
echo "Installing Certbot and Nginx SSL plugin..."
$SUDO apt-get update -y
$SUDO apt-get install -y certbot python3-certbot-nginx

# 2. Ensure firewall permits HTTP and HTTPS traffic
if command -v ufw >/dev/null 2>&1; then
    echo "Configuring firewall rules for Nginx Full..."
    $SUDO ufw allow 80/tcp || true
    $SUDO ufw allow 443/tcp || true
    $SUDO ufw allow 'Nginx Full' || true
fi

# 3. Run certbot non-interactively to generate certs and auto-configure Nginx
EMAIL="${1:-priorbrendhann@gmail.com}"
echo "Obtaining SSL certificate registered to: $EMAIL ..."

$SUDO certbot --nginx \
  -d therealbonz.com \
  -d www.therealbonz.com \
  --non-interactive \
  --agree-tos \
  -m "$EMAIL" \
  --redirect

# 4. Ensure systemd auto-renewal timer is enabled
$SUDO systemctl enable --now certbot.timer || true

echo ""
echo "=========================================================="
echo " SUCCESS! SSL Certificate installed."
echo " HTTPS URL: https://therealbonz.com"
echo " Auto-renewal: Active (renews automatically every 60 days)"
echo "=========================================================="
