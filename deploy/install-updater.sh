#!/usr/bin/env bash
# Install the narrowly scoped service permission for web-initiated updates.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
APP_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
APP_USER=$(stat -c %U "$APP_DIR")
[[ "$APP_USER" != root && -f "$APP_DIR/update_manager.py" ]] || { echo 'Invalid Traeger checkout.' >&2; exit 1; }
cat > /etc/systemd/system/traeger-update.service <<EOF
[Unit]
Description=Install Traeger Grill Monitor update from GitHub
After=network-online.target

[Service]
Type=oneshot
WorkingDirectory=$APP_DIR
ExecStart=/usr/bin/python3 $APP_DIR/update_manager.py install
TimeoutStartSec=300
EOF
printf '%s\n' "$APP_USER ALL=(root) NOPASSWD: /usr/bin/systemctl start --no-block traeger-update.service" > /etc/sudoers.d/traeger-update
chmod 0440 /etc/sudoers.d/traeger-update
visudo -cf /etc/sudoers.d/traeger-update
systemctl daemon-reload
echo 'Traeger web updater configured.'
