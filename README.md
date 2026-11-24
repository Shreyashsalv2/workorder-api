# Work Order API

A Flask REST API for machine-maintenance work orders.
- Each work order can carry a sensor reading. The API sends that reading to a separate failure-prediction service and sets the order's priority from the failure probability.
- If that service is slow or down, the order is still saved, marked `unscored`, with the reason.

**Live demo:** https://workorder-api-cyan.vercel.app · **API docs (OpenAPI / Swagger UI):** https://workorder-api-cyan.vercel.app/docs

![Demo: a work order with a worn-tool reading is scored critical (98.4%)](docs/screenshot.png)

## What it does

- **REST + JSON CRUD** for machines and work orders, with filtering (status, priority, machine) and pagination.
- **Status rules:** a work order moves `open → in_progress → done` (or back from in progress to open). Any other move is rejected with **409**.
- **One JSON error format** for every failure. Custom exception classes (`NotFoundError`, `ConflictError`, `InvalidTransitionError`, `UpstreamError`) are mapped to responses in one place. Validation, database and unexpected errors go through the same handlers:

  ```json
  {"error": {"code": "invalid_status_transition",
             "message": "Cannot move a work order from 'done' to 'open'.",
             "details": {"from": "done", "to": "open", "allowed": []}}}
  ```

  | Status | When |
  |---|---|
  | 404 | unknown machine, work order or route |
  | 405 | wrong HTTP method |
  | 409 | duplicate machine name, invalid status change, deleting a machine with unfinished orders |
  | 422 | invalid input; unknown fields are rejected too |
  | 500 | unexpected error, with no traceback or internal message leaked |

- **Third-party integration:** `PredictorClient` calls `POST /predict` on the [failure-prediction service](https://machine-failure-predictor.vercel.app).
  - Retries timeouts, connection errors and 5xx, with exponential backoff.
  - Does not retry 4xx.
  - Rejects malformed responses.
  - The probability maps to a priority: `≥ 0.8` critical, `≥ 0.5` high, `≥ 0.2` medium, otherwise low.
  - `POST /work-orders/<id>/score` re-scores an order later, for example after the service was down.
- **SQL:** SQLAlchemy ORM models plus Alembic migrations. `/reports/summary` runs plain SQL (`GROUP BY`, `LEFT JOIN`, `CASE`) that is portable across SQLite, PostgreSQL and MySQL.
- **Tests:** 44 pytest tests cover CRUD, validation, error shapes, status rules, retries, timeouts, the fallback when the prediction service is down, reports and seeding. The external API is mocked with `responses`.
- **CI** (GitHub Actions) runs the **whole suite on SQLite, PostgreSQL 16 and MySQL 8**. On each database, the migrations are applied, rolled back and re-applied first. CI then builds the **Docker** image, runs it against PostgreSQL, and calls the API on the running container.

## Endpoints

| Method | Path | What it does |
|---|---|---|
| GET | `/health` | Liveness check plus a `SELECT 1` against the database |
| GET, POST | `/machines` | List (paginated) or register a machine |
| GET, PATCH, DELETE | `/machines/<id>` | Read, update or delete. Delete is 409 while the machine has unfinished orders |
| GET, POST | `/work-orders` | List (`?status=&priority=&machine_id=&page=&per_page=`) or create, with an optional `reading` |
| GET, PATCH, DELETE | `/work-orders/<id>` | Read, update title, description or status, or delete |
| POST | `/work-orders/<id>/score` | Ask the prediction service again |
| GET | `/reports/summary` | Counts by status and priority, plus open orders per machine (plain SQL) |
| GET | `/docs`, `/openapi.json` | Interactive docs and the OpenAPI spec |

```bash
curl -X POST https://<host>/work-orders -H 'Content-Type: application/json' -d '{
  "machine_id": 1, "title": "Spindle vibration after tool change",
  "reading": {"air_temperature_k": 300, "process_temperature_k": 310,
              "rotational_speed_rpm": 1350, "torque_nm": 62, "tool_wear_min": 210}}'
# → 201 {"priority": "critical", "failure_probability": 0.9843, "scoring_note": "Scored by random_forest.", ...}
```

## Architecture

```
app.py ── create_app() (application factory)
   ├── routes/      flask-smorest blueprints: machines, work_orders, reports, health
   ├── schemas.py   marshmallow: request validation (unknown fields rejected) and JSON output
   ├── services.py  business logic: create/score/update orders, delete rules, pagination
   ├── predictor.py PredictorClient: timeout, retry with backoff, error mapping
   ├── models.py    SQLAlchemy models + status-transition rules
   ├── errors.py    exception classes + one JSON error format
   └── seed.py      demo data (idempotent, safe with several workers)
migrations/        Alembic (Flask-Migrate)
```

## Run it

```bash
# Local, SQLite
pip install -r requirements-dev.txt
AUTO_CREATE_TABLES=1 SEED_DEMO_DATA=1 flask --app app run    # http://127.0.0.1:5000  and /docs

# Docker Compose: API (gunicorn) + PostgreSQL 16; migrations run on start-up
docker compose up --build                                     # http://localhost:8000

# Tests: SQLite by default, or point at PostgreSQL / MySQL
pytest
TEST_DATABASE_URL=postgresql+psycopg://user:pass@localhost/db pytest
TEST_DATABASE_URL=mysql+pymysql://user:pass@localhost/db pytest
```

Settings (environment variables): `DATABASE_URL`, `PREDICTOR_URL`, `PREDICTOR_TIMEOUT` (seconds), `PREDICTOR_RETRIES`, `AUTO_CREATE_TABLES`, `SEED_DEMO_DATA`.

## Limits

- **The live demo's data can reset, and can differ between requests.** The demo runs on Vercel with SQLite inside each serverless instance. Each instance keeps its own copy and can reset at any time, so two requests can reach different copies. Docker Compose and CI use one real PostgreSQL or MySQL database.
- **Priority bands are fixed.** They are a simple product rule kept in one place (`PRIORITY_BANDS`), not something learned from data.
- **No authentication or user accounts.** It is a portfolio project.

## Stack

Python 3.12 · Flask · flask-smorest (OpenAPI) · marshmallow · SQLAlchemy · Alembic · PostgreSQL · MySQL · SQLite · requests · pytest · responses · Docker · gunicorn · GitHub Actions · Vercel

MIT licence.
