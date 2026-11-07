from __future__ import annotations

import json
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
from shared.config import ADMIN_API_KEY, ALLOWED_ORIGINS, DEFAULT_EMPLOYEE_ID
from shared.eval_results import load_eval_reports
from shared.tasks import complete_task, get_onboarding_status, list_checkins, reset_employee_data


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
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


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


def _require_admin(api_key: str | None) -> None:
    """Raise 403 if admin key is configured and the provided key doesn't match."""
    if not ADMIN_API_KEY:
        # Admin key not configured — dev mode, allow access
        return
    if not api_key or api_key != ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Admin access requires a valid X-Admin-Key header.")


# ─── Audit Logging ──────────────────────────────────────────────────────────────

def _audit_log(action: str, employee_id: str | None = None, performed_by: str = "api", details: dict | None = None) -> None:
    """Write an audit log entry to the database. Fails silently to not break main flow."""
    try:
        from shared.db import get_connection, _now_iso
        import json as _json
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_logs (action, employee_id, performed_by, details, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (action, employee_id, performed_by, _json.dumps(details or {}), _now_iso()),
                )
            conn.commit()
    except Exception:
        pass  # Audit failures must not break core functionality


# ─── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    from shared.db import init_db
    init_db()
    yield


# ─── App ────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="OnboardAI API",
    description="Autonomous HR onboarding agent",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if "*" in ALLOWED_ORIGINS else ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Models ──────────────────────────────────────────────────────────────

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


class AssignmentUpdateRequest(BaseModel):
    manager_name: str | None = None
    manager_email: str | None = None
    buddy_name: str | None = None
    buddy_email: str | None = None
    location: str | None = None


def _validate_chat_request(request: ChatRequest) -> list[dict]:
    validate_message_length(request.message)
    for msg in request.history:
        validate_message_length(msg.content)
    return [m.model_dump() for m in request.history]


# ─── Routes ──────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/chat")
def chat(request: ChatRequest, http_request: Request):
    ip = _get_client_ip(http_request)
    if not _check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait before sending another message.")
    _validate_employee_id(request.employee_id)
    try:
        history = _validate_chat_request(request)
        result = run_agent(request.message, request.employee_id, history)
        return result
    except InputValidationError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/chat/stream")
async def chat_stream(request: ChatRequest, http_request: Request):
    ip = _get_client_ip(http_request)
    if not _check_rate_limit(ip):
        raise HTTPException(status_code=429, detail="Rate limit exceeded. Please wait before sending another message.")
    _validate_employee_id(request.employee_id)
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
def onboarding_status(employee_id: str):
    _validate_employee_id(employee_id)
    return get_onboarding_status(employee_id)


@app.post("/api/onboarding/{employee_id}/tasks/{task_id}/complete")
def mark_task_complete(employee_id: str, task_id: int, body: CompleteTaskRequest | None = None):
    _validate_employee_id(employee_id)
    result = complete_task(task_id, employee_id)
    if not result:
        raise HTTPException(status_code=404, detail="Task not found")
    _audit_log("task_completed", employee_id=employee_id, details={"task_id": task_id})
    return result


@app.post("/api/onboarding/{employee_id}/reset")
def reset_onboarding(
    employee_id: str,
    http_request: Request,
    api_key: str | None = Security(admin_key_header),
):
    _validate_employee_id(employee_id)
    _require_admin(api_key)
    reset_employee_data(employee_id)
    _audit_log("onboarding_reset", employee_id=employee_id, performed_by="admin")
    return {"status": "reset", "employee_id": employee_id}


@app.get("/api/admin/checkins")
def admin_checkins(
    http_request: Request,
    employee_id: str | None = None,
    api_key: str | None = Security(admin_key_header),
):
    _require_admin(api_key)
    if employee_id:
        _validate_employee_id(employee_id)
    _audit_log("admin_checkins_viewed", employee_id=employee_id, performed_by="admin")
    return {"checkins": list_checkins(employee_id)}


@app.get("/api/admin/audit-logs")
def admin_audit_logs(
    http_request: Request,
    limit: int = 100,
    api_key: str | None = Security(admin_key_header),
):
    _require_admin(api_key)
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


@app.get("/api/onboarding/{employee_id}/equipment")
def get_equipment(employee_id: str):
    _validate_employee_id(employee_id)
    from shared.equipment import get_equipment_allocations
    return {"equipment": get_equipment_allocations(employee_id)}


@app.post("/api/onboarding/{employee_id}/equipment/request")
def request_new_equipment(employee_id: str, body: EquipmentRequest):
    _validate_employee_id(employee_id)
    from shared.equipment import request_equipment
    try:
        result = request_equipment(employee_id, body.item_type, body.item_name)
        _audit_log("equipment_requested", employee_id=employee_id, details=result)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@app.get("/api/onboarding/{employee_id}/trainings")
def get_trainings(employee_id: str):
    _validate_employee_id(employee_id)
    from shared.training import auto_assign_standard_trainings, list_training_assignments
    trainings = list_training_assignments(employee_id)
    if not trainings:
        trainings = auto_assign_standard_trainings(employee_id)
    return {"trainings": trainings}


@app.post("/api/onboarding/{employee_id}/trainings/{training_id}/complete")
def complete_training_task(employee_id: str, training_id: int):
    _validate_employee_id(employee_id)
    from shared.training import complete_training
    result = complete_training(training_id, employee_id)
    if not result:
        raise HTTPException(status_code=404, detail="Training assignment not found")
    _audit_log("training_completed", employee_id=employee_id, details={"training_id": training_id})
    return result


@app.get("/api/onboarding/{employee_id}/assignments")
def get_assignments(employee_id: str):
    _validate_employee_id(employee_id)
    from shared.assignments import get_employee_assignment
    return get_employee_assignment(employee_id)


@app.post("/api/onboarding/{employee_id}/assignments")
def update_assignments(
    employee_id: str,
    body: AssignmentUpdateRequest,
    api_key: str | None = Security(admin_key_header),
):
    _validate_employee_id(employee_id)
    _require_admin(api_key)
    from shared.assignments import set_employee_assignment
    result = set_employee_assignment(
        employee_id,
        manager_name=body.manager_name,
        manager_email=body.manager_email,
        buddy_name=body.buddy_name,
        buddy_email=body.buddy_email,
        location=body.location,
    )
    _audit_log("assignments_updated", employee_id=employee_id, details=result)
    return result


@app.get("/api/evals/results")
def eval_results():
    return load_eval_reports()


@app.get("/api/employee/demo")
def demo_employee() -> dict[str, Any]:
    try:
        from shared.assignments import get_employee_assignment
        assignment = get_employee_assignment(DEFAULT_EMPLOYEE_ID)
        location = assignment.get("location", "Finland")
        manager = assignment.get("manager_name", "Sarah Johnson")
        buddy = assignment.get("buddy_name", "Marcus Lee")
    except Exception:
        location = "Finland"
        manager = "Sarah Johnson"
        buddy = "Marcus Lee"

    return {
        "id": DEFAULT_EMPLOYEE_ID,
        "name": "Alex Chen",
        "role": "Software Engineer",
        "start_day": 1,
        "company": "Acme Corp",
        "location": location,
        "manager": manager,
        "buddy": buddy,
    }
