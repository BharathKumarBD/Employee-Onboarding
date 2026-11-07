from __future__ import annotations

import json
import uuid
from typing import Any

from langchain_core.tools import tool

from agent.security import MAX_TASKS_PER_REQUEST
from shared.assignments import get_employee_assignment, set_employee_assignment
from shared.documents import list_employee_documents, sign_document
from shared.equipment import get_equipment_allocations, request_equipment
from shared.payroll import get_payroll_profile, submit_payroll_details
from shared.rag import format_search_results, search_handbook, search_handbook_with_location
from shared.tasks import (
    complete_task,
    create_onboarding_task,
    get_onboarding_status,
    list_onboarding_tasks,
    schedule_checkin,
)
from shared.profiles import get_employee_profile
from shared.onboarding_operations import create_approval
from shared.training import (
    assign_training,
    auto_assign_standard_trainings,
    list_training_assignments,
)

WRITE_BLOCKED_MSG = (
    "Action blocked: this request was flagged as a potential prompt-injection attempt. "
    "Read-only operations are still available."
)


def build_research_tools():
    @tool
    def search_handbook_tool(query: str, location: str | None = None) -> str:
        """Search HR handbook documents, IT setup guides, benefits information, location guides (India, USA, etc.), and onboarding checklists 
        for policy and onboarding information. Use this for: Slack channels, office locations, headquarters, 
        IT helpdesk contacts, remote work policy, benefits, PTO, onboarding buddy timing or schedule, location-specific policies (holidays, statutory benefits, leave),
        and any factual HR or IT question."""
        # Sanitize query input
        query_clean = str(query).strip()[:500]
        loc_clean = str(location).strip()[:50] if location else None
        if loc_clean:
            results = search_handbook_with_location(query_clean, loc_clean)
        else:
            results = search_handbook(query_clean)
        return format_search_results(results)

    return [search_handbook_tool]


