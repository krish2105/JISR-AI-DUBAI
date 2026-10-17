"""
rbac.py — Role-based access control: the permission table and the checks that use it.

Why a separate file from the policy engine: policies decide how risky an action is (deterministic YAML rules);
RBAC decides which person may act on it. A high-risk approval needs the Owner, whatever the policy said
(docs/PLAN_95.md §13b). The table lives in rbac.yaml so it is reviewable as data.
"""

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

RBAC_FILE = Path(__file__).with_name("rbac.yaml")
ROLES = ("owner", "admin", "approver", "operator", "accountant", "auditor", "viewer")


class RbacTable(BaseModel):
    """The parsed rbac.yaml."""

    roles: dict[str, dict]
    permissions: dict[str, list[str]]
    approval_by_risk: dict[str, str]

    def can(self, role: str, permission: str) -> bool:
        """True when the role holds the permission. Unknown permissions are denied (fail closed)."""
        return role in self.permissions.get(permission, [])

    def permissions_of(self, role: str) -> list[str]:
        """Every permission the role holds (sent to the dashboard to show or hide controls)."""
        return sorted(p for p, roles in self.permissions.items() if role in roles)

    def rank(self, role: str) -> int:
        return int(self.roles.get(role, {}).get("rank", 0))


@lru_cache
def get_rbac() -> RbacTable:
    """Load and validate rbac.yaml once."""
    data = yaml.safe_load(RBAC_FILE.read_text(encoding="utf-8"))
    table = RbacTable(**data)
    unknown = {r for roles in table.permissions.values() for r in roles} - set(ROLES)
    if unknown or set(table.roles) != set(ROLES):
        raise ValueError(f"rbac.yaml roles do not match {ROLES}: {unknown or set(table.roles)}")
    return table


class Forbidden(Exception):
    """The signed-in user's role does not allow this action (HTTP 403)."""


def approval_permission(risk: str, payload: dict | None) -> list[str]:
    """Permissions that allow deciding an approval of this risk; any one of them is enough."""
    rbac = get_rbac()
    needed = [rbac.approval_by_risk.get(risk, "approvals.decide_high")]   # unknown risk: strictest
    if (payload or {}).get("kind") == "collection_reminder" and risk != "high":
        needed.append("approvals.decide_collections")
    return needed


def check_approval(role: str, risk: str, payload: dict | None) -> None:
    """Raise Forbidden unless the role may decide an approval of this risk."""
    rbac = get_rbac()
    if not any(rbac.can(role, p) for p in approval_permission(risk, payload)):
        who = "the Owner" if risk == "high" else "an Owner, Admin or Approver"
        raise Forbidden(f"Only {who} can decide {risk}-risk actions (your role: {role}).")
