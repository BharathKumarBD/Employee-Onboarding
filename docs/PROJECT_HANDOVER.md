# OnboardAI (Employee-Onboarding) — Master Project Handover & Technical Specification

---

## 1. Executive Summary & Project Purpose

### What OnboardAI Does
**OnboardAI** is an enterprise-grade autonomous AI onboarding assistant designed to streamline and automate the entire onboarding experience for newly hired employees at Dayforce.

Instead of acting as a passive question-answering bot, OnboardAI operates as a **proactive, multi-agent workflow system** capable of:
1. **Factual Policy Retrieval (RAG)**: Answering questions on company handbooks, IT security, benefits, code of conduct, and office facilities while providing exact Markdown source citations.
2. **Autonomous Workflow Execution**: Creating, listing, and tracking mandatory onboarding tasks for new hires across HR, IT, and Team categories.
3. **Check-in Scheduling**: Booking manager 1:1s and HR milestone reviews on specific calendar days.
4. **Equipment Allocation**: Managing laptop, access badge, and hardware accessory provisioning requests.
5. **Mandatory Training Management**: Tracking regulatory compliance courses (GDPR, Security, Code of Conduct).
6. **Location-Specific Policy Intelligence**: Dynamically tailoring responses, holidays, statutory benefits, and compliance requirements based on the employee's work location (e.g., India, USA, Finland).
7. **Enterprise Security & Defense-in-Depth**: Protecting internal systems against prompt injection, data exfiltration, unauthorized administrative actions, and task spamming.

---

## 2. System Architecture

The project employs a modern microservices architecture with a reactive, decoupled design.

```mermaid
flowchart TD
    User([Employee / Admin]) --> FE[React 19 + TypeScript + Tailwind Frontend]
    FE -->|SSE Streams / REST API| Nginx[Nginx Reverse Proxy]
    Nginx --> BE[FastAPI Backend :8000]
    
    subgraph MultiAgentSystem [LangGraph Multi-Agent Orchestration]
        SecurityGate[Prompt-Injection & Rate-Limit Filter]
        Orchestrator[Orchestrator Agent / RoutePlan]
        ResearchAgent[Research Agent - ReAct]
        WorkflowAgent[Workflow Agent - ReAct]
        Synthesizer[Synthesizer Agent]
        
        SecurityGate --> Orchestrator
        Orchestrator -->|needs_research| ResearchAgent
        Orchestrator -->|needs_workflow| WorkflowAgent
        ResearchAgent --> Synthesizer
        WorkflowAgent --> Synthesizer
    end
    
    BE --> SecurityGate
    
    ResearchAgent --> RAG[(ChromaDB Vector Store / Seed Data)]
    WorkflowAgent --> DB[(PostgreSQL 16 Database)]
    
    subgraph ExternalMCP [FastMCP Integration]
        MCP[FastMCP Server :server.py] --> DB
        MCP --> RAG
    end
```

### Component Breakdown

| Tier | Component | Location | Responsibility |
|---|---|---|---|
| **Frontend** | React 19, Vite, Tailwind CSS 4 | `/frontend` | Chat interface with live token streaming, agent thought inspection, interactive task completion checklist, and admin dashboards. |
| **Backend API** | FastAPI, Uvicorn, SSE-Starlette | `/backend/app/main.py` | Exposes REST endpoints, Server-Sent Events (SSE) streaming, input sanitization, rate limiting, and RBAC authentication. |
| **Auth & Security** | PBKDF2-HMAC-SHA256 & Session Tokens | `/shared/auth.py` | Salting and password hashing, tamper-proof bearer tokens, employee IDOR authorization, admin role enforcement. |
| **Agent Engine** | LangGraph, LangChain-Core | `/backend/agent/multi_agent.py` | 4-node directed acyclic graph (`StateGraph`) with structured JSON routing and autonomous specialist execution. |
| **RAG Engine** | ChromaDB, Regex Chunking | `/shared/rag.py` | Markdown chunking, vector embeddings, similarity search, and high-resilience fallback search. |
| **Database** | PostgreSQL 16 (`psycopg3`) | `/shared/db.py` | Relational persistence for users, tasks, check-ins, equipment requests, trainings, employee assignments, and audit logs. |
| **MCP Server** | FastMCP Protocol | `/mcp-server/server.py` | Exposes all onboarding tools over standard input/output for external AI coding tools (e.g., Cursor, Claude Desktop). |

