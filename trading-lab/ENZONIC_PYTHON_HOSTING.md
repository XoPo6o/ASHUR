# ASHUR on Enzonic Python Hosting

## Runtime
- Repository: `XoPo6o/ASHUR`
- Branch: `ashur-live-shadow`
- Python: `3.12`
- Startup command: `python -u trading-lab/ashur_daemon.py`
- Dependencies: repository-root `requirements.txt`
- Worker cadence: 300 seconds by default.

## State and safety
The daemon is paper-only. It reads public Bybit/Binance spot market data and does not place exchange orders or require exchange API keys.

Mutable state is stored outside the Git checkout at:
`~/.local/share/ashur/`

Files:
- `ashur_shadow.db`
- `ashur_shadow_status.json`

On first start, the worker copies the legacy SQLite database into this persistent directory using SQLite's backup API, then copies the legacy status JSON if no persistent copy exists. Existing persistent state is never overwritten by a later Git sync.

To use a different persistent directory, set `ASHUR_DATA_DIR` in the hosting panel. The path must be on the server's persistent filesystem, not a temporary build directory.

## Deployment checklist
1. Use the generic Python/background-worker runtime, not Enzonic Deploy serverless functions.
2. Connect the repository above and select branch `ashur-live-shadow`.
3. Use Python 3.12 and the startup command above.
4. Keep the server's persistent filesystem enabled; do not delete/reinstall the instance.
5. Start the process and confirm the console shows:
   - `ASHUR paper daemon started`
   - `STATE_STORAGE_READY`
   - `WORKER_CYCLE_END exit_code=0`

The current Enzonic game-server MCP credential is not required by this runtime. Do not put exchange keys or Enzonic API tokens in the repository.

## Existing server
The existing game server is not automatically modified by creating a separate Python-hosting instance. Do not remove or reinstall it until its live SQLite file has been backed up and verified on the new runtime.
