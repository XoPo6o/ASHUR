"""Upload and read-back verify a verified dashboard SQLite backup in Cloudflare R2.

Credentials are read only from environment variables and are never printed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _readback_sha256(body: BinaryIO) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    try:
        for chunk in iter(lambda: body.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    finally:
        body.close()
    return digest.hexdigest(), size


def _object_key(prefix: str, created_at: str, filename: str) -> str:
    prefix = prefix.strip("/")
    if not prefix or any(part in {".", ".."} for part in prefix.split("/")):
        raise ValueError("R2 prefix must be a non-empty safe object-key prefix")
    parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("backup manifest created_at must include a timezone")
    return f"{prefix}/{parsed:%Y/%m/%d}/{filename}"


def _upload_and_verify(
    client: Any, bucket: str, key: str, path: Path, content_type: str, digest: str
) -> dict[str, Any]:
    size = path.stat().st_size
    with path.open("rb") as stream:
        client.put_object(
            Bucket=bucket,
            Key=key,
            Body=stream,
            ContentLength=size,
            ContentType=content_type,
            Metadata={"sha256": digest},
        )

    head = client.head_object(Bucket=bucket, Key=key)
    if head.get("ContentLength") != size:
        raise RuntimeError(f"R2 object size mismatch after upload: {key}")
    if (head.get("Metadata") or {}).get("sha256") != digest:
        raise RuntimeError(f"R2 object checksum metadata mismatch after upload: {key}")

    response = client.get_object(Bucket=bucket, Key=key)
    remote_digest, remote_size = _readback_sha256(response["Body"])
    if remote_size != size or remote_digest != digest:
        raise RuntimeError(f"R2 read-back checksum mismatch: {key}")
    return {"key": key, "size_bytes": size, "sha256": digest, "verified": True}


def upload_verified_backup(
    backup_path: Path,
    manifest_path: Path,
    bucket: str,
    prefix: str,
    client: Any,
) -> dict[str, Any]:
    backup_path = Path(backup_path).expanduser().resolve()
    manifest_path = Path(manifest_path).expanduser().resolve()
    if not backup_path.is_file() or not manifest_path.is_file():
        raise FileNotFoundError("Both backup SQLite file and its JSON manifest are required")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("integrity_check") != "ok":
        raise ValueError("backup manifest does not confirm SQLite integrity_check=ok")
    if manifest.get("backup_file") != backup_path.name:
        raise ValueError("manifest backup_file does not match the supplied SQLite file")
    if manifest.get("size_bytes") != backup_path.stat().st_size:
        raise ValueError("backup size does not match its manifest")
    backup_digest = sha256_file(backup_path)
    if manifest.get("sha256") != backup_digest:
        raise ValueError("backup SHA-256 does not match its manifest")

    db_key = _object_key(prefix, manifest["created_at"], backup_path.name)
    db_result = _upload_and_verify(
        client, bucket, db_key, backup_path, "application/vnd.sqlite3", backup_digest
    )

    manifest_digest = sha256_file(manifest_path)
    manifest_key = db_key + ".json"
    manifest_result = _upload_and_verify(
        client, bucket, manifest_key, manifest_path, "application/json", manifest_digest
    )
    return {"bucket": bucket, "database": db_result, "manifest": manifest_result}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup", type=Path, required=True, help="Verified SQLite backup file")
    parser.add_argument("--manifest", type=Path, required=True, help="Adjacent backup JSON manifest")
    parser.add_argument("--prefix", default=os.environ.get("R2_BACKUP_PREFIX", "ashur/dashboard-history"))
    args = parser.parse_args()

    required = ("R2_ACCOUNT_ID", "R2_BUCKET", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        parser.error("missing required environment variables: " + ", ".join(missing))

    try:
        import boto3
    except ImportError:
        print(
            "Missing optional dependency. Install scripts/requirements-dashboard-backup.txt.",
            file=sys.stderr,
        )
        return 2

    endpoint = f"https://{os.environ['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com"
    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        region_name="auto",
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
    )
    result = upload_verified_backup(args.backup, args.manifest, os.environ["R2_BUCKET"], args.prefix, client)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
