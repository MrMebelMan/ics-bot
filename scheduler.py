#!/usr/bin/env python3
import random
import subprocess
import sys
import time
from datetime import datetime, timedelta

MORNING_START, MORNING_END = 6, 15
FAST_WEEKDAYS = (3, 4)  # Thursday, Friday (Monday=0) — new slots tend to drop these days
DEFAULT_INTERVAL_MIN = 30
FAST_MORNING_INTERVAL_MIN = 15
FAST_RETRY_MIN_MINUTES, FAST_RETRY_MAX_MINUTES = 4, 7
MAX_CONSECUTIVE_FAST_RETRIES = 6


def next_delay_seconds(now: datetime) -> float:
    is_fast_morning = now.weekday() in FAST_WEEKDAYS and MORNING_START <= now.hour < MORNING_END
    base_minutes = FAST_MORNING_INTERVAL_MIN if is_fast_morning else DEFAULT_INTERVAL_MIN
    jitter = base_minutes * 0.1
    return random.uniform(base_minutes - jitter, base_minutes + jitter) * 60


def main() -> None:
    consecutive_failures = 0
    while True:
        now = datetime.now()
        print(f"[{now.isoformat(timespec='seconds')}] Running checker.py --headless")
        try:
            result = subprocess.run([sys.executable, "checker.py", "--headless"], timeout=300)
            site_unavailable = result.returncode != 0
        except subprocess.TimeoutExpired:
            print("ERROR: checker.py hung past 300s, killed.")
            site_unavailable = True

        if site_unavailable:
            consecutive_failures += 1
        else:
            consecutive_failures = 0

        if site_unavailable and consecutive_failures <= MAX_CONSECUTIVE_FAST_RETRIES:
            delay = random.uniform(FAST_RETRY_MIN_MINUTES, FAST_RETRY_MAX_MINUTES) * 60
            print(f"Site unavailable ({consecutive_failures}/{MAX_CONSECUTIVE_FAST_RETRIES}) — retrying in {delay / 60:.1f}m instead of the normal schedule.")
        else:
            if site_unavailable:
                print(f"Site still unavailable after {MAX_CONSECUTIVE_FAST_RETRIES} fast retries — falling back to the normal schedule.")
            delay = next_delay_seconds(datetime.now())

        next_run = datetime.now() + timedelta(seconds=delay)
        print(f"Next run at {next_run.isoformat(timespec='seconds')} ({delay / 60:.1f}m from now)\n")

        try:
            time.sleep(delay)
        except KeyboardInterrupt:
            print("Stopped.")
            break


if __name__ == "__main__":
    main()
