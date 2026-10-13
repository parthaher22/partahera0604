import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from app.audit_util import log_audit
from app.supabase_client import supabase
from app.security import get_current_user, CurrentUser

router = APIRouter(prefix="/api/tax", tags=["tax"])


def _villager_id_for(user_id: str) -> str:
    row = supabase.table("villagers").select("villager_id").eq("user_id", user_id).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Villager profile not found")
    return row.data[0]["villager_id"]


class TaxPaymentRequest(BaseModel):
    payment_method: str = "UPI"
    gateway_name: Optional[str] = "UPI QR"
    amount: Optional[float] = None


def _empty_summary() -> dict:
    return {"total_assessed": 0, "total_paid": 0, "outstanding": 0, "pending_count": 0, "overdue_count": 0, "paid_count": 0}


@router.get("/my-taxes")
def my_taxes(current_user: CurrentUser = Depends(get_current_user)):
    """Detailed tax dues + payment history for the logged-in citizen."""
    if current_user.role != "villager":
        return {"records": [], "summary": _empty_summary()}

    villager_id = _villager_id_for(current_user.user_id)

    taxes = (
        supabase.table("tax_records")
        .select("*")
        .eq("villager_id", villager_id)
        .order("due_date", desc=True)
        .limit(200)
        .execute()
    )
    types = {t["tax_type_id"]: t for t in supabase.table("tax_types").select("*").execute().data or []}
    payments = (
        supabase.table("payments")
        .select("*")
        .eq("villager_id", villager_id)
        .order("payment_date", desc=True)
        .limit(500)
        .execute()
    )
    user = supabase.table("users").select("full_name, mobile_number").eq("user_id", current_user.user_id).execute()
    villager = supabase.table("villagers").select("house_number, ward_id, address").eq("villager_id", villager_id).execute()

    payments_by_tax = {}
    for p in payments.data or []:
        payments_by_tax.setdefault(p.get("tax_id"), []).append(p)

    records = []
    summary = {"total_assessed": 0, "total_paid": 0, "outstanding": 0, "pending_count": 0, "overdue_count": 0, "paid_count": 0}
    today = datetime.now(timezone.utc).date().isoformat()

    for t in taxes.data or []:
        tt = types.get(t.get("tax_type_id"), {})
        due = float(t.get("amount_due") or 0)
        paid = float(t.get("amount_paid") or 0)
        remaining = float(t.get("remaining_amount") or (due - paid))
        status = t.get("status") or "Overdue"
        txns = payments_by_tax.get(t.get("tax_id"), [])
        last = txns[0] if txns else None
        pending = next((p for p in txns if (p.get("payment_status") or "") == "Initiated"), None)
        records.append({
            "tax_id": t.get("tax_id"),
            "type": tt.get("name") or "Tax",
            "type_description": tt.get("description") or "",
            "frequency": tt.get("frequency") or "",
            "financial_year": t.get("financial_year") or "",
            "assessment_number": t.get("assessment_number") or "",
            "amount_due": due,
            "amount_paid": paid,
            "remaining_amount": remaining,
            "due_date": t.get("due_date") or "",
            "status": status,
            "is_overdue": status != "Paid" and bool(t.get("due_date")) and t.get("due_date") < today,
            "last_payment": {
                "receipt_number": last.get("receipt_number") if last else None,
                "transaction_reference": last.get("transaction_reference") if last else None,
                "payment_date": last.get("payment_date") if last else None,
                "payment_method": last.get("payment_method") if last else None,
                "gateway_name": last.get("gateway_name") if last else None,
                "amount": last.get("amount") if last else None,
            } if last else None,
            "pending_payment": {
                "receipt_number": pending.get("receipt_number"),
                "transaction_reference": pending.get("transaction_reference"),
                "payment_date": pending.get("payment_date"),
                "payment_method": pending.get("payment_method"),
                "gateway_name": pending.get("gateway_name"),
                "amount": pending.get("amount"),
            } if pending else None,
            "payments": [{
                "receipt_number": p.get("receipt_number"),
                "transaction_reference": p.get("transaction_reference"),
                "payment_date": p.get("payment_date"),
                "payment_method": p.get("payment_method"),
                "gateway_name": p.get("gateway_name"),
                "amount": p.get("amount"),
                "status": p.get("payment_status"),
            } for p in txns],
        })
        summary["total_assessed"] += due
        summary["total_paid"] += paid
        summary["outstanding"] += remaining
        if status == "Paid":
            summary["paid_count"] += 1
        else:
            summary["pending_count"] += 1
            if records[-1]["is_overdue"]:
                summary["overdue_count"] += 1

    profile = (user.data[0] if user.data else {}) | (villager.data[0] if villager.data else {})
    return {
        "records": records,
        "summary": {k: round(v, 2) for k, v in summary.items()},
        "profile": {
            "name": profile.get("full_name") or "",
            "mobile_number": profile.get("mobile_number") or "",
            "house_number": profile.get("house_number") or "",
            "address": profile.get("address") or "",
            "ward_id": profile.get("ward_id") or "",
        },
    }


