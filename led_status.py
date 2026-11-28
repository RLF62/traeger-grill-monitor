#!/usr/bin/env python3
"""Drive the optional common-cathode RGB LED on GPIO 17/27/22."""
import json
import signal
import subprocess
import time
from pathlib import Path

import lgpio

CONFIG = Path(__file__).resolve().parent / "private" / "update-settings.json"
PINS = {"red": 17, "green": 27, "blue": 22}
RUNNING = True


def stop(_signal, _frame):
    global RUNNING
    RUNNING = False


def brightness():
    try:
        value = json.loads(CONFIG.read_text()).get("led_brightness", 25)
        return max(0, min(100, int(value)))
    except (OSError, ValueError, TypeError, AttributeError):
        return 25


def connected():
    try:
        result = subprocess.run(("/usr/sbin/iwgetid", "-r"), capture_output=True,
                                text=True, timeout=3, check=False)
        return result.returncode == 0 and bool(result.stdout.strip())
    except (OSError, subprocess.TimeoutExpired):
        return False


def set_channel(chip, pin, duty):
    # A zero frequency stops the previous waveform before writing a steady level.
    lgpio.tx_pwm(chip, pin, 200, 0)
    if duty == 0 or duty == 100:
        lgpio.gpio_write(chip, pin, int(duty == 100))
    else:
        lgpio.tx_pwm(chip, pin, 200, duty)


def main():
    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    chip = lgpio.gpiochip_open(0)
    try:
        for pin in PINS.values():
            lgpio.gpio_claim_output(chip, pin, 0)
        started = time.monotonic()
        last = None
        while RUNNING:
            color = "green" if connected() else ("blue" if time.monotonic() - started < 30 else "red")
            level = brightness()
            state = (color, level)
            if state != last:
                for name, pin in PINS.items():
                    set_channel(chip, pin, level if name == color else 0)
                last = state
            time.sleep(2)
    finally:
        for pin in PINS.values():
            try:
                set_channel(chip, pin, 0)
            except lgpio.error:
                pass
        lgpio.gpiochip_close(chip)


if __name__ == "__main__":
    main()