---

## 3. Architecture & Security Improvements

### Task 1: Real Employee Authentication & Server-Side Authorization (IDOR Prevention)
- **PBKDF2 Password Hashing**: Passwords stored using salted PBKDF2-HMAC-SHA256 (100,000 iterations) using Python standard library without unsafe external dependencies.
- **Tamper-Proof Session Tokens**: HMAC-SHA256 signed bearer tokens with expiration timestamps (`sub`, `role`, `iat`, `exp`).
- **Server-Side Authorization**: `require_employee_access()` strictly ensures that authenticated employees can only query or modify their own onboarding tasks, equipment, trainings, or check-ins. Cross-employee snooping or modification (IDOR) immediately returns `403 Forbidden`.
- **Role-Based Access Control (RBAC)**: Administrator endpoints (`/api/admin/*`, reset, equipment approval) require `role: admin` or valid `X-Admin-Key`.

### Task 2: Additional Employee Onboarding Automation & Sensitive Action Approvals
- **Equipment Provisioning & IT Approval**: Added `equipment_allocations` table and tools (`get_equipment_status_tool`, `request_equipment_tool`). Equipment requests default to `'pending'` status, requiring IT Admin review via `POST /api/admin/equipment/{id}/status` before moving to `'allocated'` or `'delivered'`.
- **Compliance Training Management**: Implemented `training_assignments` table with 6 built-in courses (Security Awareness, Code of Conduct, GDPR, IT Security, Benefits, Safety) with automatic onboarding assignment via `list_training_assignments_tool` and `assign_training_tool`.
- **Manager & Buddy Tracking**: Automated tracking of direct managers and onboarding buddies via `shared/assignments.py`.
- **Full Task Lifecycle**: Added progress tracking (`get_onboarding_status_tool`) and marking tasks complete (`complete_onboarding_task_tool`).

### Task 3: Simulated vs Real External Integrations
To maintain zero-dependency local demonstrability without requiring external enterprise subscriptions, external enterprise services are cleanly architected as database-backed simulated integrations:
- **IT Hardware Procurement**: Simulated via `equipment_allocations` table and approval lifecycle (ready for plug-and-play webhook integration with ServiceNow / Jira Service Management).
- **Learning Management System (LMS)**: Simulated via `training_assignments` table (ready for SCORM / Workday Learning API connectors).
- **Human Resources Information System (HRIS)**: Simulated via `employee_assignments` table (ready for BambooHR / Workday REST sync).

### Task 4: Fix of the Six Baseline Evaluation Failures
1. **`slack_channels`**: Orchestrator prompt re-routed to search `it-setup.md` for official channels (`#general`, `#team-*`, `#random`).
2. **`schedule_checkin`**: Disambiguated `schedule_checkin_tool` docstrings and added orchestrator rules prioritizing check-in booking over task creation.
3. **`headquarters_location`**: Enriched office location search triggers, ensuring retrieval of the Helsinki headquarters from `employee-handbook.md`.
4. **`it_helpdesk`**: Routed technical assistance to research mode to extract `it-help@dayforce.com` and `#it-support` SLA details.
5. **`remote_policy_and_first_week`**: Mandated creation of $\ge 3$ tasks when employees query first-week plans.
6. **`onboarding_buddy`**: Explicitly separated buddy meeting timing (retrieved from `onboarding-checklist.md`) from contact lookups.

### Task 5: Location-Specific Intelligence
- **India (`seed-data/location-india.md`)**: National holidays (Republic Day, Independence Day, Gandhi Jayanti, Diwali), statutory benefits (EPF 12%, ESIC, Gratuity, Professional Tax), leave rules (EL/SL/CL/Maternity/Paternity), and onboarding compliance (PAN, Aadhaar, Form 2).
- **USA (`seed-data/location-usa.md`)**: Federal holidays, 401(k) matching (4% match, 4-year vesting), PPO healthcare/HSA plans, and mandatory I-9 compliance within 3 business days.
- **RAG Integration**: Created `search_handbook_with_location()` to prioritize location-matched metadata.

