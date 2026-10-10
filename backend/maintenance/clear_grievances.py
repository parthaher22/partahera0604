"""Blank the grievance desk: delete every complaint in Kumbhari plus its
timeline (complaint_updates) and attachments (complaint_attachments)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.config import KUMBHARI_VILLAGE_ID
from app.supabase_client import supabase


def _all_complaint_ids() -> list:
    """Fetch every Kumbhari complaint id, paging past PostgREST's 1000-row cap."""
    ids: list = []
    batch = 1000
    offset = 0
    while True:
        rows = (
            supabase.table("complaints")
            .select("complaint_id")
            .eq("village_id", KUMBHARI_VILLAGE_ID)
            .range(offset, offset + batch - 1)
            .execute()
            .data
            or []
        )
        ids.extend(r["complaint_id"] for r in rows)
        if len(rows) < batch:
            break
        offset += batch
    return ids


def main() -> None:
    ids = _all_complaint_ids()
    print(f"[clear-grievances] found {len(ids)} complaints")

    removed_updates = 0
    removed_attachments = 0
    for cid in ids:
        for table in ("complaint_updates", "complaint_attachments"):
            try:
                res = supabase.table(table).delete().eq("complaint_id", cid).execute()
                n = len(res.data or []) if res else 0
                if table == "complaint_updates":
                    removed_updates += n
                else:
                    removed_attachments += n
            except Exception as exc:
                print(f"  skip {table} for {cid}: {exc}")

    removed = 0
    if ids:
        try:
            res = (
                supabase.table("complaints")
                .delete()
                .eq("village_id", KUMBHARI_VILLAGE_ID)
                .execute()
            )
            removed = len(res.data or []) if res else 0
        except Exception as exc:
            print(f"  complaints delete failed: {exc}")

    print(
        f"[clear-grievances] removed {removed} complaints, "
        f"{removed_updates} timeline entries, {removed_attachments} attachments"
    )


if __name__ == "__main__":
    main()