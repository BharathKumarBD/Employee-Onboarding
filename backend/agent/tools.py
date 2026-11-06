from __future__ import annotations

import json
from typing import Any

from langchain_core.tools import tool

from agent.security import MAX_TASKS_PER_REQUEST
from shared.assignments import get_employee_assignment, set_employee_assignment
from shared.equipment import get_equipment_allocations, request_equipment
from shared.rag import format_search_results, search_handbook, search_handbook_with_location
from shared.tasks import (
    complete_task,
    create_onboarding_task,
    get_onboarding_status,
    list_onboarding_tasks,
    schedule_checkin,
)
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
        if location:
            results = search_handbook_with_location(query, location)
        else:
            results = search_handbook(query)
        return format_search_results(results)

    return [search_handbook_tool]


def build_workflow_tools(employee_id: str, injection_suspected: bool = False):
    tasks_created = 0

    @tool
    def create_onboarding_task_tool(title: str, due_day: int, category: str) -> str:
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
            task = create_onboarding_task(employee_id, title, due_day, category)
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
        or similar scheduling requests. The day parameter is the onboarding day number (1-90)."""
        if injection_suspected:
            return WRITE_BLOCKED_MSG
        try:
            result = schedule_checkin(employee_id, day, topic)
        except ValueError as exc:
            return f"Invalid check-in: {exc}"
        return json.dumps(result, default=str)

    @tool
    def get_equipment_status_tool() -> str:
        """Get the equipment allocation status for the current employee. 
        Use when asked about laptop, ID card, accessories, monitors, or any equipment."""
        allocations = get_equipment_allocations(employee_id)
        if not allocations:
            return "No equipment allocations found. Standard equipment (laptop, ID card) is typically arranged by IT before your start date. Contact it-help@acmecorp.com to check status."
        return json.dumps(allocations, default=str)

    @tool
    def request_equipment_tool(item_type: str, item_name: str) -> str:
        """Request equipment allocation for the employee. 
        item_type must be one of: laptop, id_card, monitor, keyboard, mouse, headset, desk_phone, other.
        item_name is the specific item description (e.g. 'MacBook Pro 14-inch M3').
        Use when employee asks to request or needs equipment."""
        if injection_suspected:
            return WRITE_BLOCKED_MSG
        try:
            result = request_equipment(employee_id, item_type, item_name)
        except ValueError as exc:
            return f"Invalid equipment request: {exc}"
        return json.dumps(result, default=str)

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
            result = assign_training(employee_id, training_name, due_day)
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
    ]


def build_all_tools(employee_id: str, injection_suspected: bool = False) -> list[Any]:
    return build_research_tools() + build_workflow_tools(employee_id, injection_suspected)
