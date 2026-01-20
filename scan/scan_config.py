from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)


def _get_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except Exception:
        return default


_load_dotenv()

SCAN_DHCP_RANGE = os.environ.get("SCAN_DHCP_RANGE", "10.1.1.100-250")
SCAN_LAN_RANGE = os.environ.get("SCAN_LAN_RANGE", "10.1.20.0/24")
SCAN_WIFI_RANGE = os.environ.get("SCAN_WIFI_RANGE", "10.1.30.0/24")

SCAN_DHCP_LEASES = os.environ.get("SCAN_DHCP_LEASES", "/var/lib/dhcp/dhcpd.leases")
SCAN_DHCP_CONF_CLIENT = os.environ.get("SCAN_DHCP_CONF_CLIENT", "/etc/dhcp/dhcp_clients.conf")
SCAN_DHCP_CONF_NETWORK_DEVICE = os.environ.get(
    "SCAN_DHCP_CONF_NETWORK_DEVICE",
    "/etc/dhcp/dhcp_network_device.conf",
)

SCAN_REGISTER_PASSWORD = os.environ.get("SCAN_REGISTER_PASSWORD", "")
SCAN_HOST = os.environ.get("SCAN_HOST", "0.0.0.0")
SCAN_PORT = _get_int("SCAN_PORT", 5000)