def build_workflow_tools(employee_id: str, injection_suspected: bool = False):
    tasks_created = 0

    @tool
    def create_onboarding_task_tool(
        title: str,
        due_day: int,
        category: str,
        required: bool = False,
        owner: str = "employee",
        depends_on: list[int] | None = None,
    ) -> str:
        """Create an onboarding task to track in the employee's checklist. 
        Category must be: HR, IT, or Team.
        Do NOT use this for scheduling check-ins or meetings — use schedule_checkin_tool for those.
        Use this for tasks like: complete HR paperwork, set up laptop, enroll in health insurance."""
        nonlocal tasks_created
        if injection_suspected:
            return WRITE_BLOCKED_MSG
        if tasks_created >= MAX_TASKS_PER_REQUEST:
            return f"Task limit reached ({MAX_TASKS_PER_REQUEST} per message)."
        try:
            due_day_int = int(due_day)
        except (ValueError, TypeError):
            return "Invalid due_day: must be an integer between 1 and 90."
        clean_title = str(title).strip()
        clean_cat = str(category).strip()
        try:
            profile = get_employee_profile(employee_id)
            task = create_onboarding_task(
                employee_id,
                clean_title,
                due_day_int,
                clean_cat,
                role=profile.get("role"),
                department=profile.get("department"),
                required=required,
                owner=owner,
                depends_on=depends_on,
            )
        except ValueError as exc:
            return f"Invalid task: {exc}"
        tasks_created += 1
        return json.dumps(task, default=str)

    @tool
    def list_onboarding_tasks_tool() -> str:
        """List all onboarding tasks for the current employee."""
        tasks = list_onboarding_tasks(employee_id)
        return json.dumps(tasks, default=str)

    @tool
    def get_onboarding_status_tool() -> str:
        """Get the current onboarding progress and completion percentage for the employee."""
        status = get_onboarding_status(employee_id)
        return json.dumps(status, default=str)

    @tool
    def complete_onboarding_task_tool(task_id: int) -> str:
        """Mark an onboarding task as completed by task ID."""
        if injection_suspected:
            return WRITE_BLOCKED_MSG
        result = complete_task(task_id, employee_id)
        if not result:
            return f"Task #{task_id} not found."
        return json.dumps(result, default=str)

    @tool
    def schedule_checkin_tool(day: int, topic: str) -> str:
        """Schedule a manager or HR check-in for a specific onboarding day. 
        Use this tool — NOT create_onboarding_task_tool — when the user explicitly says 
        'schedule a check-in', 'book a meeting', 'set up a check-in', 'meet with manager on day X', 
        or similar scheduling requests. The day parameter is the onboarding day number (1-90).
        Returns a HITL action proposal for the user to confirm before the meeting is booked."""
        if injection_suspected:
            return WRITE_BLOCKED_MSG
        try:
            day_int = int(day)
            if day_int < 1 or day_int > 90:
                return "Invalid day: must be an integer between 1 and 90."
        except (ValueError, TypeError):
            return "Invalid day: must be an integer between 1 and 90."
        clean_topic = str(topic).strip()
        if not clean_topic:
            return "Invalid check-in: Topic cannot be empty"
        # Phase 3 HITL: return a proposal for user confirmation
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        proposal = {
            "status": "proposed",
            "action_type": "schedule_checkin",
            "action_id": action_id,
            "title": f"Schedule Check-in: Day {day_int} — {clean_topic}",
            "details": {
                "day": day_int,
                "topic": clean_topic,
                "employee_id": employee_id,
            },
        }
        return json.dumps(proposal, default=str)

    @tool
    def get_equipment_status_tool() -> str:
        """Get the equipment allocation status for the current employee. 
        Use when asked about laptop, ID card, accessories, monitors, or any equipment."""
        allocations = get_equipment_allocations(employee_id)
        if not allocations:
            return "No equipment allocations found. Standard equipment (laptop, ID card) is typically arranged by IT before your start date. Contact it-help@dayforce.com to check status."
        return json.dumps(allocations, default=str)

    @tool
    def request_equipment_tool(item_type: str, item_name: str) -> str:
        """Request equipment allocation for the employee. 
        item_type must be one of: laptop, id_card, monitor, keyboard, mouse, headset, desk_phone, other.
        item_name is the specific item description (e.g. 'MacBook Pro 14-inch M3').
        Use when employee asks to request or needs equipment.
        Returns a HITL action proposal — the user must approve before the request is submitted."""
        if injection_suspected:
            return WRITE_BLOCKED_MSG
        clean_name = str(item_name).strip()
        if not clean_name:
            return "Invalid equipment request: Item name cannot be empty"
        if len(clean_name) > 200:
            return "Invalid equipment request: Item name too long (max 200 chars)"
        clean_type = str(item_type).strip().lower()
        from shared.equipment import VALID_ITEM_TYPES
        if clean_type not in VALID_ITEM_TYPES:
            clean_type = "other"
        # Phase 3 HITL: return a proposal for user confirmation
        action_id = f"act_{uuid.uuid4().hex[:8]}"
        proposal = {
            "status": "proposed",
            "action_type": "request_equipment",
            "action_id": action_id,
            "title": f"Equipment Request: {clean_name}",
            "details": {
                "item_type": clean_type,
                "item_name": clean_name,
                "approver": "IT Helpdesk",
                "employee_id": employee_id,
            },
        }
        return json.dumps(proposal, default=str)

    @tool
    def list_training_assignments_tool() -> str:
        """List all training assignments and completion status for the current employee. 
        Use when asked about training, learning modules, or mandatory courses."""
        trainings = list_training_assignments(employee_id)
        if not trainings:
            trainings = auto_assign_standard_trainings(employee_id)
            if trainings:
                return f"Standard onboarding trainings have been assigned:\n" + json.dumps(trainings, default=str)
            return "No training assignments found."
        return json.dumps(trainings, default=str)

    @tool
    def assign_training_tool(training_name: str, due_day: int) -> str:
        """Assign a new training course to the employee."""
        if injection_suspected:
            return WRITE_BLOCKED_MSG
        try:
            due_day_int = int(due_day)
        except (ValueError, TypeError):
            return "Invalid due_day: must be an integer between 1 and 90."
        clean_name = str(training_name).strip()
        try:
            result = assign_training(employee_id, clean_name, due_day_int)
            return json.dumps(result, default=str)
        except ValueError as exc:
            return f"Invalid training assignment: {exc}"

    @tool
    def get_manager_and_buddy_tool() -> str:
        """Get the assigned direct manager and onboarding buddy contact details for the employee.
        Use when asked 'who is my manager', 'who is my buddy', or for buddy contact info."""
        assignment = get_employee_assignment(employee_id)
        return json.dumps(assignment, default=str)

    @tool
    def assign_manager_or_buddy_tool(
        manager_name: str | None = None,
        manager_email: str | None = None,
        buddy_name: str | None = None,
        buddy_email: str | None = None,
    ) -> str:
        """Assign or update manager and buddy details for the current employee."""
        if injection_suspected:
            return WRITE_BLOCKED_MSG
        result = set_employee_assignment(
            employee_id,
            manager_name=manager_name,
            manager_email=manager_email,
            buddy_name=buddy_name,
            buddy_email=buddy_email,
        )
        return json.dumps(result, default=str)

    # ── Phase 1: Payroll & Document tools ─────────────────────────────────

    @tool
    def get_payroll_status_tool() -> str:
        """Get the current payroll/direct-deposit setup status for the employee.
        Use when asked about payroll, bank details, direct deposit, or salary setup."""
        profile = get_payroll_profile(employee_id)
        return json.dumps(profile, default=str)

    @tool
    def submit_direct_deposit_tool(
        bank_name: str,
        account_number_last4: str,
        routing_or_ifsc_code: str,
        tax_regime_or_w4: str,
    ) -> str:
        """Submit direct-deposit bank details and tax filing status for the employee.
        Only the LAST 4 DIGITS of the account number are accepted (for PII safety).
        routing_or_ifsc_code: US 9-digit ABA routing number for USD, Indian IFSC for INR.
        tax_regime_or_w4: e.g. 'W4_SINGLE', 'INDIA_NEW_REGIME', 'EU_STANDARD'."""
        if injection_suspected:
            return WRITE_BLOCKED_MSG
        try:
            # Infer currency from tax status if possible
            tax_upper = str(tax_regime_or_w4).strip().upper()
            if tax_upper.startswith("W4"):
                currency = "USD"
            elif tax_upper.startswith("INDIA"):
                currency = "INR"
            else:
                currency = "EUR"
            result = submit_payroll_details(
                employee_id,
                bank_name=str(bank_name).strip(),
                account_number_last4=str(account_number_last4).strip(),
                routing_or_ifsc_code=str(routing_or_ifsc_code).strip(),
                tax_filing_status=tax_upper,
                currency=currency,
            )
            create_approval(
                employee_id,
                action="Review payroll details",
                resource_type="payroll",
                resource_id=employee_id,
                reason="Payroll details submitted and awaiting HR verification.",
            )
            return json.dumps(result, default=str)
        except ValueError as exc:
            return f"Payroll submission error: {exc}"

    @tool
    def list_pending_documents_tool() -> str:
        """List all regulatory documents the employee needs to sign (NDA, I-9, handbook, etc.).
        Documents are auto-seeded based on the employee's location."""
        try:
            assignment = get_employee_assignment(employee_id)
            location = assignment.get("location", "Finland")
        except Exception:
            location = "Finland"
        docs = list_employee_documents(employee_id, location=location)
        return json.dumps(docs, default=str)

    @tool
    def sign_document_tool(document_code: str) -> str:
        """Electronically sign a regulatory document by its code (e.g. 'nda', 'i9_verification', 'handbook_ack').
        The document must exist for the employee (call list_pending_documents_tool first)."""
        if injection_suspected:
            return WRITE_BLOCKED_MSG
        result = sign_document(employee_id, document_code)
        if not result:
            return f"Document '{document_code}' not found. Use list_pending_documents_tool to see available documents."
    @tool
    def request_approval_tool(action: str, resource_type: str, reason: str) -> str:
        """Create a human approval request before a sensitive onboarding action."""
        if injection_suspected:
            return WRITE_BLOCKED_MSG
        result = create_approval(
            employee_id,
            action=action,
            resource_type=resource_type,
            reason=reason,
        )
        return json.dumps(result, default=str)

    return [
        create_onboarding_task_tool,
        list_onboarding_tasks_tool,
        get_onboarding_status_tool,
        complete_onboarding_task_tool,
        schedule_checkin_tool,
        get_equipment_status_tool,
        request_equipment_tool,
        list_training_assignments_tool,
        assign_training_tool,
        get_manager_and_buddy_tool,
        assign_manager_or_buddy_tool,
        get_payroll_status_tool,
        submit_direct_deposit_tool,
        list_pending_documents_tool,
        sign_document_tool,
        request_approval_tool,
    ]


def build_all_tools(employee_id: str, injection_suspected: bool = False) -> list[Any]:
    return build_research_tools() + build_workflow_tools(employee_id, injection_suspected)
