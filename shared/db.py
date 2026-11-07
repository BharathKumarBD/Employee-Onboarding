from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg
from psycopg.rows import dict_row

from shared.config import DATABASE_URL


def init_db() -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS onboarding_tasks (
                    id SERIAL PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    due_day INTEGER NOT NULL,
                    category TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute("ALTER TABLE onboarding_tasks ADD COLUMN IF NOT EXISTS department TEXT")
            cur.execute("ALTER TABLE onboarding_tasks ADD COLUMN IF NOT EXISTS role TEXT")
            cur.execute("ALTER TABLE onboarding_tasks ADD COLUMN IF NOT EXISTS start_date DATE")
            cur.execute("ALTER TABLE onboarding_tasks ADD COLUMN IF NOT EXISTS owner TEXT DEFAULT 'employee'")
            cur.execute("ALTER TABLE onboarding_tasks ADD COLUMN IF NOT EXISTS required BOOLEAN NOT NULL DEFAULT FALSE")
            cur.execute("ALTER TABLE onboarding_tasks ADD COLUMN IF NOT EXISTS blocked_reason TEXT")
            cur.execute("ALTER TABLE onboarding_tasks ADD COLUMN IF NOT EXISTS idempotency_key TEXT")
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS checkins (
                    id SERIAL PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    day INTEGER NOT NULL,
                    topic TEXT NOT NULL,
                    scheduled_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS equipment_allocations (
                    id SERIAL PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    item_name TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    allocated_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS training_assignments (
                    id SERIAL PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    training_name TEXT NOT NULL,
                    due_day INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS employee_assignments (
                    id SERIAL PRIMARY KEY,
                    employee_id TEXT NOT NULL UNIQUE,
                    manager_name TEXT,
                    manager_email TEXT,
                    buddy_name TEXT,
                    buddy_email TEXT,
                    location TEXT DEFAULT 'finland',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'employee', -- 'employee' or 'admin'
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id SERIAL PRIMARY KEY,
                    action TEXT NOT NULL,
                    employee_id TEXT,
                    performed_by TEXT DEFAULT 'system',
                    details JSONB,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            # ── Phase 1: Payroll profiles ─────────────────────────────────────────
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS payroll_profiles (
                    id SERIAL PRIMARY KEY,
                    employee_id TEXT NOT NULL UNIQUE,
                    bank_name TEXT,
                    account_number_masked TEXT,
                    routing_or_ifsc_code TEXT,
                    currency TEXT NOT NULL DEFAULT 'EUR',
                    tax_filing_status TEXT,
                    withholding_allowances INTEGER DEFAULT 0,
                    status TEXT NOT NULL DEFAULT 'pending_submission',
                    verified_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            cur.execute(
                """
                ALTER TABLE payroll_profiles
                ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS employee_profiles (
                    employee_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL DEFAULT 'Alex Chen',
                    role TEXT NOT NULL DEFAULT 'Software Engineer',
                    department TEXT NOT NULL DEFAULT 'Engineering',
                    start_date DATE NOT NULL DEFAULT CURRENT_DATE,
                    employment_type TEXT NOT NULL DEFAULT 'full_time',
                    work_mode TEXT NOT NULL DEFAULT 'hybrid',
                    location TEXT NOT NULL DEFAULT 'Finland',
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            # ── Phase 1: Employee documents ───────────────────────────────────────
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS employee_documents (
                    id SERIAL PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    document_code TEXT NOT NULL,
                    document_title TEXT NOT NULL,
                    mandatory BOOLEAN NOT NULL DEFAULT TRUE,
                    deadline_day INTEGER NOT NULL,
                    status TEXT NOT NULL DEFAULT 'pending_signature',
                    signed_at TIMESTAMPTZ,
                    verified_by TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE (employee_id, document_code)
                )
                """
            )
            # ── Phase 2: Worker profile matrix columns ────────────────────────────
            cur.execute(
                """
                ALTER TABLE employee_assignments
                ADD COLUMN IF NOT EXISTS worker_type TEXT NOT NULL DEFAULT 'fte',
                ADD COLUMN IF NOT EXISTS department TEXT NOT NULL DEFAULT 'engineering',
                ADD COLUMN IF NOT EXISTS onboarding_stage TEXT NOT NULL DEFAULT 'day_one'
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS task_dependencies (
                    task_id INTEGER NOT NULL REFERENCES onboarding_tasks(id) ON DELETE CASCADE,
                    depends_on_task_id INTEGER NOT NULL REFERENCES onboarding_tasks(id) ON DELETE CASCADE,
                    PRIMARY KEY (task_id, depends_on_task_id),
                    CHECK (task_id <> depends_on_task_id)
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_requests (
                    id SERIAL PRIMARY KEY,
                    employee_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    requested_by TEXT NOT NULL DEFAULT 'agent',
                    approved_by TEXT,
                    reason TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    decided_at TIMESTAMPTZ
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS agent_executions (
                    id SERIAL PRIMARY KEY,
                    execution_id TEXT NOT NULL UNIQUE,
                    employee_id TEXT NOT NULL,
                    message_hash TEXT NOT NULL,
                    status TEXT NOT NULL,
                    tool_calls JSONB NOT NULL DEFAULT '[]'::jsonb,
                    error TEXT,
                    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    completed_at TIMESTAMPTZ
                )
                """
            )
            cur.execute(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS onboarding_task_idempotency_idx
                ON onboarding_tasks (idempotency_key)
                WHERE idempotency_key IS NOT NULL
                """
            )
        conn.commit()


@contextmanager
def get_connection():
    conn = psycopg.connect(DATABASE_URL, row_factory=dict_row)
    try:
        yield conn
    finally:
        conn.close()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
