#!/usr/bin/env bash
# Install on a Raspberry Pi with the Traeger ADS1115 sensor wiring.
set -euo pipefail

usage() {
  echo 'Usage: sudo bash install.sh [--port-80] [--check]'
  echo 'Clone the public repository first as the regular Pi user.'
}
PORT80=0
CHECK=0
for arg in "$@"; do
  case "$arg" in
    --port-80) PORT80=1 ;;
    --check) CHECK=1 ;;
    --help|-h) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
  esac
done
APP_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
APP_USER=${SUDO_USER:-$(id -un)}
APP_HOME=$(getent passwd "$APP_USER" | cut -d: -f6)
APP_GROUP=$(id -gn "$APP_USER")
[[ -n "$APP_HOME" && "$APP_USER" != root ]] || { echo 'Run with sudo from the Pi account.' >&2; exit 1; }
[[ -f "$APP_DIR/requirements.txt" && -f "$APP_DIR/collector.py" ]] || { echo 'Run this from the cloned repository.' >&2; exit 1; }
[[ "$APP_DIR" != *' '* ]] || { echo 'Clone into a path without spaces.' >&2; exit 1; }
[[ -r /proc/device-tree/model ]] && grep -a -qi 'Raspberry Pi' /proc/device-tree/model || { echo 'A Raspberry Pi is required.' >&2; exit 1; }
[[ -r /etc/os-release ]] || { echo 'Cannot determine Raspberry Pi OS version.' >&2; exit 1; }
. /etc/os-release
if [[ ! "${ID:-}" =~ ^(raspbian|debian)$ || ! "${VERSION_ID:-}" =~ ^[0-9]+$ ]] || (( VERSION_ID < 13 )); then
  echo 'A fresh install requires Raspberry Pi OS Trixie (13) or newer; use the 32-bit Lite image on a Pi Zero W.' >&2
  exit 1
fi
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 12))'; then
  echo 'Python 3.12 or newer is required. Install a current Raspberry Pi OS image.' >&2
  exit 1
fi
ADC_READY=0
for dev in /sys/bus/iio/devices/iio:device*; do
  if [[ -e "$dev/in_voltage0_raw" && -e "$dev/in_voltage1_raw" && -e "$dev/in_voltage2_raw" && -e "$dev/in_voltage3_raw" ]]; then ADC_READY=1; break; fi
done
if [[ $CHECK == 1 ]]; then
  echo "Operating system: ${PRETTY_NAME}; $(python3 --version)"
  echo "User: $APP_USER; install folder: $APP_DIR; ADS1115 channels: $([[ $ADC_READY == 1 ]] && echo ready || echo 'need boot overlay and reboot')"
  echo "Dashboard: port 8081$([[ $PORT80 == 1 ]] && echo ' with Apache on port 80')"
  exit 0
fi
[[ $EUID == 0 ]] || { echo 'Run as sudo bash install.sh.' >&2; exit 1; }
[[ ! -e /etc/systemd/system/traeger-monitor.service ]] || { echo 'Monitor service already exists. Use the update procedure instead.' >&2; exit 1; }
[[ ! -e /var/www/html/Traeger/put_data.php ]] || { echo 'Old PHP monitor found. Migrate it before installing to avoid two collectors.' >&2; exit 1; }
if command -v ss >/dev/null && ss -ltn | grep -qE ':8081[[:space:]]'; then
  echo 'Port 8081 is already in use.' >&2; exit 1
fi
if [[ $PORT80 == 1 && -d /etc/apache2/sites-enabled ]]; then
  sites=$(find /etc/apache2/sites-enabled -maxdepth 1 -type l | wc -l)
  [[ $sites -le 1 && ( ! -e /etc/apache2/sites-enabled/000-default.conf || -L /etc/apache2/sites-enabled/000-default.conf ) ]] || { echo 'Custom Apache sites exist; use port 8081 and configure a proxy manually.' >&2; exit 1; }
  if [[ -e /etc/apache2/sites-enabled/000-default.conf ]]; then
    grep -q 'DocumentRoot /var/www/html' /etc/apache2/sites-enabled/000-default.conf || { echo 'Existing Apache default site is customized; leaving it intact.' >&2; exit 1; }
  fi
