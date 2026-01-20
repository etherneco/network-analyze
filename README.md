# Network Analyze

## Executive Summary
Network Analyze is a practical toolkit for visibility and control in multi-host networks. It connects live system metrics, network discovery, and lightweight remote actions into a single operational view. The focus is real infrastructure: mixed OS fleets, long-running services, and multiple subnets.

## What It Solves
- Consolidates host status, resource usage, and network context in one place.
- Reduces manual steps when you need to identify the active host and react fast.
- Adds structure to noisy network data by enriching it with DHCP and host metadata.

## Key Capabilities
- Live system metrics from agents (CPU, memory, disks, top processes).
- Screenshot capture for quick visual confirmation of active screens.
- Network discovery using DHCP lease parsing plus subnet scans.
- Remote command dispatch from a central dashboard.
- Global hotkey to send a minimal context payload to an analyzer service.

## Architecture Overview
- `metrix_server.py`: lightweight agent (Flask) exposing metrics, screenshots, command execution, clipboard, and hotkey trigger.
- `dashboard/`: PyQt6 desktop dashboard for live monitoring and control.
- `scan/`: Flask app for subnet discovery, DHCP-aware hostname resolution, and host registration.
- `run.py`: minimal helper that forwards Barrier state to the analyzer.

## Configuration
- All runtime settings are in `.env` (URLs, ports, timeouts, scan ranges, DHCP paths).
- A sample template is provided in `.env.example`.
- Sensitive values (e.g. registration password) belong in `.env` only.

## Why This Is Useful in Production
- Designed for hybrid environments (VMs + physical hosts + mixed OS).
- Focused on operational visibility and faster incident response.
- Minimal dependencies; deployable as a small agent + dashboard.

## Tech Stack
- Python, Flask, PyQt6
- psutil, requests, mss, Pillow
- Optional: nmap on hosts running `scan/`
