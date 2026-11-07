"""Deterministic Compliance Engine for OnboardAI.

Enforces prerequisite checks and timeline validation independently of the LLM.
All decisions are made in Python — the LLM cannot override these gates.
"""
from __future__ import annotations

from typing import Any


# Resources that require Security Awareness Training to be completed first
_SECURITY_GATED_RESOURCES = frozenset({
    "github", "cloud", "aws", "gcp", "azure",
    "production", "prod", "kubernetes", "k8s",
    "deploy", "ci/cd", "pipeline",
})


class ComplianceEngine:
    """Deterministic compliance gate — enforced server-side, not by the LLM."""

    @staticmethod
    def check_system_access_prerequisites(
        employee_id: str,
        target_resource: str,
    ) -> tuple[bool, str]:
        """Check whether the employee may access the requested resource.

        Returns (True, "") if access is allowed, or (False, reason) if blocked.

        Currently enforces: Security Awareness Training must be complete before
        accessing GitHub, cloud environments, AWS, or production systems.
        """
        resource_lower = target_resource.lower()
        is_security_gated = any(kw in resource_lower for kw in _SECURITY_GATED_RESOURCES)

        if not is_security_gated:
            return True, ""

        # Check training completion
        try:
            from shared.training import list_training_assignments
            trainings: list[dict[str, Any]] = list_training_assignments(employee_id)
            security_training = next(
                (t for t in trainings if "security" in t.get("training_name", "").lower()),
                None,
            )
            if security_training and security_training.get("status") == "completed":
                return True, ""
            return (
                False,
                "Policy Block: Security Awareness Training must be completed before "
                f"accessing '{target_resource}'. "
                "Please complete the Security Awareness Training module first.",
            )
        except Exception:
            # Fail-safe: block access if we cannot verify training status
            return (
                False,
                "Policy Block: Unable to verify Security Awareness Training status. "
                "Please contact HR to confirm training completion before accessing this resource.",
            )

    @staticmethod
    def validate_action_timeline(day: int) -> tuple[bool, str]:
        """Validate that an action falls within the allowed onboarding timeline (days 1–90).

        Returns (True, "") if valid, or (False, reason) if out of range.
        """
        try:
            day_int = int(day)
        except (ValueError, TypeError):
            return False, "Invalid day value: must be an integer."

        if day_int < 1:
            return False, f"Day {day_int} is before onboarding start. Valid range is Day 1 to Day 90."
        if day_int > 90:
            return False, f"Day {day_int} exceeds the 90-day onboarding window. Contact HR for extended support."
        return True, ""

    @staticmethod
    def get_worker_type_restrictions(worker_type: str) -> dict[str, Any]:
        """Return benefit restrictions based on worker type.

        FTEs receive full benefits; Contractors and Interns have restrictions.
        """
        wt = worker_type.lower().strip()
        if wt == "fte":
            return {
                "worker_type": "fte",
                "label": "Full-Time Employee",
                "healthcare": True,
                "pension_401k": True,
                "pto_days": 25,
                "equity": True,
                "equipment_tier": "premium",
                "notes": "Full benefit package applies.",
            }
        elif wt == "contractor":
            return {
                "worker_type": "contractor",
                "label": "Contractor (1099/B2B)",
                "healthcare": False,
                "pension_401k": False,
                "pto_days": 0,
                "equity": False,
                "equipment_tier": "byod",
                "notes": (
                    "Contractors are not eligible for company healthcare, 401(k)/pension, "
                    "PTO, or equity. Use BYOD or VDI. Submit invoices via Accounts Payable."
                ),
            }
        elif wt == "intern":
            return {
                "worker_type": "intern",
                "label": "Intern",
                "healthcare": False,
                "pension_401k": False,
                "pto_days": 10,
                "equity": False,
                "equipment_tier": "standard",
                "notes": (
                    "Interns receive a standard laptop and limited PTO. "
                    "No healthcare or pension benefits."
                ),
            }
        else:
            return {
                "worker_type": wt,
                "label": "Unknown",
                "notes": f"Worker type '{wt}' not recognised. Contact HR.",
            }

