from datetime import datetime, timedelta, timezone
import time

from fastapi import APIRouter, Depends, HTTPException, Query

from app.config import KUMBHARI_VILLAGE_ID
from app.supabase_client import supabase
from app.security import get_current_user, require_roles, CurrentUser

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

# SLA (days) used when a complaint has no explicit expected_resolution_date.
SLA_DAYS = {"High": 3, "Medium": 7, "Low": 14}
OPEN_STATUSES = ("Submitted", "Under Review", "Assigned", "In Progress")
COMPLETED_STATUSES = ("Resolved", "Closed", "Rejected")

# Small in-memory cache so the 12s live ticker doesn't hammer Supabase.
_TRENDS_CACHE: dict = {}
_TRENDS_TTL_SECONDS = 120


@router.get("/villager")
def villager_dashboard(current_user: CurrentUser = Depends(require_roles("villager"))):
    villager = supabase.table("villagers").select("villager_id").eq("user_id", current_user.user_id).execute()
    if not villager.data:
        raise HTTPException(status_code=404, detail="Villager profile not found")
    villager_id = villager.data[0]["villager_id"]

    stats = (
        supabase.table("vw_villager_dashboard").select("*").eq("villager_id", villager_id).execute()
    )
    recent_announcements = (
        supabase.table("vw_published_announcements").select("*").limit(5).execute()
    )
    recent_payments = (
        supabase.table("payments")
        .select("*")
        .eq("villager_id", villager_id)
        .order("created_at", desc=True)
        .limit(5)
        .execute()
    )
    return {
        "stats": stats.data[0] if stats.data else None,
        "recent_announcements": recent_announcements.data,
        "recent_payments": recent_payments.data,
    }


@router.get("/panchayat")
def panchayat_dashboard(
    village_id: str = None,
    current_user: CurrentUser = Depends(require_roles("panchayat_staff", "panchayat_admin", "system_admin")),
):
    if not village_id:
        village_id = KUMBHARI_VILLAGE_ID

    stats = supabase.table("vw_panchayat_dashboard").select("*").eq("village_id", village_id).execute()
    by_category = (
        supabase.table("vw_complaints_by_category").select("*").eq("village_id", village_id).execute()
    )
    by_ward = supabase.table("vw_complaints_by_ward").select("*").eq("village_id", village_id).execute()
    by_status = supabase.table("vw_complaints_by_status").select("*").eq("village_id", village_id).execute()
    recent_activity = (
        supabase.table("vw_recent_activity")
        .select("*")
        .eq("village_id", village_id)
        .order("activity_at", desc=True)
        .limit(10)
        .execute()
    )
    staff_rows = supabase.table("users").select("user_id").neq("role", "villager").execute()
    return {
        "stats": (stats.data[0] if stats.data else None) or {"village_id": village_id},
        "complaints_by_category": by_category.data,
        "complaints_by_ward": by_ward.data,
        "complaints_by_status": by_status.data,
        "recent_activity": recent_activity.data,
        "staff_count": len(staff_rows.data),
    }


def _fetch_all(query, max_rows: int = 20000) -> list:
    """Page through a PostgREST result (1000 rows per request)."""
    rows, offset = [], 0
    while offset < max_rows:
        page = query.range(offset, offset + 999).execute().data or []
        rows.extend(page)
        if len(page) < 1000:
            break
        offset += 1000
    return rows


