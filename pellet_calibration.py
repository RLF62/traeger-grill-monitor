"""Per-installation calibration for the ADS1115 pellet sensor."""
import json
import os
import statistics
import tempfile
from pathlib import Path

CONFIG = Path(__file__).resolve().parent / "private" / "pellet-calibration.json"
DEFAULT = {"empty_raw": 5000, "full_raw": 24600}


def validate(empty_raw, full_raw):
    empty_raw, full_raw = int(empty_raw), int(full_raw)
    if not 0 <= empty_raw <= 32767 or not 0 <= full_raw <= 32767:
        raise ValueError("Calibration readings must be between 0 and 32767.")
    if abs(full_raw - empty_raw) < 500:
        raise ValueError("Empty and full readings must differ by at least 500 counts.")
    return {"empty_raw": empty_raw, "full_raw": full_raw}


def load():
    try:
        data = json.loads(CONFIG.read_text())
        if not isinstance(data, dict):
            raise ValueError("Invalid calibration.")
        return validate(data["empty_raw"], data["full_raw"])
    except (OSError, ValueError, TypeError, KeyError):
        return dict(DEFAULT)


def save(empty_raw, full_raw):
    data = validate(empty_raw, full_raw)
    CONFIG.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".pellet-", dir=str(CONFIG.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(data, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, str(CONFIG))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    return data


def percent(raw, settings=None):
    settings = settings or load()
    empty, full = settings["empty_raw"], settings["full_raw"]
    # With the usual rising signal, near-ground readings far below the
    # calibrated empty point indicate a missing sensor signal.
    if full > empty and raw < min(1000, empty * 0.2):
        return None
    return max(0, min(100, int((raw - empty) / (full - empty) * 100)))


def current_raw(root=Path("/sys/bus/iio/devices")):
    try:
        for device in sorted(root.glob("iio:device*")):
            channel = device / "in_voltage3_raw"
            if channel.exists():
                return int(statistics.median(int(channel.read_text().strip()) for _ in range(5)))
    except (OSError, ValueError):
        pass
    return None
