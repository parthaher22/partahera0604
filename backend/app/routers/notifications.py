import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.supabase_client import supabase
from app.security import get_current_user, CurrentUser

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
def my_notifications(
    limit: int = 20,
    current_user: CurrentUser = Depends(get_current_user),
):
    rows = (
        supabase.table("notifications")
        .select("*")
        .eq("user_id", current_user.user_id)
        .order("created_at", desc=True)
        .limit(max(1, min(limit, 100)))
        .execute()
    )
    unread = (
        supabase.table("notifications")
        .select("notification_id", count="exact")
        .eq("user_id", current_user.user_id)
        .eq("is_read", False)
        .execute()
    )
    return {"results": rows.data or [], "unread": unread.count or 0}


@router.post("/read-all")
def mark_all_read(current_user: CurrentUser = Depends(get_current_user)):
    supabase.table("notifications").update({"is_read": True, "read_at": datetime.now(timezone.utc).isoformat()}).eq(
        "user_id", current_user.user_id
    ).eq("is_read", False).execute()
    return {"unread": 0}


@router.patch("/{notification_id}/read")
def mark_read(notification_id: str, current_user: CurrentUser = Depends(get_current_user)):
    result = (
        supabase.table("notifications")
        .update({"is_read": True, "read_at": datetime.now(timezone.utc).isoformat()})
        .eq("notification_id", notification_id)
        .eq("user_id", current_user.user_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"read": notification_id}
