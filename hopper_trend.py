"""Conservative estimate from a sustained decline in calibrated hopper level."""
from datetime import datetime, timedelta
from statistics import median


def estimate(rows, now=None):
    if not rows:
        return None
    now = now or datetime.now()
    cutoff = now - timedelta(hours=4)
    buckets = {}
    for row in rows:
        level = row.get("pellets")
        if not isinstance(level, (int, float)) or not 0 <= level <= 100:
            continue
        try:
            stamp = datetime.fromisoformat(row["time"])
        except (ValueError, TypeError, KeyError):
            continue
        if not cutoff <= stamp <= now + timedelta(minutes=2):
            continue
        key = int(stamp.timestamp() // 600)
        buckets.setdefault(key, []).append(level)
    points = sorted((key, median(values)) for key, values in buckets.items())
    if len(points) < 6 or (points[-1][0] - points[0][0]) * 10 < 45:
        return None
    xs = [(key - points[0][0]) / 6 for key, _ in points]
    ys = [level for _, level in points]
    average_x, average_y = sum(xs) / len(xs), sum(ys) / len(ys)
    denominator = sum((x - average_x) ** 2 for x in xs)
    slope = sum((x - average_x) * (y - average_y) for x, y in zip(xs, ys)) / denominator
    drop = median(ys[:3]) - median(ys[-3:])
    residual = sum((y - (average_y + slope * (x - average_x))) ** 2 for x, y in zip(xs, ys))
    spread = sum((y - average_y) ** 2 for y in ys)
    if slope > -2 or drop < 5 or spread <= 0 or 1 - residual / spread < 0.55:
        return None
    current = ys[-1]
    hours = current / -slope
    if current <= 0 or not 0.25 <= hours <= 24:
        return None
    return round(hours, 1)
