#!/usr/bin/env bash
# One-time VPS provisioning. Run manually once (as root or via sudo) on a
# fresh Ubuntu 22.04/24.04 box. Not run by CI — it needs the actual .p12
# certificate and .env in place, which are never uploaded via git/Actions.
#
# Usage: sudo ./provision-vps.sh [service_user]
set -euo pipefail

SERVICE_USER="${1:-icpbot}"
APP_DIR="/home/$SERVICE_USER/icp_bot"

if [ "$EUID" -ne 0 ]; then
  echo "Run this as root (sudo)." >&2
  exit 1
fi

echo "==> Installing system packages"
apt-get update
apt-get install -y python3 python3-venv libnss3-tools rsync

echo "==> Creating service user ($SERVICE_USER) with a normal login shell"
id -u "$SERVICE_USER" &>/dev/null || useradd --create-home --shell /bin/bash "$SERVICE_USER"

echo "==> Enabling lingering so the user service runs without an active SSH session"
loginctl enable-linger "$SERVICE_USER"

echo "==> Creating app directory ($APP_DIR)"
mkdir -p "$APP_DIR"
chown "$SERVICE_USER:$SERVICE_USER" "$APP_DIR"

echo "==> Setting up NSS database for $SERVICE_USER"
sudo -u "$SERVICE_USER" bash -c '
  mkdir -p "$HOME/.pki/nssdb"
  [ -f "$HOME/.pki/nssdb/cert9.db" ] || certutil -d "sql:$HOME/.pki/nssdb" -N --empty-password
'
echo "    Now import the certificate as $SERVICE_USER:"
echo "    sudo -u $SERVICE_USER pk12util -d sql:/home/$SERVICE_USER/.pki/nssdb -i /path/to/cert.p12"

echo "==> Installing AutoSelectCertificateForUrls Chromium policy"
mkdir -p /etc/chromium/policies/managed
cat > /etc/chromium/policies/managed/icp.json << 'EOF'
{
  "AutoSelectCertificateForUrls": [
    "{\"pattern\":\"https://pasarela-ident.clave.gob.es\",\"filter\":{}}"
  ]
}
EOF

echo "==> Installing systemd user unit"
sudo -u "$SERVICE_USER" mkdir -p "/home/$SERVICE_USER/.config/systemd/user"
cp "$(dirname "$0")/icp-bot.service" "/home/$SERVICE_USER/.config/systemd/user/icp-bot.service"
chown "$SERVICE_USER:$SERVICE_USER" "/home/$SERVICE_USER/.config/systemd/user/icp-bot.service"
sudo -u "$SERVICE_USER" env XDG_RUNTIME_DIR="/run/user/$(id -u "$SERVICE_USER")" systemctl --user daemon-reload
sudo -u "$SERVICE_USER" env XDG_RUNTIME_DIR="/run/user/$(id -u "$SERVICE_USER")" systemctl --user enable icp-bot.service

cat << EOF

Provisioning done. Remaining manual steps:
  1. Add your deploy SSH public key to /home/$SERVICE_USER/.ssh/authorized_keys
     (this is the identity GitHub Actions will use — put the matching private
     key in the VPS_SSH_KEY secret, and set VPS_USER=$SERVICE_USER).
  2. Copy your .p12 certificate to the server and import it:
       sudo -u $SERVICE_USER pk12util -d sql:/home/$SERVICE_USER/.pki/nssdb -i /path/to/cert.p12
  3. Deploy the code (push to main, or trigger .github/workflows/deploy.yml manually).
  4. Create $APP_DIR/.env from .env.example and fill in real values
     (chown $SERVICE_USER:$SERVICE_USER $APP_DIR/.env; chmod 600 $APP_DIR/.env).
  5. Create the venv and install deps as $SERVICE_USER:
       sudo -u $SERVICE_USER bash -c 'cd $APP_DIR && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/playwright install --with-deps chromium'
  6. Start the service:
       sudo -u $SERVICE_USER env XDG_RUNTIME_DIR=/run/user/\$(id -u $SERVICE_USER) systemctl --user start icp-bot.service
       sudo -u $SERVICE_USER env XDG_RUNTIME_DIR=/run/user/\$(id -u $SERVICE_USER) systemctl --user status icp-bot.service
       journalctl --user-unit icp-bot.service -f
EOF