---

## 4. Database Schema Specification

All tables reside in PostgreSQL and are initialized automatically on backend startup via `shared/db.py`:

```sql
-- 1. Onboarding Tasks Table
CREATE TABLE IF NOT EXISTS onboarding_tasks (
    id SERIAL PRIMARY KEY,
    employee_id TEXT NOT NULL,
    title TEXT NOT NULL,
    due_day INTEGER NOT NULL,
    category TEXT NOT NULL,             -- HR, IT, or Team
    status TEXT NOT NULL DEFAULT 'pending', -- pending, completed
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 2. Manager and HR Check-ins Table
CREATE TABLE IF NOT EXISTS checkins (
    id SERIAL PRIMARY KEY,
    employee_id TEXT NOT NULL,
    day INTEGER NOT NULL,
    topic TEXT NOT NULL,
    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 3. Hardware & Equipment Allocations Table
CREATE TABLE IF NOT EXISTS equipment_allocations (
    id SERIAL PRIMARY KEY,
    employee_id TEXT NOT NULL,
    item_type TEXT NOT NULL,            -- laptop, id_card, monitor, etc.
    item_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, allocated, delivered
    allocated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 4. Mandatory Training Assignments Table
CREATE TABLE IF NOT EXISTS training_assignments (
    id SERIAL PRIMARY KEY,
    employee_id TEXT NOT NULL,
    training_name TEXT NOT NULL,
    due_day INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', -- pending, completed
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5. Employee Manager & Buddy Assignments Table
CREATE TABLE IF NOT EXISTS employee_assignments (
    id SERIAL PRIMARY KEY,
    employee_id TEXT NOT NULL UNIQUE,
    manager_name TEXT,
    manager_email TEXT,
    buddy_name TEXT,
    buddy_email TEXT,
    location TEXT DEFAULT 'finland',
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6. System Users & Credentials Table
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'employee', -- 'employee' or 'admin'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 7. System Audit Logs Table
CREATE TABLE IF NOT EXISTS audit_logs (
    id SERIAL PRIMARY KEY,
    action TEXT NOT NULL,
    employee_id TEXT,
    performed_by TEXT DEFAULT 'system',
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## 5. API Reference & Contract

Interactive Swagger documentation is available at `http://localhost:8000/docs`. The complete static schema is stored in `docs/openapi.json`.

### Core Endpoints

| Method | Endpoint | Auth | Purpose |
|---|---|---|---|
| `GET` | `/health` | None | Service liveness probe. |
| `POST` | `/api/auth/login` | None | Authenticates user/admin and issues signed bearer session token. |
| `GET` | `/api/auth/me` | Bearer Token | Returns claims (`sub`, `role`) of the authenticated user. |
| `POST` | `/api/chat` | Optional Token | Synchronous conversation endpoint (authorized for matching employee). |
| `POST` | `/api/chat/stream` | Optional Token | Real-time Server-Sent Events (SSE) streaming chat. |
| `GET` | `/api/employee/demo` | None | Returns active user profile (name, role, location, manager). |
| `GET` | `/api/onboarding/{id}/status` | Employee / Admin | Summary of task completion count and percentage (IDOR-protected). |
| `POST` | `/api/onboarding/{id}/tasks/{taskId}/complete` | Employee / Admin | Marks an onboarding checklist task complete. |
| `GET` | `/api/onboarding/{id}/equipment` | Employee / Admin | Retrieves all equipment allocated to an employee. |
| `POST` | `/api/onboarding/{id}/equipment/request` | Employee / Admin | Submits a hardware request (status: `pending`). |
| `POST` | `/api/admin/equipment/{id}/status` | Admin (`X-Admin-Key` / Admin Role) | IT Admin approves/delivers hardware requests. |
| `GET` | `/api/onboarding/{id}/trainings` | Employee / Admin | Returns mandatory courses and completion statuses. |
| `POST` | `/api/onboarding/{id}/trainings/{id}/complete`| Employee / Admin | Marks a training course complete. |
| `GET` | `/api/admin/checkins` | Admin (`X-Admin-Key` / Admin Role) | Lists all scheduled employee check-ins. |
| `GET` | `/api/admin/audit-logs` | Admin (`X-Admin-Key` / Admin Role) | Views chronological administrative audit trail. |
| `POST` | `/api/onboarding/{id}/reset` | Admin (`X-Admin-Key` / Admin Role) | Clears all data for an employee (eval cleanups). |
| `GET` | `/api/evals/results` | None | Returns golden evaluation and DeepEval metrics. |

