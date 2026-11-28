"""Cook presets and active session for this monitor."""
import fcntl
import hashlib
import json
from datetime import datetime
import os
import shutil
import stat
import tempfile
import uuid
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"
LIST = DATA / "Cooking_Times.txt"
ACTIVE = DATA / "Cooking_Times.tmp"


class Conflict(Exception):
    pass


class BadPreset(Exception):
    pass


def parse_line(line):
    parts = line.rstrip("\r\n").split("|", 4)
    if len(parts) != 5 or not any(parts[:4]):
        return None
    try:
        return dict(grill=int(parts[0]), probe1=int(parts[1]) if parts[1] else None,
                    probe2=int(parts[2]) if parts[2] else None,
                    name=parts[3].strip(), active=parts[4].strip() == "Y")
    except ValueError:
        return None


def serialize(row):
    return "{}|{}|{}|{}|{}".format(row["grill"], row["probe1"] or "",
                                  row["probe2"] or "", row["name"],
                                  "Y" if row["active"] else "N")


def load(path=LIST):
    raw = path.read_bytes()
    rows = [row for row in (parse_line(line) for line in raw.decode("utf-8").splitlines()) if row]
    for i, row in enumerate(rows):
        row["index"] = i
    return rows, hashlib.sha256(raw).hexdigest()


def active_cook(path=ACTIVE):
    try:
        return parse_line(path.read_text(encoding="utf-8")) or None
    except OSError:
        return None


def validate(name, grill, probe1, probe2):
    name = name.strip()
    if not name or len(name) > 60 or any(c in name for c in "|\r\n"):
        raise BadPreset("Use a cook name of 1 to 60 characters without line breaks or |.")
    try:
        grill = int(grill)
        probe1 = int(probe1) if str(probe1).strip() else None
        probe2 = int(probe2) if str(probe2).strip() else None
    except ValueError:
        raise BadPreset("Temperatures must be whole numbers.")
    if not 50 <= grill <= 500 or any(p is not None and not 50 <= p <= 500 for p in (probe1, probe2)):
        raise BadPreset("Temperatures must be 50 to 500°F; probes may be blank.")
    return dict(name=name, grill=grill, probe1=probe1, probe2=probe2, active=False)


def atomic_write(path, data):
    fd, temp = tempfile.mkstemp(prefix=".cook-", dir=str(path.parent))
    try:
        os.fchmod(fd, stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o640)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            out.write(data)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def change(action, expected_version, index=None, preset=None,
           list_path=LIST, active_path=ACTIVE, lock_path=None, backup_dir=None):
    lock_path = lock_path or Path(__file__).resolve().parent / "private" / "cooks.lock"
    backup_dir = backup_dir or Path(__file__).resolve().parent / "legacy_backup"
    with lock_path.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        rows, version = load(list_path)
        if version != expected_version:
            raise Conflict("The cook list changed. Reload it before saving.")
        if action == "add":
            if preset is None:
                raise BadPreset("Enter a cook name and temperature.")
            rows.append(dict(preset, active=False))
        else:
            if index is None or not 0 <= index < len(rows):
                raise BadPreset("Select a cook from the current list.")
            if action == "edit":
                if preset is None:
                    raise BadPreset("Enter a cook name and temperature.")
                rows[index] = dict(preset, active=rows[index]["active"])
            elif action == "delete":
                removed = rows.pop(index)
                archive = backup_dir / "removed-cooks.jsonl"
                backup_dir.mkdir(mode=0o700, exist_ok=True)
                with archive.open("a", encoding="utf-8") as history:
                    history.write(json.dumps({"removed_at": datetime.now().isoformat(), "cook": removed}) + "\n")
            elif action == "activate":
                for n, row in enumerate(rows):
                    row["active"] = n == index
            elif action == "deactivate":
                for row in rows:
                    row["active"] = False
            else:
                raise BadPreset("Unknown cook action.")
        # Preserve a copy of both original files before the first edit.
        backup_dir.mkdir(mode=0o700, exist_ok=True)
        for source in (list_path, active_path):
            destination = backup_dir / source.name
            if source.exists() and not destination.exists():
                shutil.copy2(str(source), str(destination))
        old_active = active_cook(active_path)
        atomic_write(list_path, "\n".join(serialize(row) for row in rows) + "\n||||N\n")
        active = next((row for row in rows if row["active"]), None)
        if (serialize(active) if active else None) != (serialize(old_active) if old_active else None):
            atomic_write(active_path, (serialize(active) if active else "||||N") + "\n")
        return rows

