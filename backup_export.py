"""Downloadable runtime backup; credentials and session secrets are excluded."""
import json
import os
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
FILES = (
    "data/readings.csv", "data/Cooking_Times.txt", "data/Cooking_Times.tmp",
    "private/cook-session.json", "private/cook-history.json",
    "private/pellet-calibration.json", "private/update-settings.json",
    "private/alert-settings.json",
)


def create(base=BASE):
    archive = tempfile.TemporaryFile()
    try:
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
            output.writestr("backup-info.json", json.dumps({
                "created_at": datetime.now().isoformat(timespec="seconds"),
                "format": 1, "excluded": ["Pushover keys", "session secret"],
            }))
            for name in FILES:
                source = base / name
                if source.is_file() and not source.is_symlink():
                    output.write(source, arcname=name)
        archive.seek(0, os.SEEK_END)
        size = archive.tell()
        archive.seek(0)
        return archive, size
    except Exception:
        archive.close()
        raise
