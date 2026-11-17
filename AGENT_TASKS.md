# AirManager — Coding Agent Implementation Task File

This file provides sequential, self-contained engineering tasks to build, test, and deploy **AirManager v1.0** from scratch.

---

## Task 1: Database Schema & Backend Core (`backend/`)
- **Objective**: Set up the FastAPI backend, SQLAlchemy 2.0 ORM models, Fernet credential encryption, and database initialization/migrations.
- **Files to Create**:
  - `deploy/sql/001_initial_schema.sql`
  - `backend/pyproject.toml` & `backend/requirements.txt`
  - `backend/app/core/config.py`
  - `backend/app/core/security.py`
  - `backend/app/db/session.py`
  - `backend/app/models/models.py`
  - `backend/app/schemas/schemas.py`
- **Acceptance Criteria**:
  - Models cover `CredentialProfile`, `Subnet`, `Router`, `Device`, `DeviceIpHistory`, `WirelessClient`, `DeviceMetric`, and `AgentTask`.
  - Passwords are encrypted before database persistence and never returned in plaintext in public REST responses.

## Task 2: Backend Services, MAC-to-IP Reconciliation & REST API (`backend/app/api/`)
- **Objective**: Implement all frontend REST endpoints and internal Linux Agent protocol endpoints, plus automatic MAC-based IP reconciliation and realistic simulator seeding.
- **Files to Create**:
  - `backend/app/services/reconciliation.py`
  - `backend/app/services/seeder.py`
  - `backend/app/api/v1/agent.py`
  - `backend/app/api/v1/clients.py`
  - `backend/app/api/v1/devices.py`
  - `backend/app/api/v1/discovery.py`
  - `backend/app/api/v1/dashboard.py`
  - `backend/app/main.py`
- **Acceptance Criteria**:
  - When a known `mac_address` reports from a new `current_ip`, `devices.current_ip` updates and `device_ip_history` records the transition.
  - Client actions (`kick`, `acl`, `reboot`, `probe`) create `agent_tasks` and update state accurately.

## Task 3: Linux Multi-Subnet Network Agent (`agent/`)
- **Objective**: Build the async Linux daemon that scans routed CIDRs, authenticates to airOS 8 (`LiteAP GPS` & `Loco 5AC`), queries Ubiquiti routers for ARP/DHCP leases, polls `/status.cgi` and `/sta.cgi`, and executes client management actions.
- **Files to Create**:
  - `agent/pyproject.toml` & `agent/requirements.txt`
  - `agent/airmanager_agent/config.py`
  - `agent/airmanager_agent/scanner/cidr_scanner.py`
  - `agent/airmanager_agent/airos/client.py`
  - `agent/airmanager_agent/airos/simulator.py`
  - `agent/airmanager_agent/routers/ubiquiti.py`
  - `agent/airmanager_agent/poller/scheduler.py`
  - `agent/airmanager_agent/main.py`
- **Acceptance Criteria**:
  - Bounded-concurrency TCP port 443/80 CIDR scanner works across multiple `/24` subnets without broadcast traffic.
  - `airos/client.py` implements airOS 8 session login, `/status.cgi` parsing, `/sta.cgi` station parsing, station kick, MAC ACL update, and reboot.
  - `routers/ubiquiti.py` parses EdgeOS `show arp` / `show dhcp leases` and UISP/UniFi neighbor responses.

## Task 4: Next.js + TypeScript Operator Console (`frontend/`)
- **Objective**: Build the responsive web application prioritizing Connected Client Management across sectors and routed subnets.
- **Files to Create**:
  - `frontend/src/lib/types.ts` & `frontend/src/lib/api.ts`
  - `frontend/src/components/AppShell.tsx`
  - `frontend/src/components/ClientDetailDrawer.tsx`
  - `frontend/src/app/page.tsx` (Overview Dashboard)
  - `frontend/src/app/clients/page.tsx` (Connected Clients Manager)
  - `frontend/src/app/devices/page.tsx` (LiteAP GPS & Loco 5AC Inventory + IP History)
  - `frontend/src/app/discovery/page.tsx` (Routed Subnets, Ubiquiti Routers & Credentials)
  - `frontend/src/app/tasks/page.tsx` (Agent Task Queue & Audit Log)
- **Acceptance Criteria**:
  - Operators can filter connected `Loco 5AC` clients by sector, weak signal (`< -75 dBm`), chain imbalance (`>= 5 dB`), low airMAX capacity, or ACL block status.
  - Operators can kick/reconnect a station, block/unblock its MAC, reboot the remote CPE, or trigger an on-demand probe with instant UI feedback.

## Task 5: Ubuntu Bare-Metal Deployment & Automated Test Suites (`deploy/`, `tests/`)
- **Objective**: Provide production `systemd` units, Nginx config, Ubuntu installer script, and comprehensive automated tests for backend, agent, and frontend.
- **Files to Create**:
  - `deploy/systemd/airmanager-api.service`
  - `deploy/systemd/airmanager-agent.service`
  - `deploy/systemd/airmanager-web.service`
  - `deploy/nginx/airmanager.conf`
  - `deploy/install.sh`
  - `backend/tests/test_api.py`
  - `agent/tests/test_agent.py`
- **Acceptance Criteria**:
  - All backend and agent tests pass under `pytest`.
  - Next.js frontend compiles cleanly (`npm run build`) with zero TypeScript errors.
