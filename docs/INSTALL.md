# Installation, hardware and recovery

[README](../README.md) · [User guide](USER_GUIDE.md)

The installer is for a **fresh Raspberry Pi OS Lite 32-bit (Trixie 13 or newer, Python 3.12+)** installation with the original monitor's ADS1115 sensor interface. It installs a Python virtual environment, local data folders, three systemd services, and optionally an Apache proxy and RGB status LED. It does not supply probes, pellet hardware or a Pushover account. `collector.py` calibration matches the original Pi and must be checked on another grill.

![ADS1115 sensor channel map](images/sensor-map.svg)

| IIO ADC channel | Sensor |
| --- | --- |
| `in_voltage0_raw` | Grill thermistor |
| `in_voltage1_raw` | Probe 1 |
| `in_voltage2_raw` | Probe 2 |
| `in_voltage3_raw` | Pellet level |

The installer adds an ADS1115 overlay at I²C address `0x49` if the four channels are absent. Confirm I²C power and voltage, pin wiring, sensor types and calibration against a trusted thermometer before using readings or alerts. The collector uses 5000 raw counts as empty and 24600 as full by default. Calibrate both values in Settings for your hopper and sensor. With a rising signal, a reading far below the calibrated empty point is shown as unavailable instead of reporting an empty hopper. Check sensor power, ground, connector and A3 signal if that happens.

## Fresh install

1. Prepare Raspberry Pi OS with network access and a regular account with `sudo`.
2. Install the public package in one line from the regular Pi account:

   ```bash
   sudo apt update && sudo apt install -y git && git clone https://github.com/RLF62/pellet-grill-monitor.git && sudo bash pellet-grill-monitor/install.sh --port-80
   ```

3. Reboot with `sudo reboot` if the installer requests it. Open the URL printed by the installer. Apache on port 80 admits loopback and `192.168.1.0/24`; change `deploy/apache-traeger.conf` for a different trusted subnet before installation. Omit `--port-80` to serve on port 8081 only.

Run `bash pellet-grill-monitor/install.sh --check --port-80` for model, folder and ADC preflight. The installer refuses to overwrite an existing monitor service, old PHP collector, occupied port 8081 or customized Apache site. Do not run two collectors. A fresh Pi Zero W installation on Trixie with Python 3.13 was completed and verified. The installer checks the OS and Python version before installing packages. The original grill retains its site-specific `dtparam=i2c_arm_baudrate=400000` boot setting. Its former GPIO 27 activity LED overlay is removed when the optional RGB service takes control of that pin.

## Optional RGB Wi-Fi status LED

For a **common-cathode, active-high** RGB LED with appropriate current-limiting resistors, connect red to GPIO 17, green to GPIO 27, and blue to GPIO 22. This option is for those pins only; do not enable it on a Pi using them for other hardware. Add `--rgb-led` to a fresh install command, or on an existing installation run:

```bash
sudo bash ~/pellet-grill-monitor/deploy/install-rgb-led.sh
```

Use your checkout's actual directory if it still has the former `traeger-grill-monitor` name. The helper installs the system Python GPIO library and service, disables an existing activity LED overlay on GPIO 27, and requests a reboot if it changed the boot configuration. The service starts after local filesystems and GPIO initialization, before network readiness: flashing blue shows Wi-Fi connecting, flashing red shows disconnected after 30 seconds, and steady green shows connected. The LED is off during firmware boot before Linux starts the service. Settings has a 0-100% brightness slider (default 25%). This does not control the grill.

## Verify

Run `sudo systemctl status traeger-collector traeger-monitor traeger-notifications` and `sudo journalctl -u traeger-collector -n 50 --no-pager`. Confirm the dashboard's last sample advances, temperatures match a trusted thermometer and pellet percentage is plausible. Configure Pushover in Notifications and send its test alert. Keep port 8081 within the trusted LAN; this package has no public Internet authentication.

## Existing PHP installations

Back up old PHP code, the old crontab, `data.txt`, `Cooking_Times.txt` and `Cooking_Times.tmp`. Stop the old collector and remove its boot task before enabling the new one. Migrate `data.txt` to `data/readings.csv` and copy the two cook files into `data/`, preserving timestamps with `cp -p`. Review calibration and file permissions. The automatic fresh installer intentionally stops when it sees an old PHP monitor; use a planned manual migration. On the original live Pi, its old app is a rollback copy only.

## Services, files and recovery

| Item | Purpose |
| --- | --- |
| `traeger-collector.service` | Sensor sampling to `data/readings.csv` |
| `traeger-monitor.service` | Gunicorn dashboard on port 8081 |
| `traeger-notifications.service` | Pushover alert evaluation |
| `traeger-shutdown.service` | Delayed clean Pi shutdown after confirmation in Settings |
| `private/update-settings.json` | Update intervals |
| `private/pushover.json` | Local secret keys; never commit |
| `data/Cooking_Times.txt`, `data/Cooking_Times.tmp` | Saved cook targets |

Back up `data/` and `private/` separately from Git before updates. Restart the dashboard with `sudo systemctl restart traeger-monitor`; inspect `journalctl -u traeger-monitor -n 50 --no-pager` if it fails. For rollback on the original Pi, stop the three new services first, then restore its prior collector crontab from its local `legacy_backup/` and start the PHP monitor. Never leave both collectors active against the same readings file.

