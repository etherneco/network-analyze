from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    env_path = Path(__file__).resolve().parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return default


def _get_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except Exception:
        return default


def _parse_kv_map(raw: str) -> dict[str, str]:
    items: dict[str, str] = {}
    if not raw:
        return items
    for part in raw.split(","):
        part = part.strip()
        if not part or "=" not in part:
            continue
        key, value = part.split("=", 1)
        items[key.strip()] = value.strip()
    return items


_load_dotenv()

BARRIER_STATE_URL = os.environ.get("BARRIER_STATE_URL", "http://127.0.0.1:24802/current")
ANALYZER_URL = os.environ.get("ANALYZER_URL", "http://127.0.0.1:24810/analyze")

METRIX_SERVER_HOST = os.environ.get("METRIX_SERVER_HOST", "0.0.0.0")
METRIX_SERVER_PORT = _get_int("METRIX_SERVER_PORT", 28000)

BARRIER_REQUEST_TIMEOUT = _get_float("BARRIER_REQUEST_TIMEOUT", 1.2)
ANALYZER_REQUEST_TIMEOUT = _get_float("ANALYZER_REQUEST_TIMEOUT", 30.0)
RUN_REQUEST_TIMEOUT = _get_float("RUN_REQUEST_TIMEOUT", 1.0)
METRIX_REQUEST_TIMEOUT = _get_float("METRIX_REQUEST_TIMEOUT", 1.5)
COMMANDS_REQUEST_TIMEOUT = _get_float("COMMANDS_REQUEST_TIMEOUT", 2.0)
SCREENSHOT_TIMEOUT = _get_float("SCREENSHOT_TIMEOUT", 3.0)

DASHBOARD_REFRESH_INTERVAL_SEC = _get_float("DASHBOARD_REFRESH_INTERVAL_SEC", 2.0)
LIVE_SCREEN_REFRESH_MS = _get_int("LIVE_SCREEN_REFRESH_MS", 10000)

BARRIER_HOST_IP_OVERRIDES = _parse_kv_map(os.environ.get("BARRIER_HOST_IP_OVERRIDES", ""))
