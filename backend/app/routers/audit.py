from datetime import datetime, timedelta
import re
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.supabase_client import supabase
from app.security import require_roles, CurrentUser

router = APIRouter(prefix="/api", tags=["audit"])


def _sanitize_q(q: str) -> str:
    """Strip characters that would break a PostgREST or=/ilike filter."""
    return re.sub(r"[,%_]", " ", q).strip()[:80]


def _valid_date(value: Optional[str]) -> bool:
    if not value:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


@router.get("/audit-logs")
def list_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    actor_id: Optional[str] = Query(None, description="filter by acting user id"),
    action: Optional[str] = Query(None, description="substring match on action name"),
    reference: Optional[str] = Query(None, description="substring match on entity id"),
    q: Optional[str] = Query(None, description="free text: action name OR entity id"),
    entity_type: Optional[str] = None,
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    current_user: CurrentUser = Depends(
        require_roles("panchayat_staff", "panchayat_admin", "system_admin")
    ),
):
    """Audit trail with filters. Includes ip_address / user_agent columns
    (captured at write time for security auditing — not shown to citizens)."""
    query = supabase.table("audit_logs").select("*", count="exact")

    if actor_id:
        # full or partial user id (audit_logs has no actor_name column)
        query = query.ilike("actor_id", f"%{actor_id.strip()[:80]}%")
    if action:
        query = query.ilike("action", f"%{action.strip()[:60]}%")
    if reference:
        query = query.ilike("entity_id", f"%{reference.strip()[:80]}%")
    if q:
        term = _sanitize_q(q)
        if term:
            query = query.or_(f"action.ilike.%{term}%,entity_id.ilike.%{term}%,actor_id.ilike.%{term}%")
    if entity_type:
        query = query.eq("entity_type", entity_type.strip())
    if _valid_date(date_from):
        query = query.gte("timestamp", f"{date_from}T00:00:00")
    if _valid_date(date_to):
        # inclusive end-of-day
        end = (datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        query = query.lt("timestamp", f"{end}T00:00:00")

    try:
        result = query.order("timestamp", desc=True).limit(limit).execute()
    except Exception:
        # Legacy fallback (e.g. view-based deployments without filter support)
        result = (
            supabase.table("audit_logs")
            .select("*", count="exact")
            .order("timestamp", desc=True)
            .limit(limit)
            .execute()
        )

    return {
        "results": result.data,
        "total": result.count if result.count is not None else len(result.data),
        "limit": limit,
    }
