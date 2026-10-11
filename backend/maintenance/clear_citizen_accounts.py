"""Full citizen reset: remove every villager login and all citizen-owned data.

Keeps the Panchayat admin account (9921992199) and every unit of reference
data (villages, wards, tax types, schemes, projects, announcements, ...).

Deletions run in FK-safe order (children before parents). Content authored by
citizen accounts (projects / schemes) is re-attributed to the admin so it is
preserved. The script is idempotent: safe to re-run.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.supabase_client import supabase

# Panchayat Desk login — never delete this account.
ADMIN_USER_ID = "32ad1ce1-c073-46f6-8f08-c60fe5e69780"
IMPOSSIBLE = "00000000-0000-0000-0000-000000000000"

# Content FK columns that point at a user -> re-attribute to the admin.
REASSIGN = [
    ("projects", "created_by"),
    ("schemes", "created_by"),
    ("schemes", "verified_by"),
    ("announcements", "created_by"),
    ("announcements", "reviewed_by"),
]

# (table, pk_column, filter) — cleared in this exact order (children first).
# filter is a lambda receiving the table builder and returning it filtered.
PURGE_A = [
    ("complaint_attachments", "attachment_id", lambda q: q),
    ("complaint_updates", "update_id", lambda q: q),
    ("complaints", "complaint_id", lambda q: q),
    ("payments", "payment_id", lambda q: q),
    ("tax_records", "tax_id", lambda q: q),
    ("notifications", "notification_id", lambda q: q.neq("user_id", ADMIN_USER_ID)),
]
# villagers <-> family_members is a circular FK; break it before deleting both.
PURGE_B = [
    ("family_members", "family_id", lambda q: q),
    ("villagers", "villager_id", lambda q: q),
    ("audit_logs", "audit_id", lambda q: q.neq("actor_id", ADMIN_USER_ID)),
]


def count(table, **filters) -> int:
    q = supabase.table(table).select("*", count="exact")
    for col, val in filters.items():
        q = q.eq(col, val)
    return q.limit(1).execute().count or 0


def run(label, fn) -> None:
    try:
        res = fn()
        n = len(res.data) if res and res.data is not None else 0
        print(f"  [ok]   {label}: {n} rows")
    except Exception as exc:  # noqa: BLE001
        print(f"  [skip] {label}: {getattr(exc, 'message', exc)}")


def main() -> None:
    print("== BEFORE ==")
    print("  users(role=villager):", count("users", role="villager"))
    for t in ["villagers", "family_members", "complaints", "payments",
              "tax_records", "notifications"]:
        try:
            print(f"  {t}:", supabase.table(t).select("*", count="exact").limit(1).execute().count)
        except Exception as exc:  # noqa: BLE001
            print(f"  {t}: ERR {getattr(exc, 'message', exc)}")

    print("\n== Re-attribute staff-authored content to admin ==")
    for table, col in REASSIGN:
        def step(table=table, col=col):
            return (
                supabase.table(table)
                .update({col: ADMIN_USER_ID})
                .not_.is_(col, None)
                .neq(col, ADMIN_USER_ID)
                .execute()
            )
        run(f"{table}.{col}", step)

    print("\n== Purge citizen data ==")
    for table, pk, flt in PURGE_A:
        def step(table=table, pk=pk, flt=flt):
            return flt(supabase.table(table).delete()).neq(pk, IMPOSSIBLE).execute()
        run(table, step)

    print("\n== Break villagers <-> family_members FK cycle ==")
    run("family_members.head_villager_id = null",
        lambda: supabase.table("family_members").update({"head_villager_id": None}).neq("family_id", IMPOSSIBLE).execute())
    run("villagers.family_id = null",
        lambda: supabase.table("villagers").update({"family_id": None}).neq("villager_id", IMPOSSIBLE).execute())

    for table, pk, flt in PURGE_B:
        def step(table=table, pk=pk, flt=flt):
            return flt(supabase.table(table).delete()).neq(pk, IMPOSSIBLE).execute()
        run(table, step)

    print("\n== Delete villager login accounts ==")
    run("users(role=villager)",
        lambda: supabase.table("users").delete().eq("role", "villager").execute())

    print("\n== AFTER ==")
    print("  users total:", supabase.table("users").select("user_id", count="exact").limit(1).execute().count)
    print("  users(role=villager):", count("users", role="villager"))
    for t in ["villagers", "family_members", "complaints", "payments",
              "tax_records", "notifications"]:
        try:
            print(f"  {t}:", supabase.table(t).select("*", count="exact").limit(1).execute().count)
        except Exception as exc:  # noqa: BLE001
            print(f"  {t}: ERR {getattr(exc, 'message', exc)}")
    kept = supabase.table("users").select("user_id,role,mobile_number").neq("role", "villager").execute().data
    print("  non-villager accounts kept:", kept)

    print("\n== Refresh villager login-accounts Excel ==")
    from app.villager_export import sync_villagers_excel

    path = sync_villagers_excel()
    print("  status:", "regenerated" if path else "FAILED", "->", path)


if __name__ == "__main__":
    main()
