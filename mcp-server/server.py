import json
from mcp.server.fastmcp import FastMCP

from shared.config import DEFAULT_EMPLOYEE_ID
from shared.equipment import get_equipment_allocations, request_equipment
from shared.rag import format_search_results, search_handbook, search_handbook_with_location
from shared.tasks import (
    create_onboarding_task,
    list_onboarding_tasks,
    schedule_checkin,
)
from shared.training import auto_assign_standard_trainings, list_training_assignments

mcp = FastMCP("hr-onboarding")


@mcp.tool()
def search_handbook_tool(query: str, location: str | None = None) -> str:
    """Search HR handbook documents for policy and onboarding information. Returns cited excerpts.
    Optionally supply employee location (e.g. 'India', 'USA', 'Finland') for location-specific policies."""
    if location:
        results = search_handbook_with_location(query, location)
    else:
        results = search_handbook(query)
    return format_search_results(results)


@mcp.tool()
def create_onboarding_task_tool(
    title: str,
    due_day: int,
    category: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
) -> str:
    """Create an onboarding task for an employee. Category must be HR, IT, or Team."""
    task = create_onboarding_task(employee_id, title, due_day, category)
    return f"Created task #{task['id']}: {task['title']} (due day {task['due_day']}, {task['category']})"


@mcp.tool()
def list_onboarding_tasks_tool(employee_id: str = DEFAULT_EMPLOYEE_ID) -> str:
    """List all onboarding tasks for an employee with status."""
    tasks = list_onboarding_tasks(employee_id)
    if not tasks:
        return "No onboarding tasks yet."
    lines = [
        f"- [{t['status']}] #{t['id']} Day {t['due_day']} ({t['category']}): {t['title']}"
        for t in tasks
    ]
    return "\n".join(lines)


@mcp.tool()
def schedule_checkin_tool(
    day: int,
    topic: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
) -> str:
    """Schedule a manager or HR check-in for a specific onboarding day."""
    result = schedule_checkin(employee_id, day, topic)
    return result["message"]


@mcp.tool()
def get_equipment_status_tool(employee_id: str = DEFAULT_EMPLOYEE_ID) -> str:
    """Get the equipment allocation status for an employee (laptop, ID card, peripherals)."""
    allocations = get_equipment_allocations(employee_id)
    if not allocations:
        return "No equipment allocations found. Standard equipment is arranged before start date. Contact it-help@acmecorp.com."
    return json.dumps(allocations, default=str)


@mcp.tool()
def request_equipment_tool(
    item_type: str,
    item_name: str,
    employee_id: str = DEFAULT_EMPLOYEE_ID,
) -> str:
    """Request equipment for an employee (laptop, id_card, monitor, keyboard, mouse, headset, etc.)."""
    result = request_equipment(employee_id, item_type, item_name)
    return result["message"]


@mcp.tool()
def list_training_assignments_tool(employee_id: str = DEFAULT_EMPLOYEE_ID) -> str:
    """List mandatory training assignments and status for an employee."""
    trainings = list_training_assignments(employee_id)
    if not trainings:
        trainings = auto_assign_standard_trainings(employee_id)
    return json.dumps(trainings, default=str)


if __name__ == "__main__":
    mcp.run()

