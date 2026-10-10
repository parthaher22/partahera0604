import re
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.audit_util import log_audit
from app.supabase_client import supabase
from app.schemas import ComplaintCreate, ComplaintStatusUpdate
from app.security import get_current_user, require_roles, CurrentUser

router = APIRouter(prefix="/api/complaints", tags=["complaints"])

STAFF_ROLES = ("panchayat_staff", "panchayat_admin", "system_admin")

# Three-part grievance tracking stages (Submitted / In Progress / Completed)
STAGE_STATUSES = {
    "submitted": ["Submitted", "Under Review", "Assigned"],
    "in_progress": ["In Progress"],
    "completed": ["Resolved", "Closed", "Rejected"],
}

SORTABLE_COLUMNS = {"submitted_at", "updated_at", "title", "status", "priority"}


def _sanitize_q(q: str) -> str:
    """Strip characters that would break a PostgREST or=/ilike filter."""
    return re.sub(r"[,%_]", " ", q).strip()[:80]


def _villager_id_for(user_id: str) -> str:
    row = supabase.table("villagers").select("villager_id").eq("user_id", user_id).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Villager profile not found")
    return row.data[0]["villager_id"]


@router.get("")
def list_complaints(
    status_: Optional[str] = Query(None, alias="status"),
    stage: Optional[str] = Query(None, description="submitted | in_progress | completed"),
    category_id: Optional[str] = None,
    priority: Optional[str] = None,
    ward_id: Optional[str] = None,
    q: Optional[str] = Query(None, description="free text: complaint number or title"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD (submitted_at >=)"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD (submitted_at <=)"),
    sort: str = Query("submitted_at"),
    order: str = Query("desc", pattern="^(asc|desc)$"),
    page: int = 1,
    page_size: int = 20,
    current_user: CurrentUser = Depends(get_current_user),
):
    query = supabase.table("complaints").select("*", count="exact")

    # Villagers only ever see their own complaints; staff/admin see everything (optionally filtered)
    if current_user.role == "villager":
        query = query.eq("villager_id", _villager_id_for(current_user.user_id))

    if stage:
        key = stage.strip().lower()
        if key not in STAGE_STATUSES:
            raise HTTPException(status_code=400, detail="stage must be one of: submitted, in_progress, completed")
        query = query.in_("status", STAGE_STATUSES[key])
    if status_:  # ANDs with stage when both are given (empty result if inconsistent)
        query = query.eq("status", status_)
    if category_id:
        query = query.eq("category_id", category_id)
    if priority:
        query = query.eq("priority", priority)
    if ward_id:
        query = query.eq("ward_id", ward_id)
    if q:
        term = _sanitize_q(q)
        if term:
            query = query.or_(f"complaint_number.ilike.%{term}%,title.ilike.%{term}%")
    if date_from and re.match(r"^\d{4}-\d{2}-\d{2}$", date_from):
        query = query.gte("submitted_at", f"{date_from}T00:00:00")
    if date_to and re.match(r"^\d{4}-\d{2}-\d{2}$", date_to):
        query = query.lte("submitted_at", f"{date_to}T23:59:59")

    sort_col = sort if sort in SORTABLE_COLUMNS else "submitted_at"
    start = (max(page, 1) - 1) * page_size
    result = (
        query.order(sort_col, desc=(order == "desc"))
        .range(start, start + page_size - 1)
        .execute()
    )
    return {
        "page": page,
        "page_size": page_size,
        "total": result.count if result.count is not None else len(result.data),
        "results": result.data,
    }


