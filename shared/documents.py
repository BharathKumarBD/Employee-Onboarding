"""Employee regulatory document signing vault for OnboardAI.

Manages I-9, NDA, handbook acknowledgements, and country-specific forms.
Documents are auto-seeded based on employee location when first accessed.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from shared.db import _now_iso, get_connection, init_db

# Location → default document set
_LOCATION_DOCUMENTS: dict[str, list[dict[str, Any]]] = {
    "usa": [
        {"document_code": "nda", "document_title": "Non-Disclosure Agreement (NDA)", "mandatory": True, "deadline_day": 1},
        {"document_code": "handbook_ack", "document_title": "Employee Handbook Acknowledgement", "mandatory": True, "deadline_day": 2},
        {"document_code": "i9_verification", "document_title": "Form I-9 (Employment Eligibility Verification)", "mandatory": True, "deadline_day": 3},
        {"document_code": "w4", "document_title": "Form W-4 (Employee's Withholding Certificate)", "mandatory": True, "deadline_day": 5},
    ],
    "india": [
        {"document_code": "nda", "document_title": "Non-Disclosure Agreement (NDA)", "mandatory": True, "deadline_day": 1},
        {"document_code": "handbook_ack", "document_title": "Employee Handbook Acknowledgement", "mandatory": True, "deadline_day": 2},
        {"document_code": "form_11", "document_title": "Form 11 (EPF — Employee Provident Fund Declaration)", "mandatory": True, "deadline_day": 3},
        {"document_code": "form_2_gratuity", "document_title": "Form 2 (Payment of Gratuity Act Nomination)", "mandatory": True, "deadline_day": 5},
    ],
    "global": [
        {"document_code": "employment_contract", "document_title": "Employment Contract", "mandatory": True, "deadline_day": 1},
        {"document_code": "handbook_ack", "document_title": "Employee Handbook Acknowledgement", "mandatory": True, "deadline_day": 2},
        {"document_code": "tax_card", "document_title": "Tax Card (Verokortti)", "mandatory": True, "deadline_day": 5},
    ],
}

# Finland and other EU countries use the global/Finland set
_LOCATION_ALIASES: dict[str, str] = {
    "finland": "global",
    "sweden": "global",
    "germany": "global",
    "europe": "global",
    "eu": "global",
    "united states": "usa",
    "us": "usa",
    "america": "usa",
}

VALID_DOC_STATUSES = {"pending_signature", "signed", "verified"}


def _ensure_db() -> None:
    init_db()


def _resolve_location(location: str) -> str:
    """Normalise location string to a document-set key."""
    loc = location.strip().lower()
    return _LOCATION_ALIASES.get(loc, loc if loc in _LOCATION_DOCUMENTS else "global")


def list_employee_documents(employee_id: str, location: str = "Finland") -> list[dict[str, Any]]:
    """Return all documents for an employee. Auto-seeds based on location if none exist."""
    _ensure_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, employee_id, document_code, document_title, mandatory,
                       deadline_day, status, signed_at, verified_by, created_at
                FROM employee_documents
                WHERE employee_id = %s
                ORDER BY deadline_day ASC, id ASC
                """,
                (employee_id,),
            )
            rows = cur.fetchall()

    if rows:
        return [dict(r) for r in rows]

    # Auto-seed based on location
    loc_key = _resolve_location(location)
    templates = _LOCATION_DOCUMENTS.get(loc_key, _LOCATION_DOCUMENTS["global"])

    seeded: list[dict[str, Any]] = []
    now = _now_iso()

    with get_connection() as conn:
        with conn.cursor() as cur:
            for tmpl in templates:
                cur.execute(
                    """
                    INSERT INTO employee_documents
                        (employee_id, document_code, document_title, mandatory, deadline_day,
                         status, created_at)
                    VALUES (%s, %s, %s, %s, %s, 'pending_signature', %s)
                    ON CONFLICT DO NOTHING
                    RETURNING id, employee_id, document_code, document_title, mandatory,
                              deadline_day, status, signed_at, verified_by, created_at
                    """,
                    (
                        employee_id,
                        tmpl["document_code"],
                        tmpl["document_title"],
                        tmpl["mandatory"],
                        tmpl["deadline_day"],
                        now,
                    ),
                )
                row = cur.fetchone()
                if row:
                    seeded.append(dict(row))
            conn.commit()

    return seeded


def sign_document(employee_id: str, document_code: str) -> dict[str, Any] | None:
    """Mark a document as electronically signed. Returns updated record or None if not found."""
    _ensure_db()
    document_code = str(document_code).strip().lower()
    signed_at = datetime.now(timezone.utc).isoformat()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                UPDATE employee_documents
                SET status = 'signed', signed_at = %s
                WHERE employee_id = %s AND document_code = %s
                RETURNING id, employee_id, document_code, document_title, mandatory,
                          deadline_day, status, signed_at, verified_by, created_at
                """,
                (signed_at, employee_id, document_code),
            )
            row = cur.fetchone()
            conn.commit()

    if not row:
        return None

    result = dict(row)
    result["message"] = (
        f"Document '{result['document_title']}' has been electronically signed. "
        f"Signed at: {signed_at[:19]} UTC. HR will verify within 1 business day."
    )
    return result

