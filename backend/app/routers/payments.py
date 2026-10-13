"""Fee payment management for the Panchayat Desk.

This wraps the `payments` ledger that records every citizen tax/fee payment:

  * Citizens pay an assessed tax online (POST /api/tax/{tax_id}/pay) which
    records a PENDING payment awaiting confirmation.
  * The Panchayat Desk lists / filters / exports the whole fee ledger.
  * The Panchayat Desk confirms (Successful) or rejects a pending payment.
    Confirming a payment credits the linked tax_record.
  * The Panchayat Desk records an offline (cash/cheque) payment when an online
    payment never synced, crediting the tax_record immediately.
  * The Panchayat Desk raises a new fee demand (creates a tax_records row) so a
    citizen has something to pay.

PostgREST aggregates are disabled on this project, so summaries are computed by
paging lightweight columns server-side. Citizen / tax details are joined in
Python (a single village holds a small number of rows) which keeps the queries
simple and avoids relying on embedded foreign-key selects.
"""

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

router = APIRouter(prefix="/api/payments", tags=["payments"])

VIEW_ROLES = ("panchayat_staff", "panchayat_admin", "system_admin")
MANAGE_ROLES = ("panchayat_staff", "panchayat_admin", "system_admin")

# Allowed by the DB CHECK constraints:
#   payments.payment_status IN (Initiated, Successful, Failed, Processing, Refunded)
#   tax_records.status      IN (Pending, Paid, Overdue, Partially Paid)
STATUS_PENDING = "Initiated"      # citizen paid online -> awaiting Panchayat confirmation
STATUS_SUCCESS = "Successful"
STATUS_REJECTED = "Failed"
VALID_VERIFY = {STATUS_SUCCESS, STATUS_REJECTED}

SORTABLE = {"payment_date", "created_at", "amount"}

_PAGE = 1000          # PostgREST select cap -> page to read the whole table
_HARD_CAP = 200000    # safety stop for very large tables


def _msg(exc: Exception) -> str:
    return (getattr(exc, "message", None) or str(exc))[:300]


def _sanitize_q(value: Optional[str]) -> str:
    if not value:
        return ""
    return re.sub(r"[,%_*()]", " ", str(value)).strip().lower()[:80]


def _valid_date(value: Optional[str]) -> bool:
    if not value:
        return False
    try:
        datetime.strptime(str(value)[:10], "%Y-%m-%d")
        return True
    except ValueError:
        return False


