"""Estimate time to a cook target from a recent, rising sensor trend."""
from datetime import datetime, timedelta


def estimate(rows, targets, stale=False):
    result = {}
    for field in ("grill", "probe1", "probe2"):
        target = targets.get(field) if targets else None
        current = rows[-1].get(field) if rows else None
        if not isinstance(target, (int, float)) or target <= 0 or not isinstance(current, (int, float)) or current <= 0:
            result[field] = {"state": "unavailable"}
            continue
        if stale:
            result[field] = {"state": "stale"}
            continue
        if current >= target:
            result[field] = {"state": "reached"}
            continue
        grill = rows[-1].get("grill")
        if field != "grill" and (not isinstance(grill, (int, float)) or grill <= target + 5):
            result[field] = {"state": "calculating"}
            continue

        end = datetime.fromisoformat(rows[-1]["time"])
        window = 20 if field == "grill" else 60
        points = []
        for row in rows:
            value = row.get(field)
            if not isinstance(value, (int, float)) or value <= 0:
                continue
            stamp = datetime.fromisoformat(row["time"])
            if end - timedelta(minutes=window) <= stamp <= end:
                points.append(((stamp - end).total_seconds() / 60.0, value))
        # A probe moved into or out of food starts a new trend.
        if field != "grill":
            for index in range(len(points) - 1, 0, -1):
                x, y = points[index]
                previous_x, previous_y = points[index - 1]
                if x - previous_x <= 3 and abs(y - previous_y) > 25:
                    points = points[index:]
                    break
        minimum_span = 2 if field == "grill" else 4
        if len(points) < 3 or points[-1][0] - points[0][0] < minimum_span:
            result[field] = {"state": "calculating"}
            continue
        # Check that the newest part of the cook is still warming.
        recent = [point for point in points if point[0] >= -12]
        if len(recent) >= 2 and recent[-1][1] < recent[0][1] + (0.5 if field == "grill" else 0.25):
            result[field] = {"state": "calculating"}
            continue
        mean_x = sum(x for x, _ in points) / len(points)
        mean_y = sum(y for _, y in points) / len(points)
        xx = sum((x - mean_x) ** 2 for x, _ in points)
        slope = sum((x - mean_x) * (y - mean_y) for x, y in points) / xx if xx else 0
        minutes = (target - current) / slope if slope > 0 else float("inf")
        if slope < (0.1 if field == "grill" else 0.02) or not 0.5 <= minutes <= (720 if field == "grill" else 1440):
            result[field] = {"state": "calculating"}
        else:
            result[field] = {"state": "estimate", "minutes": max(1, round(minutes))}
    return result