SESSION = Path(__file__).resolve().parent / "private" / "cook-session.json"
HISTORY = Path(__file__).resolve().parent / "private" / "cook-history.json"
HISTORY_LOCK = Path(__file__).resolve().parent / "private" / "cook-history.lock"


def session_for(active, path=SESSION, legacy_path=ACTIVE):
    if not active:
        return None
    try:
        import json
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("preset") == serialize(active) and isinstance(data.get("started_at"), str):
            return data
    except (OSError, ValueError, AttributeError):
        pass
    # A migrated active cook file can mark
    # the start without clearing the temperature log.
    if legacy_path is not None:
        try:
            if serialize(active) == serialize(active_cook(legacy_path)):
                started = datetime.fromtimestamp(legacy_path.stat().st_mtime)
                return {"preset": serialize(active), "started_at": started.strftime("%Y-%m-%dT%H:%M:%S")}
        except OSError:
            pass
    return None


def start_session(active, path=SESSION):
    """Begin a new chart without touching historical collector readings."""
    with HISTORY_LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = _load_history()
        _close_previous(records, path)
        data = {"id": uuid.uuid4().hex, "preset": serialize(active),
                "started_at": datetime.now().isoformat(timespec="microseconds")}
        records.append(_record(data))
        _write_history(records)
        _write_session(data, path)


def end_session(path=SESSION):
    with HISTORY_LOCK.open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        records = _load_history()
        _close_previous(records, path)
        _write_history(records)


def _load_history(path=None):
    path = path or HISTORY
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _record(data):
    preset = parse_line(data.get("preset", "")) or {}
    legacy_id = hashlib.sha256((data["started_at"] + data.get("preset", "")).encode("utf-8")).hexdigest()[:32]
    return {"id": data.get("id") or legacy_id,
            "name": preset.get("name", "Cook"), "grill": preset.get("grill"),
            "probe1": preset.get("probe1"), "probe2": preset.get("probe2"),
            "started_at": data["started_at"], "ended_at": data.get("ended_at")}


def _close_previous(records, path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not data.get("started_at"):
            return
        match = next((row for row in records if row["id"] == data.get("id")), None)
        if match is None:
            match = _record(data)
            records.append(match)
        if not match.get("ended_at"):
            match["ended_at"] = datetime.now().isoformat(timespec="seconds")
        data["ended_at"] = match["ended_at"]
        _write_session(data, path)
    except (OSError, ValueError, TypeError, KeyError):
        pass


def _write_history(records, path=None):
    _atomic_json(path or HISTORY, records)


def list_sessions(active=None):
    records = _load_history()
    current = session_for(active) if active else None
    if current and not current.get("ended_at") and not any(row["id"] == current.get("id") for row in records):
        records.append(_record(current))
    return sorted(reversed(records), key=lambda row: row["started_at"], reverse=True)


def get_session(identifier, active=None):
    return next((row for row in list_sessions(active) if row["id"] == identifier), None)


def update_session_preset(old_active, new_active, path=SESSION):
    data = session_for(old_active, path, legacy_path=None)
    if data and new_active:
        data["preset"] = serialize(new_active)
        _write_session(data, path)
        with HISTORY_LOCK.open("a+") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            records = _load_history()
            for row in records:
                if row["id"] == data.get("id"):
                    row.update({"name": new_active["name"], "grill": new_active["grill"],
                                "probe1": new_active["probe1"], "probe2": new_active["probe2"]})
                    _write_history(records)
                    break


def _write_session(data, path):
    _atomic_json(path, data)


def _atomic_json(path, data):
    fd, temp = tempfile.mkstemp(prefix=".cook-session-", dir=str(path.parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            json.dump(data, out)
            out.flush()
            os.fsync(out.fileno())
        os.replace(temp, str(path))
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