fi
apt-get update
packages=(python3-venv python3-pip wireless-tools)
[[ $PORT80 == 1 ]] && packages+=(apache2)
DEBIAN_FRONTEND=noninteractive apt-get install -y "${packages[@]}"
runuser -u "$APP_USER" -- python3 -m venv "$APP_DIR/.venv"
runuser -u "$APP_USER" -- "$APP_DIR/.venv/bin/python" -m pip install -r "$APP_DIR/requirements.txt"
install -d -m 700 -o "$APP_USER" -g "$APP_GROUP" "$APP_DIR/private"
install -d -m 750 -o "$APP_USER" -g "$APP_GROUP" "$APP_DIR/data"
for filename in Cooking_Times.txt Cooking_Times.tmp; do
  if [[ ! -e "$APP_DIR/data/$filename" ]]; then
    printf '||||N\n' > "$APP_DIR/data/$filename"
    chown "$APP_USER:$APP_GROUP" "$APP_DIR/data/$filename"
    chmod 640 "$APP_DIR/data/$filename"
  fi
done
REBOOT=0
if [[ $ADC_READY == 0 ]]; then
  boot=/boot/firmware/config.txt
  [[ -e "$boot" ]] || boot=/boot/config.txt
  [[ -e "$boot" ]] || { echo 'No Raspberry Pi boot config found for ADS1115.' >&2; exit 1; }
  if grep -Eq '^dtoverlay=ads1115' "$boot"; then
    echo 'ADS1115 overlay exists but channels are unavailable. Check address and wiring.' >&2; exit 1
  fi
  cp -p "$boot" "$boot.traeger-before-install"
  cat >> "$boot" <<'OVERLAY'

# Traeger Grill Monitor ADS1115 on I2C address 0x49
dtparam=i2c_arm=on
dtoverlay=ads1115,addr=0x49
dtparam=cha_enable
dtparam=chb_enable
dtparam=chc_enable
dtparam=chd_enable
OVERLAY
  REBOOT=1
fi
export APP_DIR APP_USER APP_GROUP
python3 - <<'PY'
import os
from pathlib import Path
base=Path(os.environ['APP_DIR'])
for name in ('traeger-collector','traeger-monitor','traeger-notifications'):
    source=(base/'deploy'/(name+'.service')).read_text()
    source=source.replace('/home/pi/traeger-grill-monitor',str(base))
    source=source.replace('User=pi','User='+os.environ['APP_USER'])
    source=source.replace('Group=pi','Group='+os.environ['APP_GROUP'])
    source=source.replace('/home/pi/.local/bin/gunicorn',str(base/'.venv/bin/gunicorn'))
    Path('/etc/systemd/system/'+name+'.service').write_text(source)
PY
systemctl daemon-reload
  bash "$APP_DIR/deploy/install-updater.sh"
systemctl enable --now traeger-monitor.service traeger-notifications.service
if [[ $REBOOT == 0 ]]; then
  systemctl enable --now traeger-collector.service
else
  systemctl enable traeger-collector.service
fi
if [[ $PORT80 == 1 ]]; then
  a2enmod proxy proxy_http >/dev/null
  if [[ -e /etc/apache2/sites-available/000-default.conf ]]; then
    cp -p /etc/apache2/sites-available/000-default.conf /etc/apache2/sites-available/000-default.conf.traeger-before-install
  fi
  cp "$APP_DIR/deploy/apache-traeger.conf" /etc/apache2/sites-available/000-default.conf
  apache2ctl configtest
  systemctl enable --now apache2
  systemctl reload apache2
fi
ipaddr=$(hostname -I | awk '{print $1}')
echo "Monitor installed: http://${ipaddr}:8081/"
[[ $PORT80 == 0 ]] || echo "Main address: http://${ipaddr}/"
if [[ $REBOOT == 1 ]]; then
  echo 'Reboot the Pi to activate the ADS1115 overlay; the collector starts after reboot.'
else
  echo 'Collector, dashboard, and notification services are enabled.'
fi
