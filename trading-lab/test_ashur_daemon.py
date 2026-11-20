"""Offline regression tests for ASHUR daemon and persistent paper state."""
import importlib.util
import sqlite3
from pathlib import Path

MODULE_DIR = Path(__file__).resolve().parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


daemon = load_module("ashur_daemon_under_test", MODULE_DIR / "ashur_daemon.py")
worker = load_module("live_shadow_worker_under_test", MODULE_DIR / "live_shadow_worker.py")


def test_daemon_has_no_git_ledger_publisher():
    assert not hasattr(daemon, "publish_ledger")
    assert daemon.WORKER.name == "live_shadow_worker.py"


def test_legacy_sqlite_and_status_migrate_to_persistent_storage_once(tmp_path, monkeypatch):
    repo_dir = tmp_path / "repo"
    state_dir = tmp_path / "persistent-state"
    repo_dir.mkdir()

    legacy_db = repo_dir / "ashur_shadow.db"
    with sqlite3.connect(legacy_db) as conn:
        conn.execute("CREATE TABLE migration_probe (value TEXT)")
        conn.execute("INSERT INTO migration_probe VALUES ('preserve-me')")

    legacy_status = repo_dir / "ashur_shadow_status.json"
    legacy_status.write_text('{"mode":"PAPER_ONLY"}', encoding="utf-8")

    monkeypatch.setattr(worker, "ROOT", repo_dir)
    monkeypatch.setattr(worker, "DATA_DIR", state_dir)
    monkeypatch.setattr(worker, "DB", state_dir / "ashur_shadow.db")
    monkeypatch.setattr(worker, "STATUS_FILE", state_dir / "ashur_shadow_status.json")

    worker.prepare_data_dir()

    with sqlite3.connect(worker.DB) as conn:
        value = conn.execute("SELECT value FROM migration_probe").fetchone()[0]
    assert value == "preserve-me"
    assert worker.STATUS_FILE.read_text(encoding="utf-8") == '{"mode":"PAPER_ONLY"}'

    # A later code sync must never overwrite already-migrated live state.
    with sqlite3.connect(legacy_db) as conn:
        conn.execute("UPDATE migration_probe SET value='stale-repo-copy'")
    legacy_status.write_text('{"mode":"STALE"}', encoding="utf-8")

    worker.prepare_data_dir()
    with sqlite3.connect(worker.DB) as conn:
        value = conn.execute("SELECT value FROM migration_probe").fetchone()[0]
    assert value == "preserve-me"
    assert worker.STATUS_FILE.read_text(encoding="utf-8") == '{"mode":"PAPER_ONLY"}'


if __name__ == "__main__":
    import unittest
    unittest.main()
