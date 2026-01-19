# Network Analyze

## Overview
Network Analyze is a practical network discovery and analysis toolkit designed for real-world, multi-host environments.

The project focuses on **understanding, visibility and structure of local networks**, especially in setups that are long-running, virtualised and heterogeneous rather than clean, short-lived labs.

It is built from real operational needs, not as a theoretical network scanner.

---

## Context
The project originated from a working environment that includes:
- Proxmox as a central virtualisation platform
- multiple physical hosts and virtual machines
- mixed operating systems (Linux, Windows Server via RDP)
- several active subnets (e.g. `10.x`, `192.168.x`)
- multi-host workflows supported by tools such as Barrier

In such environments, it quickly becomes difficult to answer simple questions:
- what hosts are actually alive
- which network they belong to
- how they relate to each other
- which machines matter for daily work

---

## Problem Statement
Traditional network tools tend to provide:
- raw scan results
- flat lists of IP addresses
- limited contextual information

This is often insufficient for environments that evolve over time and are actively used for development, testing and operations.

Network Analyze aims to add **context and structure**, not just data.

---

## Core Concept
