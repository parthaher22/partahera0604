"""Blank the audit trail and the staff list.

- Deletes every audit_log row.
- Deletes every logged-in user whose role is not 'villager' (staff + admins).
  The main admin account (9921992199) is always preserved.
- Content authored/verified by staff (projects, schemes, financial records, ...)
  is re-attributed to the admin so it is preserved. Staff-only rows
  (staff_assignments) and empty villager profiles are removed first to satisfy
  foreign keys.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.supabase_client import supabase

# Login 9921992199 / 90garmsevak — never delete this account.
ADMIN_USER_ID = "32ad1ce1-c073-46f6-8f08-c60fe5e69780"
IMPOSSIBLE_AUDIT_ID = "00000000-0000-0000-0000-000000000000"

# FK columns to a staff user that hold content -> re-attribute to the admin.
REASSIGN = [
    ("announcements", "created_by"),
    ("announcements", "reviewed_by"),
    ("complaint_attachments", "uploaded_by"),
    ("complaint_updates", "changed_by"),
    ("complaints", "assigned_staff_id"),
    ("financial_records", "verified_by"),
    ("notifications", "user_id"),
    ("projects", "created_by"),
    ("schemes", "created_by"),
    ("schemes", "verified_by"),
]
# Staff-only rows -> delete outright.
DELETE = [
    ("staff_assignments", "staff_user_id"),
    ("staff_assignments", "assigned_by"),
    ("villagers", "user_id"),
]


def main() -> None:
    # ---- Audit trail --------------------------------------------------------
    total = supabase.table("audit_logs").select("*", count="exact").execute().count or 0
    print(f"[clear-audit] total audit rows: {total}")
    if total:
        supabase.table("audit_logs").delete().neq("audit_id", IMPOSSIBLE_AUDIT_ID).execute()
    print(f"[clear-audit] audit rows remaining: {supabase.table('audit_logs').select('*', count='exact').execute().count or 0}")

    # ---- Staff accounts -----------------------------------------------------
    ids = [
        r["user_id"]
        for r in (
            supabase.table("users")
            .select("user_id")
            .neq("role", "villager")
            .neq("user_id", ADMIN_USER_ID)
            .execute()
            .data
            or []
        )
    ]
    print(f"[clear-staff] staff/admin accounts to remove: {len(ids)}")
    if not ids:
        return

    for table, col in REASSIGN:
        try:
            q = supabase.table(table).select("*", count="exact").in_(col, ids).execute()
            if q.count:
                up = supabase.table(table).update({col: ADMIN_USER_ID}).in_(col, ids).execute()
                print(f"[clear-staff] {table}.{col}: re-attributed {len(up.data or [])}")
        except Exception as exc:
            print(f"[clear-staff] {table}.{col}: skipped ({getattr(exc, 'message', exc)})")

    for table, col in DELETE:
        try:
            q = supabase.table(table).select("*", count="exact").in_(col, ids).execute()
            if q.count:
                supabase.table(table).delete().in_(col, ids).execute()
                print(f"[clear-staff] {table}.{col}: deleted {q.count}")
        except Exception as exc:
            print(f"[clear-staff] {table}.{col}: skipped ({getattr(exc, 'message', exc)})")

    res = (
        supabase.table("users")
        .delete()
        .neq("role", "villager")
        .neq("user_id", ADMIN_USER_ID)
        .execute()
    )
    print(f"[clear-staff] deleted {len(res.data or []) if res else 0} accounts")

    remaining = (
        supabase.table("users")
        .select("user_id", count="exact")
        .neq("role", "villager")
        .neq("user_id", ADMIN_USER_ID)
        .execute()
        .count
        or 0
    )
    print(f"[clear-staff] staff/admin accounts remaining: {remaining}")
    kept = (
        supabase.table("users").select("user_id, role").eq("user_id", ADMIN_USER_ID).execute().data
        or []
    )
    print(f"[clear-staff] admin account intact: {kept}")


if __name__ == "__main__":
    main()