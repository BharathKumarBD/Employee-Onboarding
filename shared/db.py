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
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
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
