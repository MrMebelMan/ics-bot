#!/usr/bin/env python3
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta

MORNING_START, MORNING_END = 6, 12
NIGHT_START, NIGHT_END = 22, 6
FAST_RETRY_WEEKDAYS = (3, 4)  # Thursday, Friday (Monday=0) — new slots tend to drop these days
FAST_RETRY_SECONDS = 5 * 60


def next_delay_seconds(now: datetime) -> float:
    hour = now.hour
    if MORNING_START <= hour < MORNING_END:
        low, high = 0.5, 1.5
    elif hour >= NIGHT_START or hour < NIGHT_END:
        low, high = 2.0, 3.0
    else:
        low, high = 1.0, 3.0
    return random.uniform(low, high) * 3600


def main() -> None:
    while True:
        now = datetime.now()
        print(f"[{now.isoformat(timespec='seconds')}] Running checker.py --headless")
        try:
            result = subprocess.run([sys.executable, "checker.py", "--headless"], timeout=300)
            site_unavailable = result.returncode != 0
        except subprocess.TimeoutExpired:
            print("ERROR: checker.py hung past 300s, killed.")
            site_unavailable = True

        if site_unavailable and datetime.now().weekday() in FAST_RETRY_WEEKDAYS:
            delay = FAST_RETRY_SECONDS
            print(f"Site unavailable on a fast-retry day — retrying in {delay // 60:.0f}m instead of the normal schedule.")
        else:
            delay = next_delay_seconds(datetime.now())

        next_run = datetime.now() + timedelta(seconds=delay)
        print(f"Next run at {next_run.isoformat(timespec='seconds')} ({delay / 3600:.2f}h from now)\n")

        try:
            time.sleep(delay)
        except KeyboardInterrupt:
            print("Stopped.")
            break


if __name__ == "__main__":
    main()
