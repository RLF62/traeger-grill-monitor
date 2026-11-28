"""Small, credential-free summary of the last Pushover attempt."""
import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

STATE = Path(__file__).resolve().parent / "private" / "alert-delivery.json"


def load(path=STATE):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def record(message, success, emergency=False, path=STATE):
    previous = load(path)
    data = {"time": datetime.now().isoformat(timespec="seconds"),
            "message": message[:200], "success": bool(success),
            "emergency": bool(emergency),
            "sent_count": previous.get("sent_count", 0) + int(bool(success))}
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix=".alert-delivery-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
