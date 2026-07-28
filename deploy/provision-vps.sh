#!/usr/bin/env bash
# One-time VPS provisioning. Run with sudo, once, on a fresh Ubuntu 22.04/24.04
# box, as the existing sudoer user who will also run the bot (e.g. vlad).
# Not run by CI — it needs the actual .p12 certificate and .env in place,
# which are never uploaded via git/Actions.
#
# Usage: sudo ./provision-vps.sh
set -euo pipefail

if [ "$EUID" -ne 0 ]; then
  echo "Run this with sudo." >&2
  exit 1
fi

SERVICE_USER="${SUDO_USER:-}"
if [ -z "$SERVICE_USER" ]; then
  echo "Run this via 'sudo ./provision-vps.sh' as the user who should own the bot (not directly as root)." >&2
  exit 1
fi
APP_DIR="/home/$SERVICE_USER/icp_bot"

echo "==> Installing system packages"
apt-get update
apt-get install -y python3 python3-venv libnss3-tools rsync

echo "==> Enabling lingering for $SERVICE_USER so the user service runs without an active SSH session"
loginctl enable-linger "$SERVICE_USER"

echo "==> Creating app directory ($APP_DIR)"
sudo -u "$SERVICE_USER" mkdir -p "$APP_DIR"

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

Provisioning done, running as $SERVICE_USER (no separate service account created).
Remaining manual steps:
  1. Make sure the SSH key GitHub Actions will use is in
     /home/$SERVICE_USER/.ssh/authorized_keys (put the matching private key
     in the VPS_SSH_KEY secret, and set VPS_USER=$SERVICE_USER).
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