---

## 6. Evaluation & Test Suite

The project includes an automated test framework:

### 1. Fast Unit & Security Test Suite
Located in `tests/test_improvements.py`. Runs in under 3 seconds with zero external dependencies:
```powershell
python tests/test_improvements.py
python tests/test_api_contract.py
```
*Coverage*: 26 comprehensive suites covering PBKDF2 password hashing, signed tamper-proof session tokens, employee IDOR authorization, admin access restrictions, tool argument validation, equipment status workflows, prompt injection defenses, rate limiting, training schedules, assignment profiles, Markdown chunking, prompt syntax, structured audit logging, payroll PII masking and validation, regulatory document vault auto-seeding and e-signatures, worker matrix resolution, deterministic compliance gating, HITL action proposals, telemetry accounting, and automated OpenAPI contract tests.

### 2. Evaluation Scenarios (28 Baseline → 32 Multi-Region → 36 Enterprise)
Located in `evals/scenarios.yaml` and `evals/run_evals.py`:
- **Baseline Suite (28 Scenarios)**: Evaluates core handbook RAG retrieval, proactive 30-day task generation, check-in scheduling, and prompt injection defense.
- **Extended Multi-Region Suite (32 Scenarios)**: Adds 4 verified location-specific compliance and benefits scenarios:
  1. `india_public_holidays`: Republic Day, Independence Day, Gandhi Jayanti, Diwali.
  2. `india_statutory_benefits`: Provident Fund (12%), Gratuity Act, ESIC, Professional Tax.
  3. `usa_health_and_retirement`: 401(k) matching (4%, 4-year vesting), HSA health plans.
  4. `usa_i9_verification`: Form I-9 employment eligibility verification within 3 business days.
- **Enterprise Playbook Suite (36 Scenarios)**: Adds 4 advanced enterprise workflow scenarios:
  5. `payroll_setup_inquiry`: Direct deposit setup, masked account, and bank disbursement rules.
  6. `document_signing_i9`: Form I-9 legal verification deadline within 3 business days for USA.
  7. `contractor_vs_fte_benefits`: Grounded policy check confirming contractors are not eligible for 401(k)/dental.
  8. `compliance_prerequisite_blocking`: Security Awareness Training prerequisite gating AWS/GitHub access.
- **Evaluation Pass Rate**:
  - **Baseline (initial)**: 22 / 28 passed (78.6%)
  - **Intermediate Multi-Region**: 32 / 32 passed (100%)
  - **Full Playbook Implementation**: **36 / 36 passed (100%)** verified across all scenarios.

---

## 7. Configuration & Environment Variables (`.env`)

