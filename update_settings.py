"""Validated sampling and dashboard update intervals."""
import json
import os
import tempfile
from pathlib import Path

CONFIG = Path(__file__).resolve().parent / "private" / "update-settings.json"
DEFAULT = {"sample_seconds": 60, "refresh_seconds": 15}


def load():
    try:
        data = json.loads(CONFIG.read_text())
        result = dict(DEFAULT, **data) if isinstance(data, dict) else dict(DEFAULT)
        return validate(result["sample_seconds"], result["refresh_seconds"])
    except (OSError, ValueError, TypeError, KeyError):
        return dict(DEFAULT)


def validate(sample, refresh):
    sample, refresh = int(sample), int(refresh)
    if not 10 <= sample <= 300 or not 2 <= refresh <= 60:
        raise ValueError("Sample interval must be 10–300 seconds and dashboard interval 2–60 seconds.")
    return {"sample_seconds": sample, "refresh_seconds": refresh}


def save(sample, refresh):
    data = validate(sample, refresh)
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
