# SOC Readiness SaaS Platform

A SOC 2 examination workflow platform for internal GRC teams preparing for Type 1
and Type 2 audits — control inventory, evidence collection, AI-assisted evidence
evaluation against AICPA testing attributes, and vendor threat monitoring, in one
place.

---

## Live Demo
Try it now: [soc-readiness-saas-demo.vercel.app](https://soc-readiness-saas-demo.vercel.app)

Click "View Demo" on the login page for instant read-only access — no signup required.

> Note: the backend may take ~15-30 seconds to wake up on first load if it's 
> been idle (free-tier hosting). Subsequent requests are fast.

---

## What this is

Most compliance tooling (Vanta, Drata, and similar) focuses on automated evidence
*collection* — pulling configuration snapshots from connected systems and treating
"connected" as "compliant." This project takes a different angle: **audit
preparation intelligence**. It assumes evidence has to be gathered manually (which
is still true for a large share of real-world SOC 2 controls) and instead focuses
on getting that evidence *audit-ready before the auditor sees it*.

The core of this is `app/ai/evidence_evaluator.py`, which evaluates uploaded
evidence against the same distinctions an auditor actually reasons in:

- **Walkthrough** evidence must prove a control *exists* and is *suitably
  designed* — design effectiveness, point in time.
- **Population** evidence must prove the *complete population* of items the
  control operated on during the test period.
- **IPE** (Information Produced by the Entity) evidence must prove that
  population export is itself *complete and accurate* — a distinct audit step
  most GRC tooling skips entirely.
- **Sample** evidence must prove the control *operated for a specific item*
  drawn from that population — contemporaneous evidence only.

Getting this distinction right is most of what separates evidence that survives
audit scrutiny from evidence that gets kicked back. The evaluator returns a
verdict (`ready_to_submit` / `needs_work` / `do_not_submit`), a rejection-risk
rating, and specific gaps to fix — not just a pass/fail.

A secondary module (the original "vendor threat monitor") collects vendor-related
security incidents from RSS/CVE feeds, classifies them with AI, and maps them to
the TSC criteria they affect, feeding the Incidents view in the dashboard.

---

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 16 (App Router, TypeScript), Tailwind CSS v4, Tremor Raw, TanStack Table, Radix UI |
| Backend | FastAPI (Python, async), psycopg2 |
| Database / Auth | Supabase (Postgres + Row Level Security + Auth) |
| AI | OpenAI GPT-4.1 (evidence evaluation), GPT-4.1-mini (incident classification) |
| Threat collector | feedparser (RSS), RapidFuzz (vendor matching) |
| Document handling | PyMuPDF, python-docx, openpyxl, reportlab |

---

## Architecture

```
frontend/                        Next.js 16 App Router, TypeScript
├── app/(dashboard)/             Controls, Vendors, Incidents, Settings
├── app/api/proxy/[...path]/     Server-side proxy → FastAPI
└── lib/api.ts                   Thin client wrapper around the proxy

api/                              FastAPI backend (JSON API, :8000)
├── main.py                      App entry point, router mounts, CORS
├── dependencies.py               Supabase JWT verification (JWKS)
├── routers/                     incidents, vendors, controls, admin, evidence, auth, profile
└── schemas/                     Pydantic request/response models

app/                              Shared business logic, imported by api/
├── ai/                          evidence_evaluator, incident_classifier, severity_scorer
├── collectors/                  RSS + CVE feed collectors
├── alerts/                      Email / Slack alerting for the threat collector
├── utils/                       db_postgres, control_classification, soc_mapper, pii_scrubber, ...
└── reports/                     (currently empty — see Known Limitations)

scripts/                          Entry points: run_api.py, run_collector.py, ad-hoc test scripts
supabase/migrations/              Incremental schema migrations (see Setup — not the full schema)
```

**Auth flow.** The frontend never talks to FastAPI directly. Every request goes
through `frontend/app/api/proxy/[...path]/route.ts`, a Next.js route handler that
reads the caller's Supabase session server-side, injects it as a `Bearer` token,
and forwards the request to FastAPI. FastAPI verifies the token against
Supabase's JWKS endpoint (`api/dependencies.py`) — `org_id` and `role` arrive as
custom JWT claims via a Supabase Auth hook, so there's no extra DB round-trip to
authorize a request.

**Control classification.** `app/utils/control_classification.py` is the other
piece of core domain logic: given a control's type (`manual` / `automated` /
`itdm`) and testing frequency, it derives what evidence an auditor will actually
expect — whether a population export and IPE validation are required, and the
suggested sample size (e.g. an annual manual control needs one instance; a weekly
one needs a 15-item sample). This drives what the evidence-evaluator checks for
and what the UI prompts the user to upload.

