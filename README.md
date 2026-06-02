# Oracle NL2SQL Assistant

On-premises natural-language Oracle query assistant built with FastAPI, NVIDIA NeMo Guardrails, an OpenAI-compatible LLM API, and a lightweight React chat UI.

## What It Does

- Accepts a business question in natural language.
- Runs an input guardrail and semantic analysis step.
- Resolves synonyms and business terms from Excel metadata.
- Generates read-only Oracle SQL.
- Validates SQL before execution.
- Requires explicit user approval before executing even read-only SQL.
- Executes only `SELECT` or `WITH` queries against an external Oracle database.
- Synthesizes the SQL result into a user-facing answer.

## Project Layout

```text
apps/
  api/              FastAPI backend and NL2SQL pipeline
  web/              React/Vite frontend served by nginx
configs/
  guardrails/       NeMo Guardrails config templates
docs/
  metadata-format.md
deploy/
  rhel9/            RHEL9 x86_64 offline deployment files
docker-compose.yml
.env.example
```

## Quick Start

1. Copy `.env.example` to `.env` and fill in the LLM and Oracle settings.

2. Start the stack.

```bash
docker compose up -d --build
```

3. Open the web UI.

```text
http://localhost:3000
```

4. Upload an Excel metadata workbook. The expected sheets are:

- `tables`
- `columns`
- `relationships`
- `terms`
- `metrics`

You can download a generated template from the UI or from `GET /api/metadata/template`.

## Environment

Required for production-like operation:

- `LLM_BASE_URL`
- `LLM_API_KEY`
- `LLM_MODEL`
- `ORACLE_DSN`
- `ORACLE_USER`
- `ORACLE_PASSWORD`

The Oracle account should be read-only. The application also blocks non-read SQL before execution, but database privileges should remain the final safety boundary.

## API

- `GET /api/health`
- `POST /api/chat`
- `POST /api/sql/preview`
- `POST /api/sql/execute`
- `POST /api/metadata/upload`
- `GET /api/metadata/catalog`
- `GET /api/metadata/template`
- `GET /api/settings/oracle`
- `POST /api/settings/oracle`
- `POST /api/settings/oracle/test`

## RHEL9 x86_64 Offline Deployment

RHEL9 deployment files live under `deploy/rhel9`.

The final server only needs Python prepared first:

```bash
sudo dnf install python3.12
```

The full project transfer archive is generated under `dist/`. To regenerate it after changes:

```bash
./deploy/rhel9/scripts/create-project-transfer-archive.sh
```

Copy only these two files to the final server:

```text
dist/oracle-nl2sql-project-rhel9-x86_64.tar.gz
dist/install-oracle-nl2sql-project-rhel9.sh
```

On the final server:

```bash
sudo bash install-oracle-nl2sql-project-rhel9.sh oracle-nl2sql-project-rhel9-x86_64.tar.gz
```

The server-side installer extracts the project, installs included RPMs and Python packages, creates a host virtualenv, starts a systemd `oracle-nl2sql` service, and runs a smoke test. Container image tar creation is not required for this deployment path.

## Local API Development

```bash
cd apps/api
python3.12 -m venv .venv
. .venv/Scripts/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

## Local Web Development

```bash
cd apps/web
npm install
npm run dev
```

Set `VITE_API_BASE_URL=http://localhost:8000/api` when running the web app outside Docker.

## Tests

```bash
cd apps/api
pytest
```
