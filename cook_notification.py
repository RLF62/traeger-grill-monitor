"""Format a cook start message from the most recent trustworthy sample."""
from datetime import datetime, timedelta


def start_message(cook, sample, unit="F", now=None):
    now = now or datetime.now()
    fresh = False
    if sample:
        try:
            age = now - datetime.fromisoformat(sample["time"])
            fresh = timedelta(seconds=-30) <= age <= timedelta(minutes=3)
        except (KeyError, TypeError, ValueError):
            pass
    current = sample if fresh else {}
    temperature = current.get("grill")
    if isinstance(temperature, (int, float)) and temperature > 0:
        value = round((temperature - 32) * 5 / 9) if unit == "C" else round(temperature)
        grill = "{}°{}".format(value, unit)
    else:
        grill = "unavailable"
    pellets = current.get("pellets")
    hopper = "{}%".format(round(pellets)) if isinstance(pellets, (int, float)) and 0 <= pellets <= 100 else "unavailable"
    wifi = current.get("wifi") or "unavailable"
    return "Now cooking: {} • Grill {} • Pellets {} • Wi-Fi {}".format(cook["name"], grill, hopper, wifi)
