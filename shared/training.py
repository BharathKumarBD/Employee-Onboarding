from __future__ import annotations

from typing import Any
from shared.db import _now_iso, get_connection, init_db

VALID_STATUSES = {"pending", "in_progress", "completed"}
STANDARD_TRAININGS = [
    {"name": "Security Awareness Training", "due_day": 3},
    {"name": "Code of Conduct & Ethics", "due_day": 5},
    {"name": "Data Privacy & GDPR Basics", "due_day": 7},
    {"name": "IT Security & Password Policy", "due_day": 5},
    {"name": "Benefits Overview Session", "due_day": 10},
    {"name": "Workplace Safety & Emergency Procedures", "due_day": 14},
]


def ensure_db() -> None:
    init_db()


def list_training_assignments(employee_id: str) -> list[dict[str, Any]]:
    ensure_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, employee_id, training_name, due_day, status, created_at
                FROM training_assignments
                WHERE employee_id = %s
                ORDER BY due_day ASC, id ASC
                """,
                (employee_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def assign_training(employee_id: str, training_name: str, due_day: int) -> dict[str, Any]:
    ensure_db()
    training_name = training_name.strip()
    if not training_name:
        raise ValueError("Training name cannot be empty")
    if len(training_name) > 300:
        raise ValueError("Training name too long (max 300 chars)")
    if not 1 <= due_day <= 90:
        raise ValueError("due_day must be between 1 and 90")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO training_assignments (employee_id, training_name, due_day, status, created_at)
                VALUES (%s, %s, %s, 'pending', %s)
                RETURNING id
                """,
                (employee_id, training_name, due_day, _now_iso()),
            )
            row = cur.fetchone()
            conn.commit()
            tr_id = row["id"]

    return {
        "id": tr_id,
        "employee_id": employee_id,
        "training_name": training_name,
        "due_day": due_day,
        "status": "pending",
    }


def complete_training(training_id: int, employee_id: str) -> dict[str, Any] | None:
    ensure_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE training_assignments SET status = 'completed' WHERE id = %s AND employee_id = %s",
                (training_id, employee_id),
            )
            cur.execute(
                "SELECT * FROM training_assignments WHERE id = %s AND employee_id = %s",
                (training_id, employee_id),
            )
            row = cur.fetchone()
            conn.commit()
    return dict(row) if row else None


def auto_assign_standard_trainings(employee_id: str) -> list[dict[str, Any]]:
    """Assign all standard onboarding trainings if not already assigned."""
    existing = list_training_assignments(employee_id)
    existing_names = {t["training_name"] for t in existing}
    created = []
    for t in STANDARD_TRAININGS:
        if t["name"] not in existing_names:
            result = assign_training(employee_id, t["name"], t["due_day"])
            created.append(result)
    return created
