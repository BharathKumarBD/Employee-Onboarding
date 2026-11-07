from __future__ import annotations

import json
import logging
import re
import time
from collections import defaultdict
from typing import Any

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel, Field

from agent.onboarding_agent import run_agent, stream_agent
from agent.security import InputValidationError, validate_message_length
from shared.auth import (
    create_token,
    get_current_user,
    get_current_user_optional,
    hash_password,
    require_admin_role,
    require_employee_access,
    verify_password,
)
from shared.config import ADMIN_API_KEY, ALLOWED_ORIGINS, DEFAULT_EMPLOYEE_ID, TRUSTED_PROXIES
from shared.eval_results import load_eval_reports
from shared.tasks import complete_task, get_onboarding_status, list_checkins, reset_employee_data
from shared.onboarding_operations import (
    calculate_readiness,
    create_approval,
    decide_approval,
    get_onboarding_exceptions,
    list_approvals,
    list_executions,
)
from shared.profiles import get_employee_profile, list_demo_profiles, upsert_employee_profile

audit_logger = logging.getLogger("aarambh_ai.audit")


# ─── Rate Limiting ──────────────────────────────────────────────────────────────

RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX = 20  # requests per window per IP

_rate_buckets: dict[str, list[float]] = defaultdict(list)


def _check_rate_limit(ip: str) -> bool:
    """Returns True if request is allowed, False if rate limited."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW
    timestamps = _rate_buckets[ip]
    # Prune old timestamps
    _rate_buckets[ip] = [t for t in timestamps if t > window_start]
    if len(_rate_buckets[ip]) >= RATE_LIMIT_MAX:
        return False
    _rate_buckets[ip].append(now)
    return True


def _get_client_ip(request: Request) -> str:
    """Extract client IP securely.
    
    Only trusts X-Forwarded-For if request.client.host is in TRUSTED_PROXIES.
    Otherwise, uses the direct connection IP to prevent spoofing and rate limit bypasses.
    """
    direct_ip = request.client.host if request.client else "unknown"
    if direct_ip in TRUSTED_PROXIES:
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            # Client IP is the leftmost IP in the chain
            client_ip = forwarded.split(",")[0].strip()
            if client_ip:
                return client_ip
    return direct_ip


# ─── Employee ID Validation ─────────────────────────────────────────────────────

EMPLOYEE_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{1,100}$')


def _validate_employee_id(employee_id: str) -> str:
    """Validate and return a sanitized employee_id."""
    if not EMPLOYEE_ID_RE.match(employee_id):
        raise HTTPException(
            status_code=400,
            detail="Invalid employee_id: must be 1-100 alphanumeric characters, hyphens, or underscores.",
        )
    return employee_id


# ─── Admin Auth ─────────────────────────────────────────────────────────────────

admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


def _require_admin(api_key: str | None, user: dict[str, Any] | None = None) -> None:
    """Enforce strict admin authorization.
    
    Requires either an authenticated user with 'admin' role, or a valid X-Admin-Key matching ADMIN_API_KEY.
    Strictly forbids admin access when ADMIN_API_KEY is not configured or empty.
    """
    if user and user.get("role") == "admin":
        return

    import hmac
    import shared.config as config
    key = getattr(config, "ADMIN_API_KEY", "").strip()
    if not key:
        raise HTTPException(
            status_code=403,
            detail="Admin access is disabled. ADMIN_API_KEY must be configured on the server.",
        )
    if not api_key or not hmac.compare_digest(api_key, key):
        raise HTTPException(
            status_code=403,
            detail="Admin access requires a valid X-Admin-Key header or admin authentication.",
        )


# ─── Audit Logging ──────────────────────────────────────────────────────────────

def _audit_log(
    action: str,
    employee_id: str | None = None,
    performed_by: str = "api",
    details: dict | None = None,
) -> bool:
    """Write an audit log entry to the database and application logger.
    
    Never silently swallows errors; logs an explicit error if database write fails.
    Returns True if successfully written to the database, False otherwise.
    """
    from shared.db import _now_iso
    timestamp = _now_iso()
    details_dict = details or {}
    success = False
    try:
        from shared.db import get_connection
        import json as _json
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs (action, employee_id, performed_by, details, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (action, employee_id, performed_by, _json.dumps(details_dict), timestamp),
                )
            conn.commit()
        success = True
    except Exception as exc:
        audit_logger.error(
            "AUDIT LOG STORAGE FAILURE: action=%s, employee_id=%s, performed_by=%s, error=%s",
            action, employee_id, performed_by, exc,
            exc_info=True,
        )

    audit_logger.info(
        "AUDIT: action=%s employee=%s actor=%s status=%s details=%s",
        action, employee_id, performed_by, "persisted" if success else "storage_failed", details_dict,
    )
    return success


# ─── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from shared.db import init_db
    try:
        init_db()
    except Exception as exc:
        logging.getLogger("aarambh_ai").warning(
            "Database connection could not be established at startup: %s. "
            "Ensure PostgreSQL is running (e.g. run start-postgres.bat, or docker-compose up -d postgres).",
            exc,
        )
    yield


# ─── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Aarambh-AI API",
    description="Autonomous HR onboarding agent",
    version="1.0.0",
    lifespan=lifespan,
)

# Disallow wildcard origin with credentials (RFC / browser security requirement)
cors_origins = [o for o in ALLOWED_ORIGINS if o != "*"]
has_wildcard = "*" in ALLOWED_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins if cors_origins else (["*"] if has_wildcard else ["http://localhost:5173", "http://localhost:3000"]),
    allow_credentials=False if (has_wildcard and not cors_origins) else True,
    allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Admin-Key", "X-Session-Token"],
)


# ─── Request Models ──────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: str


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    employee_id: str = DEFAULT_EMPLOYEE_ID
    history: list[ChatMessage] = Field(default_factory=list)


class CompleteTaskRequest(BaseModel):
    employee_id: str = DEFAULT_EMPLOYEE_ID


class EquipmentRequest(BaseModel):
    item_type: str = "laptop"
    item_name: str


class EquipmentStatusUpdateRequest(BaseModel):
    status: str = "allocated"


class AssignmentUpdateRequest(BaseModel):
    manager_name: str | None = None
    manager_email: str | None = None
    buddy_name: str | None = None
    buddy_email: str | None = None
    location: str | None = None
    worker_type: str | None = None
    department: str | None = None
    onboarding_stage: str | None = None


class PersonaUpdateRequest(BaseModel):
    location: str | None = None
    worker_type: str | None = None
    department: str | None = None
    onboarding_stage: str | None = None


# ── Phase 1: Payroll & Document models ──────────────────────────────────────

class PayrollSubmitRequest(BaseModel):
    bank_name: str
    account_number_last4: str
    routing_or_ifsc_code: str
    tax_filing_status: str
    currency: str = "EUR"
    withholding_allowances: int = 0


class DocumentSignRequest(BaseModel):
    document_code: str


# ── Phase 3: HITL Action Execution model ────────────────────────────────────

class ActionExecuteRequest(BaseModel):
    action_type: str
    payload: dict = Field(default_factory=dict)


class EmployeeProfileRequest(BaseModel):
    name: str | None = None
    role: str | None = None
    department: str | None = None
    start_date: str | None = None
    employment_type: str | None = None
    work_mode: str | None = None
    location: str | None = None


class ApprovalDecisionRequest(BaseModel):
    status: str
    approved_by: str


def _validate_chat_request(request: ChatRequest) -> list[dict]:
    validate_message_length(request.message)
    for msg in request.history:
        validate_message_length(msg.content)
    return [m.model_dump() for m in request.history]


# ─── Routes ──────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/auth/login", response_model=LoginResponse)
def login(creds: LoginRequest):
    """Authenticate employee or admin, returning a signed session token."""
    username = creds.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    from shared.config import DEFAULT_ADMIN_PASSWORD, DEFAULT_EMPLOYEE_PASSWORD
    from shared.db import get_connection

    # 1. Check database for created user
    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT username, password_hash, role FROM users WHERE username = %s", (username,))
                row = cur.fetchone()
                if row and verify_password(creds.password, row["password_hash"]):
                    token = create_token(row["username"], row["role"])
                    _audit_log("user_login", employee_id=row["username"], performed_by=row["username"])
                    return LoginResponse(access_token=token, user_id=row["username"], role=row["role"])
    except Exception:
        pass

    # 2. Check default bootstrap accounts if configured
    if username == "admin":
        if DEFAULT_ADMIN_PASSWORD and creds.password == DEFAULT_ADMIN_PASSWORD:
            token = create_token("admin", "admin")
            _audit_log("admin_login", employee_id="admin", performed_by="admin")
            return LoginResponse(access_token=token, user_id="admin", role="admin")
    elif username == DEFAULT_EMPLOYEE_ID:
        if DEFAULT_EMPLOYEE_PASSWORD and creds.password == DEFAULT_EMPLOYEE_PASSWORD:
            token = create_token(DEFAULT_EMPLOYEE_ID, "employee")
            _audit_log("employee_login", employee_id=DEFAULT_EMPLOYEE_ID, performed_by=DEFAULT_EMPLOYEE_ID)
            return LoginResponse(access_token=token, user_id=DEFAULT_EMPLOYEE_ID, role="employee")

    # In dev mode with no passwords configured, allow ONLY the default demo employee (never admin)
    if not DEFAULT_ADMIN_PASSWORD and not DEFAULT_EMPLOYEE_PASSWORD and username == DEFAULT_EMPLOYEE_ID:
        token = create_token(DEFAULT_EMPLOYEE_ID, "employee")
        _audit_log("dev_demo_login", employee_id=DEFAULT_EMPLOYEE_ID, performed_by=DEFAULT_EMPLOYEE_ID)
        return LoginResponse(access_token=token, user_id=DEFAULT_EMPLOYEE_ID, role="employee")

    raise HTTPException(status_code=401, detail="Invalid username or password")


@app.get("/api/auth/me")
def get_me(user: dict[str, Any] = Security(get_current_user)):
    """Return claims of the authenticated user."""
    return user


@app.post("/api/chat")
def chat(
    request: ChatRequest,
    http_request: Request,
    user: dict[str, Any] = Security(get_current_user),
):
    ip = _get_client_ip(http_request)
    if not _check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait before sending another message.")
    _validate_employee_id(request.employee_id)
    require_employee_access(request.employee_id, user)
    try:
        history = _validate_chat_request(request)
        result = run_agent(request.message, request.employee_id, history)
        return result
    except InputValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    user: dict[str, Any] = Security(get_current_user),
):
    ip = _get_client_ip(http_request)
    if not _check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait before sending another message.")
    _validate_employee_id(request.employee_id)
    require_employee_access(request.employee_id, user)
    try:
        history = _validate_chat_request(request)
    except InputValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    async def event_generator():
        try:
            async for event in stream_agent(request.message, request.employee_id, history):
                yield f"event: {event['event']}\ndata: {json.dumps(event['data'])}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/api/onboarding/{employee_id}/status")
def onboarding_status(
    employee_id: str,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    return get_onboarding_status(employee_id)


@app.get("/api/onboarding/{employee_id}/readiness")
def onboarding_readiness(employee_id: str):
    _validate_employee_id(employee_id)
    return calculate_readiness(employee_id)


@app.get("/api/onboarding/{employee_id}/exceptions")
def onboarding_exceptions(employee_id: str):
    _validate_employee_id(employee_id)
    return {"exceptions": get_onboarding_exceptions(employee_id)}


@app.get("/api/onboarding/{employee_id}/profile")
def employee_profile(employee_id: str):
    _validate_employee_id(employee_id)
    return get_employee_profile(employee_id)


@app.post("/api/onboarding/{employee_id}/profile")
def update_employee_profile(
    employee_id: str,
    body: EmployeeProfileRequest,
    api_key: str | None = Security(admin_key_header),
):
    _validate_employee_id(employee_id)
    _require_admin(api_key)
    result = upsert_employee_profile(employee_id, **body.model_dump(exclude_none=True))
    _audit_log("employee_profile_updated", employee_id=employee_id, details=result)
    return result


@app.post("/api/onboarding/{employee_id}/tasks/{task_id}/complete")
def mark_task_complete(
    employee_id: str,
    task_id: int,
    body: CompleteTaskRequest | None = None,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    result = complete_task(task_id, employee_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    _audit_log("task_completed", employee_id=employee_id, performed_by=user.get("sub", "api"), details={"task_id": task_id})
    return result


@app.post("/api/onboarding/{employee_id}/reset")
def reset_onboarding(
    employee_id: str,
    http_request: Request,
    api_key: str | None = Security(admin_key_header),
    user: dict[str, Any] | None = Security(get_current_user_optional),
):
    _validate_employee_id(employee_id)
    _require_admin(api_key, user)
    reset_employee_data(employee_id)
    _audit_log("onboarding_reset", employee_id=employee_id, performed_by=user.get("sub", "admin") if user else "admin")
    return {"status": "reset", "employee_id": employee_id}


@app.get("/api/admin/checkins")
def admin_checkins(
    http_request: Request,
    employee_id: str | None = None,
    api_key: str | None = Security(admin_key_header),
    user: dict[str, Any] | None = Security(get_current_user_optional),
):
    _require_admin(api_key, user)
    if employee_id:
        _validate_employee_id(employee_id)
    _audit_log("admin_checkins_viewed", employee_id=employee_id, performed_by=user.get("sub", "admin") if user else "admin")
    return {"checkins": list_checkins(employee_id)}


@app.get("/api/admin/audit-logs")
def admin_audit_logs(
    http_request: Request,
    limit: int = 100,
    api_key: str | None = Security(admin_key_header),
    user: dict[str, Any] | None = Security(get_current_user_optional),
):
    _require_admin(api_key, user)
    try:
        from shared.db import get_connection
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, action, employee_id, performed_by, details, created_at
                    FROM audit_logs
                    ORDER BY created_at DESC
                    LIMIT %s
                    """,
                    (min(limit, 500),),
                )
                rows = cur.fetchall()
        return {"audit_logs": [dict(row) for row in rows]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/admin/approvals")
def admin_approvals(
    employee_id: str | None = None,
    api_key: str | None = Security(admin_key_header),
    user: dict[str, Any] | None = Security(get_current_user_optional),
):
    _require_admin(api_key, user)
    if employee_id:
        _validate_employee_id(employee_id)
    return {"approvals": list_approvals(employee_id)}


@app.post("/api/admin/approvals/{approval_id}/decision")
def admin_decide_approval(
    approval_id: int,
    body: ApprovalDecisionRequest,
    api_key: str | None = Security(admin_key_header),
    user: dict[str, Any] | None = Security(get_current_user_optional),
):
    _require_admin(api_key, user)
    try:
        result = decide_approval(approval_id, body.status, body.approved_by)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=404, detail="Approval request not found or already decided")
    _audit_log("approval_decided", employee_id=result["employee_id"], performed_by=body.approved_by, details=result)
    return result


