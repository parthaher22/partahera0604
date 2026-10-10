import io
import os
import random
import string
from urllib.parse import urlencode

from fastapi import APIRouter, Query, Response

import segno

router = APIRouter(prefix="/api/pay", tags=["pay"])

PAYEE_UPI_ID = os.getenv("PAYEE_UPI_ID", "gramsetukumbhari@okhdfcbank")
PAYEE_NAME = os.getenv("PAYEE_NAME", "Kumbhari Gram Panchayat")


def _transaction_ref() -> str:
    return "GS" + "".join(random.choices(string.digits, k=10))


@router.get("/upi-qr")
def upi_qr(
    amount: float = Query(0, ge=0),
    name: str = Query(PAYEE_NAME),
    note: str = Query(None),
    upi_id: str = Query(PAYEE_UPI_ID),
):
    params = {
        "pa": upi_id,
        "pn": (name or PAYEE_NAME)[:48],
        "cu": "INR",
        "tr": _transaction_ref(),
    }
    if amount > 0:
        params["am"] = f"{amount:.2f}"
    if note:
        params["tn"] = note[:80]

    qr = segno.make("upi://pay?" + urlencode(params), error="m")
    buf = io.BytesIO()
    qr.save(buf, kind="png", scale=6, border=2)
    buf.seek(0)
    return Response(
        content=buf.getvalue(),
        media_type="image/png",
        headers={"Cache-Control": "no-store", "X-UPI-ID": PAYEE_UPI_ID},
    )