"""Cook start messages use fresh readings and obey alert controls."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

import cook_notification


class CookNotificationTests(unittest.TestCase):
    def test_fresh_sample_and_units(self):
        now = datetime(2026, 11, 28, 12, 0)
        sample = {"time": (now - timedelta(seconds=40)).isoformat(),
                  "grill": 212, "pellets": 53, "wifi": "-62 dBm"}
        self.assertEqual(cook_notification.start_message({"name": "Ham"}, sample, "F", now),
                         "Now cooking: Ham • Grill 212°F • Pellets 53% • Wi-Fi -62 dBm")
        self.assertIn("Grill 100°C", cook_notification.start_message({"name": "Ham"}, sample, "C", now))

    def test_stale_sample_does_not_claim_current_status(self):
        now = datetime(2026, 11, 28, 12, 0)
        old = {"time": (now - timedelta(minutes=5)).isoformat(),
               "grill": 400, "pellets": 90, "wifi": "-55 dBm"}
        self.assertEqual(cook_notification.start_message({"name": "Ham"}, old, now=now),
                         "Now cooking: Ham • Grill unavailable • Pellets unavailable • Wi-Fi unavailable")

    def test_disabled_or_snoozed_start_does_not_send(self):
        import app
        with patch.object(app, "alert_settings", return_value={"enabled": False, "new_cook": True}), \
             patch.object(app, "send_message") as send:
            app.notify_cook_started({"name": "Ham"})
            send.assert_not_called()
        with patch.object(app, "alert_settings", return_value={"enabled": True, "new_cook": True,
                                                                "snooze_until": (datetime.now() + timedelta(hours=1)).isoformat()}), \
             patch.object(app, "send_message") as send:
            app.notify_cook_started({"name": "Ham"})
            send.assert_not_called()

    def test_enabled_start_sends_and_records_delivery(self):
        import app
        reading = {"time": datetime.now().isoformat(), "grill": 225, "pellets": 70, "wifi": "-60 dBm"}
        with patch.object(app, "alert_settings", return_value={"enabled": True, "new_cook": True,
                                                                "snooze_until": None}), \
             patch.object(app, "credentials", return_value={"PUSHOVER_APP_TOKEN": "token", "PUSHOVER_USER_KEY": "key"}), \
             patch.object(app, "recent_readings", return_value=[reading]), \
             patch.object(app, "send_message", return_value=True) as send, \
             patch.object(app.alert_delivery, "record") as record:
            app.notify_cook_started({"name": "Ham"})
            message = send.call_args.args[0]
            self.assertIn("Now cooking: Ham", message)
            self.assertIn("Grill 225°F", message)
            self.assertIn("Pellets 70%", message)
            self.assertIn("Wi-Fi -60 dBm", message)
            record.assert_called_once_with(message, True)


if __name__ == "__main__":
    unittest.main()
