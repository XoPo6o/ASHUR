import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.verify_dashboard_history_restore import verify_restored_backup


class DashboardRestoreVerificationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.backup = root / "history.sqlite3"
        self.manifest = root / "history.sqlite3.json"
        with sqlite3.connect(self.backup) as conn:
            conn.executescript("""
                CREATE TABLE dashboard_snapshots (id INTEGER PRIMARY KEY, captured_at TEXT NOT NULL);
                CREATE TABLE dashboard_account_snapshots (
                    snapshot_id INTEGER NOT NULL,
                    strategy_id TEXT NOT NULL,
                    FOREIGN KEY(snapshot_id) REFERENCES dashboard_snapshots(id)
                );
            """)
            conn.execute("INSERT INTO dashboard_snapshots VALUES (1, '2026-11-25T00:00:00+00:00')")
            conn.executemany(
                "INSERT INTO dashboard_account_snapshots VALUES (1, ?)",
                [(f"strategy-{i}",) for i in range(6)],
            )
        self.write_manifest()

    def write_manifest(self):
        self.manifest.write_text(json.dumps({
            "integrity_check": "ok",
            "backup_file": self.backup.name,
            "size_bytes": self.backup.stat().st_size,
            "sha256": hashlib.sha256(self.backup.read_bytes()).hexdigest(),
        }), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_verifies_restored_snapshot_read_only(self):
        result = verify_restored_backup(self.backup, self.manifest)
        self.assertTrue(result["verified"])
        self.assertEqual(result["portfolio_snapshots"], 1)
        self.assertEqual(result["strategy_snapshots"], 6)

    def test_rejects_checksum_mismatch(self):
        self.backup.write_bytes(b"tampered")
        with self.assertRaises(ValueError):
            verify_restored_backup(self.backup, self.manifest)

    def test_rejects_missing_strategy_rows(self):
        with sqlite3.connect(self.backup) as conn:
            conn.execute("DELETE FROM dashboard_account_snapshots WHERE strategy_id='strategy-5'")
        self.write_manifest()
        with self.assertRaises(sqlite3.DatabaseError):
            verify_restored_backup(self.backup, self.manifest)


if __name__ == "__main__":
    unittest.main()
