"""
api/main.py

FastAPI application entry point.

Run with:
    uvicorn api.main:app --reload --port 8000
    (or: python scripts/run_api.py)

Serves the JSON API on :8000, consumed by the Next.js frontend via its
/api/proxy route (frontend/app/api/proxy/[...path]/route.ts), which
injects the caller's Supabase bearer token server-side.
"""

import logging

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import incidents, vendors, controls, admin, evidence
from api.routers.auth import router as auth_router
from api.routers.profile import router as profile_router

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Vendor Threat Monitor API",
    description="SOC 2 compliance and vendor threat intelligence platform.",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(profile_router, prefix="/api/v1")

# ---------------------------------------------------------------------------
# CORS
# During development: allow localhost:3000 (Next.js)
# In production: restrict to actual domain
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js dev server
        "http://localhost:8000",   # FastAPI itself (for Swagger UI)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers — all mounted under /api/v1
# ---------------------------------------------------------------------------

app.include_router(incidents.router, prefix="/api/v1", tags=["incidents"])
app.include_router(vendors.router,   prefix="/api/v1", tags=["vendors"])
app.include_router(controls.router,  prefix="/api/v1", tags=["controls"])
app.include_router(admin.router,     prefix="/api/v1", tags=["admin"])
app.include_router(evidence.router,  prefix="/api/v1", tags=["evidence"])


# ---------------------------------------------------------------------------
# Health check — unauthenticated, used by deployment health probes
# ---------------------------------------------------------------------------

@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "version": "1.0.0"}