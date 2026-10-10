"""Blank the Kumbhari notice board: delete every notice, its citizen inbox
copies, and refresh the board Excel so it mirrors the (now empty) board."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.config import KUMBHARI_VILLAGE_ID
from app.supabase_client import supabase


def main() -> None:
    rows = (
        supabase.table("announcements")
        .select("announcement_id")
        .eq("village_id", KUMBHARI_VILLAGE_ID)
        .execute()
        .data
        or []
    )
    ids = [r["announcement_id"] for r in rows]
    print(f"[clear-notice-board] found {len(ids)} notices")

    purged = 0
    for nid in ids:
        try:
            res = supabase.table("notifications").delete().eq("reference_id", nid).execute()
            purged += len(res.data or [])
        except Exception as exc:
            print(f"  skip notifications for {nid}: {exc}")

    deleted = 0
    if ids:
        try:
            res = (
                supabase.table("announcements")
                .delete()
                .eq("village_id", KUMBHARI_VILLAGE_ID)
                .execute()
            )
            deleted = len(res.data or [])
        except Exception as exc:
            print(f"  announcements delete failed: {exc}")

    print(f"[clear-notice-board] purged {purged} inbox notifications, deleted {deleted} notices")

    try:
        from app.routers.announcements import _sync_notice_excel

        path = _sync_notice_excel()
        print(f"[clear-notice-board] board excel refreshed: {path}")
    except Exception as exc:
        print(f"[clear-notice-board] excel refresh skipped: {exc}")


if __name__ == "__main__":
    main()