@app.get("/api/admin/executions")
def admin_executions(
    employee_id: str | None = None,
    api_key: str | None = Security(admin_key_header),
    user: dict[str, Any] | None = Security(get_current_user_optional),
):
    _require_admin(api_key, user)
    if employee_id:
        _validate_employee_id(employee_id)
    return {"executions": list_executions(employee_id)}


@app.get("/api/onboarding/{employee_id}/equipment")
def get_equipment(
    employee_id: str,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    from shared.equipment import get_equipment_allocations
    return {"equipment": get_equipment_allocations(employee_id)}


@app.post("/api/onboarding/{employee_id}/equipment/request")
def request_new_equipment(
    employee_id: str,
    body: EquipmentRequest,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    from shared.equipment import request_equipment
    try:
        result = request_equipment(employee_id, body.item_type, body.item_name)
        _audit_log("equipment_requested", employee_id=employee_id, performed_by=user.get("sub", "api"), details=result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.post("/api/admin/equipment/{equipment_id}/status")
def update_equipment_request_status(
    equipment_id: int,
    body: EquipmentStatusUpdateRequest,
    api_key: str | None = Security(admin_key_header),
    user: dict[str, Any] | None = Security(get_current_user_optional),
):
    """Admin/IT approval endpoint to update equipment status (pending -> allocated / delivered)."""
    _require_admin(api_key, user)
    from shared.equipment import update_equipment_status
    try:
        updated = update_equipment_status(equipment_id, body.status)
        if not updated:
            raise HTTPException(status_code=404, detail="Equipment allocation not found")
        _audit_log(
            "equipment_status_updated",
            employee_id=updated.get("employee_id"),
            performed_by=user.get("sub", "admin") if user else "admin",
            details=updated,
        )
        return updated
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e



@app.get("/api/onboarding/{employee_id}/trainings")
def get_trainings(
    employee_id: str,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    from shared.training import auto_assign_standard_trainings, list_training_assignments
    trainings = list_training_assignments(employee_id)
    if not trainings:
        trainings = auto_assign_standard_trainings(employee_id)
    return {"trainings": trainings}


@app.post("/api/onboarding/{employee_id}/trainings/{training_id}/complete")
def complete_training_task(
    employee_id: str,
    training_id: int,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    from shared.training import complete_training
    result = complete_training(training_id, employee_id)
    if not result:
        raise HTTPException(status_code=404, detail="Training assignment not found")
    _audit_log("training_completed", employee_id=employee_id, performed_by=user.get("sub", "api"), details={"training_id": training_id})
    return result


@app.get("/api/onboarding/{employee_id}/assignments")
def get_assignments(
    employee_id: str,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    from shared.assignments import get_employee_assignment
    return get_employee_assignment(employee_id)


@app.post("/api/onboarding/{employee_id}/assignments")
def update_assignments(
    employee_id: str,
    body: AssignmentUpdateRequest,
    api_key: str | None = Security(admin_key_header),
    user: dict[str, Any] | None = Security(get_current_user_optional),
):
    _validate_employee_id(employee_id)
    _require_admin(api_key, user)
    from shared.assignments import set_employee_assignment
    result = set_employee_assignment(
        employee_id,
        manager_name=body.manager_name,
        manager_email=body.manager_email,
        buddy_name=body.buddy_name,
        buddy_email=body.buddy_email,
        location=body.location,
        worker_type=body.worker_type,
        department=body.department,
        onboarding_stage=body.onboarding_stage,
    )
    _audit_log("assignments_updated", employee_id=employee_id, performed_by=user.get("sub", "admin") if user else "admin", details=result)
    return result


@app.patch("/api/onboarding/{employee_id}/persona")
def update_persona(
    employee_id: str,
    body: PersonaUpdateRequest,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    from shared.assignments import set_employee_assignment
    result = set_employee_assignment(
        employee_id,
        location=body.location,
        worker_type=body.worker_type,
        department=body.department,
        onboarding_stage=body.onboarding_stage,
    )
    _audit_log("persona_updated", employee_id=employee_id, performed_by=user.get("sub", employee_id), details=result)
    return result


# ── Phase 1: Payroll Endpoints ──────────────────────────────────────────────

@app.get("/api/onboarding/{employee_id}/payroll")
def get_payroll(
    employee_id: str,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    from shared.payroll import get_payroll_profile
    return get_payroll_profile(employee_id)


@app.post("/api/onboarding/{employee_id}/payroll/submit")
def submit_payroll(
    employee_id: str,
    body: PayrollSubmitRequest,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    from shared.payroll import submit_payroll_details
    try:
        result = submit_payroll_details(
            employee_id,
            bank_name=body.bank_name,
            account_number_last4=body.account_number_last4,
            routing_or_ifsc_code=body.routing_or_ifsc_code,
            tax_filing_status=body.tax_filing_status,
            currency=body.currency,
            allowances=body.withholding_allowances,
        )
        create_approval(
            employee_id,
            action="Review payroll details",
            resource_type="payroll",
            resource_id=employee_id,
            reason="Payroll details submitted and awaiting HR verification.",
        )
        _audit_log("payroll_submitted", employee_id=employee_id, performed_by=user.get("sub", "api"), details={"bank": body.bank_name})
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


# ── Phase 1: Document Endpoints ─────────────────────────────────────────────

@app.get("/api/onboarding/{employee_id}/documents")
def get_documents(
    employee_id: str,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    from shared.documents import list_employee_documents
    from shared.assignments import get_employee_assignment
    try:
        assignment = get_employee_assignment(employee_id)
        location = assignment.get("location", "Finland")
    except Exception:
        location = "Finland"
    return {"documents": list_employee_documents(employee_id, location=location)}


@app.post("/api/onboarding/{employee_id}/documents/sign")
def sign_employee_document(
    employee_id: str,
    body: DocumentSignRequest,
    user: dict[str, Any] = Security(get_current_user),
):
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)
    from shared.documents import sign_document
    result = sign_document(employee_id, body.document_code)
    if not result:
        raise HTTPException(status_code=404, detail=f"Document '{body.document_code}' not found for this employee")
    _audit_log("document_signed", employee_id=employee_id, performed_by=user.get("sub", "api"), details={"document_code": body.document_code})
    return result


# ── Phase 3: HITL Action Execution Endpoint ──────────────────────────────────

@app.post("/api/onboarding/{employee_id}/actions/execute")
def execute_confirmed_action(
    employee_id: str,
    body: ActionExecuteRequest,
    user: dict[str, Any] = Security(get_current_user),
):
    """Execute a user-confirmed action proposal (equipment request, check-in scheduling)."""
    _validate_employee_id(employee_id)
    require_employee_access(employee_id, user)

    if body.action_type == "request_equipment":
        from shared.equipment import request_equipment
        try:
            result = request_equipment(
                employee_id,
                body.payload.get("item_type", "other"),
                body.payload.get("item_name", "Unknown"),
            )
            _audit_log("equipment_requested", employee_id=employee_id, performed_by="user", details=result)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    elif body.action_type == "schedule_checkin":
        from shared.tasks import schedule_checkin
        try:
            result = schedule_checkin(
                employee_id,
                int(body.payload.get("day", 1)),
                str(body.payload.get("topic", "Check-in")),
            )
            _audit_log("checkin_scheduled", employee_id=employee_id, performed_by="user", details=result)
            return result
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e)) from e
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action_type: {body.action_type}")


@app.get("/api/evals/results")
def eval_results():
    return load_eval_reports()


@app.get("/api/employee/demo")
def demo_employee() -> dict[str, Any]:
    return demo_employee_by_id(DEFAULT_EMPLOYEE_ID)


def demo_employee_by_id(employee_id: str) -> dict[str, Any]:
    profile = next((item for item in list_demo_profiles() if item["employee_id"] == employee_id), None)
    if not profile:
        raise HTTPException(status_code=404, detail="Demo employee not found")
    try:
        from shared.assignments import get_employee_assignment
        assignment = get_employee_assignment(employee_id)
        location = assignment.get("location", "Finland")
        manager = assignment.get("manager_name", "Sarah Johnson")
        buddy = assignment.get("buddy_name", "Marcus Lee")
    except Exception:
        location = "Finland"
        manager = "Sarah Johnson"
        buddy = "Marcus Lee"

    demo_token = create_token(employee_id, "employee")
    return {
        "id": employee_id,
        "name": profile["name"],
        "role": profile["role"],
        "start_day": 1,
        "company": "Dayforce",
        "location": profile["location"] or location,
        "manager": manager,
        "buddy": buddy,
        "access_token": demo_token,
    }


@app.get("/api/employees/demo")
def demo_employees() -> dict[str, Any]:
    return {
        "employees": [
            {
                **profile,
                "id": profile["employee_id"],
                "access_token": create_token(profile["employee_id"], "employee"),
            }
            for profile in list_demo_profiles()
        ]
    }


@app.get("/api/employee/demo/{employee_id}")
def demo_employee_selected(employee_id: str) -> dict[str, Any]:
    return demo_employee_by_id(employee_id)
