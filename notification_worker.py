#!/usr/bin/env python3
"""Poll new collector samples; send alerts only after explicit enablement."""
import json
import logging
import os
import tempfile
import time
from pathlib import Path

import app
from alert_rules import DEFAULTS, evaluate

STATE = app.PRIVATE / "alert-state.json"
SETTINGS = app.PRIVATE / "alert-settings.json"


def load_json(path):
    try:
        value = json.loads(path.read_text())
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def save_json(path, data):
    fd, tmp = tempfile.mkstemp(prefix=".alert-", dir=str(app.PRIVATE))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(data, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, str(path))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def tick():
    samples = app.recent_readings(2)
    if not samples:
        return
    current = samples[-1]
    saved = load_json(STATE)
    if saved.get("last_sample") == current["time"]:
        return
    settings = dict(DEFAULTS, **load_json(SETTINGS))
    settings["temperature_unit"] = app.update_settings.load()["temperature_unit"]
    configured = bool(app.credentials().get("PUSHOVER_APP_TOKEN") and app.credentials().get("PUSHOVER_USER_KEY"))
    prior = saved.get("previous")
    state = saved.get("flags", {})
    state, messages = evaluate(prior, current, state, settings)
    if not (settings["enabled"] and configured):
        messages = []
    for message in messages:
        if app.send_message(message):
            logging.info("Sent alert: %s", message)
        else:
            logging.warning("Alert delivery failed: %s", message)
    save_json(STATE, {"last_sample": current["time"], "previous": current, "flags": state})


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            tick()
        except Exception:
            logging.exception("Notification worker tick failed")
        time.sleep(15)
