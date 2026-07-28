# Ubuntu setup

These instructions target Ubuntu 22.04 or 24.04.

## 1. Install Python and certificate tools

```bash
sudo apt update
sudo apt install -y python3 python3-venv libnss3-tools
```

## 2. Create a virtual environment

Run these commands from the project directory:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Activate the virtual environment again whenever you open a new shell:

```bash
source .venv/bin/activate
```

## 3. Install Chromium and its Ubuntu dependencies

```bash
python -m playwright install --with-deps chromium
```

Playwright's documentation covers
[browser and system dependency installation](https://playwright.dev/python/docs/browsers).

## 4. Configure the checker

Create `.env` from the provided example if it does not already exist:

```bash
cp .env.example .env
chmod 600 .env
nano .env
```

Configure the values for your environment:

```dotenv
P12_PATH=/absolute/path/to/certificate.p12
P12_PASSPHRASE=certificate-password

TELEGRAM_BOT_TOKEN=your-token
TELEGRAM_CHAT_IDS=first-chat-id,second-chat-id

NO_SLOTS_TEXT=En este momento no hay citas disponibles
TARGET_URL=https://icp.administracionelectronica.gob.es/icpplustieb/citar?p=8&locale=es

TIMEOUT=30000
NOTIFY_ON_ERROR=1
```

Telegram is optional. Without its token and chat IDs, notifications are printed
to the terminal instead of being sent. `TELEGRAM_CHAT_IDS` accepts one or more
comma-separated IDs. The older singular `TELEGRAM_CHAT_ID` setting remains
supported when `TELEGRAM_CHAT_IDS` is not set.

To discover each recipient's ID, run the helper bot:

```bash
python bot.py
```

Each person should open the bot in Telegram and send `/start`. The bot replies
with that person's Telegram user ID. Put both returned IDs in
`TELEGRAM_CHAT_IDS`, separated by a comma, then stop `bot.py` with `Ctrl+C`.

The helper uses Telegram's
[`getUpdates`](https://core.telegram.org/bots/api#getupdates) long polling, so
it cannot run while a webhook is configured for the same bot.

The proxy fields are also optional:

```dotenv
PROXY_SERVER=
PROXY_USER=
PROXY_PASS=
```

The appointment site may reject connections from outside Spain. In that case,
use a Spanish proxy or connect the included WireGuard configuration.

Set `NO_SLOTS_TEXT` to text that actually appears on the result page when no
appointments are available. The checker treats its absence as an available-slot
notification.

## 5. Import the client certificate

The current browser setup does not pass `P12_PATH` directly to Playwright.
Chromium therefore needs the certificate in the NSS database belonging to the
Linux user that runs the checker.

Create the database:

```bash
mkdir -p "$HOME/.pki/nssdb"
certutil -d "sql:$HOME/.pki/nssdb" -N --empty-password
```

Import the certificate:

```bash
pk12util -d "sql:$HOME/.pki/nssdb" -i /absolute/path/to/certificate.p12
```

`pk12util` prompts for the `.p12` password, which avoids putting the password
directly in shell history.

Verify the import:

```bash
certutil -d "sql:$HOME/.pki/nssdb" -L
```

If the checker will run through cron or systemd, import the certificate as the
same Linux user that will run that service.

## 6. Test the checker

On an Ubuntu desktop, first run it with a visible browser:

```bash
source .venv/bin/activate
python checker.py
```

On a server or for normal automated checks, run it headlessly:

```bash
source .venv/bin/activate
python checker.py --headless
```

The exploration script opens the target page and leaves the browser available
for manual navigation:

```bash
python explore.py
```

## 7. Optional WireGuard connection

Connect before running the checker:

```bash
sudo wg-quick up ./wg-ES-96.conf
python checker.py --headless
sudo wg-quick down ./wg-ES-96.conf
```

Always bring the VPN down after the checker exits, including when the checker
fails.

## Troubleshooting

List the browsers installed for the active Python environment:

```bash
python -m playwright install --list
```

If Chromium fails after upgrading Playwright, reinstall the matching browser:

```bash
python -m playwright install --with-deps chromium
```

If certificate authentication fails, confirm that:

- `certutil -d "sql:$HOME/.pki/nssdb" -L` lists the certificate.
- The certificate was imported as the user running the checker.
- The certificate is valid and has not expired.
- Only the intended client certificate is available if Chromium displays a
  certificate-selection prompt.

Keep `.env`, `.p12` files, proxy credentials, Telegram tokens, and WireGuard
configuration private. Do not commit them to source control.
