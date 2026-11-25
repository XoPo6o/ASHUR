import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from scripts.backup_dashboard_history import create_verified_backup


class DashboardBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source_dir = self.root / "app-data"
        self.backup_dir = self.root / "external-backups"
        self.source_dir.mkdir()
        self.source = self.source_dir / "history.sqlite3"
        with sqlite3.connect(self.source) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE snapshots (id INTEGER PRIMARY KEY, equity REAL)")
            conn.executemany("INSERT INTO snapshots(equity) VALUES (?)", [(1000.0,), (1010.5,)])

    def tearDown(self):
        self.temp.cleanup()

    def test_creates_integrity_checked_snapshot_and_manifest(self):
        result = create_verified_backup(self.source, self.backup_dir)
        backup = self.backup_dir / result["backup_file"]
        manifest_path = backup.with_suffix(backup.suffix + ".json")
        self.assertTrue(backup.is_file())
        self.assertTrue(manifest_path.is_file())
        self.assertEqual(result["integrity_check"], "ok")
        self.assertEqual(result["size_bytes"], backup.stat().st_size)
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(manifest["sha256"], result["sha256"])
        with sqlite3.connect(backup) as conn:
            rows = conn.execute("SELECT equity FROM snapshots ORDER BY id").fetchall()
        self.assertEqual(rows, [(1000.0,), (1010.5,)])

    def test_rejects_destination_inside_source_tree(self):
        with self.assertRaises(ValueError):
            create_verified_backup(self.source, self.source_dir / "backups")

    def test_rejects_missing_source(self):
        with self.assertRaises(FileNotFoundError):
            create_verified_backup(self.source_dir / "missing.sqlite3", self.backup_dir)


if __name__ == "__main__":
    unittest.main()
