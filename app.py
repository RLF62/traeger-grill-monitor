#!/usr/bin/env python3
"""Traeger monitor rebuild preview. Never starts or controls the grill."""
import hmac
import ipaddress
import json
import os
import re
import secrets
import subprocess
import tempfile
import urllib.parse
import urllib.request
from pathlib import Path
from collections import deque
from datetime import datetime, timedelta

from flask import Flask, abort, jsonify, redirect, render_template, request, session, url_for
from alert_rules import DEFAULTS
import cook_presets
import update_settings
import update_manager
from eta import estimate

BASE = Path(__file__).resolve().parent
PRIVATE = BASE / "private"
CONFIG = PRIVATE / "pushover.json"
SESSION_KEY = PRIVATE / "session.key"
ALERT_SETTINGS = PRIVATE / "alert-settings.json"
READINGS = BASE / "data" / "readings.csv"
PUSHOVER_URL = "https://api.pushover.net/1/messages.json"
KEY_PATTERN = re.compile(r"^[A-Za-z0-9]{30}$")

PRIVATE.mkdir(mode=0o700, exist_ok=True)
os.chmod(str(PRIVATE), 0o700)
if not SESSION_KEY.exists():
    fd = os.open(str(SESSION_KEY), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as out:
        out.write(secrets.token_hex(32))
os.chmod(str(SESSION_KEY), 0o600)

app = Flask(__name__)
app.secret_key = SESSION_KEY.read_text().strip()
app.config.update(SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict")


@app.context_processor
def page_branding():
    return {"page_name": update_settings.load()["page_name"]}


def credentials():
    try:
        data = json.loads(CONFIG.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_credentials(token, user):
    data = {"PUSHOVER_APP_TOKEN": token, "PUSHOVER_USER_KEY": user}
    fd, tmp = tempfile.mkstemp(prefix=".pushover-", dir=str(PRIVATE))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(data, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, str(CONFIG))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def send_message(message):
    cfg = credentials()
    if not cfg.get("PUSHOVER_APP_TOKEN") or not cfg.get("PUSHOVER_USER_KEY"):
        return False
    body = urllib.parse.urlencode({
        "token": cfg["PUSHOVER_APP_TOKEN"],
        "user": cfg["PUSHOVER_USER_KEY"],
        "title": "Traeger Grill Monitor",
        "message": message,
    }).encode("utf-8")
    req = urllib.request.Request(PUSHOVER_URL, data=body, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            result = json.load(response)
            return response.status == 200 and result.get("status") == 1
    except (OSError, ValueError, KeyError):
        app.logger.exception("Pushover request failed")
        return False


def alert_settings():
    try:
        data = json.loads(ALERT_SETTINGS.read_text())
        return dict(DEFAULTS, **data) if isinstance(data, dict) else dict(DEFAULTS)
    except (OSError, ValueError):
        return dict(DEFAULTS)


def save_alert_settings(data):
    fd, tmp = tempfile.mkstemp(prefix=".alert-settings-", dir=str(PRIVATE))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w") as out:
            json.dump(data, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(tmp, str(ALERT_SETTINGS))
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def latest_reading():
    try:
        with READINGS.open() as source:
            *_, last = source
        fields = last.strip().split(",")
        if len(fields) < 10:
            return None
        return dict(zip(("time", "grill", "pellets", "rssi", "probe1",
                         "probe2", "probe1_target", "probe2_target",
                         "grill_target", "pi_temp"), fields))
    except (OSError, ValueError):
        return None


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return session["csrf"]


def check_csrf():
    supplied = request.form.get("csrf", "")
    if not hmac.compare_digest(supplied, session.get("csrf", "")):
        abort(400)


def safe_credential_form():
    # The monitor is intended for the owner's trusted 192.168.1.0/24 LAN.
    try:
        address = ipaddress.ip_address(request.remote_addr)
    except ValueError:
        return False
    return request.is_secure or address.is_loopback or address in ipaddress.ip_network("192.168.1.0/24")


@app.after_request
def security_headers(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; style-src 'self'; script-src 'self'; "
        "img-src 'self'; form-action 'self'; base-uri 'none'"
    )
    return response


def recent_readings(limit=180):
    """Read a bounded number of collector samples."""
    try:
        with READINGS.open("rb") as source:
            source.seek(0, os.SEEK_END)
            position = source.tell()
            chunks = []
            remaining = max(limit * 2, 360)
            while position > 0 and remaining >= 0:
                size = min(position, 8192)
                position -= size
                source.seek(position)
                chunk = source.read(size)
                chunks.append(chunk)
                remaining -= chunk.count(b"\n")
        lines = b"".join(reversed(chunks)).decode("utf-8", errors="replace").splitlines()[-max(limit * 2, 360):]
    except OSError:
        return []
    rows = []
    for line in lines:
        fields = line.strip().split(",")
        if len(fields) < 10:
            continue
        try:
            stamp = datetime.strptime(fields[0], "%Y-%m-%d %H:%M:%S")
            values = [float(fields[i]) if fields[i] else None for i in (1, 2, 4, 5, 6, 7, 8, 9)]
            if any(v is not None and (v < -50 or v > 1200) for v in values):
                continue
        except ValueError:
            continue
        rows.append(dict(time=stamp.isoformat(), grill=values[0], pellets=values[1],
                         probe1=values[2], probe2=values[3], probe1_target=values[4],
                         probe2_target=values[5], grill_target=values[6], pi_temp=values[7],
                         wifi=fields[3]))
    return rows[-limit:]


def wifi_name():
    try:
        result = subprocess.run(["/usr/sbin/iwgetid", "-r"], stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, universal_newlines=True,
                                timeout=2, check=False)
        return result.stdout.strip()[:64] if result.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


@app.route("/api/readings")
def api_readings():
    active = cook_presets.active_cook()
    cook_session = cook_presets.session_for(active)
    rows = recent_readings(1800 if cook_session else 180)
    latest = rows[-1] if rows else None
    history = ([row for row in rows if row["time"] >= cook_session["started_at"]]
               if cook_session else rows)
    stale = not latest or datetime.now() - datetime.fromisoformat(latest["time"]) > timedelta(minutes=3)
    settings_data = update_settings.load()
    eta = estimate(history, active, stale) if active and settings_data["show_eta"] else {}
    if len(history) > 400:
        step = (len(history) + 398) // 399
        history = history[::step]
        if history[-1] != latest:
            history.append(latest)
    return jsonify({"latest": latest, "history": history, "stale": stale, "wifi_name": wifi_name(),
                    "active_cook": active, "session_start": cook_session["started_at"] if cook_session else None,
                    "refresh_seconds": settings_data["refresh_seconds"],
                    "gauge_ticks": settings_data["gauge_ticks"],
                    "show_eta": settings_data["show_eta"], "eta": eta})


@app.route("/")
def index():
    return render_template("index.html", reading=latest_reading())


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if request.method == "POST":
        check_csrf()
        if not safe_credential_form():
            abort(403)
        try:
            update_settings.save(request.form.get("sample_seconds", ""),
                                 request.form.get("refresh_seconds", ""),
                                 request.form.get("gauge_ticks") == "on",
                                 request.form.get("show_eta") == "on",
                                 request.form.get("page_name", ""),
                                 request.form.get("led_brightness", update_settings.load()["led_brightness"]))
            return redirect(url_for("settings", result="saved"))
        except (ValueError, TypeError):
            return redirect(url_for("settings", result="invalid"))
    return render_template("settings.html", intervals=update_settings.load(),
                           rgb_led_available=Path("/etc/systemd/system/traeger-led.service").exists(),
                           csrf=csrf_token(), result=request.args.get("result", ""),
                           update=update_manager.status(),
                           update_error=session.pop("update_error", ""))


@app.route("/settings/software-update", methods=["POST"])
def software_update():
    check_csrf()
    if not safe_credential_form():
        abort(403)
    action = request.form.get("action")
    if action == "check":
        try:
            update_manager.check(fetch=True)
            return redirect(url_for("settings", result="checked"))
        except update_manager.UpdateError as exc:
            session["update_error"] = str(exc)
            return redirect(url_for("settings", result="update_error"))
    if action == "install":
        try:
            update_manager.start_install()
            return redirect(url_for("settings", result="install_started"))
        except update_manager.UpdateError as exc:
            session["update_error"] = str(exc)
            return redirect(url_for("settings", result="update_error"))
    abort(400)


@app.route("/cooks", methods=["GET", "POST"])
def cooks():
    if request.method == "POST":
        check_csrf()
        if not safe_credential_form():
            abort(403)
        action = request.form.get("action", "")
        try:
            index = int(request.form["index"]) if action not in ("add",) else None
            preset = (cook_presets.validate(request.form.get("name", ""),
                      request.form.get("grill", ""), request.form.get("probe1", ""),
                      request.form.get("probe2", "")) if action in ("add", "edit") else None)
            before = cook_presets.active_cook()
            cook_presets.change(action, request.form.get("version", ""),
                                index=index, preset=preset)
            after = cook_presets.active_cook()
            if action == "activate" and after:
                cook_presets.start_session(after)
            elif action == "edit":
                cook_presets.update_session_preset(before, after)
            return redirect(url_for("cooks", result="saved"))
        except (cook_presets.BadPreset, cook_presets.Conflict, ValueError, KeyError) as exc:
            return redirect(url_for("cooks", result="error", reason=str(exc)))
    rows, version = cook_presets.load()
    return render_template("cooks.html", rows=rows, version=version,
                           active=cook_presets.active_cook(), csrf=csrf_token(),
                           result=request.args.get("result", ""),
                           reason=request.args.get("reason", ""))


@app.route("/notifications", methods=["GET", "POST"])
def notifications():
    cfg = credentials()
    configured = bool(cfg.get("PUSHOVER_APP_TOKEN") and cfg.get("PUSHOVER_USER_KEY"))
    secure_form = safe_credential_form()
    if request.method == "POST":
        check_csrf()
        action = request.form.get("action", "")
        if action == "test":
            if not configured:
                return redirect(url_for("notifications", result="missing"))
            ok = send_message("Traeger Grill Monitor test notification. No grill action was taken.")
            return redirect(url_for("notifications", result="sent" if ok else "failed"))
        if action == "save_alerts":
            if not secure_form:
                abort(403)
            if request.form.get("enabled") and not configured:
                return redirect(url_for("notifications", result="missing"))
            try:
                thresholds = {
                    "pellet_threshold": int(request.form["pellet_threshold"]),
                    "pi_threshold": int(request.form["pi_threshold"]),
                    "deviation_percent": int(request.form["deviation_percent"]),
                }
            except (ValueError, KeyError):
                return redirect(url_for("notifications", result="invalid_alerts"))
            if not (5 <= thresholds["pellet_threshold"] <= 50 and
                    120 <= thresholds["pi_threshold"] <= 220 and
                    5 <= thresholds["deviation_percent"] <= 40):
                return redirect(url_for("notifications", result="invalid_alerts"))
            toggles = ("enabled", "grill_reached", "probe1_reached", "probe2_reached",
                       "grill_deviation", "pellet_low", "pi_hot")
            settings = dict(thresholds, **{key: key in request.form for key in toggles})
            save_alert_settings(settings)
            return redirect(url_for("notifications", result="alerts_saved"))
        if action != "save":
            abort(400)
        if not secure_form:
            abort(403)
        token = request.form.get("pushover_app_token", "").strip() or cfg.get("PUSHOVER_APP_TOKEN", "")
        user = request.form.get("pushover_user_key", "").strip() or cfg.get("PUSHOVER_USER_KEY", "")
        if not KEY_PATTERN.fullmatch(token) or not KEY_PATTERN.fullmatch(user):
            return redirect(url_for("notifications", result="invalid"))
        save_credentials(token, user)
        return redirect(url_for("notifications", result="saved"))
    return render_template("notifications.html", configured=configured,
                           secure_form=secure_form, result=request.args.get("result", ""),
                           csrf=csrf_token(), settings=alert_settings())


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001)
