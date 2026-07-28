# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A bot that checks the Spanish government's ICP appointment system for available TIE (Tarjeta de Identidad de Extranjero) fingerprint slots in Barcelona, and sends a Telegram notification when slots appear.

## Commit style

Concise conventional commits: `type: short imperative summary`, one line, no body unless truly necessary (e.g. `fix: force full chromium instead of headless-shell substitute`). Types: `feat`, `fix`, `chore`, `docs`, `refactor`.

## Environment

NixOS. Always use `nix-shell` to enter the dev environment — it provides Python 3.13 + playwright, sets `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to the system Chromium, and has `wireguard-tools` and `nssTools` available.

```bash
nix-shell
```

## Running

```bash
# Single check (headless)
python3 checker.py --headless

# Single check (visible browser, for debugging)
python3 checker.py

# Open browser and navigate manually (stays open until you close it)
python3 explore.py

# Run forever, checking on a randomized interval (see scheduler.py for windows)
python3 scheduler.py
```

## Architecture

- `common.py` — shared config (env vars), Telegram senders, and `launch_browser()` (proxy + stealth fingerprint setup used by both `checker.py` and `explore.py`). Any change to browser launch args, headers, or fingerprint spoofing goes here so both scripts stay in sync.
- `checker.py` — one full run: navigate → select tramite → Cl@ve auth → detect slots → notify. Always closes the browser via `finally`, even on error.
- `explore.py` — same browser setup as checker.py, but opens headed and stays open for manual navigation/debugging.
- `scheduler.py` — long-running loop: runs `checker.py --headless` as a subprocess, then sleeps before the next run (with a 300s subprocess timeout so a stuck run can't block the loop forever). Default interval is 30 minutes (±10% jitter); drops to 15 minutes on Thursday/Friday mornings (06:00–15:00, new slots tend to drop those days) — see `MORNING_START`/`MORNING_END`/`FAST_WEEKDAYS`. On any run failure (site unavailable), retries in 5 minutes instead of waiting out the normal interval, regardless of day — see `FAST_RETRY_SECONDS`.
- `bot.py` — one-off helper to discover a Telegram user/chat ID: run it, have each recipient DM the bot `/start`, it replies with their ID to put in `TELEGRAM_CHAT_IDS`.

## Configuration

Copy `.env.example` to `.env` and fill in:
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_IDS` — comma-separated chat IDs; the first one is the admin account and always receives error notifications on every failure, all of them receive slot-available alerts
- `NO_SLOTS_TEXT` — exact Spanish text shown when no slots exist (`En este momento no hay citas disponibles.`)
- `TARGET_URL` — defaults to Barcelona (p=8)
- `PROXY_SERVER` / `PROXY_USER` / `PROXY_PASS` — residential proxy (see Geoblocking below); a session id is auto-appended to `PROXY_PASS` per run if not already present, so one run keeps one IP but each new run gets a fresh one
- `TIMEOUT` — per-step Playwright timeout in ms (default 15000)

**Never read `.env` — it contains secrets. Use `.env.example` instead.**

## Certificate setup (one-time)

The .p12 must be imported into the system NSS database so Chromium presents it automatically across all Cl@ve redirect domains:

```bash
mkdir -p ~/.pki/nssdb
certutil -d sql:$HOME/.pki/nssdb -N --empty-password
pk12util -d sql:$HOME/.pki/nssdb -i /path/to/cert.p12 -W YOUR_PASSPHRASE
```

Headless Chromium cannot show the "select a certificate" picker dialog, so it needs the `AutoSelectCertificateForUrls` enterprise policy to auto-select the imported cert for the Cl@ve identity domain. This policy is only honored by a real system browser binary launched via `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` (`executable_path=`) — **not** Playwright's own bundled Chromium (`playwright install chromium`), which doesn't read OS enterprise policy paths at all.

On Ubuntu, `apt install chromium-browser` is a transitional package that installs the **snap** build (default since 19.10) — snap confinement can't see `/etc/*/policies/managed/`, so the policy silently never applies. Use real Google Chrome instead (a genuine `.deb`, not a snap):

