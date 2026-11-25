# ASHUR Dashboard Runtime Deployment Runbook

Status: preparation only. This runbook does not authorize merging, deployment, changing the Paper/Shadow worker, or touching trading state.

## Current architecture

- The dashboard is served by `dashboard.http_server` from the supervisor process.
- The listener requires `SERVER_PORT` and binds to `0.0.0.0`.
- The browser consumes only same-origin read-only endpoints:
  - `/healthz`
  - `/api/dashboard/v1/status`
  - `/api/dashboard/v1/history?days=1|7|30|90`
- The server reads the sanitized worker export at `$ASHUR_DATA_DIR/ashur_shadow_status.json`.
- History is isolated in `$ASHUR_DATA_DIR/ashur_dashboard_history.sqlite3`; it is not the trading database.
- The dashboard must remain read-only. Do not expose panel file APIs, worker controls, exchange credentials, or trading database paths.

## Hosting-panel prerequisites

Before changing the hosting panel, record the existing configuration and confirm:

1. The deployed commit is exactly the reviewed head of PR #4.
2. The panel supports a persistent data volume mounted at the same path across restarts.
3. The panel exposes the application port and supplies `SERVER_PORT`.
4. The supervisor starts normally and the existing Paper/Shadow worker watchdog remains unchanged.
5. There is a safe way to run a TLS tunnel as a sidecar process, or the host provides an HTTPS reverse proxy.

Do not guess the port. Read the actual `SERVER_PORT` value from the hosting panel. Do not overwrite existing startup commands or environment variables.

## HTTPS options

### Preferred when the host permits a sidecar: Cloudflare Tunnel

1. Create a dedicated Cloudflare Tunnel and a DNS hostname for the dashboard.
2. Store the tunnel token in a protected file outside the repository and web-served paths. For `cloudflared` 2025.4.0 or later, prefer `--token-file <PATH>` / `TUNNEL_TOKEN_FILE` so the token does not appear in process arguments. Never commit it, print it, or put it in browser code.
3. Configure the tunnel ingress to forward the hostname to the dashboard listener on loopback, using the actual application port:
   `http://127.0.0.1:<SERVER_PORT>`
4. Configure a final catch-all ingress rule to return 404.
5. Run `cloudflared` as a supervised sidecar. It must restart independently and must not replace or wrap the trading supervisor in a way that changes worker lifecycle. Confirm the host permits a second supervised process and that the pinned `cloudflared` binary matches the container architecture before enabling it.
6. Enable HTTPS at the Cloudflare edge, redirect HTTP to HTTPS, and enable HSTS only after HTTPS has been verified.
7. Restrict access to the dashboard hostname with Cloudflare Access or an equivalent identity-aware access policy. The dashboard currently has no application login.

A tunnel token is a secret. Do not paste it into chat, source control, logs, or a command line that is persisted in process listings.

### Alternative: hosting-provider reverse proxy

Use this only if the provider supplies TLS termination and a stable HTTPS hostname. Proxy only the dashboard listener. Preserve same-origin requests and do not expose unrelated panel or filesystem routes. Enable HTTPS redirect and HSTS at the proxy after certificate validation.

## Environment and storage

- `SERVER_PORT`: use the exact port assigned by the hosting panel.
- `ASHUR_DATA_DIR`: point to the persistent mounted data directory, not an ephemeral container filesystem.
- `ASHUR_DASHBOARD_ALLOWED_ORIGINS`: normally leave unset for same-origin use. If a separate trusted origin is required, enter only the exact HTTPS origin; never use a wildcard.
- Do not add exchange API keys or panel API credentials to dashboard environment variables.

The worker status export and dashboard history DB must survive a container restart. The trading database must remain untouched by dashboard setup.

## Runtime verification gate

Run these checks only after a deployment candidate is explicitly approved:

1. Confirm the deployed commit SHA equals the reviewed PR head.
2. Confirm the supervisor and Paper/Shadow worker start normally; verify existing watchdog heartbeat and strategy count.
3. From the public HTTPS hostname, verify:
   - `GET /healthz` returns HTTP 200 and `{"status":"ok"}`.
   - `GET /api/dashboard/v1/status` returns HTTP 200 only for a fresh, valid `PAPER_ONLY` snapshot.
   - `GET /api/dashboard/v1/history?days=1` returns either HTTP 200 with observed history or the documented unavailable response before the first snapshot; it must never fabricate data.
   - The dashboard HTML loads without mixed-content errors and its status indicator reflects API freshness.
4. Verify an unrelated Origin is rejected and POST/PUT/PATCH/DELETE remain HTTP 405.
5. Verify no browser request reaches hosting-panel file APIs and no secrets appear in HTML, JavaScript, responses, or logs.
6. Restart the application once during an approved maintenance window; confirm the history database persists and collection resumes without duplicate snapshots.
7. Re-check worker heartbeat, all six strategies, and protection status after restart.

Record the timestamp, deployed SHA, public hostname, HTTP status codes, and screenshots/results. Redact tokens, cookies, and account identifiers.

## Backup and retention decision

