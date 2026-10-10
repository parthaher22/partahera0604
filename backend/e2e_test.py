import json, urllib.request, urllib.error, random

from app.supabase_client import supabase

BASE = "http://127.0.0.1:5000"

def req(path, method="GET", body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    r = urllib.request.Request(BASE + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=25) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read().decode()
        try:
            parsed = json.loads(raw)
        except Exception:
            parsed = raw
        return e.code, parsed

def show(label, status, body):
    print(f"[{label}] HTTP {status}")
    print("   ", json.dumps(body, indent=None, ensure_ascii=False)[:700] if isinstance(body, (dict, list)) else body)

s, b = req("/health"); show("health", s, b)

s, villages = req("/api/villages")
s, categories = req("/api/complaint-categories")
vid = villages[0]["village_id"]
s, wards = req("/api/wards?village_id=" + vid)
wid = wards[0]["ward_id"]
catid = categories[0]["category_id"]
print("reference ok:", vid[:8], wid[:8], catid[:8])

mobile = "9" + str(random.randint(100000000, 999999999))
reg = {"full_name": "E2E Test User", "mobile_number": mobile, "password": "Test@1234", "village_id": vid, "ward_id": wid}
s, b = req("/api/auth/register", "POST", reg); show("register", s, b)
uid = b["user_id"]
tok = b["access_token"]

s, b = req("/api/auth/login", "POST", {"mobile_number": mobile, "password": "Test@1234"}); show("login", s, b)
tok = b["access_token"]

s, b = req("/api/auth/login", "POST", {"mobile_number": mobile, "password": "wrong"}); show("login-bad-pwd", s, b)

s, b = req("/api/auth/me", token=tok); show("me-(villager)", s, b)

comp = {"category_id": catid, "title": "E2E: Street light out", "description": "Backend wiring test.", "location": "Test point", "priority": "High"}
s, b = req("/api/complaints", "POST", comp, tok); show("create-complaint(villager)", s, b)
cid = b["complaint_id"]

s, b = req("/api/audit-logs", token=tok); show("audit-logs(villager->403 expected)", s, b)
s, b = req(f"/api/complaints/{cid}/status", "PATCH", {"new_status": "Resolved"}, tok); show("status-patch(villager->403 expected)", s, b)

s, b = req("/api/announcements", token=tok); show("announcements(villager)", s, b)

# --- promote to staff and re-login (role is embedded in the JWT at login) ---
print(">>> Promoting user to panchayat_staff via service-role client...")
supabase.table("users").update({"role": "panchayat_staff"}).eq("user_id", uid).execute()
s, b = req("/api/auth/login", "POST", {"mobile_number": mobile, "password": "Test@1234"}); show("login(staff)", s, b)
stok = b["access_token"]
print("   staff role claim:", stok.split(".")[1] and "panchayat_staff" in __import__("base64").urlsafe_b64decode(stok.split(".")[1] + "==").decode())

s, b = req("/api/auth/me", token=stok); show("me-(staff)", s, b)
s, b = req("/api/audit-logs", token=stok); show("audit-logs(staff)", s, b)
s, b = req(f"/api/complaints/{cid}/status", "PATCH", {"new_status": "Under Review", "remark": "Verified in system."}, stok); show("status-patch(staff)", s, b)
s, b = req(f"/api/complaints/{cid}", token=stok); show("detail-after-update", s, b)
s, b = req("/api/complaints", token=stok); show("list-complaints(staff)", s, b)

print("\nDONE. Test user:", mobile)