```bash
wget -qO /tmp/chrome.deb https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install -y /tmp/chrome.deb

sudo mkdir -p /etc/opt/chrome/policies/managed
sudo tee /etc/opt/chrome/policies/managed/icp.json << 'EOF'
{
  "AutoSelectCertificateForUrls": [
    "{\"pattern\":\"https://pasarela-ident.clave.gob.es\",\"filter\":{}}"
  ]
}
EOF
```

Then set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/google-chrome-stable` in `.env`.

On NixOS, `programs.chromium.{enable, extraOpts}` in `configuration.nix` writes the equivalent policy for the system nixpkgs Chromium (`/etc/chromium/policies/managed/extra.json`), which is what `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` should point at there instead.

## Geoblocking

The site rejects non-Spanish IPs at the WAF level. A residential proxy (e.g. IPRoyal) with Spanish country/city targeting is required — datacenter IPs (VPN providers like ProtonVPN, most VPS IPs) get blocked outright. Configure via `PROXY_SERVER`/`PROXY_USER`/`PROXY_PASS` in `.env`.

## Automation flow

`checker.py` navigates through this sequence:
1. Load `TARGET_URL` (province pre-selected via `p=8`)
2. Wait for `#tramiteGrupo[0]` select → select value `4010` (TOMA DE HUELLAS / TIE)
3. Random 1–3s delay → click `#btnAceptar`
4. Wait for info page → click `#btnAccesoClave` (Cl@ve auth path)
5. Wait → click `button.idp-button[onclick*='AFIRMA']` (DNIe / Certificado electrónico — there are multiple `.idp-button` elements on this page, so it must be targeted by its `onclick` attribute, not the class alone). On timeout here, a screenshot is saved to `timeout_debug.png` before re-raising, to help diagnose stuck cert/auth flows.
6. Wait for redirect to `/acEntrada`
7. Check page text for `NO_SLOTS_TEXT`. If absent, slots are available — notify immediately. If present, this page's text is **not conclusive on its own** — continue: click `#btnCopiar` → `#btnEnviar` ("Aceptar") → `#btnEnviar` ("Solicitar Cita") to reach the 5-step booking wizard, then check `NO_SLOTS_TEXT` again on that page, which is the reliable signal.

## Notifications

Telegram bot. Get token from `@BotFather`, chat ID from `@userinfobot`. Slot-available alerts go to every ID in `TELEGRAM_CHAT_IDS`; error alerts fire unconditionally on every failed run and go only to the first (admin) ID.

## Production deployment (VPS)

A small VPS (1 vCPU / 2GB RAM) is sufficient — one headless Chromium instance runs sequentially per check, never concurrently, and the process exits between runs. `--disable-dev-shm-usage` and `--disable-gpu` are already in `common.py`'s launch args to avoid Docker shared-memory limits and unnecessary GPU init in headless environments. Configure swap (`vm.swappiness=10`) as general hardening, not because this workload needs it.

### One-time provisioning

`deploy/provision-vps.sh` (run once via `sudo`, as the existing sudoer account that will own the bot — no separate service user) installs system deps, sets up that user's NSS cert database, installs the `AutoSelectCertificateForUrls` Chromium policy, and installs `deploy/icp-bot.service` as a **user-level** systemd unit (`systemctl --user`, with `loginctl enable-linger` so it survives SSH disconnects) — deliberately not a system-level unit, so restarting it never needs sudo/root once set up.

After provisioning, `.env` and the `.p12` cert are placed on the server by hand — never via git/CI, since they're secrets.

### CI/CD

`.github/workflows/deploy.yml` runs on push to `main` (or manually via `workflow_dispatch`): rsyncs the repo to `~/icp_bot` on the VPS (excluding `.env`, `*.p12`, `.venv`, `deploy/`), reinstalls Python deps, and restarts the `icp-bot` user service over SSH. `deploy/` is deliberately excluded from both the trigger and the sync — provisioning changes (packages, systemd unit, browser policy) must be applied manually. Required repo secrets: `VPS_HOST`, `VPS_USER` (the sudoer account the bot runs as), `VPS_SSH_KEY` (private key matching an `authorized_keys` entry on the server), `VPS_PORT` (optional, defaults to 22).
