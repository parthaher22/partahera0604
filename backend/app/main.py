from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import ALLOWED_ORIGINS
from app.routers import auth, complaints, announcements, dashboard, reference, audit, staff, pay, tax, notifications, finance

app = FastAPI(title="E-GramPanchayat API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(complaints.router)
app.include_router(announcements.router)
app.include_router(dashboard.router)
app.include_router(reference.router)
app.include_router(audit.router)
app.include_router(staff.router)
app.include_router(pay.router)
app.include_router(tax.router)
app.include_router(notifications.router)
app.include_router(finance.router)


@app.get("/health")
def health():
    return {"status": "ok"}
