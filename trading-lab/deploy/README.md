# ASHUR — Oracle Always Free paper worker

This deployment runs the existing six-strategy paper worker on a small Linux VM. It does **not** place exchange orders and needs no exchange API keys.

## Free-tier target

Use Oracle Cloud Infrastructure **Always Free** resources only:

- Shape: `VM.Standard.A1.Flex` (Arm/Ampere)
- Suggested size: **1 OCPU, 6 GB RAM**
- Image: Ubuntu 22.04 or 24.04, marked **Always Free Eligible**
- Boot volume: default 50 GB
- Region: choose the nearest available home region (Singapore is a sensible first choice from Vietnam, if offered)

Oracle documents up to 2 OCPUs and 12 GB RAM total as Always Free for A1, plus 200 GB total block storage. Always Free capacity is region-dependent and may be temporarily unavailable. The VM must be created in the tenancy's home region.

**Important limitations:** Oracle requires a valid credit/debit card for identity verification; it may place a temporary authorization hold. Do not upgrade to Pay As You Go and do not create any resource that is not explicitly labelled Always Free. Oracle does not provide an SLA for Always Free, and may reclaim an Always Free compute instance if its CPU, network and (for A1) memory utilization all remain below the published thresholds for seven days. So this is the best no-monthly-fee always-on VM option we found, not a guaranteed uptime contract.

Official references:
- https://www.oracle.com/cloud/free/
- https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm
- https://www.oracle.com/cloud/free/faq/

## Provisioning

1. Create an Oracle Cloud Free Tier account yourself. Use accurate personal details. Choose a home region close to Vietnam if available; it cannot normally be changed later.
2. In OCI Console, create a Compute VM:
   - Image: Ubuntu 22.04/24.04, Always Free Eligible
   - Shape: VM.Standard.A1.Flex
   - OCPU: 1
   - Memory: 6 GB
   - Boot volume: default 50 GB, Always Free eligible
   - Assign a public IPv4 address
   - Add your SSH public key
3. Connect to the VM over SSH as `ubuntu`.
4. Run:

```bash
sudo apt-get update
sudo apt-get install -y git
git clone --single-branch --branch ashur-live-shadow https://github.com/XoPo6o/ASHUR.git /tmp/ashur-setup
cd /tmp/ashur-setup
sudo bash trading-lab/deploy/install_oci.sh
```

The installer creates a dedicated Linux user, Python virtual environment, systemd service and a separate GitHub SSH deploy key. It starts the daemon immediately and then repeats the paper worker every 300 seconds.

5. The installer prints a **public** SSH deploy key. In GitHub, open:
   `XoPo6o/ASHUR → Settings → Deploy keys → Add deploy key`.
   Paste that public key and enable **Allow write access**. This allows the VM to publish its paper ledger (SQLite DB + JSON status) back to branch `ashur-live-shadow`. Never share the private key from `/home/ashur/.ssh/id_ed25519`.
6. Check the service:

```bash
sudo systemctl status ashur-live-shadow
sudo journalctl -u ashur-live-shadow -f
```

Expected log lines include `WORKER_CYCLE_START`, six strategy results, and `LEDGER_PUBLISHED to ashur-live-shadow`.

## Operations

- Start: `sudo systemctl start ashur-live-shadow`
- Stop: `sudo systemctl stop ashur-live-shadow`
- Restart: `sudo systemctl restart ashur-live-shadow`
- Logs: `sudo journalctl -u ashur-live-shadow --since "1 hour ago"`

Do not disable the existing GitHub Actions schedule until the VM has been verified to publish several consecutive five-minute updates. Once the VM is confirmed, disable the GitHub cron to prevent two writers from updating the same SQLite ledger.

## Safety

- Paper-only. No exchange credentials, order endpoints or leverage.
- The SQLite ledger remains on the VM and is published to the repository branch.
- A GitHub deploy key is used only for this repository; keep its private half on the VM.
- Oracle Always Free has no uptime SLA and can reclaim sufficiently idle compute instances. Check OCI usage/alerts periodically.

## Enzonic Python Generic (persistent server)

Use the **Python Generic server** in Enzonic's server catalog for this worker. Do not use the separate Enzonic Deploy/serverless project flow: ASHUR is a long-running background process and needs a persistent server filesystem.

1. Create/select a Python Generic server and connect repository `XoPo6o/ASHUR`, branch `ashur-live-shadow`, repository root `/`.
2. Use Python 3.12. The repository-root `requirements.txt` installs the worker dependency (`pandas`).
3. Set the startup command to:

   ```bash
   bash trading-lab/deploy/start_enzonic.sh
   ```

4. Start the server. On first launch, the script creates a repository-scoped SSH key and prints its **public** half in the console.
5. Add that public key at `XoPo6o/ASHUR → Settings → Deploy keys → Add deploy key`, with **Allow write access** enabled. Do not copy or share the private `id_ed25519` file.
6. The daemon runs the six paper strategies every 300 seconds and publishes the SQLite ledger plus JSON status to `ashur-live-shadow`. Check the console for `WORKER_CYCLE_START` and `LEDGER_PUBLISHED to ashur-live-shadow`.

GitHub Actions is retained as a **manual-only fallback** (`workflow_dispatch`). Do not run it while the Enzonic worker is active, because both processes write to the same SQLite ledger.

