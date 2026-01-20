import requests

import config
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

BARRIER_URL = config.BARRIER_STATE_URL

COMMANDS = {}
_last_known_host = None

@dataclass
class Metrics:
    cpu_percent: float = 0.0
    cores: int = 0
    memory_used: float = 0.0
    memory_total: float = 1.0
    swap_used: float = 0.0
    swap_total: float = 1.0
    disks: Dict[str, Dict[str, float]] = field(default_factory=dict)
    processes: List[Dict] = field(default_factory=list)

    def memory_percent(self):
        return 0.0 if self.memory_total == 0 else (self.memory_used / self.memory_total) * 100.0

def fetch_host_info() -> Optional[Tuple[str, str]]:
    try:
        r = requests.get(BARRIER_URL, timeout=config.BARRIER_REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        server = data.get("server", {})
        name = server.get("current")
        ip = server.get("ip")
        if name in config.BARRIER_HOST_IP_OVERRIDES:
            ip = config.BARRIER_HOST_IP_OVERRIDES[name]
       
        if name and ip:
            return (name, ip)
        return None
    except Exception:
        return None

def _update_commands_cache(ip: str):
    global COMMANDS
    try:
        url = f"http://{ip}:{config.METRIX_SERVER_PORT}/command_list"
        r = requests.get(url, timeout=config.COMMANDS_REQUEST_TIMEOUT)
        if r.status_code == 200:
            COMMANDS.update(r.json())
    except Exception:
        pass

def fetch_remote_metrics(ip: str, hostname: str) -> Optional[Metrics]:
    global _last_known_host
    if hostname != _last_known_host:
        _update_commands_cache(ip)
        _last_known_host = hostname

    try:
        url = f"http://{ip}:{config.METRIX_SERVER_PORT}/metrics?host={hostname}"
        r = requests.get(url, timeout=config.METRIX_REQUEST_TIMEOUT)
        r.raise_for_status()
        data = r.json()
        
        m = Metrics()
        cpu = data.get("cpu", {})
        m.cpu_percent = float(cpu.get("usage_percent", 0.0))
        m.cores = cpu.get("cores", 0)
        
        mem = data.get("memory", {})
        m.memory_used = float(mem.get("used", 0.0))
        m.memory_total = float(mem.get("total", 1.0))
        
        swap = data.get("swap", {})
        m.swap_used = float(swap.get("used", 0.0))
        m.swap_total = float(swap.get("total", 1.0))
        
        m.disks = data.get("disks", {})
        m.processes = data.get("processes", [])
        
        return m
    except Exception:
        return None

def send_command_to_server(ip: str, host: str, cmd: str) -> str:
    try:
        url = f"http://{ip}:{config.METRIX_SERVER_PORT}/command"
        payload = {"host": host, "cmd": cmd}
        r = requests.post(url, json=payload, timeout=config.COMMANDS_REQUEST_TIMEOUT)
        try:
            r.raise_for_status()
            resp = r.json() if r.headers.get("Content-Type", "").startswith("application/json") else {"status": "ok"}
            return resp.get("message", "Command sent")
        except Exception:
            return f"HTTP {r.status_code}"
    except Exception as e:
        return str(e)
