"""Create a consistent, integrity-checked SQLite backup of dashboard history.

This creates a local backup artifact only. The destination must be on storage
outside the application volume to count as an off-host backup.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def create_verified_backup(source: Path, destination_dir: Path) -> dict[str, Any]:
    source = Path(source).expanduser().resolve()
    destination_dir = Path(destination_dir).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(f"SQLite source database not found: {source}")
    if destination_dir == source.parent or source.parent in destination_dir.parents:
        raise ValueError("backup destination must not be inside the source directory tree")

    destination_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    final_db = destination_dir / f"{source.stem}-{stamp}.sqlite3"
    final_manifest = final_db.with_suffix(final_db.suffix + ".json")

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{source.stem}-", suffix=".sqlite3.tmp", dir=destination_dir
    )
    os.close(fd)
    temporary_db = Path(temporary_name)
    temporary_manifest = final_manifest.with_suffix(final_manifest.suffix + ".tmp")
    try:
        with sqlite3.connect(str(source), timeout=10) as source_conn:
            with sqlite3.connect(str(temporary_db), timeout=10) as target_conn:
                source_conn.backup(target_conn, pages=128, sleep=0.05)
                check = target_conn.execute("PRAGMA integrity_check").fetchone()
                if not check or check[0] != "ok":
                    raise sqlite3.DatabaseError("backup integrity_check did not return ok")
                target_conn.commit()

        with temporary_db.open("rb") as stream:
            os.fsync(stream.fileno())
        digest = _sha256(temporary_db)
        size = temporary_db.stat().st_size
        os.replace(temporary_db, final_db)
        manifest = {
            "schema_version": 1,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_database": source.name,
            "backup_file": final_db.name,
            "size_bytes": size,
            "sha256": digest,
            "integrity_check": "ok",
        }
        with temporary_manifest.open("w", encoding="utf-8") as stream:
            json.dump(manifest, stream, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_manifest, final_manifest)
        return manifest
    except Exception:
        temporary_db.unlink(missing_ok=True)
        temporary_manifest.unlink(missing_ok=True)
        # Do not leave a database artifact without its verification manifest.
        if final_db.exists() and not final_manifest.exists():
            final_db.unlink()
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="SQLite database to back up")
    parser.add_argument(
        "--destination-dir", type=Path, required=True,
        help="Backup directory; use a mounted volume outside the application disk",
    )
    args = parser.parse_args()
    manifest = create_verified_backup(args.source, args.destination_dir)
    print(json.dumps(manifest, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
