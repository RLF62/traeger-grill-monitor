#!/usr/bin/env python3
"""Independent ADS1115 sampler. Reads sensors; never sends grill commands."""
import logging
import math
import os
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path

import cook_presets
import pellet_calibration
import update_settings

BASE = Path(__file__).resolve().parent
READINGS = Path(os.environ.get("TRAEGER_DATA_FILE", str(BASE / "data" / "readings.csv")))
ACTIVE = Path(os.environ.get("TRAEGER_ACTIVE_FILE", str(BASE / "data" / "Cooking_Times.tmp")))
IIO_ROOT = Path(os.environ.get("TRAEGER_IIO_ROOT", "/sys/bus/iio/devices"))


def find_adc(root=IIO_ROOT):
    for device in sorted(root.glob("iio:device*")):
        if all((device / "in_voltage{}_raw".format(n)).exists() for n in range(4)):
            return device
    raise OSError("ADS1115 IIO channels 0–3 are unavailable")


def read_channels(device, count=5):
    # The kernel driver updates each raw channel when its sysfs file is read.
    values = [[], [], [], []]
    for _ in range(count):
        for channel in range(4):
            raw = int((device / "in_voltage{}_raw".format(channel)).read_text().strip())
            values[channel].append(raw)
    return [sum(series) / len(series) for series in values]


def thermistor_f(raw):
    try:
        mapped = raw * 1023.0 / 26446.0
        resistance = 10000.0 / (1024.0 / mapped - 1.0)
        kelvin = 1.0 / (math.log(resistance / 10000.0) / 3950.0 + 1.0 / (24.0 + 273.15))
        fahrenheit = (kelvin - 273.15) * 1.8 + 32
        return round(fahrenheit, 2) if math.isfinite(fahrenheit) and fahrenheit > -20 else 0.0
    except (ValueError, ZeroDivisionError, OverflowError):
        return 0.0


def pellet_percent(raw):
    return pellet_calibration.percent(raw)


def pi_temp_f():
    try:
        result = subprocess.run(["/usr/bin/vcgencmd", "measure_temp"], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, universal_newlines=True, timeout=3, check=True)
        match = re.search(r"temp=([0-9.]+)", result.stdout)
        return int(float(match.group(1)) * 1.8 + 32) if match else 0
    except (OSError, subprocess.SubprocessError, ValueError):
        return 0


def wifi_signal():
    try:
        result = subprocess.run(["/usr/sbin/iwconfig", "wlan0"], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, universal_newlines=True, timeout=3, check=False)
        match = re.search(r"Signal level=(-?\d+)\s*dBm", result.stdout)
        return match.group(1) + " dBm" if match else ""
    except (OSError, subprocess.SubprocessError):
        return ""


def sample(device=None, active_path=ACTIVE):
    raw = read_channels(device or find_adc())
    cook = cook_presets.active_cook(active_path)
    return dict(time=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                grill=thermistor_f(raw[0]), pellets=pellet_percent(raw[3]), pellet_raw=round(raw[3]),
                wifi=wifi_signal(), probe1=thermistor_f(raw[1]),
                probe2=thermistor_f(raw[2]), probe1_target=cook["probe1"] if cook else None,
                probe2_target=cook["probe2"] if cook else None,
                grill_target=cook["grill"] if cook else None, pi_temp=pi_temp_f())


def csv_line(row):
    fields = ("time", "grill", "pellets", "wifi", "probe1", "probe2",
              "probe1_target", "probe2_target", "grill_target", "pi_temp", "pellet_raw")
    return ",".join("" if row.get(key) is None else str(row[key]) for key in fields) + "\n"


def append(row, path=READINGS):
    path.parent.mkdir(mode=0o750, parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o640)
    with os.fdopen(fd, "w") as out:
        out.write(csv_line(row))
        out.flush()
        os.fsync(out.fileno())


def run():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    while True:
        started = time.monotonic()
        try:
            row = sample()
            append(row)
            logging.info("Sample grill=%.1f probe1=%.1f probe2=%.1f pellets=%s%%",
                         row["grill"], row["probe1"], row["probe2"], row["pellets"])
        except Exception:
            logging.exception("Sensor sample failed; no reading appended")
        interval = int(os.environ.get("TRAEGER_SAMPLE_SECONDS") or update_settings.load()["sample_seconds"])
        time.sleep(max(1, interval - (time.monotonic() - started)))


if __name__ == "__main__":
    run()
