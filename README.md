# AirManager (Ubiquiti Network Manager) — v1.0

Multi-subnet **Ubiquiti airOS 8** network discovery and connected client management platform built for **LiteAP GPS** access points and **NanoStation Loco 5AC** client stations, engineered for native bare-metal deployment on **Ubuntu (no Docker)**.

---

## Key Architecture & Specification Documents

- **[SPECIFICATION.md](file:///Users/ahmedadil/Downloads/untitled%20folder/ubiquiti/SPECIFICATION.md)**: Complete Version 1.0 Implementation Specification (Hybrid multi-subnet discovery engine, PostgreSQL schema, FastAPI contracts, Linux agent protocol, UI architecture, and Ubuntu systemd deployment).
- **[AGENT_TASKS.md](file:///Users/ahmedadil/Downloads/untitled%20folder/ubiquiti/AGENT_TASKS.md)**: Phased engineering task breakdown and acceptance criteria.
- **[deploy/sql/001_initial_schema.sql](file:///Users/ahmedadil/Downloads/untitled%20folder/ubiquiti/deploy/sql/001_initial_schema.sql)**: PostgreSQL 16 DDL schema (`credential_profiles`, `subnets`, `routers`, `devices`, `device_ip_history`, `wireless_clients`, `device_metrics`, `agent_tasks`).

---

## Repository Structure

- `backend/` — FastAPI Central Backend, MAC-based IP reconciliation engine, Fernet credential vault, and simulated multi-subnet WISP seeder.
- `agent/` — Linux Multi-Subnet Network Agent (`RoutedSubnetScanner`, `AirOS8Client` for `/api/auth`, `/status.cgi`, `/sta.cgi`, `/kick.cgi`, `/cfg.cgi`, `/reboot.cgi`, and Ubiquiti EdgeOS/UISP ARP & DHCP lease adapters).
- `frontend/` — Next.js + TypeScript Operator Console prioritizing **Connected Client Management** (`/clients`), plus standalone zero-dependency preview server (`frontend/server.mjs`).
- `deploy/` — Native Ubuntu `systemd` unit files (`airmanager-api.service`, `airmanager-agent.service`, `airmanager-web.service`), Nginx config (`airmanager.conf`), and bare-metal installer (`install.sh`).

---

## Running Locally (Zero-Config Demo & Test Mode)

1. **Run Automated Test Suites**:
   ```bash
   python3 backend/tests/test_api.py -v
   python3 agent/tests/test_agent.py -v
   ```

2. **Start the Backend API Server** (ports `8000`, auto-seeds 3 routed subnets, 2 Ubiquiti routers, 4 LiteAP GPS sectors, and 36 Loco 5AC clients):
   ```bash
   cd backend && python3 -m app.main
   ```

3. **Start the Operator Console UI** (port `3000`):
   ```bash
   # With Next.js (if node_modules installed):
   cd frontend && npm run dev

   # Or immediately with the standalone zero-dependency server:
   node frontend/server.mjs
   ```
   Then open `http://127.0.0.1:3000`.
