#!/usr/bin/env python3
"""Check and install fast-forward updates from the fixed Traeger GitHub repository."""
import json
import os
import pwd
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
STATE = BASE / "private" / "software-update.json"
REMOTE = "https://github.com/RLF62/traeger-grill-monitor.git"
UNIT = "traeger-update.service"
SERVICES = ("traeger-collector.service", "traeger-notifications.service",
            "traeger-monitor.service")


class UpdateError(Exception):
    pass


def command(args, timeout=30, user=None, check=True):
    if user:
        args = ["runuser", "-u", user, "--"] + args
    try:
        result = subprocess.run(args, cwd=str(BASE), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, universal_newlines=True,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError("Update command unavailable or timed out: " + str(exc))
    if check and result.returncode:
        raise UpdateError((result.stderr or result.stdout).strip()[-350:] or
                          "Update command failed.")
    return result.stdout.strip()


def git(*args, user=None, timeout=30):
    return command(["git", "-C", str(BASE)] + list(args), user=user, timeout=timeout)


def check(fetch=False, user=None):
    if git("remote", "get-url", "origin", user=user) != REMOTE:
        raise UpdateError("GitHub origin does not match the official Traeger repository.")
    if git("branch", "--show-current", user=user) != "main":
        raise UpdateError("Switch the checkout to the main branch before updating.")
    if fetch:
        git("fetch", "--no-tags", "origin", "main", user=user, timeout=45)
    installed = git("rev-parse", "HEAD", user=user)
    available = git("rev-parse", "refs/remotes/origin/main", user=user)
    dirty = bool(git("status", "--porcelain", "--untracked-files=no", user=user))
    ancestor = subprocess.run((["runuser", "-u", user, "--"] if user else []) +
                              ["git", "-C", str(BASE), "merge-base", "--is-ancestor",
                               installed, available], timeout=10, check=False).returncode == 0
    return {"installed": installed[:12], "available": available[:12],
            "update_available": installed != available and ancestor,
            "blocked": dirty or not ancestor,
            "reason": ("Local tracked files have changed." if dirty else
                       "GitHub history has diverged from this installation." if not ancestor else "")}


def write_state(phase, message):
    STATE.parent.mkdir(mode=0o700, exist_ok=True)
    temporary = STATE.with_suffix(".tmp")
    temporary.write_text(json.dumps({"phase": phase, "message": message}))
    os.chmod(str(temporary), 0o644)
    os.replace(str(temporary), str(STATE))


def status():
    try:
        result = check()
    except UpdateError as exc:
        result = {"installed": "unknown", "available": "unknown",
                  "update_available": False, "blocked": True, "reason": str(exc)}
    try:
        state = json.loads(STATE.read_text())
        if isinstance(state, dict):
            result.update({key: state.get(key, "") for key in ("phase", "message")})
    except (OSError, ValueError):
        pass
    return result


def start_install():
    result = check()
    if result["blocked"]:
        raise UpdateError(result["reason"])
    if not result["update_available"]:
        raise UpdateError("Check GitHub for updates first; the installed copy is current.")
    active = command(["systemctl", "is-active", UNIT], check=False)
    if active == "active" or active == "activating":
        raise UpdateError("An update is already running.")
    command(["sudo", "-n", "/usr/bin/systemctl", "start", "--no-block", UNIT],
            timeout=10)


def install():
    if os.geteuid() != 0:
        raise UpdateError("The updater must run as the system service.")
    owner = pwd.getpwuid(BASE.stat().st_uid).pw_name
    write_state("running", "Checking GitHub and installing the update.")
    previous = None
    try:
        result = check(fetch=True, user=owner)
        if result["blocked"]:
            raise UpdateError(result["reason"])
        if not result["update_available"]:
            write_state("current", "Already on the latest GitHub version.")
            return
        previous = git("rev-parse", "HEAD", user=owner)
        git("merge", "--ff-only", "origin/main", user=owner)
        python = BASE / ".venv" / "bin" / "python"
        if not python.exists():
            raise UpdateError("Python environment missing; use the installation guide.")
        command([str(python), "-m", "pip", "install", "-r", str(BASE / "requirements.txt")],
                user=owner, timeout=180)
        for service in SERVICES:
            command(["systemctl", "restart", service], timeout=25)
        for service in SERVICES:
            if command(["systemctl", "is-active", service]) != "active":
                raise UpdateError(service + " did not start.")
        write_state("success", "Installed GitHub commit " + git("rev-parse", "--short", "HEAD",
                                                                   user=owner) + ".")
    except (UpdateError, OSError) as exc:
        if previous:
            try:
                git("reset", "--hard", previous, user=owner)
                for service in SERVICES:
                    command(["systemctl", "restart", service], timeout=25)
                write_state("failed", str(exc) + " Previous code restored.")
            except UpdateError as rollback:
                write_state("failed", str(exc) + " Rollback failed: " + str(rollback))
        else:
            write_state("failed", str(exc))
        raise


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["install"]:
            install()
        else:
            raise UpdateError("Usage: update_manager.py install")
    except UpdateError as exc:
        print(exc, file=sys.stderr)
        sys.exit(1)
