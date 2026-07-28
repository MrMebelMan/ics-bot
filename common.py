#!/usr/bin/env python3
import os
import secrets

import requests as _requests
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Browser, BrowserContext

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
_telegram_chat_ids = os.getenv("TELEGRAM_CHAT_IDS", "")
if _telegram_chat_ids:
    TELEGRAM_CHAT_IDS = tuple(
        dict.fromkeys(chat_id.strip() for chat_id in _telegram_chat_ids.split(",") if chat_id.strip())
    )
else:
    _legacy_chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()
    TELEGRAM_CHAT_IDS = (_legacy_chat_id,) if _legacy_chat_id else ()
TARGET_URL = os.getenv("TARGET_URL", "https://icp.administracionelectronica.gob.es/icpplustieb/citar?p=8&locale=es")
CHROMIUM_PATH = os.getenv("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH") or None
PROXY_SERVER = os.getenv("PROXY_SERVER", "")
PROXY_USER = os.getenv("PROXY_USER", "")
PROXY_PASS = os.getenv("PROXY_PASS", "")


def _send_to(chat_ids: tuple, message: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not chat_ids:
        print(f"[NOTIFY] {message}")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    for chat_id in chat_ids:
        try:
            response = _requests.post(url, json={"chat_id": chat_id, "text": message}, timeout=10)
            response.raise_for_status()
        except _requests.RequestException as error:
            print(f"[NOTIFY ERROR] Could not send Telegram message to chat {chat_id}: {type(error).__name__}")


def send_telegram(message: str) -> None:
    """Slot-available notifications go to everyone."""
    _send_to(TELEGRAM_CHAT_IDS, message)


def send_telegram_error(message: str) -> None:
    """Error notifications go only to the primary (first) chat id."""
    primary = TELEGRAM_CHAT_IDS[:1]
    _send_to(primary, message)


def send_telegram_success(message: str) -> None:
    """Success heartbeats go only to the primary (first, admin) chat id."""
    primary = TELEGRAM_CHAT_IDS[:1]
    _send_to(primary, message)


def send_telegram_photo(photo_path: str, caption: str = "") -> None:
    """Not currently called anywhere — wired up for later use, see checker.py."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS:
        print(f"[NOTIFY] (photo) {photo_path}: {caption}")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendPhoto"
    for chat_id in TELEGRAM_CHAT_IDS:
        try:
            with open(photo_path, "rb") as f:
                response = _requests.post(url, data={"chat_id": chat_id, "caption": caption}, files={"photo": f}, timeout=30)
            response.raise_for_status()
        except _requests.RequestException as error:
            print(f"[NOTIFY ERROR] Could not send Telegram photo to chat {chat_id}: {type(error).__name__}")


async def launch_browser(playwright, headless: bool = True) -> tuple[Browser, BrowserContext]:
    proxy_pass = PROXY_PASS
    if proxy_pass and "_session-" not in proxy_pass:
        proxy_pass = f"{proxy_pass}_session-{secrets.token_hex(4)}"
    proxy = {"server": PROXY_SERVER, "username": PROXY_USER, "password": proxy_pass} if PROXY_SERVER else None
    browser = await playwright.chromium.launch(
        headless=headless,
        executable_path=CHROMIUM_PATH,
        args=["--disable-blink-features=AutomationControlled", "--disable-dev-shm-usage", "--disable-gpu"],
        proxy=proxy,
    )
    context = await browser.new_context(
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36",
        extra_http_headers={
            "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
            "sec-ch-ua": '"Google Chrome";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
            "sec-ch-ua-platform": '"macOS"',
            "sec-ch-ua-mobile": "?0",
        },
    )
    await context.add_init_script("""
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'platform', {get: () => 'MacIntel'});
        Object.defineProperty(navigator, 'languages', {get: () => ['es-ES', 'es', 'en']});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        window.chrome = {runtime: {}};
    """)
    return browser, context
