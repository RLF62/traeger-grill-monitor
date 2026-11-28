#!/usr/bin/env bash
# Optional RGB LED, common cathode: GPIO17 red, GPIO27 green, GPIO22 blue.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run this helper with sudo.' >&2; exit 1; }
APP_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)
[[ -f "$APP_DIR/led_status.py" ]] || { echo 'Run from the grill monitor checkout.' >&2; exit 1; }
boot=/boot/firmware/config.txt
[[ -e "$boot" ]] || boot=/boot/config.txt
[[ -e "$boot" ]] || { echo 'Pi boot configuration not found.' >&2; exit 1; }
DELAY_START=0
if grep -Eq '^[[:space:]]*dtoverlay=(pi3-)?act-led,gpio=27([,[:space:]]|$)' "$boot"; then
  cp -p "$boot" "$boot.traeger-before-rgb-led"
  sed -i -E '/^[[:space:]]*dtoverlay=(pi3-)?act-led,gpio=27([,[:space:]]|$)/s/^/# RGB status service owns GPIO 27; /' "$boot"
  DELAY_START=1
fi
DEBIAN_FRONTEND=noninteractive apt-get install -y python3-lgpio wireless-tools
sed "s|/home/pi/traeger-grill-monitor|$APP_DIR|g" "$APP_DIR/deploy/traeger-led.service" > /etc/systemd/system/traeger-led.service
systemctl daemon-reload
systemctl enable traeger-led.service
if [[ $DELAY_START == 1 ]]; then
  echo 'Restart the Pi to release GPIO 27; the RGB LED service starts on boot.'
else
  systemctl restart traeger-led.service
  echo 'RGB LED service started.'
fi
