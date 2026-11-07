"""Payroll profile management for OnboardAI.

Handles bank account setup, tax filing status, and payroll verification.
PII is masked at ingestion: only the last 4 digits of an account number are stored.
"""
from __future__ import annotations

import re
from typing import Any

from shared.db import _now_iso, get_connection, init_db

# Routing number validation patterns
_US_ROUTING_RE = re.compile(r'^\d{9}$')
_IN_IFSC_RE = re.compile(r'^[A-Z]{4}0[A-Z0-9]{6}$')
_INDIAN_BANK_PREFIXES = {
    "SBI": "SBIN",
    "STATE BANK OF INDIA": "SBIN",
    "HDFC": "HDFC",
    "HDFC BANK": "HDFC",
    "ICICI": "ICIC",
    "ICICI BANK": "ICIC",
    "AXIS": "UTIB",
    "AXIS BANK": "UTIB",
    "KOTAK": "KKBK",
    "KOTAK MAHINDRA BANK": "KKBK",
    "PNB": "PUNB",
    "PUNJAB NATIONAL BANK": "PUNB",
}

VALID_CURRENCIES = {"EUR", "USD", "INR"}
VALID_STATUSES = {"pending_submission", "submitted", "verified"}
VALID_TAX_STATUSES = {
    "W4_SINGLE", "W4_MARRIED", "W4_HOH",
    "INDIA_NEW_REGIME", "INDIA_OLD_REGIME",
    "EU_STANDARD",
}


def _ensure_db() -> None:
    init_db()


def get_payroll_profile(employee_id: str) -> dict[str, Any]:
    """Return the payroll profile for an employee, or a default pending profile."""
    _ensure_db()
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, employee_id, bank_name, account_number_masked,
                       routing_or_ifsc_code, currency, tax_filing_status,
                       withholding_allowances, status, verified_at, created_at, updated_at
                FROM payroll_profiles
                WHERE employee_id = %s
                """,
                (employee_id,),
            )
            row = cur.fetchone()

    if row:
        return dict(row)

    return {
        "employee_id": employee_id,
        "status": "pending_submission",
        "bank_name": None,
        "account_number_masked": None,
        "routing_or_ifsc_code": None,
        "currency": "EUR",
        "tax_filing_status": None,
        "withholding_allowances": 0,
        "verified_at": None,
        "message": "Payroll details not yet submitted. Please provide bank and tax information.",
    }


def submit_payroll_details(
    employee_id: str,
    bank_name: str,
    account_number_last4: str,
    routing_or_ifsc_code: str,
    tax_filing_status: str,
    currency: str = "EUR",
    allowances: int = 0,
) -> dict[str, Any]:
    """Submit payroll/bank details for an employee.

    Security rules:
    - Only accepts the last 4 digits of an account number (not a full number).
    - Validates routing numbers for USD (9-digit US ABA) and IFSC for INR.
    - Rejects unrecognised currencies and tax statuses.
    """
    _ensure_db()

    # Sanitise
    bank_name = str(bank_name).strip()[:200]
    account_number_last4 = str(account_number_last4).strip()
    routing_or_ifsc_code = str(routing_or_ifsc_code).strip()
    tax_filing_status = str(tax_filing_status).strip().upper()
    currency = str(currency).strip().upper()
    if not bank_name:
        raise ValueError("Bank name is required.")

    # --- Validate account number: reject full account numbers ---
    if not re.match(r'^\d{4}$', account_number_last4):
        raise ValueError(
            "Only the last 4 digits of your account number are accepted for security. "
            "Please provide exactly 4 digits (e.g. '4892')."
        )

    # --- Currency validation ---
    if currency not in VALID_CURRENCIES:
        raise ValueError(f"Unsupported currency '{currency}'. Must be one of: {', '.join(sorted(VALID_CURRENCIES))}")

    # --- Routing/IFSC validation ---
    if currency == "USD":
        if not _US_ROUTING_RE.match(routing_or_ifsc_code):
            raise ValueError(
                "US ABA routing number must be exactly 9 digits (e.g. '021000021')."
            )
    elif currency == "INR":
        routing_or_ifsc_code = routing_or_ifsc_code.upper()
        if not _IN_IFSC_RE.match(routing_or_ifsc_code):
            expected_prefix = _INDIAN_BANK_PREFIXES.get(bank_name.upper())
            example = f"{expected_prefix}0001234" if expected_prefix else "HDFC0001234"
            raise ValueError(
                f"Indian IFSC code must be exactly 11 characters in format XXXX0YYYYYY "
                f"(for example {example})."
            )
        expected_prefix = _INDIAN_BANK_PREFIXES.get(bank_name.upper())
        if expected_prefix and not routing_or_ifsc_code.startswith(expected_prefix):
            raise ValueError(
                f"The IFSC code does not match {bank_name}. "
                f"Use an IFSC beginning with {expected_prefix}0 (for example {expected_prefix}0001234)."
            )

    # --- Tax status validation ---
    if tax_filing_status not in VALID_TAX_STATUSES:
        raise ValueError(
            f"Unrecognised tax filing status '{tax_filing_status}'. "
            f"Valid values: {', '.join(sorted(VALID_TAX_STATUSES))}"
        )

    # --- Allowances ---
    try:
        allowances_int = int(allowances)
    except (ValueError, TypeError):
        raise ValueError("withholding_allowances must be a non-negative integer.")
    if allowances_int < 0:
        raise ValueError("withholding_allowances cannot be negative.")

    masked = f"•••• {account_number_last4}"
    now = _now_iso()

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO payroll_profiles
                    (employee_id, bank_name, account_number_masked, routing_or_ifsc_code,
                     currency, tax_filing_status, withholding_allowances, status, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'submitted', %s, %s)
                ON CONFLICT (employee_id) DO UPDATE SET
                    bank_name = EXCLUDED.bank_name,
                    account_number_masked = EXCLUDED.account_number_masked,
                    routing_or_ifsc_code = EXCLUDED.routing_or_ifsc_code,
                    currency = EXCLUDED.currency,
                    tax_filing_status = EXCLUDED.tax_filing_status,
                    withholding_allowances = EXCLUDED.withholding_allowances,
                    status = 'submitted',
                    updated_at = EXCLUDED.updated_at
                RETURNING id, employee_id, bank_name, account_number_masked,
                          routing_or_ifsc_code, currency, tax_filing_status,
                          withholding_allowances, status, created_at, updated_at
                """,
                (
                    employee_id, bank_name, masked, routing_or_ifsc_code,
                    currency, tax_filing_status, allowances_int, now, now,
                ),
            )
            row = cur.fetchone()
            conn.commit()

    result = dict(row) if row else {}
    result["message"] = (
        f"Payroll details submitted successfully. "
        f"Bank: {bank_name}, Account: {masked}, Currency: {currency}. "
        f"HR will verify within 2 business days."
    )
    return result
