# Battlecard Generator

Hackathon-ready SaaS prototype for fintech/BFSI competitive intelligence.

The app takes a competitor company name and generates a 1-page, citation-grounded battlecard with progress tracking and PDF export.

## Stack

- Monorepo: npm workspaces
- Frontend: Next.js 15, TypeScript, Tailwind CSS, shadcn-style UI primitives
- Backend: FastAPI
- Crawl and extraction: httpx + BeautifulSoup with parallel fetching
- Search: free web discovery flow (DuckDuckGo HTML search strategy)
- Data store: SQLite
- LLM: Groq API with strict JSON mode and grounded fallback
- PDF: server-side markdown to PDF via Playwright

## Monorepo Structure

- apps/web: Next.js app
- apps/api: FastAPI service and generation pipeline
- packages/shared: cross-app types/contracts
- packages/scraper: reusable scraper helpers
- packages/prompts: LLM prompt constants
- packages/utils: shared utility helpers
- samples: sample battlecard markdown

## Core Product Flow

1. User enters competitor name in web UI.
2. API creates a run and starts async pipeline.
3. Pipeline stages:
- normalize competitor key
- discover sources
- resolve canonical domain
- crawl pages in parallel
- extract and score snippets
- generate grounded battlecard JSON
- render markdown
- export PDF
- cache completed result
4. UI polls run status and shows stage-level progress.
5. Completed run shows markdown battlecard, citations, and PDF download.

## API Endpoints

- POST /api/battlecard/generate
- GET /api/battlecard/{id}
- GET /api/battlecard/{id}/pdf
- GET /api/battlecard/recent/list
- GET /api/health

## Data Model (SQLite)

### runs

- id
- competitor_name
- canonical_domain
- status
- error_message
- markdown
- json_output
- pdf_path
- sources_json
- snippets_json
- created_at
- updated_at

### events

- run_id
- stage
- message
- progress
- created_at

### cache_entries

- competitor_key
- run_id
- canonical_domain
- markdown
- json_output
- pdf_path
- sources_json
- snippets_json
- created_at
- expires_at

## Setup

### 1) Prerequisites

- Node.js 20+
- Python 3.11+

### 2) Install web dependencies

From repo root:

npm install --workspaces

### 3) Setup backend venv

From apps/api:

python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
playwright install chromium

### 4) Configure environment

- Copy .env.example to .env at root for global values, or set env directly.
- Copy apps/web/.env.example to apps/web/.env.local.
- Copy apps/api/.env.example to apps/api/.env.

Important values:

- NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
- GROQ_API_KEY=your_key
- GROQ_MODEL=optional (if empty, backend uses default)

## Run Locally

Terminal 1 (backend):

cd apps/api
uvicorn main:app --reload --host 0.0.0.0 --port 8000

Terminal 2 (frontend):

npm run dev:web

Open http://localhost:3000

## Reliability Rules Implemented

- Citations rendered in output and source panel.
- Every section falls back to Not enough public data found when evidence is missing.
- Hard failures are persisted with status=failed and pipeline event trail.
- Source ranking prioritizes canonical domain and high-signal pages.
- Cache speeds up repeated competitor requests.

## Notes on Grounding

- Groq generation is constrained to provided evidence snippets and source URLs.
- If Groq is unavailable or invalid JSON is returned, deterministic grounded fallback is used.
- Fallback behavior is explicit in payload grounding field.

## Demo Assets

- Sample output: samples/sample_battlecard.md

## Basic Troubleshooting

- If PDF export fails, ensure playwright install chromium was run in backend environment.
- If no sources are found, try a more specific competitor name or rerun to bypass transient web search issues.
- If Groq key is missing, app still returns a grounded fallback battlecard.