@router.post("/{tax_id}/pay", status_code=201)
def pay_tax(tax_id: str, payload: TaxPaymentRequest, request: Request, current_user: CurrentUser = Depends(get_current_user)):
    """Citizen initiates an online fee payment.

    The payment is recorded as PENDING and the tax balance is left untouched
    until the Panchayat Desk confirms it (POST /api/payments/{id}/verification).
    """
    if current_user.role != "villager":
        raise HTTPException(status_code=403, detail="Only citizens can pay taxes")

    villager_id = _villager_id_for(current_user.user_id)
    row = supabase.table("tax_records").select("*").eq("tax_id", tax_id).execute()
    if not row.data:
        raise HTTPException(status_code=404, detail="Tax record not found")
    tax = row.data[0]
    if tax.get("villager_id") != villager_id:
        raise HTTPException(status_code=403, detail="This tax record belongs to another citizen")

    remaining = float(tax.get("remaining_amount") or (float(tax.get("amount_due") or 0) - float(tax.get("amount_paid") or 0)))
    if remaining <= 0:
        raise HTTPException(status_code=400, detail="This tax is already fully paid")

    pending_rows = (
        supabase.table("payments")
        .select("payment_id, receipt_number")
        .eq("tax_id", tax_id)
        .eq("payment_status", "Initiated")
        .execute()
        .data
        or []
    )
    if pending_rows:
        raise HTTPException(
            status_code=409,
            detail="A payment for this tax is already awaiting confirmation by the Panchayat Desk.",
        )

    amount = float(payload.amount) if payload.amount else remaining
    if amount <= 0 or amount > remaining:
        raise HTTPException(status_code=400, detail="Amount must be between ₹1 and the outstanding balance")

    now = datetime.now(timezone.utc).isoformat()
    year = datetime.now().year
    receipt_number = f"RCPT-{year}-{uuid.uuid4().hex[:8].upper()}"
    transaction_reference = f"TXN{year}{uuid.uuid4().hex[:10].upper()}"

    payment = {
        "payment_id": str(uuid.uuid4()),
        "villager_id": villager_id,
        "tax_id": tax_id,
        "amount": round(amount, 2),
        "payment_method": payload.payment_method,
        "gateway_name": payload.gateway_name or "UPI QR",
        "transaction_reference": transaction_reference,
        "gateway_reference": None,
        "payment_status": "Initiated",
        "payment_date": now,
        "receipt_number": receipt_number,
        "failure_reason": None,
        "created_at": now,
        "updated_at": now,
    }
    supabase.table("payments").insert(payment).execute()

    log_audit(
        actor_id=current_user.user_id,
        action="Initiate Tax Payment",
        entity_type="tax_record",
        entity_id=tax_id,
        new_values={"amount": amount, "receipt_number": receipt_number, "method": payload.payment_method},
        request=request,
    )

    # The tax balance is credited only after the Panchayat confirms the payment.
    return {"payment": payment, "tax": dict(tax)}
