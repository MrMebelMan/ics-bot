# ICP Bot

Checks the Spanish government's ICP appointment system for available TIE
(Tarjeta de Identidad de Extranjero) fingerprint appointment slots in
Barcelona, and pings you on Telegram the moment one opens up — so you don't
have to open that page and refresh it yourself every day.

## How it works

1. Logs into the ICP site using your FNMT digital certificate (the same way
   you'd authenticate on a Spanish government site in a normal browser).
2. Navigates to the TIE fingerprint appointment ("TOMA DE HUELLAS") booking
   page for Barcelona.
3. Checks whether the "no appointments available" message is showing.
4. If it's *not* showing — slots might be open — it sends you a Telegram
   message immediately.
5. Repeats this on a randomized schedule so it looks like normal, occasional
   human traffic rather than a bot hammering the site.

## Requirements

- The site blocks non-Spanish IP addresses, so this needs to run through a
  Spanish residential proxy (a VPN is not enough — datacenter/VPN IPs get
  blocked too; only real residential IPs work).
- Your `.p12` FNMT certificate file and its passphrase.
- A Telegram bot (free, takes 2 minutes to set up) to receive notifications.

## Setup

1. Enter the dev environment:
   ```bash
   nix-shell
   ```
2. Copy the example config and fill in your details:
   ```bash
   cp .env.example .env
   ```
   You'll need to fill in:
   - Path to your `.p12` certificate and its passphrase
   - A Telegram bot token and your chat ID(s)
   - Residential proxy credentials (see `CLAUDE.md` for provider notes)
3. Import your certificate into the system certificate store (one-time):
   ```bash
   mkdir -p ~/.pki/nssdb
   certutil -d sql:$HOME/.pki/nssdb -N --empty-password
   pk12util -d sql:$HOME/.pki/nssdb -i /path/to/cert.p12 -W YOUR_PASSPHRASE
   ```

## Usage

**Run one check right now:**
```bash
python3 checker.py --headless
```

**Watch it run in a visible browser window** (useful the first time, to make
sure everything works):
```bash
python3 checker.py
```

**Run forever**, checking automatically every 1–3 hours (with shorter gaps in
the morning and longer gaps overnight):
```bash
python3 scheduler.py
```
Leave this running in a terminal, `tmux`/`screen` session, or as a background
service on a small always-on server.

**Just want to poke around the site manually** (e.g. to find a new button
selector after the government changes their page again)?
```bash
python3 explore.py
```
This opens a normal, visible browser window and leaves it open until you
close it yourself.

## Notifications

You'll get a Telegram message like:

> SLOTS AVAILABLE — sending notification!
> https://icp.administracionelectronica.gob.es/icpplustieb/citar?p=8&locale=es

If you listed more than one Telegram chat ID, everyone on the list gets the
"slots available" message. Only the first person on the list (the admin
account) also gets pinged automatically whenever the bot itself breaks
(expired certificate, proxy down, government changed the page layout, etc.).

## Troubleshooting

- **"The requested URL was rejected"** — your proxy isn't routing through a
  Spanish IP, or the WAF is blocking datacenter/VPN traffic. Double check
  your proxy config.
- **Asked to select a certificate in a popup** — this only happens with a
  visible browser (`checker.py` without `--headless`, or `explore.py`).
  Headless runs need the `AutoSelectCertificateForUrls` policy set up — see
  `CLAUDE.md` for the exact steps.
- **Nothing happens / blank page** — the certificate might not be imported
  correctly, or the government site changed something. Run
  `python3 explore.py` to look at what's actually on the page.

For anything more technical (architecture, file-by-file breakdown, exact
automation flow), see `CLAUDE.md`.
