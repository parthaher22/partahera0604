"""Financial ledger management for the Panchayat Desk.

Wraps the `financial_records` table (village income & expenditure ledger).

  * List / filter / paginate entries
  * Aggregate summary (income, expenditure, net, verification counts)
  * Create / update / delete entries
  * Verify / reject entries
  * CSV export of the filtered ledger

PostgREST aggregates are disabled on this project, so the summary is computed
by paging lightweight columns server-side.
"""

import csv
import io
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from app.audit_util import log_audit
from app.supabase_client import supabase
from app.security import require_roles, CurrentUser

router = APIRouter(prefix="/api/finance", tags=["finance"])

VIEW_ROLES = ("panchayat_staff", "panchayat_admin", "system_admin")
MANAGE_ROLES = ("panchayat_staff", "panchayat_admin", "system_admin")
DELETE_ROLES = ("panchayat_admin", "system_admin")

# Kumbhari Gram Panchayat (default village for new entries).
DEFAULT_VILLAGE_ID = "0acdee35-23bd-4b17-adce-33ebdfbfaf18"

VALID_TYPES = {"Income", "Expenditure"}
VALID_STATUSES = {"Pending", "Verified", "Rejected"}
SORTABLE = {"transaction_date", "amount", "created_at", "updated_at"}

_PAGE = 1000          # PostgREST select cap  -> page to read the whole table
_HARD_CAP = 200000    # safety stop for very large tables


class FinanceCreate(BaseModel):
    transaction_date: str = Field(min_length=4, description="YYYY-MM-DD")
    transaction_type: str = "Expenditure"
    category: str = Field(min_length=1)
    description: str = Field(min_length=1)
    amount: float = Field(gt=0)
    financial_year: Optional[str] = None
    source_of_fund: Optional[str] = None
    source_reference: Optional[str] = None
    document_url: Optional[str] = None
    project_id: Optional[str] = None
    village_id: Optional[str] = None


class FinanceUpdate(BaseModel):
    transaction_date: Optional[str] = None
    transaction_type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    amount: Optional[float] = Field(default=None, gt=0)
    financial_year: Optional[str] = None
    source_of_fund: Optional[str] = None
    source_reference: Optional[str] = None
    document_url: Optional[str] = None
    project_id: Optional[str] = None


class VerifyBody(BaseModel):
    status: str = "Verified"


