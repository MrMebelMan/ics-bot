#!/usr/bin/env python3
"""Reply to /start with the sender's Telegram user and chat IDs."""

import os
import time
from typing import Any

import requests
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
POLL_TIMEOUT = 30


def telegram_request(method: str, **payload: Any) -> Any:
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}"

    try:
        response = requests.post(url, json=payload, timeout=POLL_TIMEOUT + 10)
    except requests.RequestException as error:
        raise RuntimeError(f"Telegram request failed: {type(error).__name__}") from None

    if not response.ok:
        raise RuntimeError(f"Telegram returned HTTP {response.status_code}")

    data = response.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram rejected {method}: {data.get('description', 'unknown error')}")

    return data["result"]


def start_reply(message: dict[str, Any]) -> None:
    sender = message.get("from")
    chat = message.get("chat")
    if not sender or not chat:
        return

    user_id = sender["id"]
    chat_id = chat["id"]
    reply = f"Your Telegram user ID is: {user_id}"
    if chat_id != user_id:
        reply += f"\nThis chat's ID is: {chat_id}"

    telegram_request("sendMessage", chat_id=chat_id, text=reply)
    print(f"Replied to Telegram user {user_id}")


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set in .env")

    bot = telegram_request("getMe")
    print(f"Listening for /start as @{bot.get('username', bot['id'])}. Press Ctrl+C to stop.")

    offset = None
    while True:
        try:
            poll_parameters: dict[str, Any] = {
                "timeout": POLL_TIMEOUT,
                "allowed_updates": ["message"],
            }
            if offset is not None:
                poll_parameters["offset"] = offset

            updates = telegram_request("getUpdates", **poll_parameters)

            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message", {})
                command = message.get("text", "").split(maxsplit=1)[0].split("@", maxsplit=1)[0].lower()
                if command == "/start":
                    start_reply(message)
        except RuntimeError as error:
            print(f"{error}; retrying in 3 seconds")
            time.sleep(3)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
