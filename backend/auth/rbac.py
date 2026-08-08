import logging
from enum import Enum
from typing import Optional, Dict, Any
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class OrgRole(str, Enum):
    ADMIN = "admin"
    MEMBER = "member"
    VIEWER = "viewer"

ROLE_HIERARCHY = {
    OrgRole.ADMIN: 3,
    OrgRole.MEMBER: 2,
    OrgRole.VIEWER: 1,
}

async def require_run_access(
    run_id: str,
    user: Dict[str, Any],
    min_role: OrgRole = OrgRole.VIEWER,
) -> Dict[str, Any]:
    """
    Verify the authenticated user's org owns this run.
    Returns the run dict if access is granted.
    Raises 403/404 otherwise.
    """
    from db.runs_repository import RunsRepository
    run = await RunsRepository.get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # If run has no org_id, it's accessible to all authenticated users
    run_org = run.get("org_id")
    user_org = user.get("org_id")

    if run_org and user_org and str(run_org) != str(user_org):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this optimization run"
        )

    return run

def check_role(user: Dict[str, Any], required_role: OrgRole) -> bool:
    """Check if a user has at least the required role."""
    user_role = user.get("role", OrgRole.VIEWER)
    return ROLE_HIERARCHY.get(OrgRole(user_role), 0) >= ROLE_HIERARCHY.get(required_role, 0)
