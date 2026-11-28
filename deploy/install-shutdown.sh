#!/usr/bin/env bash
# Allow the monitor account to start only the dedicated clean shutdown unit.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run with sudo.' >&2; exit 1; }
APP_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
APP_USER=$(stat -c %U "$APP_DIR")
[[ "$APP_USER" != root && -f "$APP_DIR/app.py" ]] || { echo 'Invalid monitor checkout.' >&2; exit 1; }
cat > /etc/systemd/system/traeger-shutdown.service <<'UNIT'
[Unit]
Description=Safely shut down the Pellet Grill Monitor Pi

[Service]
Type=oneshot
ExecStartPre=/usr/bin/sleep 8
ExecStart=/usr/bin/systemctl poweroff
UNIT
printf '%s\n' "$APP_USER ALL=(root) NOPASSWD: /usr/bin/systemctl start --no-block traeger-shutdown.service" > /etc/sudoers.d/traeger-shutdown
chmod 0440 /etc/sudoers.d/traeger-shutdown
visudo -cf /etc/sudoers.d/traeger-shutdown
systemctl daemon-reload
echo 'Traeger clean shutdown service configured.'