def _sla_due_date(row: dict, now_date):
    """Return the SLA due date (datetime.date) for an open complaint."""
    expected = row.get("expected_resolution_date")
    if expected:
        try:
            return datetime.strptime(str(expected)[:10], "%Y-%m-%d").date()
        except ValueError:
            pass
    try:
        submitted = datetime.strptime(str(row.get("submitted_at"))[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        submitted = now_date
    return submitted + timedelta(days=SLA_DAYS.get(row.get("priority") or "Medium", 7))


@router.get("/trends")
def dashboard_trends(
    days: int = Query(30, ge=7, le=90, description="window length in days"),
    village_id: str = None,
    current_user: CurrentUser = Depends(
        require_roles("panchayat_staff", "panchayat_admin", "system_admin")
    ),
):
    """Operational trends for the Panchayat Desk: received-this-week, average
    resolution time, SLA overdue/due-soon/on-track counts, and a daily
    received/resolved series for the 7/30-day activity chart."""
    if not village_id:
        village_id = KUMBHARI_VILLAGE_ID

    cache_key = (village_id, days)
    cached = _TRENDS_CACHE.get(cache_key)
    if cached and time.time() - cached[0] < _TRENDS_TTL_SECONDS:
        return cached[1]

    now = datetime.now(timezone.utc)
    now_date = now.date()
    cutoff_iso = (now - timedelta(days=days)).isoformat()
    week_cutoff_iso = (now - timedelta(days=7)).isoformat()

    # 1) Complaints received inside the window (for the daily chart + weekly count)
    received_rows = _fetch_all(
        supabase.table("complaints")
        .select("complaint_id, submitted_at")
        .eq("village_id", village_id)
        .gte("submitted_at", cutoff_iso)
    )

    # 2) Complaints completed inside the window (resolution times + daily chart)
    completed_rows = _fetch_all(
        supabase.table("complaints")
        .select("complaint_id, submitted_at, resolved_at, closed_at")
        .eq("village_id", village_id)
        .in_("status", list(COMPLETED_STATUSES))
        .gte("resolved_at", cutoff_iso)
    )

    # 3) All currently open complaints (SLA health)
    open_rows = _fetch_all(
        supabase.table("complaints")
        .select("complaint_id, priority, submitted_at, expected_resolution_date")
        .eq("village_id", village_id)
        .in_("status", list(OPEN_STATUSES))
    )

    daily = {
        (now_date - timedelta(days=i)).isoformat(): {"received": 0, "resolved": 0}
        for i in range(days - 1, -1, -1)
    }

    received_in_window = 0
    received_this_week = 0
    for row in received_rows:
        ts = row.get("submitted_at")
        if not ts:
            continue
        day = str(ts)[:10]
        if day in daily:
            daily[day]["received"] += 1
        received_in_window += 1
        if str(ts) >= week_cutoff_iso:
            received_this_week += 1

    resolved_in_window = 0
    resolution_hours = []
    for row in completed_rows:
        resolved_at = row.get("resolved_at") or row.get("closed_at")
        if not resolved_at:
            continue
        day = str(resolved_at)[:10]
        if day in daily:
            daily[day]["resolved"] += 1
        resolved_in_window += 1
        if row.get("submitted_at"):
            try:
                started = datetime.fromisoformat(str(row["submitted_at"]).replace("Z", "+00:00"))
                ended = datetime.fromisoformat(str(resolved_at).replace("Z", "+00:00"))
                hours = (ended - started).total_seconds() / 3600
                if hours >= 0:
                    resolution_hours.append(hours)
            except ValueError:
                continue

    overdue = due_soon = on_track = 0
    for row in open_rows:
        due = _sla_due_date(row, now_date)
        if due < now_date:
            overdue += 1
        elif due <= now_date + timedelta(days=2):
            due_soon += 1
        else:
            on_track += 1

    avg_hours = round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else None
    payload = {
        "village_id": village_id,
        "window_days": days,
        "received_this_week": received_this_week,
        "received_in_window": received_in_window,
        "resolved_in_window": resolved_in_window,
        "avg_resolution_hours": avg_hours,
        "avg_resolution_days": round(avg_hours / 24, 1) if avg_hours is not None else None,
        "open_total": len(open_rows),
        "overdue": overdue,
        "due_soon": due_soon,
        "on_track": on_track,
        "daily": [{"date": d, **counts} for d, counts in daily.items()],
        "generated_at": now.isoformat(),
    }

    _TRENDS_CACHE[cache_key] = (time.time(), payload)
    return payload
