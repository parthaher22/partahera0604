"""Blank the financial ledger: delete every row in `financial_records`.

Nothing else in the schema references `financial_id`, so a plain table wipe is
safe. Idempotent — running it on an empty ledger is a no-op.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # backend/
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from app.supabase_client import supabase

# A value no financial_id (uuid) can ever take, so the filter matches every row.
MATCH_ALL = "00000000-0000-0000-0000-000000000000"


def _count() -> int:
    res = (
        supabase.table("financial_records")
        .select("financial_id", count="exact")
        .limit(1)
        .execute()
    )
    return res.count or 0


def main() -> None:
    before = _count()
    print(f"[clear-finance] found {before} financial records")

    if before == 0:
        print("[clear-finance] ledger already empty — nothing to do")
        return

    try:
        supabase.table("financial_records").delete().neq("financial_id", MATCH_ALL).execute()
    except Exception as exc:
        print(f"  bulk delete failed: {exc}")
        raise

    after = _count()
    print(f"[clear-finance] removed {before - after} rows; remaining {after}")


if __name__ == "__main__":
    main()
