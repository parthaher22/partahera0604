from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.audit_util import log_audit
from app.supabase_client import supabase
from app.security import hash_password, require_roles, CurrentUser

router = APIRouter(prefix="/api/staff", tags=["staff"])

STAFF_ROLES = {"panchayat_staff", "panchayat_admin"}
ALL_ROLES = {"villager", "panchayat_staff", "panchayat_admin", "system_admin"}
VIEW_ROLES = ("panchayat_staff", "panchayat_admin", "system_admin")
MANAGE_ROLES = ("panchayat_admin", "system_admin")
VALID_STATUSES = {"active", "suspended"}


class StaffCreate(BaseModel):
    full_name: str = Field(min_length=2)
    mobile_number: str = Field(pattern=r"^[6-9]\d{9}$")
    password: str = Field(min_length=6)
    role: str = "panchayat_staff"


class StaffUpdate(BaseModel):
    role: Optional[str] = None
    account_status: Optional[str] = None


@router.get("")
def list_staff(current_user: CurrentUser = Depends(require_roles(*VIEW_ROLES))):
    result = (
        supabase.table("users")
        .select("user_id, full_name, mobile_number, email, role, account_status, last_login, created_at")
        .neq("role", "villager")
        .order("created_at", desc=True)
        .execute()
    )
    staff = result.data
    active = sum(1 for s in staff if s.get("account_status") == "active")
    admins = sum(1 for s in staff if s.get("role") in ("panchayat_admin", "system_admin"))
    return {"staff": staff, "total": len(staff), "active": active, "admins": admins}


@router.post("", status_code=201)
def create_staff(
    payload: StaffCreate,
    request: Request,
    current_user: CurrentUser = Depends(require_roles(*MANAGE_ROLES)),
):
    if payload.role not in STAFF_ROLES:
        raise HTTPException(status_code=400, detail="Role must be panchayat_staff or panchayat_admin")

    existing = (
        supabase.table("users").select("user_id").eq("mobile_number", payload.mobile_number).execute()
    )
    if existing.data:
        raise HTTPException(status_code=400, detail="Mobile number already registered")

    row = (
        supabase.table("users")
        .insert(
            {
                "full_name": payload.full_name,
                "mobile_number": payload.mobile_number,
                "password_hash": hash_password(payload.password),
                "role": payload.role,
                "account_status": "active",
            }
        )
        .execute()
    )
    user = row.data[0]
    log_audit(
        actor_id=current_user.user_id,
        action="CreateStaff",
        entity_type="user",
        entity_id=user["user_id"],
        new_values={"role": user["role"]},
        request=request,
    )

    return {
        "user_id": user["user_id"],
        "full_name": user["full_name"],
        "mobile_number": user["mobile_number"],
        "role": user["role"],
        "account_status": user["account_status"],
    }


@router.patch("/{user_id}")
def update_staff(
    user_id: str,
    payload: StaffUpdate,
    request: Request,
    current_user: CurrentUser = Depends(require_roles(*MANAGE_ROLES)),
):
    target = (
        supabase.table("users").select("*").eq("user_id", user_id).execute()
    )
    if not target.data:
        raise HTTPException(status_code=404, detail="User not found")

    if user_id == current_user.user_id:
        raise HTTPException(status_code=400, detail="You cannot change your own role or account status")

    updates = {}
    if payload.role is not None:
        if payload.role not in ALL_ROLES:
            raise HTTPException(status_code=400, detail="Invalid role")
        updates["role"] = payload.role
    if payload.account_status is not None:
        if payload.account_status not in VALID_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid account status")
        updates["account_status"] = payload.account_status

    if not updates:
        raise HTTPException(status_code=400, detail="No changes provided")

    updated = (
        supabase.table("users").update(updates).eq("user_id", user_id).execute()
    )
    result = updated.data[0]
    log_audit(
        actor_id=current_user.user_id,
        action="UpdateStaff",
        entity_type="user",
        entity_id=user_id,
        new_values=updates,
        request=request,
    )

    return {
        "user_id": result["user_id"],
        "full_name": result["full_name"],
        "mobile_number": result["mobile_number"],
        "role": result["role"],
        "account_status": result["account_status"],
    }