Before enabling collection in the live host, choose and record:

- Backup destination outside the application volume.
- Backup frequency and retention period.
- Restore owner and restore-test schedule.

Back up the dashboard history database using SQLite's online backup mechanism or a consistent filesystem snapshot. Do not copy only the main SQLite file while WAL writes are active. Include the worker status export only if operationally required and protect it as private operational data.

No backup retention policy is assumed by this runbook. Do not delete old data until a retention policy is approved and a restore test succeeds.

## Rollback

If the dashboard or tunnel causes instability:

1. Stop only the dashboard/tunnel sidecar using the hosting panel's supported process controls.
2. Keep the Paper/Shadow worker and watchdog running.
3. Revert the dashboard deployment to the last reviewed commit if needed.
4. Do not reset, delete, or restore the trading database as part of dashboard rollback.
5. Verify worker heartbeat and all six strategies after rollback.

## Release blockers

PR #4 must remain Draft until HTTPS, access control, persistent-volume behavior, backup/restore, and public-origin runtime checks are evidenced. Passing CI is not proof of successful hosting-panel deployment.


## Verified SQLite backup utility

The dashboard branch includes `scripts/backup_dashboard_history.py`. It uses Python's
SQLite online backup API, runs `PRAGMA integrity_check`, and writes a SHA-256
manifest beside the snapshot. This avoids copying only the main database file
while WAL writes may be active.

Example (replace the destination with a separately mounted backup volume):

```bash
python scripts/backup_dashboard_history.py \
  --source "$ASHUR_DATA_DIR/ashur_dashboard_history.sqlite3" \
  --destination-dir "/mnt/ashur-offhost-backups"
```

The script refuses a destination inside the source directory tree. A successful
local run is not, by itself, an off-host backup: the destination must be backed
by storage independent of the SillyDev application volume. The utility does not
upload to cloud storage, configure credentials, schedule jobs, or prune old
backups. Those actions remain disabled until the external destination and
retention policy are explicitly configured and a restore test is completed.

For restoration testing, copy one verified snapshot to a disposable directory,
open it with SQLite, run `PRAGMA integrity_check`, and verify expected tables
and row counts. Never restore over the live history database as part of a test.


## Cloudflare R2 off-host backup uploader

The branch also includes `scripts/upload_dashboard_history_backup.py`. It is deliberately
separate from the SQLite snapshot utility and is not started by the worker or dashboard
supervisor. It requires the optional dependency in
`scripts/requirements-dashboard-backup.txt`.

The uploader:
- accepts only a backup whose adjacent JSON manifest confirms `integrity_check=ok`;
- recomputes the local SQLite file SHA-256 and size before network access;
- uploads the SQLite object first and its manifest second;
- checks object size and SHA-256 metadata with HEAD, then downloads each object and
  recomputes SHA-256 before reporting success;
- prints object keys and checksums only; it never prints credentials.

### R2 bucket and credentials

Create a **private** R2 bucket dedicated to ASHUR dashboard history. Create an R2
S3 API token with Object Read & Write permission scoped to that bucket only. Store
the Access Key ID and Secret Access Key in the hosting provider's protected
environment/secret settings. Never put them in GitHub source, a checked-in env
file, a command argument, a browser variable, or a log.

Required environment variable names:
- `R2_ACCOUNT_ID`
- `R2_BUCKET`
- `R2_ACCESS_KEY_ID`
- `R2_SECRET_ACCESS_KEY`

Optional object prefix: `R2_BACKUP_PREFIX` (defaults to
`ashur/dashboard-history`). The S3 endpoint is constructed as
`https://<ACCOUNT_ID>.r2.cloudflarestorage.com` and uses region `auto`.

### Manual upload sequence

Install the optional dependency in an isolated environment, then create a local
verified SQLite snapshot in a temporary location outside the application data
directory. Upload it only after the R2 bucket and bucket-scoped credentials exist:

```bash
python -m pip install -r scripts/requirements-dashboard-backup.txt
python scripts/backup_dashboard_history.py \
  --source "$ASHUR_DATA_DIR/ashur_dashboard_history.sqlite3" \
  --destination-dir "/tmp/ashur-backup-staging"
python scripts/upload_dashboard_history_backup.py \
  --backup "/tmp/ashur-backup-staging/<BACKUP_FILENAME>.sqlite3" \
  --manifest "/tmp/ashur-backup-staging/<BACKUP_FILENAME>.sqlite3.json"
```

The filename placeholder must be replaced with the exact filename printed by the
snapshot command. A successful upload reports `verified: true` for both objects.
This is a manual utility only: no automatic schedule, retry daemon, retention
deletion, lifecycle rule, or restore-to-live action is configured.

After the first upload, perform a separate restore test by downloading the exact
database object into a disposable directory, comparing its SHA-256 with the
manifest, and running SQLite `PRAGMA integrity_check` plus expected schema/row
checks. Do not overwrite the live history database.

Do not enable lifecycle deletion until a successful restore test exists and a
retention period has been explicitly approved. Keep the bucket private; do not
enable public access or create public object URLs.
