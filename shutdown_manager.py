"""Request the dedicated shutdown service without broad root privileges."""
import subprocess
from pathlib import Path

UNIT = "traeger-shutdown.service"
UNIT_PATH = Path("/etc/systemd/system") / UNIT


class ShutdownError(Exception):
    pass


def available():
    return UNIT_PATH.is_file()


def start():
    if not available():
        raise ShutdownError("Shutdown service is not installed yet.")
    try:
        result = subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "start", "--no-block", UNIT],
                                capture_output=True, text=True, timeout=6, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ShutdownError("Could not request shutdown: {}".format(exc)) from exc
    if result.returncode:
        raise ShutdownError((result.stderr or "Shutdown request failed.").strip()[-200:])
