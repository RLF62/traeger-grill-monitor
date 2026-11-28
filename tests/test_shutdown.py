"""The shutdown UI cannot power off without a local, confirmed POST."""
import subprocess
import unittest
from unittest.mock import patch

import app
import shutdown_manager


class ShutdownTests(unittest.TestCase):
    def test_service_command_is_narrow_and_nonblocking(self):
        with patch.object(shutdown_manager, "available", return_value=True), \
             patch.object(shutdown_manager.subprocess, "run", return_value=subprocess.CompletedProcess([], 0)) as run:
            shutdown_manager.start()
        self.assertEqual(run.call_args.args[0],
                         ["sudo", "-n", "/usr/bin/systemctl", "start", "--no-block", "traeger-shutdown.service"])

    def test_confirmation_requires_local_csrf_post(self):
        client = app.app.test_client()
        with patch.object(app.shutdown_manager, "start") as start:
            self.assertEqual(client.get("/settings/shutdown").status_code, 200)
            start.assert_not_called()
            self.assertEqual(client.post("/settings/shutdown", data={"csrf": "wrong"}).status_code, 400)
            with client.session_transaction() as browser:
                token = browser["csrf"]
            self.assertEqual(client.post("/settings/shutdown", data={"csrf": token},
                                         environ_overrides={"REMOTE_ADDR": "10.0.0.8"}).status_code, 403)
            response = client.post("/settings/shutdown", data={"csrf": token})
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Shutting down the Pi", response.data)
            start.assert_called_once_with()

    def test_service_failure_keeps_confirmation_page(self):
        client = app.app.test_client()
        client.get("/settings/shutdown")
        with client.session_transaction() as browser:
            token = browser["csrf"]
        with patch.object(app.shutdown_manager, "start", side_effect=shutdown_manager.ShutdownError("Service unavailable")):
            response = client.post("/settings/shutdown", data={"csrf": token})
        self.assertEqual(response.status_code, 503)
        self.assertIn(b"Service unavailable", response.data)


if __name__ == "__main__":
    unittest.main()
