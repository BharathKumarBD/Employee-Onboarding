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
