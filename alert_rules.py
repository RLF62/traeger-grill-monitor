"""Pure alert transitions for the read-only Traeger monitor."""
DEFAULTS = {
    "enabled": False,
    "new_cook": True,
    "grill_reached": True,
    "probe1_reached": True,
    "probe2_reached": True,
    "grill_deviation": True,
    "pellet_low": True,
    "pellet_sensor": True,
    "pi_hot": True,
    "pellet_threshold": 20,
    "pi_threshold": 180,
    "deviation_percent": 15,
    "emergency_grill": False,
    "emergency_pellets": False,
    "snooze_until": None,
}


def evaluate(previous, current, state, settings):
    """Return new state and messages. The caller must only evaluate new samples."""
    state = dict(state)
    messages = []
    unit = "C" if settings.get("temperature_unit") == "C" else "F"
    def temp(value):
        return "{}°{}".format(round((value - 32) * 5 / 9) if unit == "C" else round(value), unit)
    if previous is None:
        return state, messages

    def positive(row, key):
        value = row.get(key)
        return value if isinstance(value, (int, float)) and value > 0 else None

    target = positive(current, "grill_target")
    prior_target = positive(previous, "grill_target")
    current_grill = positive(current, "grill")
    prior_grill = positive(previous, "grill")

    if target != prior_target:
        state["grill_reached"] = False
        state["grill_deviation"] = None
    for name, label in (("grill", "Grill"), ("probe1", "Probe 1"), ("probe2", "Probe 2")):
        goal = positive(current, name + "_target")
        old_goal = positive(previous, name + "_target")
        value = positive(current, name)
        old_value = positive(previous, name)
        if goal != old_goal:
            state[name + "_reached"] = False
        if goal and old_goal == goal and value and old_value and old_value < goal <= value and not state.get(name + "_reached"):
            state[name + "_reached"] = True
            if settings.get(name + "_reached"):
                messages.append("{} reached target: {} of {}.".format(label, temp(value), temp(goal)))

    if target and current_grill and state.get("grill_reached") and settings.get("grill_deviation"):
        delta = (current_grill - target) / target * 100
        limit = settings["deviation_percent"]
        previous_alert = state.get("grill_deviation")
        new_alert = "high" if delta >= limit else "low" if delta <= -limit else None
        if new_alert and previous_alert != new_alert:
            messages.append("Grill temperature too {}: {} vs {} target.".format(new_alert, temp(current_grill), temp(target)))
            state["grill_deviation"] = new_alert
        elif previous_alert and abs(delta) <= limit * 0.7:
            messages.append("Grill temperature recovered: {} vs {} target.".format(temp(current_grill), temp(target)))
            state["grill_deviation"] = None

    pellets = current.get("pellets")
    if not isinstance(pellets, (int, float)) or not 0 <= pellets <= 100:
        pellets = None
    limit = settings["pellet_threshold"]
    if settings.get("pellet_low") and pellets is not None:
        if pellets <= limit and not state.get("pellet_low"):
            messages.append("Pellet level low: {}% remaining.".format(round(pellets)))
            state["pellet_low"] = True
        elif pellets > limit + 5:
            state["pellet_low"] = False

    status = current.get("pellet_status", "legacy")
    if status in ("unavailable", "out_of_range"):
        state["sensor_ok_streak"] = 0
        if settings.get("pellet_sensor") and not state.get("sensor_check"):
            raw = current.get("pellet_raw")
            detail = ("signal outside the calibrated range ({} raw counts)".format(round(raw))
                      if status == "out_of_range" and isinstance(raw, (int, float))
                      else "no valid reading")
            messages.append("Check pellet sensor: {}.".format(detail))
            state["sensor_check"] = True
    elif status == "ok":
        streak = state.get("sensor_ok_streak", 0) + 1
        state["sensor_ok_streak"] = min(streak, 2)
        if streak >= 2:
            state["sensor_check"] = False

    pi_temp = positive(current, "pi_temp")
    old_pi = positive(previous, "pi_temp")
    limit = settings["pi_threshold"]
    if settings.get("pi_hot") and pi_temp and old_pi:
        if old_pi < limit <= pi_temp and not state.get("pi_hot"):
            messages.append("Grill monitor Pi temperature high: {}.".format(temp(pi_temp)))
            state["pi_hot"] = True
        elif pi_temp < limit - 10:
            state["pi_hot"] = False
    return state, messages