---

## Setup

### Prerequisites

- Node.js 20+
- Python 3.11+
- A [Supabase](https://supabase.com) project (free tier is enough)
- An OpenAI API key

### 1. Clone and install

```bash
git clone <this-repo>
cd vendor-threat-monitor

python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

cd frontend && npm install && cd ..
```

### 2. Set up Supabase

1. Create a new Supabase project.
2. **Base schema**: this repo's schema was originally created directly in the
   Supabase SQL Editor rather than as a version-controlled migration (see Known
   Limitations) — there is currently no single script that creates
   `organizations`, `profiles`, `vendors`, `controls`, `incidents`, etc. from
   scratch. `supabase/migrations/` only contains *incremental* changes on top of
   that base schema.
3. Apply any files in `supabase/migrations/` in filename order, by pasting them
   into the Supabase SQL Editor rather than running them via `psql` — that's the
   workflow this project actually uses day to day, even though the migration
   file's own header comment (written when it was authored) suggests `psql`.
4. **Auth hook**: under Authentication → Hooks, configure a Custom Access Token
   hook that embeds `org_id` and `role` into the JWT as custom claims. FastAPI's
   auth dependency (`api/dependencies.py`) reads these directly from the token —
   without the hook, every authenticated request will fail with a 401.
5. Grab your project's URL, anon key, service role key, and Postgres connection
   string from Project Settings → API / Database.

### 3. Environment variables

Copy the example files and fill in the values from your Supabase project and
OpenAI account:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

See `.env.example` and `frontend/.env.example` for the full list of variables —
none of the placeholder values in either file are real.

### 4. Run it

```bash
# Backend — http://localhost:8000 (Swagger UI at /api/docs)
python scripts/run_api.py

# Frontend — http://localhost:3000
cd frontend && npm run dev
```

### 5. Optional: threat collector

```bash
python scripts/run_collector.py
```

Pulls from RSS/CVE feeds, classifies with AI, and stores incidents. Intended to
run on a schedule (e.g. cron every few hours) rather than continuously — there's
no built-in scheduler.

---

## Known limitations

Documented here deliberately, not hidden — this is what's left to harden, not a
claim that it's finished:

- **Single-tenant assumptions remain in the threat collector.** `scripts/run_collector.py`
  hardcodes `org_id=1` when fetching vendors and storing incidents. The rest of
  the platform (controls, evidence, auth) is properly multi-tenant via Supabase
  RLS; the collector hasn't caught up.
- **No CI or formal test suite yet.** `scripts/test_phase4_security.py` and
  `scripts/test_pipeline.py` are ad-hoc smoke-test scripts that exercise real
  code paths (PII scrubbing, prompt injection guards, the classification
  pipeline) but aren't wired into any CI pipeline or test runner.
- **Base schema isn't version-controlled.** As noted in Setup, the initial
  Postgres schema was created via the Supabase Studio SQL Editor rather than a
  migration file. `supabase/migrations/` only captures changes made *after*
  that point. Same goes for the Auth hook — it's dashboard configuration, not
  code.
- **`app/reports/`** is currently an empty package — the PDF report generator
  that lived there was removed once its only caller, the Flask `threat_monitor`
  blueprint, was deleted; nothing in the current FastAPI/Next.js stack generates
  PDF exports yet.
- **`npm audit`** reports 3 high-severity advisories (PostCSS XSS/path traversal, 
  sharp/libvips CVEs) in dependencies bundled internally by Next.js's image 
  optimization pipeline. As of Next.js 16.2.12 (the latest release at time of 
  writing), no patched version is yet available upstream. Confirmed unreachable 
  in this app: no usage of next/image or sharp anywhere in the codebase (verified 
  via grep — zero matches outside node_modules). Will resolve automatically on 
  the next Next.js patch release.

---

## License

MIT — see [LICENSE](LICENSE).
