from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.audit_util import log_audit
from app.supabase_client import supabase
from app.schemas import RegisterRequest, LoginRequest, ChangePasswordRequest, TokenResponse
from app.security import hash_password, verify_password, create_access_token, get_current_user, CurrentUser

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request):
    existing = (
        supabase.table("users")
        .select("user_id")
        .eq("mobile_number", payload.mobile_number)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=400, detail="Mobile number already registered")

    user_row = (
        supabase.table("users")
        .insert(
            {
                "full_name": payload.full_name,
                "mobile_number": payload.mobile_number,
                "email": payload.email,
                "password_hash": hash_password(payload.password),
                "role": "villager",
                "account_status": "active",
            }
        )
        .execute()
    )
    user_id = user_row.data[0]["user_id"]

    try:
        supabase.table("villagers").insert(
            {
                "user_id": user_id,
                "village_id": payload.village_id,
                "ward_id": payload.ward_id,
                "house_number": payload.house_number,
                "address": payload.address,
                "date_of_birth": str(payload.date_of_birth) if payload.date_of_birth else None,
                "gender": payload.gender,
                "occupation": payload.occupation,
            }
        ).execute()
    except Exception:
        # Roll back the orphaned user row since Postgres FK requires villagers.user_id -> users
        supabase.table("users").delete().eq("user_id", user_id).execute()
        raise HTTPException(status_code=400, detail="Invalid village_id/ward_id")

    log_audit(
        actor_id=user_id,
        action="Register",
        entity_type="user",
        entity_id=user_id,
        request=request,
    )

    token = create_access_token(user_id, "villager")
    return TokenResponse(access_token=token, role="villager", user_id=user_id)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request):
    result = (
        supabase.table("users")
        .select("user_id, password_hash, role, account_status")
        .eq("mobile_number", payload.mobile_number)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = result.data[0]
    if user["account_status"] != "active":
        log_audit(
            actor_id=user["user_id"],
            action="Login Blocked (inactive account)",
            entity_type="user",
            entity_id=user["user_id"],
            request=request,
        )
        raise HTTPException(status_code=403, detail="Account is not active")
    if not verify_password(payload.password, user["password_hash"]):
        log_audit(
            actor_id=user["user_id"],
            action="Login Failed (bad password)",
            entity_type="user",
            entity_id=user["user_id"],
            request=request,
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    supabase.table("users").update(
        {"last_login": datetime.now(timezone.utc).isoformat()}
    ).eq("user_id", user["user_id"]).execute()

    log_audit(
        actor_id=user["user_id"],
        action="Login",
        entity_type="user",
        entity_id=user["user_id"],
        request=request,
    )

    token = create_access_token(user["user_id"], user["role"])
    return TokenResponse(access_token=token, role=user["role"], user_id=user["user_id"])


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
):
    user_row = (
        supabase.table("users").select("password_hash").eq("user_id", current_user.user_id).execute()
    )
    if not user_row.data:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(payload.current_password, user_row.data[0]["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")

    supabase.table("users").update(
        {"password_hash": hash_password(payload.new_password)}
    ).eq("user_id", current_user.user_id).execute()

    log_audit(
        actor_id=current_user.user_id,
        action="Change Password",
        entity_type="user",
        entity_id=current_user.user_id,
        request=request,
    )

    return {"detail": "Password updated successfully"}


@router.get("/me")
def read_me(current_user: CurrentUser = Depends(get_current_user)):
    user_row = (
        supabase.table("users").select("*").eq("user_id", current_user.user_id).execute()
    )
    if not user_row.data:
        raise HTTPException(status_code=404, detail="User not found")
    user = dict(user_row.data[0])
    user.pop("password_hash", None)

    profile = {}
    villager = (
        supabase.table("villagers")
        .select("*")
        .eq("user_id", current_user.user_id)
        .execute()
    )
    if villager.data:
        profile = villager.data[0]

    return {**user, "profile": profile, "panchayat_member": {}}
