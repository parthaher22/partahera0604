# E-GramPanchayat — FastAPI Backend Starter

This is a backend API layer sitting between your frontend and the Supabase
Postgres database (`spknqgeqoschbtlwzhxj`). The frontend never talks to Supabase
directly — it only calls this API, which uses the Supabase **service role key**
(full trust, bypasses RLS) and enforces authorization itself.

## What's implemented

- `POST /api/auth/register`, `POST /api/auth/login` — issues your own JWT
- `GET/POST /api/complaints`, `GET /api/complaints/:id`, `PATCH /api/complaints/:id/status`
- `GET/POST/PATCH /api/announcements`
- `GET /api/dashboard/villager`, `GET /api/dashboard/panchayat`

This covers the core flow end-to-end (register → login → file a complaint →
staff updates status → villager sees it on their dashboard) so you can see the
whole pattern working. The remaining endpoints from the spec (members, schemes,
taxes, payments, projects, finance, notifications, reports) follow the exact
same shape — see "Adding a new endpoint" below.

## Setup

```bash
cd egram-backend
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env:
#   - SUPABASE_SERVICE_ROLE_KEY: Supabase Dashboard -> Project Settings -> API -> service_role
#   - JWT_SECRET: any long random string (e.g. `openssl rand -hex 32`)
```

## Run

```bash
uvicorn app.main:app --reload --port 5000
```

Visit `http://localhost:5000/docs` for interactive Swagger UI — you can register,
log in, and try every endpoint from the browser before wiring up your frontend.

## Run the (already wired) frontend

The dashboard at `grampanchayat/frontend/` talks to this backend through
`window.gramSetu` (`app.js`, base URL `http://localhost:5000`, override via
`window.GRAMSETU_API`). Serve it and open it in a browser:

```bash
python -m http.server 8001 --directory grampanchayat/frontend
# then open http://localhost:8001  (origin must be in ALLOWED_ORIGINS)
```

Login/registration hit `/api/auth/*`; complaints, announcements and audit logs
are real API calls. Members, schemes, taxes and the finance module still use the
`DEMO_*` data in `app.js` until those endpoints are implemented.

## Calling it from the frontend

Plain `fetch`, works from React/Vue/plain JS/anything:

```js
const API_BASE = "http://localhost:5000"; // your deployed backend URL in production

// 1. Register
const registerRes = await fetch(`${API_BASE}/api/auth/register`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    full_name: "Ramesh Patil",
    mobile_number: "9876543210",
    password: "secret123",
    village_id: "<a real village_id from your DB>",
    ward_id: "<a real ward_id in that village>",
  }),
});
const { access_token } = await registerRes.json();

// 2. Store the token (e.g. localStorage, or an httpOnly cookie set by your backend)
localStorage.setItem("token", access_token);

// 3. Call authenticated endpoints with the token
const complaints = await fetch(`${API_BASE}/api/complaints`, {
  headers: { Authorization: `Bearer ${localStorage.getItem("token")}` },
}).then((r) => r.json());

// 4. File a complaint
await fetch(`${API_BASE}/api/complaints`, {
  method: "POST",
  headers: {
    "Content-Type": "application/json",
    Authorization: `Bearer ${localStorage.getItem("token")}`,
  },
  body: JSON.stringify({
    category_id: "<a real category_id>",
    title: "Water pipeline leaking near main road",
    description: "There has been a water leak for 3 days near ward office.",
    priority: "High",
  }),
});
```

To find real `village_id`/`ward_id`/`category_id` values for testing, query them
via Swagger UI's SQL, or add a quick `GET /api/villages`, `GET /api/wards`,
`GET /api/complaint-categories` endpoint (trivial — same pattern as below).

## Adding a new endpoint (the pattern)

Every route follows the same shape:

```python
from fastapi import APIRouter, Depends
from app.supabase_client import supabase
from app.security import get_current_user, require_roles, CurrentUser

router = APIRouter(prefix="/api/schemes", tags=["schemes"])

@router.get("")
def list_schemes(current_user: CurrentUser = Depends(get_current_user)):
    result = supabase.table("schemes").select("*").eq("status", "active").execute()
    return result.data

@router.post("", status_code=201)
def create_scheme(payload: dict, current_user: CurrentUser = Depends(require_roles("panchayat_admin"))):
    inserted = supabase.table("schemes").insert({**payload, "created_by": current_user.user_id}).execute()
    return inserted.data[0]
```

Then in `app/main.py`:
```python
from app.routers import schemes
app.include_router(schemes.router)
```

Repeat for `taxes`, `payments`, `projects`, `financial-records` (filter
`verification_status = 'Verified'` for villager reads), `notifications`
(filter `user_id = current_user.user_id`), and the `reports/*` endpoints
(read straight from the `vw_*` analytics views — see the main documentation
doc for which view backs which report).

## Deployment notes

- Deploy this API anywhere that runs Python (Render, Railway, Fly.io, a VM, etc.).
  Set the same environment variables there.
- Point your frontend's `API_BASE` at the deployed URL, and update
  `ALLOWED_ORIGINS` in `.env` to your frontend's real domain.
- Never put `SUPABASE_SERVICE_ROLE_KEY` in any frontend code or public repo.
- Postgres unique/FK/CHECK constraints are your last line of defense — even if
  a bug slips past this API's own validation, the database will reject bad data.
