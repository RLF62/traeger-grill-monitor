"""Validated sampling and dashboard update intervals."""
import json
import os
import tempfile
from pathlib import Path

CONFIG = Path(__file__).resolve().parent / "private" / "update-settings.json"
DEFAULT = {"sample_seconds": 60, "refresh_seconds": 15, "gauge_ticks": False,
           "show_eta": True, "page_name": "Traeger Grill Monitor"}


def load():
    try:
        data = json.loads(CONFIG.read_text())
        result = dict(DEFAULT, **data) if isinstance(data, dict) else dict(DEFAULT)
        return validate(result["sample_seconds"], result["refresh_seconds"], result["gauge_ticks"],
                        result["show_eta"], result["page_name"])
    except (OSError, ValueError, TypeError, KeyError):
        return dict(DEFAULT)


def validate(sample, refresh, gauge_ticks=False, show_eta=True, page_name="Traeger Grill Monitor"):
    if not isinstance(show_eta, bool):
        raise ValueError("Time to target setting must be on or off.")
    if not isinstance(gauge_ticks, bool):
        raise ValueError("Gauge tick setting must be on or off.")
    sample, refresh = int(sample), int(refresh)
    if not 10 <= sample <= 300 or not 2 <= refresh <= 60:
        raise ValueError("Sample interval must be 10–300 seconds and dashboard interval 2–60 seconds.")
    if not isinstance(page_name, str) or not (1 <= len(page_name.strip()) <= 60) or any(ord(c) < 32 for c in page_name):
        raise ValueError("Page name must be 1-60 characters without control characters.")
    return {"sample_seconds": sample, "refresh_seconds": refresh, "gauge_ticks": gauge_ticks,
            "show_eta": show_eta, "page_name": page_name.strip()}


def save(sample, refresh, gauge_ticks=False, show_eta=True, page_name="Traeger Grill Monitor"):
    data = validate(sample, refresh, gauge_ticks, show_eta, page_name)
    fd, temp = tempfile.mkstemp(prefix=".update-", dir=str(CONFIG.parent))
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
