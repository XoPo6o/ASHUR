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

### HTTPS tunnel (only if a free, already-available option is confirmed)

1. Use only a tunnel service that is already available at no additional cost; do not create a paid subscription or add a payment method for this project.
2. Store the tunnel token in a protected file outside the repository and web-served paths. If the selected tunnel client supports token files, keep its token outside the repository and web-served paths. Never commit it, print it, or put it in browser code.
3. Configure the tunnel ingress to forward the hostname to the dashboard listener on loopback, using the actual application port:
   `http://127.0.0.1:<SERVER_PORT>`
4. Configure a final catch-all ingress rule to return 404.
5. Use an HTTPS tunnel or reverse proxy only if a genuinely no-cost option is already available and its terms have been checked. Confirm the host permits the required supervised process and that the client matches the container architecture before enabling it.
6. Enable HTTPS, redirect HTTP to HTTPS, and enable HSTS only after HTTPS has been verified.
7. Restrict access to the dashboard hostname with an identity-aware access policy that adds no paid subscription or payment requirement. The dashboard currently has no application login. If no suitable free option is available, keep the dashboard private and do not publish it.

A tunnel token is a secret. Do not paste it into chat, source control, logs, or a command line that is persisted in process listings.

### Alternative: hosting-provider reverse proxy

Use this only if the provider supplies TLS termination and a stable HTTPS hostname. Proxy only the dashboard listener. Preserve same-origin requests and do not expose unrelated panel or filesystem routes. Enable HTTPS redirect and HSTS at the proxy after certificate validation.

## Temporary private preview without a custom domain

Cloudflare Quick Tunnels can provide an HTTPS `trycloudflare.com` URL without a Cloudflare account or owned domain. The current `cloudflared` release also supports email allow-listing with `--allowed-mail`, which requires a one-time email PIN before a visitor reaches the local service.

Example for a temporary preview only:

```bash
cloudflared tunnel --url "http://127.0.0.1:$SERVER_PORT" --allowed-mail "OWNER_EMAIL"
```

Operational limits:
- The hostname is temporary and changes when the Quick Tunnel is restarted.
- Anyone not on the allow-list must be denied before traffic reaches the dashboard.
- The tunnel process must remain running; stopping it disables the URL.
- Quick Tunnels have no uptime guarantee, allow at most 200 in-flight requests, and do not support Server-Sent Events (SSE). The current Wall preview uses ordinary HTTP `fetch` polling, not SSE.
- This is suitable for a short private review, not a stable production hostname or a substitute for persistent storage and off-host backups.
- Never publish the dashboard through an unrestricted Quick Tunnel.
- Do not place an email address or tunnel configuration containing secrets in source control.

For a stable production hostname, use a named Cloudflare Tunnel and a domain routed through Cloudflare. If no suitable free domain and identity-aware access setup are available, keep The Wall private.

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
