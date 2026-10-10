from typing import Optional

from fastapi import APIRouter, HTTPException

from app.config import KUMBHARI_VILLAGE_ID
from app.supabase_client import supabase

router = APIRouter(prefix="/api", tags=["reference"])


def _safe_list(table: str) -> list:
    try:
        result = supabase.table(table).select("*").execute()
        return result.data
    except HTTPException:
        raise
    except Exception as exc:  # table/view not present in the DB yet
        raise HTTPException(
            status_code=501, detail=f"Reference table '{table}' is not available"
        ) from exc


@router.get("/villages")
def list_villages():
    try:
        result = supabase.table("villages").select("*").eq("village_id", KUMBHARI_VILLAGE_ID).execute()
        return result.data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=501, detail="Reference table 'villages' is not available"
        ) from exc


@router.get("/wards")
def list_wards(village_id: Optional[str] = None):
    try:
        query = supabase.table("wards").select("*")
        if village_id:
            query = query.eq("village_id", village_id)
        result = query.execute()
        return result.data
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=501, detail="Reference table 'wards' is not available"
        ) from exc


@router.get("/complaint-categories")
def list_complaint_categories():
    return _safe_list("complaint_categories")