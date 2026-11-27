from datetime import datetime, timedelta

def estimate(rows, targets, stale=False):
    result = {}
    for field in ('grill', 'probe1', 'probe2'):
        target = targets.get(field) if targets else None
        current = rows[-1].get(field) if rows else None
        if not isinstance(target, (int, float)) or target <= 0 or not isinstance(current, (int, float)) or current <= 0:
            result[field] = {'state': 'unavailable'}
            continue
        if stale:
            result[field] = {'state': 'stale'}
            continue
        if current >= target:
            result[field] = {'state': 'reached'}
            continue
        if field != 'grill' and (not isinstance(rows[-1].get('grill'), (int, float)) or rows[-1]['grill'] <= target + 5):
            result[field] = {'state': 'calculating'}
            continue
        end = datetime.fromisoformat(rows[-1]['time'])
        points = []
        for row in rows:
            value = row.get(field)
            if isinstance(value, (int, float)) and value > 0:
                stamp = datetime.fromisoformat(row['time'])
                if end - timedelta(minutes=20) <= stamp <= end:
                    points.append(((stamp - end).total_seconds() / 60, value))
        if len(points) < 4 or points[-1][0] - points[0][0] < 5:
            result[field] = {'state': 'calculating'}
            continue
        mx = sum(x for x, y in points) / len(points)
        my = sum(y for x, y in points) / len(points)
        xx = sum((x-mx)**2 for x, y in points)
        yy = sum((y-my)**2 for x, y in points)
        slope = sum((x-mx)*(y-my) for x, y in points) / xx if xx else 0
        fit = slope*slope*xx/yy if yy else 0
        minutes = (target-current)/slope if slope > 0 else float('inf')
        if slope < (0.3 if field == 'grill' else 0.12) or fit < 0.6 or not 1 <= minutes <= 480:
            result[field] = {'state': 'calculating'}
        else:
            result[field] = {'state': 'estimate', 'minutes': round(minutes)}
    return result