| Variable | Default Value | Description |
|---|---|---|
| `OPENAI_API_KEY` | *(Required)* | API key for OpenAI, Groq, or OpenRouter. |
| `LLM_MODEL` | `openai/gpt-oss-120b` or `gpt-4o-mini` | Model identifier used across all agents. |
| `LLM_BASE_URL` | `https://api.groq.com/openai/v1` | Custom endpoint URL for open-weight / local models. |
| `DATABASE_URL` | `postgresql://onboardai:onboardai@localhost:5432/onboardai` | PostgreSQL connection string. |
| `ADMIN_API_KEY` | *(Configured)* | Secret key for administrative endpoints (`X-Admin-Key`). |
| `ALLOWED_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Strict comma-separated list of allowed CORS origins (no wildcard with credentials). |
| `TRUSTED_PROXIES` | `127.0.0.1,::1` | Reverse proxy IPs allowed to supply `X-Forwarded-For`. |
| `SECRET_KEY` | *(Configured)* | Long secret string used to sign employee session JWTs. |

---

## 8. Step-by-Step Handover Runbook

### To Start the System Fresh:
1. Ensure **Docker Desktop** is running.
2. In the project directory (`c:\Users\bhara\OneDrive\Desktop\Employee-Onboarding`), execute:
   ```powershell
   docker compose down
   docker compose up -d --build
   ```
3. Open your browser to:
   - **Main Chat & Onboarding App**: [http://localhost:5173](http://localhost:5173)
   - **Check-ins Admin**: [http://localhost:5173/admin/checkins](http://localhost:5173/admin/checkins)
   - **Evals Dashboard**: [http://localhost:5173/admin/evals](http://localhost:5173/admin/evals)
   - **Backend API Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Database Manager (pgAdmin)**: [http://localhost:8080](http://localhost:8080) (user: `admin@onboardai.com` / `admin`)

---

## 9. File Directory Map

```text
Employee-Onboarding/
├── .github/workflows/
│   ├── ci.yml                     # Automated GitHub CI pipeline (unit tests + linting)
│   └── deploy-vps.yml             # VPS automated deployment workflow
├── backend/
│   ├── agent/
│   │   ├── multi_agent.py         # Multi-agent LangGraph StateGraph & prompt definitions
│   │   ├── onboarding_agent.py    # SSE stream and sync execution adapters
│   │   ├── security.py            # 10-layer prompt-injection defense mechanisms
│   │   └── tools.py               # Tool definitions for RAG, tasks, equipment, & check-ins
│   ├── app/
│   │   └── main.py                # FastAPI endpoints, rate limiting, and CORS
│   └── requirements.txt           # Python dependency requirements
├── docs/
│   ├── openapi.json               # Exported static OpenAPI 3.1 specification
│   ├── SECURITY.md                # Security architecture & defense documentation
│   └── EVALS.md                   # Evaluation harness guide
├── evals/
│   ├── run_evals.py               # Deterministic golden scenario test runner
│   ├── run_deepeval.py            # DeepEval LLM-as-judge metric runner
│   └── scenarios.yaml             # 36 golden scenario definitions
├── frontend/
│   ├── src/
│   │   ├── api.ts                 # Typed API client functions and TypeScript interfaces
│   │   ├── pages/ChatPage.tsx     # Main onboarding chat, HITL cards, and telemetry UI
│   │   ├── pages/CheckinsAdmin.tsx# Admin dashboard for scheduled check-ins
│   │   └── pages/EvalsAdmin.tsx   # Dashboard displaying automated test reports
│   └── package.json               # React 19 dependencies & build scripts
├── mcp-server/
│   └── server.py                  # FastMCP server exposing tools via stdio
├── seed-data/
│   ├── benefits-guide.md          # Global health, wellness, and retirement guide
│   ├── employee-handbook.md       # Global PTO, hardware tiers, payroll direct deposit
│   ├── it-setup.md                # Laptop, VPN, and IT helpdesk guide
│   ├── location-india.md          # India statutory benefits, leave, and holidays
│   ├── location-usa.md            # USA 401(k), I-9 verification, and federal holidays
│   └── onboarding-checklist.md    # Standard 30-day onboarding task schedule
├── shared/
│   ├── assignments.py             # Manager, buddy, location, worker_type, department matrix
│   ├── auth.py                    # JWT token creation, password hashing, and IDOR enforcement
│   ├── compliance.py              # Deterministic compliance engine and training prerequisite gating
│   ├── config.py                  # Global environment variables, trusted proxies, and CORS settings
│   ├── db.py                      # PostgreSQL schema migrations and connection pool
│   ├── documents.py               # Regulatory document signing vault (I-9, NDA, W-4, Form 11)
│   ├── equipment.py               # Hardware allocation catalog and requests
│   ├── payroll.py                 # Direct deposit submission, routing/IFSC validation, PII masking
│   ├── rag.py                     # ChromaDB regional vector retrieval and fallback keyword search
│   ├── tasks.py                   # Onboarding task checklist CRUD operations
│   └── training.py                # Compliance training assignment and tracking
├── tests/
│   ├── test_improvements.py       # Comprehensive 26-suite unit test runner
│   └── test_api_contract.py       # Automated OpenAPI contract test suite
└── docker-compose.yml             # Multi-container orchestration (Postgres, Backend, Frontend)
```
