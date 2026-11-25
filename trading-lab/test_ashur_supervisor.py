"""Offline tests for the ASHUR SillyDev process supervisor."""
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "ashur_supervisor_under_test", MODULE_DIR / "ashur_supervisor.py"
)
supervisor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(supervisor)


class TestSupervisorHeartbeat(unittest.TestCase):
    def test_reads_fresh_heartbeat_age(self):
        now = datetime(2026, 11, 25, 10, 0, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as directory:
            status = Path(directory) / "status.json"
            status.write_text(
                json.dumps({"updated_at": (now - timedelta(minutes=2)).isoformat()}),
                encoding="utf-8",
            )
            self.assertEqual(supervisor.heartbeat_age_seconds(status, now), 120.0)

    def test_missing_or_invalid_status_returns_none(self):
        with tempfile.TemporaryDirectory() as directory:
            status = Path(directory) / "missing.json"
            self.assertIsNone(supervisor.heartbeat_age_seconds(status))
            status.write_text("{broken", encoding="utf-8")
            self.assertIsNone(supervisor.heartbeat_age_seconds(status))

    def test_fresh_heartbeat_does_not_restart(self):
        self.assertFalse(supervisor.heartbeat_is_stale(
            60, 1200, max_age_seconds=900, startup_grace_seconds=300
        ))

    def test_startup_grace_prevents_premature_restart(self):
        self.assertFalse(supervisor.heartbeat_is_stale(
            5000, 120, max_age_seconds=900, startup_grace_seconds=300
        ))

    def test_stale_heartbeat_restarts_after_grace(self):
        self.assertTrue(supervisor.heartbeat_is_stale(
            901, 301, max_age_seconds=900, startup_grace_seconds=300
        ))

    def test_missing_heartbeat_restarts_after_grace(self):
        self.assertTrue(supervisor.heartbeat_is_stale(
            None, 301, max_age_seconds=900, startup_grace_seconds=300
        ))


if __name__ == "__main__":
    unittest.main()
