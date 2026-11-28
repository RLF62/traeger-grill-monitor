"""Calibration endpoints and disconnected-signal behavior."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pellet_calibration as calibration


class PelletCalibrationTests(unittest.TestCase):
    def test_default_and_custom_endpoints(self):
        self.assertEqual(calibration.percent(5000, calibration.DEFAULT), 0)
        self.assertEqual(calibration.percent(24600, calibration.DEFAULT), 100)
        self.assertIsNone(calibration.percent(270, calibration.DEFAULT))
        rising = calibration.validate(8000, 18000)
        self.assertEqual(calibration.percent(13000, rising), 50)
        falling = calibration.validate(24000, 4000)
        self.assertEqual(calibration.percent(14000, falling), 50)
        self.assertEqual(calibration.percent(4000, falling), 100)

    def test_reject_too_close_and_save_locally(self):
        with self.assertRaises(ValueError):
            calibration.validate(5000, 5200)
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(calibration, "CONFIG", Path(folder) / "private" / "calibration.json"):
                calibration.save(7000, 22000)
                self.assertEqual(calibration.load(), {"empty_raw": 7000, "full_raw": 22000})
                self.assertEqual(calibration.CONFIG.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
