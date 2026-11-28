"""Low pellet alert must survive sensor gaps and avoid duplicate messages."""
import unittest

from alert_rules import DEFAULTS, evaluate


class PelletAlertTests(unittest.TestCase):
    def test_unavailable_samples_do_not_hide_low_hopper(self):
        settings = dict(DEFAULTS, enabled=True)
        high = {"pellets": 47}
        missing = {"pellets": None}
        low = {"pellets": 3}
        state, first = evaluate(high, missing, {}, settings)
        self.assertEqual(first, [])
        state, crossed = evaluate(missing, low, state, settings)
        self.assertEqual(crossed, ["Pellet level low: 3% remaining."])
        state, again = evaluate(low, {"pellets": 2}, state, settings)
        self.assertEqual(again, [])
        state, _ = evaluate(low, {"pellets": 40}, state, settings)
        state, empty = evaluate({"pellets": 40}, {"pellets": 0}, state, settings)
        self.assertEqual(empty, ["Pellet level low: 0% remaining."])

    def test_sensor_warning_once_until_two_good_samples(self):
        settings = dict(DEFAULTS, enabled=True)
        high = {"pellets": 47, "pellet_status": "ok"}
        bad = {"pellets": None, "pellet_raw": 2160, "pellet_status": "out_of_range"}
        state, first = evaluate(high, bad, {}, settings)
        self.assertEqual(first, ["Check pellet sensor: signal outside the calibrated range (2160 raw counts)."])
        state, repeat = evaluate(bad, bad, state, settings)
        self.assertEqual(repeat, [])
        state, low = evaluate(bad, {"pellets": 3, "pellet_status": "ok"}, state, settings)
        self.assertEqual(low, ["Pellet level low: 3% remaining."])
        state, _ = evaluate(high, high, state, settings)
        state, again = evaluate(high, {"pellets": None, "pellet_status": "unavailable"}, state, settings)
        self.assertEqual(again, ["Check pellet sensor: no valid reading."])


if __name__ == "__main__":
    unittest.main()