def _fy_from_date(date_str: Optional[str]) -> str:
    """Indian financial year (Apr-Mar) as stored, e.g. '2025-2026'."""
    try:
        d = datetime.strptime(str(date_str)[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        d = datetime.now()
    start = d.year if d.month >= 4 else d.year - 1
    return f"{start}-{start + 1}"


def _fy_short(fy: str) -> str:
    try:
        start, end = fy.split("-")
        return f"{start}-{end[2:]}"
    except (ValueError, IndexError):
        return fy


# ---------------------------------------------------------------------------
# Data access helpers
# ---------------------------------------------------------------------------

def _query_payments(
    payment_status: Optional[str] = None,
    payment_method: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
):
    query = supabase.table("payments").select("*")
    if payment_status:
        query = query.eq("payment_status", payment_status.strip()[:20])
    if payment_method:
        query = query.eq("payment_method", payment_method.strip()[:30])
    if _valid_date(date_from):
        query = query.gte("payment_date", str(date_from)[:10])
    if _valid_date(date_to):
        query = query.lte("payment_date", str(date_to)[:10])
    return query


def _fetch_payments(
    payment_status: Optional[str] = None,
    payment_method: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list:
    rows, offset = [], 0
    while offset < _HARD_CAP:
        page = (
            _query_payments(payment_status, payment_method, date_from, date_to)
            .order("payment_date", desc=True)
            .range(offset, offset + _PAGE - 1)
            .execute()
            .data
            or []
        )
        rows.extend(page)
        if len(page) < _PAGE:
            break
        offset += _PAGE
    return rows


def _entity_maps(villager_ids: set, tax_ids: set):
    villager_map, user_map, tax_map, type_map = {}, {}, {}, {}
    if villager_ids:
        vs = (
            supabase.table("villagers")
            .select("villager_id,user_id,house_number,address,ward_id")
            .in_("villager_id", list(villager_ids))
            .execute()
            .data
            or []
        )
        user_ids = set()
        for v in vs:
            villager_map[v["villager_id"]] = v
            if v.get("user_id"):
                user_ids.add(v["user_id"])
        if user_ids:
            us = (
                supabase.table("users")
                .select("user_id,full_name,mobile_number")
                .in_("user_id", list(user_ids))
                .execute()
                .data
                or []
            )
            for u in us:
                user_map[u["user_id"]] = u
    if tax_ids:
        ts = (
            supabase.table("tax_records")
            .select("*")
            .in_("tax_id", list(tax_ids))
            .execute()
            .data
            or []
        )
        for t in ts:
            tax_map[t["tax_id"]] = t
        type_ids = {t.get("tax_type_id") for t in ts if t.get("tax_type_id")}
        if type_ids:
            for tt in (
                supabase.table("tax_types")
                .select("tax_type_id,name,frequency")
                .in_("tax_type_id", list(type_ids))
                .execute()
                .data
                or []
            ):
                type_map[tt["tax_type_id"]] = tt
    return villager_map, user_map, tax_map, type_map


def _enrich_payments(rows: list) -> list:
    villager_ids = {r.get("villager_id") for r in rows if r.get("villager_id")}
    tax_ids = {r.get("tax_id") for r in rows if r.get("tax_id")}
    villager_map, user_map, tax_map, type_map = _entity_maps(villager_ids, tax_ids)

    out = []
    for r in rows:
        v = villager_map.get(r.get("villager_id"), {})
        u = user_map.get(v.get("user_id"), {})
        t = tax_map.get(r.get("tax_id"), {})
        tt = type_map.get(t.get("tax_type_id"), {})
        out.append({
            **r,
            "citizen_name": u.get("full_name") or "Unknown citizen",
            "mobile_number": u.get("mobile_number") or "",
            "house_number": v.get("house_number") or "",
            "address": v.get("address") or "",
            "ward_id": v.get("ward_id") or "",
            "tax_type": tt.get("name") or "",
            "tax_frequency": tt.get("frequency") or "",
            "financial_year": t.get("financial_year") or "",
            "assessment_number": t.get("assessment_number") or "",
            "amount_due": t.get("amount_due"),
            "amount_paid": t.get("amount_paid"),
            "remaining_amount": t.get("remaining_amount"),
            "due_date": t.get("due_date") or "",
            "tax_status": t.get("status") or "",
        })
    return out


def _matches(row: dict, term: str) -> bool:
    haystack = " ".join(str(row.get(k) or "") for k in (
        "citizen_name", "mobile_number", "house_number", "receipt_number",
        "transaction_reference", "assessment_number", "tax_type", "payment_status",
        "payment_method", "financial_year",
    )).lower()
    return term in haystack


def _sort_key(row: dict, field: str):
    if field == "amount":
        try:
            return float(row.get("amount") or 0)
        except (TypeError, ValueError):
            return 0.0
    return str(row.get(field) or "")


def _filtered_enriched(
    payment_status: Optional[str] = None,
    payment_method: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list:
    rows = _fetch_payments(payment_status, payment_method, date_from, date_to)
    enriched = _enrich_payments(rows)
    term = _sanitize_q(q)
    if term:
        enriched = [r for r in enriched if _matches(r, term)]
    return enriched


def _credit_tax(tax_id: str, amount: float) -> Optional[dict]:
    """Add a confirmed payment amount to a tax record and recompute its status."""
    rows = supabase.table("tax_records").select("*").eq("tax_id", tax_id).execute().data
    if not rows:
        return None
    t = rows[0]
    due = float(t.get("amount_due") or 0)
    paid = float(t.get("amount_paid") or 0)
    new_paid = round(paid + float(amount or 0), 2)
    remaining = round(max(due - new_paid, 0), 2)
    today = datetime.now(timezone.utc).date().isoformat()
    if remaining <= 0:
        status = "Paid"
    elif new_paid > 0:
        status = "Partially Paid"
    elif t.get("due_date") and str(t["due_date"])[:10] < today:
        status = "Overdue"
    else:
        status = "Pending"
    update = {"amount_paid": new_paid, "status": status, "updated_at": datetime.now(timezone.utc).isoformat()}
    supabase.table("tax_records").update(update).eq("tax_id", tax_id).execute()
    return update


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------

class VerifyPayment(BaseModel):
    status: str = STATUS_SUCCESS
    reason: Optional[str] = None


class ManualPayment(BaseModel):
    tax_id: str
    amount: float = Field(gt=0)
    payment_method: str = Field(min_length=1)
    gateway_name: Optional[str] = None
    transaction_reference: Optional[str] = None
    note: Optional[str] = None


class DemandCreate(BaseModel):
    villager_id: str
    tax_type_id: str
    amount: float = Field(gt=0)
    financial_year: Optional[str] = None
    due_date: Optional[str] = None
    assessment_number: Optional[str] = None
    note: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
def list_payments(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    sort: str = Query("payment_date"),
    order: str = Query("desc"),
    payment_status: Optional[str] = Query(None, description="Initiated | Successful | Failed"),
    payment_method: Optional[str] = None,
    q: Optional[str] = Query(None, description="citizen / receipt / reference / tax type"),
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    date_to: Optional[str] = Query(None, description="YYYY-MM-DD (inclusive)"),
    current_user: CurrentUser = Depends(require_roles(*VIEW_ROLES)),
):
    rows = _filtered_enriched(payment_status, payment_method, q, date_from, date_to)
    sort_field = sort if sort in SORTABLE else "payment_date"
    rows.sort(key=lambda r: _sort_key(r, sort_field), reverse=(order != "asc"))
    total = len(rows)
    return {"results": rows[offset: offset + limit], "total": total, "limit": limit, "offset": offset}


@router.get("/summary")
def payments_summary(
    payment_status: Optional[str] = None,
    payment_method: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: CurrentUser = Depends(require_roles(*VIEW_ROLES)),
):
    rows = _filtered_enriched(payment_status, payment_method, q, date_from, date_to)
    today = datetime.now(timezone.utc).date().isoformat()
    collected = pending_amount = rejected_amount = today_collected = 0.0
    counts = {"total": 0, "successful": 0, "pending": 0, "rejected": 0}
    for r in rows:
        amount = float(r.get("amount") or 0)
        status = r.get("payment_status")
        counts["total"] += 1
        if status == STATUS_SUCCESS:
            counts["successful"] += 1
            collected += amount
            if str(r.get("payment_date") or "")[:10] == today:
                today_collected += amount
        elif status == STATUS_PENDING:
            counts["pending"] += 1
            pending_amount += amount
        elif status == STATUS_REJECTED:
            counts["rejected"] += 1
            rejected_amount += amount
    return {
        "total_collected": round(collected, 2),
        "today_collected": round(today_collected, 2),
        "pending_amount": round(pending_amount, 2),
        "rejected_amount": round(rejected_amount, 2),
        "counts": counts,
    }


@router.get("/export")
def export_payments(
    payment_status: Optional[str] = None,
    payment_method: Optional[str] = None,
    q: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    current_user: CurrentUser = Depends(require_roles(*VIEW_ROLES)),
):
    """Download the filtered fee-payment ledger as an Excel (.xlsx) spreadsheet."""
    rows = _filtered_enriched(payment_status, payment_method, q, date_from, date_to)

    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    headers = [
        "Receipt No", "Payment Date", "Status", "Citizen", "Mobile", "House No",
        "Tax Type", "Financial Year", "Assessment No", "Amount (INR)", "Method",
        "Gateway", "Transaction Ref", "Due Date", "Tax Status", "Remarks", "Recorded At",
    ]
    wb = Workbook()
    ws = wb.active
    ws.title = "Fee Payments"
    ws.append(headers)
    head_fill = PatternFill("solid", fgColor="0C4A6E")
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = head_fill
        cell.alignment = Alignment(horizontal="center", vertical="center")

    for r in rows:
        ws.append([
            r.get("receipt_number") or "",
            str(r.get("payment_date") or "")[:19].replace("T", " "),
            r.get("payment_status") or "",
            r.get("citizen_name") or "",
            r.get("mobile_number") or "",
            r.get("house_number") or "",
            r.get("tax_type") or "",
            r.get("financial_year") or "",
            r.get("assessment_number") or "",
            float(r.get("amount") or 0),
            r.get("payment_method") or "",
            r.get("gateway_name") or "",
            r.get("transaction_reference") or "",
            str(r.get("due_date") or "")[:10],
            r.get("tax_status") or "",
            r.get("failure_reason") or "",
            str(r.get("created_at") or "")[:19].replace("T", " "),
        ])

    widths = [18, 20, 12, 24, 14, 10, 20, 14, 18, 14, 14, 16, 22, 12, 12, 26, 20]
    for idx, width in enumerate(widths, start=1):
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = width
    ws.freeze_panes = "A2"

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    filename = f"kumbhari-fee-payments-{datetime.now().strftime('%Y-%m-%d')}.xlsx"
    return Response(
        content=buffer.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"', "Cache-Control": "no-store"},
    )


@router.get("/tax-types")
def list_tax_types(current_user: CurrentUser = Depends(require_roles(*VIEW_ROLES))):
    """Active tax/fee catalog used by the raise-demand modal."""
    rows = (
        supabase.table("tax_types")
        .select("tax_type_id,name,description,frequency,active")
        .eq("active", True)
        .order("name")
        .execute()
        .data
        or []
    )
    return rows


@router.get("/villagers")
def search_villagers(
    q: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=100),
    current_user: CurrentUser = Depends(require_roles(*VIEW_ROLES)),
):
    """Citizen lookup for the raise-demand / offline-payment modals."""
    vs = (
        supabase.table("villagers")
        .select("villager_id,user_id,house_number,address,ward_id")
        .execute()
        .data
        or []
    )
    user_ids = {v.get("user_id") for v in vs if v.get("user_id")}
    user_map = {}
    if user_ids:
        for u in (
            supabase.table("users")
            .select("user_id,full_name,mobile_number")
            .in_("user_id", list(user_ids))
            .execute()
            .data
            or []
        ):
            user_map[u["user_id"]] = u

    term = _sanitize_q(q)
    out = []
    for v in vs:
        u = user_map.get(v.get("user_id"), {})
        row = {
            "villager_id": v["villager_id"],
            "name": u.get("full_name") or "Unknown citizen",
            "mobile_number": u.get("mobile_number") or "",
            "house_number": v.get("house_number") or "",
            "ward_id": v.get("ward_id") or "",
        }
        if term and term not in " ".join(str(x).lower() for x in row.values()):
            continue
        out.append(row)
    out.sort(key=lambda r: r["name"].lower())
    return out[:limit]


@router.get("/dues")
def list_dues(
    q: Optional[str] = Query(None),
    limit: int = Query(60, ge=1, le=200),
    current_user: CurrentUser = Depends(require_roles(*VIEW_ROLES)),
):
    """Outstanding tax records across citizens (for offline payment recording)."""
    taxes = (
        supabase.table("tax_records")
        .select("*")
        .gt("remaining_amount", 0)
        .order("due_date", desc=False)
        .limit(1000)
        .execute()
        .data
        or []
    )
    villager_ids = {t.get("villager_id") for t in taxes if t.get("villager_id")}
    type_ids = {t.get("tax_type_id") for t in taxes if t.get("tax_type_id")}
    villager_map, user_map, type_map = {}, {}, {}
    if villager_ids:
        for v in (
            supabase.table("villagers")
            .select("villager_id,user_id,house_number")
            .in_("villager_id", list(villager_ids))
            .execute()
            .data
            or []
        ):
            villager_map[v["villager_id"]] = v
        user_ids = {v.get("user_id") for v in villager_map.values() if v.get("user_id")}
        if user_ids:
            for u in (
                supabase.table("users")
                .select("user_id,full_name,mobile_number")
                .in_("user_id", list(user_ids))
                .execute()
                .data
                or []
            ):
                user_map[u["user_id"]] = u
    if type_ids:
        for tt in (
            supabase.table("tax_types")
            .select("tax_type_id,name")
            .in_("tax_type_id", list(type_ids))
            .execute()
            .data
            or []
        ):
            type_map[tt["tax_type_id"]] = tt

    term = _sanitize_q(q)
    out = []
    for t in taxes:
        v = villager_map.get(t.get("villager_id"), {})
        u = user_map.get(v.get("user_id"), {})
        tt = type_map.get(t.get("tax_type_id"), {})
        row = {
            "tax_id": t["tax_id"],
            "villager_id": t.get("villager_id"),
            "citizen_name": u.get("full_name") or "Unknown citizen",
            "mobile_number": u.get("mobile_number") or "",
            "house_number": v.get("house_number") or "",
            "tax_type": tt.get("name") or "Tax",
            "financial_year": t.get("financial_year") or "",
            "assessment_number": t.get("assessment_number") or "",
            "amount_due": float(t.get("amount_due") or 0),
            "amount_paid": float(t.get("amount_paid") or 0),
            "remaining_amount": float(t.get("remaining_amount") or 0),
            "due_date": t.get("due_date") or "",
            "status": t.get("status") or "",
        }
        if term and term not in " ".join(str(x).lower() for x in row.values()):
            continue
        out.append(row)
    return out[:limit]


@router.post("/{payment_id}/verification")
def verify_payment(
    payment_id: str,
    payload: VerifyPayment,
    request: Request,
    current_user: CurrentUser = Depends(require_roles(*MANAGE_ROLES)),
):
    if payload.status not in VALID_VERIFY:
        raise HTTPException(status_code=400, detail="Status must be Successful or Failed")

    rows = supabase.table("payments").select("*").eq("payment_id", payment_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Payment not found")
    payment = rows[0]
    if payment.get("payment_status") != STATUS_PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"This payment is already {payment.get('payment_status')} and cannot be changed again.",
        )

    now = datetime.now(timezone.utc).isoformat()
    update = {"payment_status": payload.status, "updated_at": now}
    if payload.status == STATUS_SUCCESS:
        update["failure_reason"] = None
        if payment.get("tax_id"):
            _credit_tax(payment["tax_id"], float(payment.get("amount") or 0))
    else:
        update["failure_reason"] = (payload.reason or "Rejected by Panchayat Desk").strip()[:500]

    result = supabase.table("payments").update(update).eq("payment_id", payment_id).execute()
    updated = result.data[0] if result.data else {**payment, **update}

    log_audit(
        actor_id=current_user.user_id,
        action=f"MarkFeePayment{payload.status}",
        entity_type="payment",
        entity_id=payment_id,
        old_values={"status": STATUS_PENDING},
        new_values={"status": payload.status, "amount": payment.get("amount"), "reason": payload.reason},
        request=request,
    )
    return updated


@router.post("/manual", status_code=201)
def record_manual_payment(
    payload: ManualPayment,
    request: Request,
    current_user: CurrentUser = Depends(require_roles(*MANAGE_ROLES)),
):
    """Record an offline (cash / cheque) payment when an online payment never synced."""
    rows = supabase.table("tax_records").select("*").eq("tax_id", payload.tax_id).execute().data
    if not rows:
        raise HTTPException(status_code=404, detail="Tax record not found")
    tax = rows[0]

    due = float(tax.get("amount_due") or 0)
    paid = float(tax.get("amount_paid") or 0)
    remaining = round(due - paid, 2)
    if remaining <= 0:
        raise HTTPException(status_code=400, detail="This tax is already fully paid")
    amount = round(float(payload.amount), 2)
    if amount <= 0 or amount > remaining + 0.001:
        raise HTTPException(status_code=400, detail="Amount must be between ₹1 and the outstanding balance")

    now = datetime.now(timezone.utc).isoformat()
    year = datetime.now().year
    payment = {
        "payment_id": str(uuid.uuid4()),
        "villager_id": tax.get("villager_id"),
        "tax_id": payload.tax_id,
        "amount": amount,
        "payment_method": payload.payment_method.strip()[:30],
        "gateway_name": (payload.gateway_name or payload.payment_method).strip()[:60],
        "transaction_reference": (payload.transaction_reference or "").strip()[:60]
        or f"OFF{year}{uuid.uuid4().hex[:10].upper()}",
        "gateway_reference": None,
        "payment_status": STATUS_SUCCESS,
        "payment_date": now,
        "receipt_number": f"RCPT-{year}-{uuid.uuid4().hex[:8].upper()}",
        "failure_reason": (payload.note or "").strip()[:500] or None,
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = supabase.table("payments").insert(payment).execute()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not save payment: {_msg(exc)}")
    created = result.data[0] if result.data else payment

    _credit_tax(payload.tax_id, amount)

    log_audit(
        actor_id=current_user.user_id,
        action="RecordOfflineFeePayment",
        entity_type="payment",
        entity_id=payment["payment_id"],
        new_values={"amount": amount, "method": payment["payment_method"], "tax_id": payload.tax_id},
        request=request,
    )
    return created


@router.post("/demands", status_code=201)
def raise_demand(
    payload: DemandCreate,
    request: Request,
    current_user: CurrentUser = Depends(require_roles(*MANAGE_ROLES)),
):
    """Raise a new fee demand: create a tax record for a citizen to pay."""
    vrows = (
        supabase.table("villagers")
        .select("villager_id,family_id,village_id")
        .eq("villager_id", payload.villager_id)
        .execute()
        .data
    )
    if not vrows:
        raise HTTPException(status_code=404, detail="Citizen profile not found")

    tt = (
        supabase.table("tax_types")
        .select("tax_type_id,name")
        .eq("tax_type_id", payload.tax_type_id)
        .execute()
        .data
    )
    if not tt:
        raise HTTPException(status_code=404, detail="Tax type not found")

    if payload.due_date and not _valid_date(payload.due_date):
        raise HTTPException(status_code=400, detail="due_date must be YYYY-MM-DD")

    today = datetime.now(timezone.utc).date().isoformat()
    fy = (payload.financial_year or "").strip() or _fy_from_date(payload.due_date or today)
    due_date = str(payload.due_date)[:10] if payload.due_date else None
    if due_date and due_date < today:
        status = "Overdue"
    else:
        status = "Pending"
    assessment = (payload.assessment_number or "").strip()[:60] or \
        f"ASMT-{_fy_short(fy)}-{uuid.uuid4().hex[:6].upper()}"

    now = datetime.now(timezone.utc).isoformat()
    record = {
        "tax_id": str(uuid.uuid4()),
        "villager_id": payload.villager_id,
        "family_id": vrows[0].get("family_id"),
        "tax_type_id": payload.tax_type_id,
        "financial_year": fy,
        "assessment_number": assessment,
        "amount_due": round(float(payload.amount), 2),
        "amount_paid": 0,
        "due_date": due_date,
        "status": status,
        "created_at": now,
        "updated_at": now,
    }
    try:
        result = supabase.table("tax_records").insert(record).execute()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Could not raise demand: {_msg(exc)}")
    created = result.data[0] if result.data else record

    log_audit(
        actor_id=current_user.user_id,
        action="RaiseFeeDemand",
        entity_type="tax_record",
        entity_id=record["tax_id"],
        new_values={"villager_id": payload.villager_id, "tax_type": tt[0].get("name"), "amount": record["amount_due"]},
        request=request,
    )
    return created
