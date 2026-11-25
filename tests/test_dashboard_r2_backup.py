import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.upload_dashboard_history_backup import upload_verified_backup


class FakeBody:
    def __init__(self, data: bytes):
        self.data = data
        self.offset = 0
        self.closed = False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self.data) - self.offset
        result = self.data[self.offset:self.offset + size]
        self.offset += len(result)
        return result

    def close(self):
        self.closed = True


class FakeR2:
    def __init__(self, corrupt_readback: bool = False):
        self.objects: dict[str, bytes] = {}
        self.metadata: dict[str, dict[str, str]] = {}
        self.corrupt_readback = corrupt_readback

    def put_object(self, **kwargs: Any):
        body = kwargs["Body"].read()
        self.objects[kwargs["Key"]] = body
        self.metadata[kwargs["Key"]] = kwargs["Metadata"]

    def head_object(self, **kwargs: Any):
        key = kwargs["Key"]
        return {"ContentLength": len(self.objects[key]), "Metadata": self.metadata[key]}

    def get_object(self, **kwargs: Any):
        body = self.objects[kwargs["Key"]]
        if self.corrupt_readback:
            body += b"corrupt"
        return {"Body": FakeBody(body)}


class DashboardR2BackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        self.backup = root / "history-20261125.sqlite3"
        self.manifest = root / "history-20261125.sqlite3.json"
        self.backup.write_bytes(b"sqlite snapshot bytes")
        self.manifest_data = {
            "schema_version": 1,
            "created_at": "2026-11-25T14:00:00+00:00",
            "backup_file": self.backup.name,
            "size_bytes": self.backup.stat().st_size,
            "sha256": hashlib.sha256(self.backup.read_bytes()).hexdigest(),
            "integrity_check": "ok",
        }
        self.manifest.write_text(json.dumps(self.manifest_data), encoding="utf-8")

    def tearDown(self):
        self.temp.cleanup()

    def test_uploads_database_then_manifest_and_verifies_readback(self):
        client = FakeR2()
        result = upload_verified_backup(self.backup, self.manifest, "private-bucket", "ashur/history", client)
        self.assertTrue(result["database"]["verified"])
        self.assertTrue(result["manifest"]["verified"])
        self.assertIn("ashur/history/2026/11/25/" + self.backup.name, client.objects)
        self.assertEqual(len(client.objects), 2)

    def test_rejects_modified_backup_before_upload(self):
        self.backup.write_bytes(b"tampered")
        client = FakeR2()
        with self.assertRaises(ValueError):
            upload_verified_backup(self.backup, self.manifest, "private-bucket", "ashur/history", client)
        self.assertEqual(client.objects, {})

    def test_detects_corrupt_remote_readback(self):
        client = FakeR2(corrupt_readback=True)
        with self.assertRaises(RuntimeError):
            upload_verified_backup(self.backup, self.manifest, "private-bucket", "ashur/history", client)

    def test_rejects_unsafe_prefix(self):
        client = FakeR2()
        with self.assertRaises(ValueError):
            upload_verified_backup(self.backup, self.manifest, "private-bucket", "../unsafe", client)


if __name__ == "__main__":
    unittest.main()
