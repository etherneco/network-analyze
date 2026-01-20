#!/usr/bin/env python3

import sys
import requests

import config


def die(msg):
    sys.exit(f"[run.py] {msg}")


def main():
    # Step 1: fetch current screen from Barrier
    try:
        r = requests.get(config.BARRIER_STATE_URL, timeout=config.RUN_REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        die(f"Barrier state error: {e}")

    server = data.get("server", {})
    screen = server.get("current")
    screen_ip = server.get("ip")

    if not screen or not screen_ip:
        die("Invalid barrier payload")

    # Step 2: send minimal context to analyzer
    payload = {
        "screen_name": screen,
        "ip_actual_screen": screen_ip,
    }

    try:
        requests.post(
            config.ANALYZER_URL,
            json=payload,
            timeout=config.RUN_REQUEST_TIMEOUT,
        )
    except Exception as e:
        die(f"Analyzer error: {e}")


if __name__ == "__main__":
    main()