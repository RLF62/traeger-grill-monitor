"""Sensor trust, trend, history, alert snooze and backup boundaries."""
import json
import tempfile
import unittest
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import backup_export
import cook_presets
import hopper_trend
import pellet_calibration


class FeatureTests(unittest.TestCase):
    def test_outside_calibration_is_not_empty(self):
        settings = pellet_calibration.validate(6500, 24600)
        self.assertEqual(pellet_calibration.percent(6500, settings), 0)
        self.assertEqual(pellet_calibration.health(1800, settings), "out_of_range")
        self.assertIsNone(pellet_calibration.percent(1800, settings))
        reversed_settings = pellet_calibration.validate(24000, 4000)
        self.assertEqual(pellet_calibration.percent(4000, reversed_settings), 100)
        self.assertIsNone(pellet_calibration.percent(30000, reversed_settings))

    def test_hopper_estimate_requires_a_steady_decline(self):
        now = datetime(2026, 11, 28, 12, 0)
        rows = [{"time": (now - timedelta(minutes=110 - i * 10)).isoformat(),
                 "pellets": 80 - i * 3} for i in range(12)]
        self.assertAlmostEqual(hopper_trend.estimate(rows, now), 2.6, delta=0.3)
        self.assertIsNone(hopper_trend.estimate(rows[:4], now))
        flat = [dict(row, pellets=75) for row in rows]
        self.assertIsNone(hopper_trend.estimate(flat, now))

    def test_cook_history_closes_sessions_and_keeps_records(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            path = base / "session.json"
            first = {"name":"Ham", "grill":225, "probe1":160, "probe2":None, "active":True}
            second = dict(first, name="Brisket")
            with patch.object(cook_presets, "HISTORY", base / "history.json"), patch.object(cook_presets, "HISTORY_LOCK", base / "lock"):
                cook_presets.start_session(first, path=path)
                cook_presets.start_session(second, path=path)
                cook_presets.end_session(path=path)
                records = cook_presets.list_sessions()
                self.assertEqual([row["name"] for row in records], ["Brisket", "Ham"])
                self.assertTrue(all(row["ended_at"] for row in records))
                self.assertEqual(len({row["id"] for row in records}), 2)

    def test_backup_excludes_keys_and_preserves_data(self):
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            (base / "data").mkdir()
            (base / "private").mkdir()
            (base / "data/readings.csv").write_text("one sample\n")
            (base / "private/pushover.json").write_text("secret")
            (base / "private/session.key").write_text("secret")
            archive, _ = backup_export.create(base)
            try:
                with zipfile.ZipFile(archive) as zipped:
                    self.assertEqual(zipped.read("data/readings.csv"), b"one sample\n")
                    self.assertNotIn("private/pushover.json", zipped.namelist())
                    self.assertNotIn("private/session.key", zipped.namelist())
            finally:
                archive.close()


if __name__ == "__main__":
    unittest.main()
