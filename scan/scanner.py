from flask import Flask, jsonify, render_template, request
import subprocess
import re
import socket
import sys
from pathlib import Path

SCAN_DIR = Path(__file__).resolve().parent
if str(SCAN_DIR) not in sys.path:
    sys.path.insert(0, str(SCAN_DIR))

import scan_config as config

app = Flask(__name__)

# --------------------------------------------------
# BASIC UTILS
# --------------------------------------------------
def read_file(path):
    try:
        with open(path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def get_mac(ip):
    try:
        out = subprocess.check_output(["/sbin/arp", "-n", ip]).decode()
        for line in out.splitlines():
            if ip in line:
                return line.split()[2]
    except Exception:
        pass
    return "N/A"


def get_reverse_dns(ip):
    try:
        return socket.gethostbyaddr(ip)[0]
    except Exception:
        return None

# --------------------------------------------------
# DHCP LEASES — NAJWAŻNIEJSZE
# --------------------------------------------------
def parse_dhcp_leases():
    """
    ZAWSZE bierze NAJNOWSZY lease w pliku
    """
    leases = {}
    content = read_file(config.SCAN_DHCP_LEASES)

    blocks = re.findall(
        r'lease\s+(\S+)\s*{([^}]*)}',
        content,
        re.DOTALL
    )

    for ip, block in blocks:
        m = re.search(r'client-hostname\s+"([^"]+)"', block)
        if m:
            hostname = m.group(1).strip()
            if hostname:
                leases[ip] = hostname  # ostatni = aktualny

    return leases

# --------------------------------------------------
# DHCP CONFIG (statyczne)
# --------------------------------------------------
def parse_dhcp_config():
    hosts = []
    content = read_file(config.SCAN_DHCP_CONF_CLIENT) + read_file(config.SCAN_DHCP_CONF_NETWORK_DEVICE)

    matches = re.findall(
        r'host\s+(\S+)\s*{[^}]*fixed-address\s+([\d.]+);',
        content,
        re.DOTALL
    )

    for hostname, ip in matches:
        if ip.startswith(("10.1.20.", "10.1.30.")):
            hosts.append({
                "hostname": hostname.strip(),
                "ip": ip.strip()
            })

    return hosts

# --------------------------------------------------
# NETWORK SCAN (TYLKO status + MAC)
# --------------------------------------------------
def scan_network(subnet):
    hosts = {}
    cmd = ['nmap', '-sn', '-T4', '--max-retries', '2', subnet]

    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        current_ip = None

        for line in res.stdout.splitlines():
            if "Nmap scan report for" in line:
                current_ip = line.split()[-1].strip("()")
                hosts[current_ip] = {"status": "online", "mac": "N/A"}

            elif "MAC Address:" in line and current_ip:
                hosts[current_ip]["mac"] = line.split("MAC Address: ")[1].split()[0]

    except Exception:
        pass

    return hosts

# --------------------------------------------------
# HOSTNAME RESOLUTION — JEDNO MIEJSCE
# --------------------------------------------------
def resolve_hostname(ip, lease_hosts, static_hosts, seen):
    """
    1. DHCP LEASE
    2. DHCP CONF
    3. reverse DNS
    4. fallback host-x-x-x-x
    """

    # 1. lease
    if ip in lease_hosts:
        hostname = lease_hosts[ip]

    # 2. static dhcp
    elif ip in static_hosts:
        hostname = static_hosts[ip]

    # 3. reverse dns
    else:
        hostname = get_reverse_dns(ip)

    # 4. fallback
    if not hostname or hostname.lower() == "for":
        hostname = f"host-{ip.replace('.', '-')}"

    # unikalność
    base = hostname
    i = 2
    while hostname in seen:
        hostname = f"{base}-{i}"
        i += 1

    seen.add(hostname)
    return hostname

# --------------------------------------------------
# AGGREGATOR
# --------------------------------------------------
def get_host_info():
    lease_hosts = parse_dhcp_leases()
    static_cfg = parse_dhcp_config()

    static_hosts = {h["ip"]: h["hostname"] for h in static_cfg}

    active = {}
    active.update(scan_network(config.SCAN_DHCP_RANGE))
    active.update(scan_network(config.SCAN_LAN_RANGE))
    active.update(scan_network(config.SCAN_WIFI_RANGE))

    seen = set()
    result = {}

    # wszystkie IP jakie znamy
    all_ips = set(lease_hosts) | set(static_hosts) | set(active)

    for ip in sorted(all_ips, key=lambda x: list(map(int, x.split(".")))):
        hostname = resolve_hostname(ip, lease_hosts, static_hosts, seen)

        result[ip] = {
            "hostname": hostname,
            "ip": ip,
            "status": "online" if ip in active else "offline",
            "mac": active.get(ip, {}).get("mac", "N/A"),
            "disk": "N/A",
            "ram": "N/A",
            "source": (
                "DHCP" if ip in lease_hosts else
                "LAN" if ip.startswith("10.1.20.") else
                "WiFi" if ip.startswith("10.1.30.") else
                "UNKNOWN"
            )
        }

    return list(result.values())

# --------------------------------------------------
# DHCP UPDATE
# --------------------------------------------------
def update_dhcp_entry(hostname, mac, iface_octet, client_id):
    content = read_file(config.SCAN_DHCP_CONF_CLIENT)
    ip = f"10.1.{iface_octet}.{client_id}"

    pattern = re.compile(r"host\s+(\S+)\s*{[^}]*}", re.DOTALL)
    new = []
    updated = False

    for m in pattern.finditer(content):
        entry = m.group(0)
        if mac in entry or ip in entry:
            new.append(
                f"host {hostname} {{\n"
                f"    hardware ethernet {mac};\n"
                f"    fixed-address {ip};\n"
                f"}}\n"
            )
            updated = True
        else:
            new.append(entry)

    if not updated:
        new.append(
            f"host {hostname} {{\n"
            f"    hardware ethernet {mac};\n"
            f"    fixed-address {ip};\n"
            f"}}\n"
        )

    with open(config.SCAN_DHCP_CONF_CLIENT, "w") as f:
        f.write("\n".join(new))

# --------------------------------------------------
# ROUTES
# --------------------------------------------------
@app.route("/")
def index_block():
    ip = request.remote_addr
    return render_template(
        "index_block.html",
        client_ip=ip,
        client_mac=get_mac(ip),
        client_id=ip.split(".")[-1],
        detected_hostname=get_reverse_dns(ip) or ""
    )


@app.route("/display")
def display():
    return render_template("index.html")


@app.route("/api/hosts")
def api_hosts():
    return jsonify({"hosts": get_host_info()})


@app.route("/", methods=["POST"])
def register_host():
    if not config.SCAN_REGISTER_PASSWORD:
        return "Server misconfigured", 500
    if request.form.get("password") != config.SCAN_REGISTER_PASSWORD:
        return "Invalid password", 403

    iface_map = {"LAN": 20, "WiFi": 30, "VPN": 40}
    iface = iface_map.get(request.form.get("interface"), 20)

    update_dhcp_entry(
        request.form.get("hostname"),
        get_mac(request.remote_addr),
        iface,
        request.form.get("client_id")
    )

    subprocess.run(["sudo", "systemctl", "restart", "isc-dhcp-server"])
    return "OK"

# --------------------------------------------------
if __name__ == "__main__":
    app.run(host=config.SCAN_HOST, port=config.SCAN_PORT)
