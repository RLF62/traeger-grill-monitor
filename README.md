# Traeger Grill Monitor

A Raspberry Pi dashboard for a sensor-equipped Traeger grill. It shows grill and probe temperatures, pellet level, Wi-Fi status, history, saved cook presets and Pushover alerts. **The monitor reads sensors; it does not control the grill.**

## Try the interactive demo

[Open the simulated Traeger Grill Monitor](https://rlf62.github.io/traeger-grill-monitor/demo/). It runs with sample readings in your browser. Try the cook presets, gauge tick marks, and estimated time-to-target controls without connecting to a grill or sending alerts.

## Estimated time to target

On your Pi, open **Settings** and use **Show estimated time to target** to turn predictions on or off:

![Settings page showing the estimated time to target on/off checkbox](docs/images/settings-time-to-target.png)

A recorded warmup example shows an estimate beneath the Grill gauge. It recalculates with each new sensor sample, so the predicted time can change. A probe with no useful rising trend shows “calculating” until enough readings arrive.

![Recorded grill warmup showing about 14 minutes to target](docs/images/time-to-target.png)

## One-line install

On a fresh Raspberry Pi OS installation with matching ADS1115 hardware, run this as the normal Pi user:

```bash
sudo apt update && sudo apt install -y git && git clone https://github.com/RLF62/traeger-grill-monitor.git && sudo bash traeger-grill-monitor/install.sh --port-80
```

Open the URL printed at the end. Reboot first if the installer enables the ADC overlay. Omit `--port-80` to use port 8081 only. The bundled Apache config allows the `192.168.1.0/24` trusted LAN; review it for another subnet. The installer stops if an older PHP monitor or new service already exists. See [installation and hardware](docs/INSTALL.md) for details. The source repository is public. The dashboard itself is intended for the trusted LAN and has no public Internet login.

## Screens

| Page | Features |
| --- | --- |
| Dashboard | Gauges with target marks and optional time-to-target estimates, Wi-Fi name, pellet level, matching trace colors, hover values and clickable legend. |
| Cook Presets | Save targets, activate a cook and start a fresh chart session without deleting old readings. |
| Notifications | Configure Pushover keys and individual alerts. |
| Settings | Set sensor and browser update intervals; toggle gauge tick marks and time-to-target estimates. |

Read the illustrated [user guide](docs/USER_GUIDE.md). Estimates update with each new sensor sample. A gauge shows “calculating” until a rising trend is available, and the estimate may move as the grill or probe temperature changes.

## How it works

`collector.py` reads the ADS1115 and Pi and writes `data/readings.csv`. `app.py` serves the dashboard on port 8081, optionally behind Apache on port 80. `cook_presets.py` manages recipes and chart sessions. `notification_worker.py` handles alerts. The three systemd services start on boot. Calibration is specific to the original sensors and should be verified against trusted measurements on another grill.

Runtime files in `data/`, credentials and settings in `private/`, and the old rollback copy in `legacy_backup/` are excluded from Git. Back them up separately. The current live Pi is at `http://192.168.1.248/`; the new app does not read the previous PHP installation. Installer syntax and hardware preflight passed on that Pi; a clean second-Pi end-to-end install remains to be tested.

