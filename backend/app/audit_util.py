"""Central audit writer.

Every administrative mutation goes through log_audit() so the audit trail
consistently captures WHO did WHAT — including the requesting IP address and
browser user-agent (privacy: stored for security auditing only, never shown
to citizens).
"""

from typing import Optional

from fastapi import Request

from app.supabase_client import supabase


def _client_meta(request: Optional[Request]):
    if request is None:
        return None, None
    try:
        ip = request.client.host if request.client else None
    except Exception:
        ip = None
    try:
        ua = (request.headers.get("user-agent") or "").strip()[:300] or None
    except Exception:
        ua = None
    return ip, ua


def log_audit(
    actor_id: Optional[str],
    action: str,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    old_values: Optional[dict] = None,
    new_values: Optional[dict] = None,
    request: Optional[Request] = None,
) -> None:
    payload = {
        "actor_id": actor_id,
        "action": action,
        "entity_type": entity_type,
        "entity_id": entity_id,
        "old_values": old_values,
        "new_values": new_values,
    }
    ip, ua = _client_meta(request)
    if ip:
        payload["ip_address"] = ip
    if ua:
        payload["user_agent"] = ua
    try:
        supabase.table("audit_logs").insert(payload).execute()
    except Exception as exc:
        # An audit failure must never break the business operation.
        print(f"[audit] write failed for '{action}': {exc}", flush=True)
