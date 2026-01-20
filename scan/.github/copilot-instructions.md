# Network Scanner & DHCP Manager

## Project Overview
This is a Flask web application for monitoring network hosts and managing DHCP client registrations in a home network environment. It combines DHCP configuration parsing, lease file analysis, and active network scanning using nmap.

## Architecture
- **Main App**: `scanner.py` - Single Flask application handling both web UI and API endpoints
- **Data Sources**: 
  - DHCP client configs (`/etc/dhcp/dhcp_clients.conf`, `/etc/dhcp/dhcp_network_device.conf`)
  - DHCP leases (`/var/lib/dhcp/dhcpd.leases`)
  - Active network scans via nmap
- **IP Ranges**:
  - DHCP pool: `10.1.1.100-250`
  - LAN: `10.1.20.0/24`
  - WiFi: `10.1.30.0/24`

## Key Components
- **Host Discovery**: Combines static DHCP entries, active leases, and nmap scan results
- **Client Registration**: Web form for devices to register/update DHCP entries with password "doksadeo"
- **Network Scanning**: Uses `nmap -sn -T4 --min-parallelism 10 --max-retries 2` for fast host discovery

## Developer Workflows
- **Run App**: `python scanner.py` (listens on 0.0.0.0:5000)
- **DHCP Updates**: Requires sudo access for `systemctl restart isc-dhcp-server`
- **Network Access**: Needs permissions for nmap scanning and ARP table access

## Code Patterns
- **DHCP Parsing**: Use regex `r'host\s+(\S+)\s*{[^}]*fixed-address\s+(\S+);'` to extract hostname-IP pairs
- **MAC Detection**: Query ARP table with `/sbin/arp -n <ip>` for client MAC addresses
- **Hostname Resolution**: `socket.gethostbyaddr(ip)[0]` with fallback to None
- **Error Handling**: File operations use try/except with FileNotFoundError for missing configs

## File Structure
- `scanner.py`: Main application logic
- `templates/index.html`: Host display interface with auto-refresh every 60 seconds
- `templates/index_block.html`: Client registration form
- `static/style.css`: Simple responsive styling
- `cert.pem`/`key.pem`: SSL certificates (currently unused in app.run)

## Security Notes
- Client registration protected by hardcoded password "doksadeo"
- Runs as root or with sudo for DHCP service management
- No authentication for host listing API endpoint

## Dependencies
- flask
- subprocess (built-in)
- re, os, socket (built-in)
- nmap (system package)
- isc-dhcp-server (system service)