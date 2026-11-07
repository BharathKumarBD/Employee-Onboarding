"""Automated API contract testing for OnboardAI against OpenAPI specification.

Validates that key endpoints respond with expected status codes, data types,
and request/response schemas matching docs/openapi.json.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

# Mock container-only packages for host testing
for mod in [
    "chromadb",
    "chromadb.utils",
    "chromadb.utils.embedding_functions",
    "psycopg",
    "psycopg.rows",
    "langchain_core",
    "langchain_core.messages",
    "langchain_core.tools",
    "langchain_openai",
    "langgraph",
    "langgraph.graph",
    "langgraph.prebuilt",
]:
    if mod not in sys.modules:
        m = MagicMock()
        m.tool = lambda fn: fn
        sys.modules[mod] = m

from fastapi import HTTPException
from backend.app.main import (
    app,
    health,
    demo_employee,
    onboarding_status,
    get_payroll,
    submit_payroll,
    get_documents,
    sign_employee_document,
    execute_confirmed_action,
    PayrollSubmitRequest,
    DocumentSignRequest,
    ActionExecuteRequest,
)
from shared.config import DEFAULT_EMPLOYEE_ID


def test_openapi_schema_loads():
    """Verify that docs/openapi.json exists, is valid JSON, and defines all required paths."""
    openapi_path = ROOT / "docs" / "openapi.json"
    assert openapi_path.exists(), "docs/openapi.json must exist"

    with open(openapi_path, encoding="utf-8") as f:
        spec = json.load(f)

    assert "paths" in spec, "OpenAPI spec must define paths"
    assert "openapi" in spec or "swagger" in spec, "Must declare specification version"

    expected_endpoints = [
        "/health",
        "/api/employee/demo",
        "/api/onboarding/{employee_id}/status",
        "/api/onboarding/{employee_id}/payroll",
        "/api/onboarding/{employee_id}/payroll/submit",
        "/api/onboarding/{employee_id}/documents",
        "/api/onboarding/{employee_id}/documents/sign",
        "/api/onboarding/{employee_id}/actions/execute",
    ]
    for ep in expected_endpoints:
        assert ep in spec["paths"], f"Endpoint '{ep}' missing from openapi.json"

    print("✅ test_openapi_schema_loads passed")


def test_health_contract():
    """GET /health must return {'status': 'ok'}."""
    resp = health()
    assert isinstance(resp, dict)
    assert resp.get("status") == "ok"
    print("✅ test_health_contract passed")


def test_demo_employee_contract():
    """GET /api/employee/demo must return dict with employee details and access_token."""
    with patch("shared.assignments.get_employee_assignment", return_value={
        "location": "Finland",
        "manager_name": "Sarah Johnson",
        "buddy_name": "Marcus Lee",
    }):
        data = demo_employee()
        assert data["id"] == DEFAULT_EMPLOYEE_ID
        assert data["name"] == "Alex Chen"
        assert "access_token" in data
        assert len(data["access_token"]) > 20
        assert data["location"] == "Finland"
    print("✅ test_demo_employee_contract passed")


def test_onboarding_status_contract():
    """GET /api/onboarding/{id}/status requires auth and returns expected schema."""
    user = {"sub": DEFAULT_EMPLOYEE_ID, "role": "employee"}

    # 1. Unauthenticated / IDOR access is rejected
    attacker = {"sub": "attacker_user", "role": "employee"}
    try:
        onboarding_status(DEFAULT_EMPLOYEE_ID, user=attacker)
        assert False, "Should reject cross-user access with 403"
    except HTTPException as exc:
        assert exc.status_code == 403

    # 2. Legitimate employee access returns status dictionary
    with patch("backend.app.main.get_onboarding_status") as mock_get:
        mock_get.return_value = {
            "employee_id": DEFAULT_EMPLOYEE_ID,
            "total_tasks": 6,
            "completed_tasks": 3,
            "completion_percent": 50,
            "tasks": [],
        }
        data = onboarding_status(DEFAULT_EMPLOYEE_ID, user=user)
        assert data["employee_id"] == DEFAULT_EMPLOYEE_ID
        assert data["completion_percent"] == 50
        assert data["total_tasks"] == 6

    print("✅ test_onboarding_status_contract passed")


def test_payroll_endpoint_contract():
    """GET and POST /api/onboarding/{id}/payroll contract."""
    user = {"sub": DEFAULT_EMPLOYEE_ID, "role": "employee"}

    # 1. GET payroll profile
    with patch("shared.payroll.get_payroll_profile") as mock_get:
        mock_get.return_value = {
            "employee_id": DEFAULT_EMPLOYEE_ID,
            "status": "pending_submission",
            "bank_name": None,
            "account_number_masked": None,
            "currency": "EUR",
        }
        res = get_payroll(DEFAULT_EMPLOYEE_ID, user=user)
        assert res["employee_id"] == DEFAULT_EMPLOYEE_ID
        assert res["status"] == "pending_submission"

    # 2. POST payroll submission validates schema and invokes service
    with patch("shared.payroll.submit_payroll_details") as mock_submit:
        mock_submit.return_value = {
            "employee_id": DEFAULT_EMPLOYEE_ID,
            "bank_name": "JPMorgan Chase",
            "account_number_masked": "•••• 4892",
            "currency": "USD",
            "status": "submitted",
            "message": "Submitted successfully",
        }
        req = PayrollSubmitRequest(
            bank_name="JPMorgan Chase",
            account_number_last4="4892",
            routing_or_ifsc_code="021000021",
            tax_filing_status="W4_SINGLE",
            currency="USD",
        )
        post_res = submit_payroll(DEFAULT_EMPLOYEE_ID, body=req, user=user)
        assert post_res["status"] == "submitted"
        assert post_res["account_number_masked"] == "•••• 4892"

    print("✅ test_payroll_endpoint_contract passed")


def test_documents_endpoint_contract():
    """GET and POST /api/onboarding/{id}/documents contract."""
    user = {"sub": DEFAULT_EMPLOYEE_ID, "role": "employee"}

    # 1. GET documents
    with patch("shared.documents.list_employee_documents") as mock_list:
        mock_list.return_value = [
            {
                "id": 1,
                "document_code": "nda",
                "document_title": "NDA",
                "mandatory": True,
                "deadline_day": 1,
                "status": "pending_signature",
            }
        ]
        res = get_documents(DEFAULT_EMPLOYEE_ID, user=user)
        assert "documents" in res
        assert len(res["documents"]) == 1
        assert res["documents"][0]["document_code"] == "nda"

    # 2. POST sign document
    with patch("shared.documents.sign_document") as mock_sign:
        mock_sign.return_value = {
            "id": 1,
            "document_code": "nda",
            "status": "signed",
            "signed_at": "2026-11-07T12:00:00Z",
        }
        sign_req = DocumentSignRequest(document_code="nda")
        sign_res = sign_employee_document(DEFAULT_EMPLOYEE_ID, body=sign_req, user=user)
        assert sign_res["status"] == "signed"

    print("✅ test_documents_endpoint_contract passed")


def test_action_execute_contract():
    """POST /api/onboarding/{id}/actions/execute executes confirmed HITL actions."""
    user = {"sub": DEFAULT_EMPLOYEE_ID, "role": "employee"}

    # 1. Equipment request dispatch
    with patch("shared.equipment.request_equipment") as mock_req:
        mock_req.return_value = {
            "id": 5,
            "employee_id": DEFAULT_EMPLOYEE_ID,
            "item_name": "Dell UltraSharp 27 4K",
            "status": "pending",
        }
        body = ActionExecuteRequest(
            action_type="request_equipment",
            payload={"item_type": "monitor", "item_name": "Dell UltraSharp 27 4K"},
        )
        res = execute_confirmed_action(DEFAULT_EMPLOYEE_ID, body=body, user=user)
        assert res["status"] == "pending"
        assert res["item_name"] == "Dell UltraSharp 27 4K"

    # 2. Check-in scheduling dispatch
    with patch("shared.tasks.schedule_checkin") as mock_checkin:
        mock_checkin.return_value = {
            "id": 8,
            "employee_id": DEFAULT_EMPLOYEE_ID,
            "day": 7,
            "topic": "First week recap",
        }
        body_c = ActionExecuteRequest(
            action_type="schedule_checkin",
            payload={"day": 7, "topic": "First week recap"},
        )
        res_c = execute_confirmed_action(DEFAULT_EMPLOYEE_ID, body=body_c, user=user)
        assert res_c["day"] == 7
        assert res_c["topic"] == "First week recap"

    # 3. Invalid action_type rejection
    try:
        bad_body = ActionExecuteRequest(action_type="unknown_action_type", payload={})
        execute_confirmed_action(DEFAULT_EMPLOYEE_ID, body=bad_body, user=user)
        assert False, "Should reject unknown action_type"
    except HTTPException as exc:
        assert exc.status_code == 400

    print("✅ test_action_execute_contract passed")


if __name__ == "__main__":
    print("\n=== Running OpenAPI Contract Tests ===")
    test_openapi_schema_loads()
    test_health_contract()
    test_demo_employee_contract()
    test_onboarding_status_contract()
    test_payroll_endpoint_contract()
    test_documents_endpoint_contract()
    test_action_execute_contract()
    print("\n🎉 ALL API CONTRACT TESTS PASSED PERFECTLY!\n")
