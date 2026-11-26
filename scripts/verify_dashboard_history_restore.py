"""Verify a downloaded dashboard-history backup without touching the live database."""
from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any


REQUIRED_TABLES = {"dashboard_snapshots", "dashboard_account_snapshots"}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_restored_backup(
    backup_path: Path,
    manifest_path: Path,
    expected_strategy_count: int = 6,
) -> dict[str, Any]:
    backup_path = Path(backup_path).expanduser().resolve()
    manifest_path = Path(manifest_path).expanduser().resolve()
    if not backup_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("Backup database and JSON manifest are both required")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("integrity_check") != "ok":
        raise ValueError("manifest does not confirm the original SQLite integrity check")
    if manifest.get("backup_file") != backup_path.name:
        raise ValueError("manifest backup_file does not match the supplied database")
    if manifest.get("size_bytes") != backup_path.stat().st_size:
        raise ValueError("database size does not match the manifest")
    digest = _sha256(backup_path)
    if manifest.get("sha256") != digest:
        raise ValueError("database SHA-256 does not match the manifest")

    uri = backup_path.as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=10) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise sqlite3.DatabaseError("restored database failed PRAGMA integrity_check")
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        missing = REQUIRED_TABLES - tables
        if missing:
            raise sqlite3.DatabaseError("restored database is missing required tables")
        snapshot_count = int(conn.execute("SELECT COUNT(*) FROM dashboard_snapshots").fetchone()[0])
        account_count = int(conn.execute("SELECT COUNT(*) FROM dashboard_account_snapshots").fetchone()[0])
        foreign_key_errors = conn.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_errors:
            raise sqlite3.DatabaseError("restored database has foreign-key violations")
        if snapshot_count == 0:
            raise sqlite3.DatabaseError("restored history database contains no portfolio snapshots")
        if account_count != snapshot_count * expected_strategy_count:
            raise sqlite3.DatabaseError(
                "account snapshot count does not match portfolio snapshots × expected strategies"
            )

    return {
        "verified": True,
        "backup_file": backup_path.name,
        "sha256": digest,
        "integrity_check": "ok",
        "foreign_key_check": "ok",
        "portfolio_snapshots": snapshot_count,
        "strategy_snapshots": account_count,
        "strategies_per_snapshot": expected_strategy_count,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--expected-strategies", type=int, default=6)
    args = parser.parse_args()
    if args.expected_strategies < 1:
        parser.error("--expected-strategies must be positive")
    print(json.dumps(
        verify_restored_backup(args.backup, args.manifest, args.expected_strategies),
        sort_keys=True,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