def _sanitize_q(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[,%_*()]", " ", value).strip()[:80]


def _valid_date(value: Optional[str]) -> bool:
    if not value:
        return False
    try:
        datetime.strptime(value, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _fy_from_date(date_str: str) -> str:
    """Indian financial year (Apr–Mar) as stored, e.g. '2025-2026'."""
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return str(datetime.now().year)
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{start + 1}"


def _filtered(
    columns: str = "*",
    count: Optional[str] = None,
    financial_year: Optional[str] = None,
    transaction_type: Optional[str] = None,
    category: Optional[str] = None,
    verification_status: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    project_id: Optional[str] = None,
):
    query = supabase.table("financial_records").select(columns, count=count)
    if financial_year:
        query = query.eq("financial_year", financial_year.strip()[:20])
    if transaction_type:
        query = query.eq("transaction_type", transaction_type.strip()[:20])
    if category:
        query = query.ilike("category", f"%{category.strip()[:60]}%")
    if verification_status:
        query = query.eq("verification_status", verification_status.strip()[:20])
    if project_id:
        query = query.eq("project_id", project_id.strip()[:64])
    if _valid_date(date_from):
        query = query.gte("transaction_date", date_from)
    if _valid_date(date_to):
        query = query.lte("transaction_date", date_to)
    term = _sanitize_q(q)
    if term:
        query = query.or_(
            f"description.ilike.%{term}%,source_reference.ilike.%{term}%,source_of_fund.ilike.%{term}%"
        )
    return query


@router.get("/records")
def list_records(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("transaction_date"),
    order: str = Query("desc"),
    financial_year: Optional[str] = None,
    transaction_type: Optional[str] = None,
    category: Optional[str] = None,
    verification_status: Optional[str] = None,
    q: Optional[str] = Query(None, description="substring: description / reference / fund source"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    project_id: Optional[str] = None,
    current_user: CurrentUser = Depends(require_roles(*VIEW_ROLES)),
):
    sort_field = sort if sort in SORTABLE else "transaction_date"
    result = (
        _filtered(
            columns="*",
            count="exact",
            financial_year=financial_year,
            transaction_type=transaction_type,
            category=category,
            verification_status=verification_status,
            q=q,
            date_from=date_from,
            date_to=date_to,
            project_id=project_id,
        )
        .order(sort_field, desc=(order != "asc"))
        .range(offset, offset + limit - 1)
        .execute()
    )
    rows = result.data or []
    total = result.count if result.count is not None else len(rows)
    return {"results": rows, "total": total, "limit": limit, "offset": offset}


@router.get("/records/summary")
def records_summary(
    financial_year: Optional[str] = None,
    transaction_type: Optional[str] = None,
    category: Optional[str] = None,
    verification_status: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    project_id: Optional[str] = None,
    current_user: CurrentUser = Depends(require_roles(*VIEW_ROLES)),
):
    total_income = 0.0
    total_expenditure = 0.0
    counts = {"total": 0, "pending": 0, "verified": 0, "rejected": 0}

    offset = 0
    while True:
        rows = (
            _filtered(
                columns="amount,transaction_type,verification_status",
                financial_year=financial_year,
                transaction_type=transaction_type,
                category=category,
                verification_status=verification_status,
                q=q,
                date_from=date_from,
                date_to=date_to,
                project_id=project_id,
            )
            .range(offset, offset + _PAGE - 1)
            .execute()
            .data
            or []
        )
        for row in rows:
            amount = float(row.get("amount") or 0)
            if row.get("transaction_type") == "Income":
                total_income += amount
            else:
                total_expenditure += amount
            counts["total"] += 1
            status = row.get("verification_status")
            if status == "Verified":
                counts["verified"] += 1
            elif status == "Rejected":
                counts["rejected"] += 1
            else:
                counts["pending"] += 1
        if len(rows) < _PAGE:
            break
        offset += _PAGE
        if offset >= _HARD_CAP:
            break

    return {
        "total_income": round(total_income, 2),
        "total_expenditure": round(total_expenditure, 2),
        "net": round(total_income - total_expenditure, 2),
        "counts": counts,
    }


@router.get("/records/export")
def export_records(
    financial_year: Optional[str] = None,
    transaction_type: Optional[str] = None,
    category: Optional[str] = None,
    verification_status: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    project_id: Optional[str] = None,
    current_user: CurrentUser = Depends(require_roles(*VIEW_ROLES)),
):
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "financial_id", "transaction_date", "financial_year", "transaction_type",
        "category", "description", "amount", "source_of_fund", "source_reference",
        "verification_status", "project_id", "document_url", "created_at",
    ])

    offset = 0
    while True:
        rows = (
            _filtered(
                columns="*",
                financial_year=financial_year,
                transaction_type=transaction_type,
                category=category,
                verification_status=verification_status,
                q=q,
                date_from=date_from,
                date_to=date_to,
                project_id=project_id,
            )
            .order("transaction_date", desc=True)
            .range(offset, offset + _PAGE - 1)
            .execute()
            .data
            or []
        )
        for row in rows:
            writer.writerow([
                row.get("financial_id", ""),
                row.get("transaction_date", ""),
                row.get("financial_year", ""),
                row.get("transaction_type", ""),
                row.get("category", ""),
                row.get("description", ""),
                row.get("amount", ""),
                row.get("source_of_fund", ""),
                row.get("source_reference", ""),
                row.get("verification_status", ""),
                row.get("project_id") or "",
                row.get("document_url", ""),
                row.get("created_at", ""),
            ])
        if len(rows) < _PAGE:
            break
        offset += _PAGE
        if offset >= _HARD_CAP:
            break

    filename = f"kumbhari-financial-ledger-{datetime.now().strftime('%Y-%m-%d')}.csv"
    return Response(
        content=buffer.getvalue().encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/records", status_code=201)
def create_record(
    payload: FinanceCreate,
    request: Request,
    current_user: CurrentUser = Depends(require_roles(*MANAGE_ROLES)),
):
    if payload.transaction_type not in VALID_TYPES:
        raise HTTPException(status_code=400, detail="Type must be Income or Expenditure")
    if not _valid_date(payload.transaction_date):
        raise HTTPException(status_code=400, detail="transaction_date must be YYYY-MM-DD")

    now = datetime.now(timezone.utc).isoformat()
    fy = (payload.financial_year or "").strip() or _fy_from_date(payload.transaction_date)
    village_id = (payload.village_id or "").strip() or DEFAULT_VILLAGE_ID

    record = {
        "financial_id": str(uuid.uuid4()),
        "village_id": village_id,
        "financial_year": fy,
        "category": payload.category.strip(),
        "transaction_type": payload.transaction_type,
        "description": payload.description.strip(),
        "amount": round(float(payload.amount), 2),
        "source_of_fund": (payload.source_of_fund or "").strip() or None,
        "source_reference": (payload.source_reference or "").strip()
        or f"REF-{fy}-{uuid.uuid4().hex[:8].upper()}",
        "document_url": (payload.document_url or "").strip() or None,
        "project_id": (payload.project_id or "").strip() or None,
        "transaction_date": payload.transaction_date,
        "verification_status": "Pending",
        "verified_by": None,
        "created_at": now,
        "updated_at": now,
    }
    result = supabase.table("financial_records").insert(record).execute()
    created = result.data[0] if result.data else record

    log_audit(
        actor_id=current_user.user_id,
        action="CreateFinancialRecord",
        entity_type="financial_record",
        entity_id=record["financial_id"],
        new_values={
            "type": record["transaction_type"],
            "amount": record["amount"],
            "category": record["category"],
        },
        request=request,
    )
    return created


@router.patch("/records/{financial_id}")
def update_record(
    financial_id: str,
    payload: FinanceUpdate,
    request: Request,
    current_user: CurrentUser = Depends(require_roles(*MANAGE_ROLES)),
):
    existing = (
        supabase.table("financial_records")
        .select("*")
        .eq("financial_id", financial_id)
        .execute()
        .data
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Financial record not found")

    updates = {}
    if payload.transaction_date is not None:
        if not _valid_date(payload.transaction_date):
            raise HTTPException(status_code=400, detail="transaction_date must be YYYY-MM-DD")
        updates["transaction_date"] = payload.transaction_date
    if payload.transaction_type is not None:
        if payload.transaction_type not in VALID_TYPES:
            raise HTTPException(status_code=400, detail="Type must be Income or Expenditure")
        updates["transaction_type"] = payload.transaction_type
    if payload.category is not None:
        updates["category"] = payload.category.strip()
    if payload.description is not None:
        updates["description"] = payload.description.strip()
    if payload.amount is not None:
        updates["amount"] = round(float(payload.amount), 2)
    if payload.financial_year is not None:
        updates["financial_year"] = payload.financial_year.strip() or None
    if payload.source_of_fund is not None:
        updates["source_of_fund"] = payload.source_of_fund.strip() or None
    if payload.source_reference is not None:
        updates["source_reference"] = payload.source_reference.strip() or None
    if payload.document_url is not None:
        updates["document_url"] = payload.document_url.strip() or None
    if payload.project_id is not None:
        updates["project_id"] = payload.project_id.strip() or None

    if not updates:
        raise HTTPException(status_code=400, detail="No changes provided")

    updates["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = (
        supabase.table("financial_records")
        .update(updates)
        .eq("financial_id", financial_id)
        .execute()
    )
    updated = result.data[0] if result.data else updates

    log_audit(
        actor_id=current_user.user_id,
        action="UpdateFinancialRecord",
        entity_type="financial_record",
        entity_id=financial_id,
        old_values={"amount": existing[0].get("amount"), "status": existing[0].get("verification_status")},
        new_values={k: v for k, v in updates.items() if k != "updated_at"},
        request=request,
    )
    return updated


@router.post("/records/{financial_id}/verification")
def set_verification(
    financial_id: str,
    payload: VerifyBody,
    request: Request,
    current_user: CurrentUser = Depends(require_roles(*MANAGE_ROLES)),
):
    if payload.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail="Status must be Pending, Verified or Rejected")

    existing = (
        supabase.table("financial_records")
        .select("financial_id,verification_status")
        .eq("financial_id", financial_id)
        .execute()
        .data
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Financial record not found")

    update = {
        "verification_status": payload.status,
        "verified_by": current_user.user_id if payload.status != "Pending" else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    result = (
        supabase.table("financial_records")
        .update(update)
        .eq("financial_id", financial_id)
        .execute()
    )

    log_audit(
        actor_id=current_user.user_id,
        action=f"MarkFinancialRecord{payload.status}",
        entity_type="financial_record",
        entity_id=financial_id,
        old_values={"status": existing[0].get("verification_status")},
        new_values={"status": payload.status},
        request=request,
    )
    return result.data[0] if result.data else update


@router.delete("/records/{financial_id}")
def delete_record(
    financial_id: str,
    request: Request,
    current_user: CurrentUser = Depends(require_roles(*DELETE_ROLES)),
):
    existing = (
        supabase.table("financial_records")
        .select("*")
        .eq("financial_id", financial_id)
        .execute()
        .data
    )
    if not existing:
        raise HTTPException(status_code=404, detail="Financial record not found")

    supabase.table("financial_records").delete().eq("financial_id", financial_id).execute()

    log_audit(
        actor_id=current_user.user_id,
        action="DeleteFinancialRecord",
        entity_type="financial_record",
        entity_id=financial_id,
        old_values={
            "amount": existing[0].get("amount"),
            "category": existing[0].get("category"),
            "description": existing[0].get("description"),
        },
        request=request,
    )
    return {"ok": True, "financial_id": financial_id}
