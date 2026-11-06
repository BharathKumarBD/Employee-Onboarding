from __future__ import annotations

from typing import Any
from shared.db import _now_iso, get_connection, init_db

DEFAULT_ASSIGNMENTS = {
    "manager_name": "Sarah Johnson",
    "manager_email": "sarah.johnson@acmecorp.com",
    "buddy_name": "Marcus Lee",
    "buddy_email": "marcus.lee@acmecorp.com",
    "location": "Finland",
}


def ensure_db() -> None:
    init_db()


def get_employee_assignment(employee_id: str) -> dict[str, Any]:
    """Retrieve manager, buddy, and location for an employee."""
    ensure_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT employee_id, manager_name, manager_email, buddy_name, buddy_email, location, updated_at
                FROM employee_assignments
                WHERE employee_id = %s
                """,
                (employee_id,),
            )
            row = cur.fetchone()

    if row:
        return dict(row)

    # Return default demo profile if not explicitly saved yet
    return {
        "employee_id": employee_id,
        "manager_name": DEFAULT_ASSIGNMENTS["manager_name"],
        "manager_email": DEFAULT_ASSIGNMENTS["manager_email"],
        "buddy_name": DEFAULT_ASSIGNMENTS["buddy_name"],
        "buddy_email": DEFAULT_ASSIGNMENTS["buddy_email"],
        "location": DEFAULT_ASSIGNMENTS["location"],
        "is_default": True,
    }


def set_employee_assignment(
    employee_id: str,
    manager_name: str | None = None,
    manager_email: str | None = None,
    buddy_name: str | None = None,
    buddy_email: str | None = None,
    location: str | None = None,
) -> dict[str, Any]:
    """Assign or update manager, buddy, and location for an employee."""
    ensure_db()
    current = get_employee_assignment(employee_id)

    mgr_name = manager_name if manager_name is not None else current.get("manager_name")
    mgr_email = manager_email if manager_email is not None else current.get("manager_email")
    bdy_name = buddy_name if buddy_name is not None else current.get("buddy_name")
    bdy_email = buddy_email if buddy_email is not None else current.get("buddy_email")
    loc = location if location is not None else current.get("location", "Finland")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO employee_assignments (employee_id, manager_name, manager_email, buddy_name, buddy_email, location, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (employee_id) DO UPDATE SET
                    manager_name = EXCLUDED.manager_name,
                    manager_email = EXCLUDED.manager_email,
                    buddy_name = EXCLUDED.buddy_name,
                    buddy_email = EXCLUDED.buddy_email,
                    location = EXCLUDED.location,
                    updated_at = EXCLUDED.updated_at
                """,
                (employee_id, mgr_name, mgr_email, bdy_name, bdy_email, loc, _now_iso()),
            )
            conn.commit()

    return {
        "employee_id": employee_id,
        "manager_name": mgr_name,
        "manager_email": mgr_email,
        "buddy_name": bdy_name,
        "buddy_email": bdy_email,
        "location": loc,
        "message": f"Assignments updated for {employee_id}: Manager={mgr_name}, Buddy={bdy_name}, Location={loc}",
    }