@router.post("", status_code=201)
def create_complaint(
    payload: ComplaintCreate,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
):
    if current_user.role != "villager":
        raise HTTPException(status_code=403, detail="Only villagers can file complaints")

    villager = (
        supabase.table("villagers")
        .select("villager_id, village_id, ward_id")
        .eq("user_id", current_user.user_id)
        .execute()
    )
    if not villager.data:
        raise HTTPException(status_code=404, detail="Villager profile not found")
    v = villager.data[0]

    # complaint_number is generated app-side here for simplicity; for guaranteed
    # atomicity under concurrent writes, move this to a Postgres trigger/sequence.
    year = __import__("datetime").datetime.now().year
    count_this_year = (
        supabase.table("complaints")
        .select("complaint_id", count="exact")
        .gte("submitted_at", f"{year}-01-01")
        .execute()
    )
    seq = (count_this_year.count or 0) + 1
    complaint_number = f"GP-{year}-{seq:06d}"

    inserted = (
        supabase.table("complaints")
        .insert(
            {
                "complaint_number": complaint_number,
                "villager_id": v["villager_id"],
                "village_id": v["village_id"],
                "ward_id": v["ward_id"],
                "category_id": payload.category_id,
                "title": payload.title,
                "description": payload.description,
                "location": payload.location,
                "priority": payload.priority,
                "status": "Submitted",
            }
        )
        .execute()
    )
    complaint = inserted.data[0]

    supabase.table("complaint_updates").insert(
        {
            "complaint_id": complaint["complaint_id"],
            "old_status": None,
            "new_status": "Submitted",
            "remark": "Complaint registered by villager.",
            "changed_by": current_user.user_id,
        }
    ).execute()

    log_audit(
        actor_id=current_user.user_id,
        action="Create Complaint",
        entity_type="complaint",
        entity_id=complaint["complaint_id"],
        request=request,
    )

    return complaint


@router.get("/{complaint_id}")
def get_complaint(complaint_id: str, current_user: CurrentUser = Depends(get_current_user)):
    result = supabase.table("complaints").select("*").eq("complaint_id", complaint_id).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Complaint not found")
    complaint = result.data[0]

    if current_user.role == "villager":
        if complaint["villager_id"] != _villager_id_for(current_user.user_id):
            raise HTTPException(status_code=403, detail="Not your complaint")

    history = (
        supabase.table("complaint_updates")
        .select("*")
        .eq("complaint_id", complaint_id)
        .order("changed_at")
        .execute()
    )
    attachments = (
        supabase.table("complaint_attachments").select("*").eq("complaint_id", complaint_id).execute()
    )
    return {"complaint": complaint, "history": history.data, "attachments": attachments.data}


@router.patch("/{complaint_id}/status")
def update_status(
    complaint_id: str,
    payload: ComplaintStatusUpdate,
    request: Request,
    current_user: CurrentUser = Depends(require_roles(*STAFF_ROLES)),
):
    current = supabase.table("complaints").select("status").eq("complaint_id", complaint_id).execute()
    if not current.data:
        raise HTTPException(status_code=404, detail="Complaint not found")
    old_status = current.data[0]["status"]

    now = datetime.now(timezone.utc).isoformat()
    updates = {"status": payload.new_status}
    if payload.new_status == "Resolved":
        updates["resolved_at"] = now
    if payload.new_status == "Closed":
        updates["closed_at"] = now
    if payload.assigned_to:
        updates["assigned_to"] = payload.assigned_to

    try:
        supabase.table("complaints").update(updates).eq("complaint_id", complaint_id).execute()
    except Exception:
        # `assigned_to` may not exist on this deployment's complaints table yet.
        updates.pop("assigned_to", None)
        supabase.table("complaints").update(updates).eq("complaint_id", complaint_id).execute()

    supabase.table("complaint_updates").insert(
        {
            "complaint_id": complaint_id,
            "old_status": old_status,
            "new_status": payload.new_status,
            "remark": payload.remark,
            "changed_by": current_user.user_id,
        }
    ).execute()

    log_audit(
        actor_id=current_user.user_id,
        action="Change Complaint Status",
        entity_type="complaint",
        entity_id=complaint_id,
        old_values={"status": old_status},
        new_values={"status": payload.new_status},
        request=request,
    )

    return {"complaint_id": complaint_id, "status": payload.new_status}
