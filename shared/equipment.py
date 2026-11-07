from __future__ import annotations

from typing import Any
from shared.db import _now_iso, get_connection, init_db

VALID_ITEM_TYPES = {"laptop", "id_card", "monitor", "keyboard", "mouse", "headset", "desk_phone", "other"}
VALID_STATUSES = {"pending", "allocated", "delivered"}


def ensure_db() -> None:
    init_db()


def get_equipment_allocations(employee_id: str) -> list[dict[str, Any]]:
    ensure_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, employee_id, item_type, item_name, status, allocated_at, created_at
                FROM equipment_allocations
                WHERE employee_id = %s
                ORDER BY created_at ASC
                """,
                (employee_id,),
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]


def request_equipment(employee_id: str, item_type: str, item_name: str) -> dict[str, Any]:
    ensure_db()
    item_type = item_type.lower().strip()
    if item_type not in VALID_ITEM_TYPES:
        item_type = "other"
    item_name = item_name.strip()
    if not item_name:
        raise ValueError("Item name cannot be empty")
    if len(item_name) > 200:
        raise ValueError("Item name too long (max 200 chars)")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO equipment_allocations (employee_id, item_type, item_name, status, created_at)
                VALUES (%s, %s, %s, 'pending', %s)
                RETURNING id
                """,
                (employee_id, item_type, item_name, _now_iso()),
            )
            row = cur.fetchone()
            conn.commit()
            eq_id = row["id"]

    return {
        "id": eq_id,
        "employee_id": employee_id,
        "item_type": item_type,
        "item_name": item_name,
        "status": "pending",
        "message": f"Equipment request submitted: {item_name} ({item_type}). IT will process this request.",
    }


def update_equipment_status(equipment_id: int, status: str = "allocated") -> dict[str, Any] | None:
    """Update equipment request status (e.g. IT admin approval: pending -> allocated/delivered)."""
    ensure_db()
    status = status.lower().strip()
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of: {VALID_STATUSES}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE equipment_allocations
                SET status = %s,
                    allocated_at = CASE WHEN %s IN ('allocated', 'delivered') THEN %s ELSE allocated_at END
                WHERE id = %s
                RETURNING id, employee_id, item_type, item_name, status, allocated_at, created_at
                """,
                (status, status, _now_iso(), equipment_id),
            )
            row = cur.fetchone()
            conn.commit()
            if not row:
                return None
            return dict(row)

