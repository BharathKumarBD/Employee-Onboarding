from __future__ import annotations

from datetime import date
from typing import Any

from shared.db import _now_iso, get_connection, init_db


DEFAULT_PROFILE = {
    "name": "Alex Chen",
    "role": "Software Engineer",
    "department": "Engineering",
    "employment_type": "full_time",
    "work_mode": "hybrid",
    "location": "Finland",
}

DEMO_EMPLOYEES = (
    {
        "employee_id": "alex-chen",
        "name": "Alex Chen",
        "role": "Software Engineer",
        "department": "Engineering",
        "employment_type": "full_time",
        "work_mode": "hybrid",
        "location": "Finland",
    },
    {
        "employee_id": "priya-sharma",
        "name": "Priya Sharma",
        "role": "Product Designer",
        "department": "Design",
        "employment_type": "full_time",
        "work_mode": "remote",
        "location": "India",
    },
    {
        "employee_id": "marcus-lee",
        "name": "Marcus Lee",
        "role": "Implementation Consultant",
        "department": "Operations",
        "employment_type": "contractor",
        "work_mode": "hybrid",
        "location": "United States",
    },
)


def list_demo_profiles() -> list[dict[str, Any]]:
    return [dict(profile) for profile in DEMO_EMPLOYEES]


def get_employee_profile(employee_id: str) -> dict[str, Any]:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM employee_profiles WHERE employee_id = %s", (employee_id,))
            row = cur.fetchone()
    if row:
        return dict(row)
    return {"employee_id": employee_id, **DEFAULT_PROFILE, "start_date": date.today(), "is_default": True}


def upsert_employee_profile(employee_id: str, **updates: Any) -> dict[str, Any]:
    current = get_employee_profile(employee_id)
    profile = {**current, **{key: value for key, value in updates.items() if value is not None}}
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO employee_profiles
                    (employee_id, name, role, department, start_date, employment_type, work_mode, location, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (employee_id) DO UPDATE SET
                    name = EXCLUDED.name, role = EXCLUDED.role, department = EXCLUDED.department,
                    start_date = EXCLUDED.start_date, employment_type = EXCLUDED.employment_type,
                    work_mode = EXCLUDED.work_mode, location = EXCLUDED.location,
                    updated_at = EXCLUDED.updated_at
                RETURNING *
                """,
                (
                    employee_id,
                    profile["name"],
                    profile["role"],
                    profile["department"],
                    profile["start_date"],
                    profile["employment_type"],
                    profile["work_mode"],
                    profile["location"],
                    _now_iso(),
                ),
            )
            result = dict(cur.fetchone())
        conn.commit()
    return result
