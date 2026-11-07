from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from shared.db import _now_iso, get_connection, init_db


def create_approval(
    employee_id: str,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    reason: str | None = None,
) -> dict[str, Any]:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT * FROM approval_requests
                WHERE employee_id = %s
                  AND action = %s
                  AND resource_type = %s
                  AND status = 'pending'
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (employee_id, action, resource_type),
            )
            existing = cur.fetchone()
            if existing:
                return dict(existing)
            cur.execute(
                """
                INSERT INTO approval_requests
                    (employee_id, action, resource_type, resource_id, reason)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING *
                """,
                (employee_id, action, resource_type, resource_id, reason),
            )
            row = dict(cur.fetchone())
        conn.commit()
    return row


def list_approvals(employee_id: str | None = None) -> list[dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            if employee_id:
                cur.execute(
                    "SELECT * FROM approval_requests WHERE employee_id = %s ORDER BY created_at DESC",
                    (employee_id,),
                )
            else:
                cur.execute("SELECT * FROM approval_requests ORDER BY created_at DESC")
            return [dict(row) for row in cur.fetchall()]


def decide_approval(approval_id: int, status: str, approved_by: str) -> dict[str, Any] | None:
    if status not in {"approved", "rejected"}:
        raise ValueError("Approval status must be approved or rejected")
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE approval_requests
                SET status = %s, approved_by = %s, decided_at = %s
                WHERE id = %s AND status = 'pending'
                RETURNING *
                """,
                (status, approved_by, _now_iso(), approval_id),
            )
            row = cur.fetchone()
        conn.commit()
    return dict(row) if row else None


def get_onboarding_exceptions(employee_id: str) -> list[dict[str, Any]]:
    init_db()
    now = datetime.now(timezone.utc)
    exceptions: list[dict[str, Any]] = []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT t.id, t.title, t.due_day, t.status, t.required, t.blocked_reason,
                       t.owner, t.created_at
                FROM onboarding_tasks t
                WHERE t.employee_id = %s
                  AND (t.status IN ('blocked', 'overdue')
                       OR (t.required = TRUE AND t.status <> 'completed' AND t.due_day <= 7))
                ORDER BY t.due_day, t.id
                """,
                (employee_id,),
            )
            rows = cur.fetchall()
    for row in rows:
        item = dict(row)
        if item["status"] not in {"blocked", "overdue"} and item["due_day"] <= 7:
            item["status"] = "at_risk"
        item["severity"] = "high" if item["required"] else "medium"
        item["responsible_party"] = item["owner"] or "employee"
        exceptions.append(item)
    return exceptions


def calculate_readiness(employee_id: str) -> dict[str, Any]:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (WHERE status = 'completed') AS completed,
                    COUNT(*) FILTER (WHERE required = TRUE AND status <> 'completed') AS blockers
                FROM onboarding_tasks WHERE employee_id = %s
                """,
                (employee_id,),
            )
            task_row = dict(cur.fetchone())
            cur.execute(
                "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'delivered') AS delivered FROM equipment_allocations WHERE employee_id = %s",
                (employee_id,),
            )
            equipment = dict(cur.fetchone())
            cur.execute(
                "SELECT COUNT(*) AS total, COUNT(*) FILTER (WHERE status = 'completed') AS completed FROM training_assignments WHERE employee_id = %s",
                (employee_id,),
            )
            training = dict(cur.fetchone())
    task_score = (int(task_row["completed"]) / int(task_row["total"]) * 100) if task_row["total"] else 0
    equipment_score = (int(equipment["delivered"]) / int(equipment["total"]) * 100) if equipment["total"] else 100
    training_score = (int(training["completed"]) / int(training["total"]) * 100) if training["total"] else 0
    score = round((task_score + equipment_score + training_score) / 3)
    return {
        "employee_id": employee_id,
        "readiness_percent": score,
        "components": {
            "tasks": round(task_score),
            "equipment": round(equipment_score),
            "training": round(training_score),
        },
        "mandatory_blockers": int(task_row["blockers"]),
        "exceptions": get_onboarding_exceptions(employee_id),
    }


def start_execution(employee_id: str, message: str) -> tuple[str, bool]:
    execution_id = str(uuid.uuid4())
    message_hash = hashlib.sha256(message.encode("utf-8")).hexdigest()
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO agent_executions (execution_id, employee_id, message_hash, status)
                VALUES (%s, %s, %s, 'running')
                """,
                (execution_id, employee_id, message_hash),
            )
        conn.commit()
    return execution_id, True


def finish_execution(
    execution_id: str,
    status: str,
    tool_calls: list[dict[str, Any]] | None = None,
    error: str | None = None,
) -> None:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE agent_executions
                SET status = %s, tool_calls = %s, error = %s, completed_at = %s
                WHERE execution_id = %s
                """,
                (status, json.dumps(tool_calls or []), error, _now_iso(), execution_id),
            )
        conn.commit()


def list_executions(employee_id: str | None = None) -> list[dict[str, Any]]:
    init_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            if employee_id:
                cur.execute(
                    "SELECT * FROM agent_executions WHERE employee_id = %s ORDER BY started_at DESC",
                    (employee_id,),
                )
            else:
                cur.execute("SELECT * FROM agent_executions ORDER BY started_at DESC")
            return [dict(row) for row in cur.fetchall()]
