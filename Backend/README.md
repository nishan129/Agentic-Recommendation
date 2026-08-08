# Agentic Recommendation System — Backend

A production-ready FastAPI backend foundation for an **Agentic Recommendation
System**. It works today as a heuristic recommendation engine with full
auth, product catalog, and event-tracking, and is architected so a
LangGraph agent can be dropped in later without a rewrite.

## 1. Project overview

The backend serves two roles — **user** and **admin** — over a product
catalog (products *and* courses), tracks user behavioral events, and
returns personalized recommendations. The first version ships with a
simple, explainable heuristic recommender; the service layer is the seam
where a LangGraph agent (with User Profile / Event History / Product
Search / Vector Search / Ranking tools) will plug in later.

## 2. Architecture

```
FastAPI Router -> Pydantic Schema -> Service Layer -> Repository Layer -> SQLAlchemy -> PostgreSQL
```

Every feature follows this chain — routes never touch the ORM directly,
and services never build HTTP responses. This keeps the codebase testable
and makes it possible to swap the recommendation logic for a LangGraph
agent, or the event pipeline for Celery/Kafka, without touching routes or
schemas.

```
                         React Frontend
                              |
                         FastAPI API
                              |
                    Authentication Layer (JWT)
                              |
                    RecommendationService  <- today: heuristic
                              |               tomorrow: LangGraph Agent
             +----------------+----------------+
             |                |                |
       User Profile       Event History    Product Search
             |                |                |
             +----------------+----------------+
                              |
                     Ranking / Personalization
                              |
                    Stored Recommendations
                              |
                         PostgreSQL
```

## 3. Technology stack

- Python 3.11+, FastAPI, Uvicorn
- PostgreSQL + SQLAlchemy 2.x (async, `asyncpg`) + Alembic migrations
- Pydantic v2 / Pydantic Settings
- JWT auth (`python-jose`) + `pwdlib` (argon2) password hashing
- `slowapi` rate limiting, structured request logging
- `pytest` + `pytest-asyncio` + `httpx` for testing (SQLite in-memory, no
  external services required)

## 4. Folder structure

```
backend/
├── app/
│   ├── main.py                 # FastAPI app factory
│   ├── core/                   # config, security, exceptions, dependencies, limiter
│   ├── db/                     # async engine/session, declarative base
│   ├── models/                 # SQLAlchemy models (user, product, event, recommendation)
│   ├── schemas/                # Pydantic request/response schemas
│   ├── repositories/           # data-access layer (one per model)
│   ├── services/                # business logic (auth, product, event, recommendation)
│   ├── api/v1/                 # routers (auth, products, admin, events, recommendations, health)
│   └── utils/                  # logging middleware
├── alembic/                    # migrations
├── tests/                      # pytest suite
├── .env.example
├── alembic.ini
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## 5. Database schema

| Table             | Purpose                                              |
|--------------------|-------------------------------------------------------|
| `users`            | Accounts, `role` = `user` \| `admin`                  |
| `products`         | Catalog items; `product_type` = `product` \| `course` |
| `user_events`      | Behavioral events (views, clicks, purchases, ...)     |
| `recommendations`  | Stored recommendation results, with `reason`/`source` |

Key indexes: `users.email` (unique), `user_events.user_id/event_type/timestamp/product_id`,
`recommendations.user_id/product_id`, `products.category/title`.

## 6. Environment variables

See [`.env.example`](.env.example). Copy it to `.env` and fill in real
values before running:

```bash
cp .env.example .env
```

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | Async DB URL used by the app (`asyncpg`) |
| `DATABASE_URL_SYNC` | Sync DB URL used by Alembic (`psycopg2`) |
| `SECRET_KEY` | JWT signing secret — **change in production** |
| `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES` | JWT config |
| `CORS_ORIGINS` | Allowed frontend origins |
| `EVENT_BATCH_MAX_SIZE` | Max events per `/events/batch` request |
| `EVENT_RATE_LIMIT_PER_MINUTE`, `AUTH_RATE_LIMIT_PER_MINUTE` | Rate limits |
| `RECOMMENDATION_MODEL_VERSION`, `RECOMMENDATION_DEFAULT_LIMIT` | Recommender config |

## 7. Installation (local, no Docker)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                # then edit DATABASE_URL etc.
```

## 8. PostgreSQL setup

Any local or hosted Postgres 14+ works. Quick local option:

```bash
docker run --name recsys-postgres -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=recsys -p 5432:5432 -d postgres:16-alpine
```

## 9. Alembic migrations

```bash
alembic upgrade head                                  # apply migrations
alembic revision --autogenerate -m "add new field"     # generate a new one
```

The initial migration (`0001_initial_schema.py`) creates `users`,
`products`, `user_events`, and `recommendations` with all indexes and
foreign keys. Schema changes always go through Alembic —
`Base.metadata.create_all()` is not used for production schema
management.

## 10. Running locally

```bash
uvicorn app.main:app --reload --port 8000
```

Then visit `http://localhost:8000/docs` (Swagger UI) or `/redoc`.

## 11. Docker setup

```bash
docker compose up --build
```

This starts Postgres, runs `alembic upgrade head`, and starts the API on
`http://localhost:8000`. Redis is included behind the `with-redis` compose
profile for when event processing moves to a background worker:

```bash
docker compose --profile with-redis up --build
```

## 12. API endpoints

All routes are versioned under `/api/v1`.

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/v1/auth/register` | – | Register a new user |
| POST | `/api/v1/auth/login` | – | Login, returns JWT |
| GET | `/api/v1/auth/me` | user | Current profile |
| PATCH | `/api/v1/auth/me` | user | Update profile |
| GET | `/api/v1/products` | – | Browse/search catalog (pagination, filters) |
| GET | `/api/v1/products/{id}` | – | Product detail |
| POST | `/api/v1/admin/products` | admin | Create product |
| GET | `/api/v1/admin/products` | admin | List all (incl. inactive) |
| PUT/PATCH | `/api/v1/admin/products/{id}` | admin | Update product |
| DELETE | `/api/v1/admin/products/{id}` | admin | Delete product |
| GET | `/api/v1/admin/dashboard` | admin | Summary counts |
| GET | `/api/v1/admin/stats/events` | admin | Event counts by type |
| GET | `/api/v1/admin/stats/recommendations` | admin | Recommendation counts by source |
| POST | `/api/v1/events` | user | Track one event (non-blocking) |
| POST | `/api/v1/events/batch` | user | Track a batch of events (non-blocking) |
| GET | `/api/v1/recommendations` | user | Get personalized recommendations |
| GET | `/api/v1/recommendations/history` | user | Past recommendations |
| GET | `/health`, `/health/db` | – | Liveness / DB connectivity |

### Example requests

Register:
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"name": "Nishant", "email": "user@example.com", "password": "password123"}'
```

Login:
```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "password123"}'
```

Track a batch of events:
```bash
curl -X POST http://localhost:8000/api/v1/events/batch \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{"events": [
        {"event_type": "product_click", "product_id": "<id>"},
        {"event_type": "time_spent", "product_id": "<id>", "metadata": {"duration_seconds": 42}}
      ]}'
```

Get recommendations:
```bash
curl http://localhost:8000/api/v1/recommendations -H "Authorization: Bearer <token>"
```

## 13. Authentication flow

1. `POST /auth/register` — password hashed with argon2 (`pwdlib`), role defaults to `user`.
2. `POST /auth/login` — verifies password, issues a JWT (`sub`=user id, `role`, expiry).
3. Every protected route depends on `get_current_user`, which decodes the
   JWT and **re-fetches the user's role from the database** on every
   request — so role changes take effect immediately, without waiting for
   token expiry. `get_current_admin` layers a role check on top.

## 14. Event tracking architecture

```
Frontend -> POST /events or /events/batch
         -> Pydantic validation (fast, synchronous)
         -> EventService builds ORM objects (user_id/timestamp from
            the authenticated request context, never trusted from the client)
         -> FastAPI BackgroundTask persists them AFTER the response is sent
         -> PostgreSQL (bulk insert, one round trip per batch)
```

The endpoint returns `202 Accepted` immediately — the frontend is never
blocked on DB latency. High-frequency signals (`time_spent`, `scroll`,
`video_progress`) are expected to be **batched client-side** (debounced,
or flushed on page unload) and sent through `/events/batch`
(`EVENT_BATCH_MAX_SIZE` caps batch size, default 100).

This is intentionally simple for v1. To scale further without changing
any router/service code, replace the `BackgroundTask` call in
`app/api/v1/events.py` with a push to Redis/Celery/Kafka and consume it
in a separate worker process — `EventService.persist_events` /
`EventRepository.create_many` stay exactly as they are.

## 15. Recommendation architecture

`RecommendationService.get_recommendations`:

1. Pulls the user's recent events (`EventRepository.get_recent_for_user`).
2. Weights event types by interest strength (`purchase` > `add_to_cart` >
   `product_view` > `search`, etc.) to build a category-affinity score.
3. Cold start (no signal yet): falls back to top-rated active products.
4. Otherwise: candidates come from the user's top-3 affinity categories,
   already-seen products are excluded, and each candidate is scored as
   `0.7 * category_affinity + 0.3 * rating`.
5. Results are persisted to `recommendations` (with `reason`, `source`,
   `model_version`, `expires_at`) and returned.

This is the seam for LangGraph: swap the body of `get_recommendations` for
an agent invocation (User Profile Tool -> Event History Tool -> Product
Search Tool -> Vector Search Tool -> Ranking Tool) — the router, schemas,
and repository layer don't need to change.

## 16. Testing

```bash
pytest -q
```

Tests run against an isolated in-memory SQLite database per test (no
Postgres required) and cover:

- **Auth**: register, duplicate email, login, invalid password, JWT auth
- **Authorization**: user blocked from admin routes, admin allowed
- **Products**: create, update, delete, get, search/filter
- **Events**: single event, batch, invalid payload, unauthorized, batch-too-large
- **Recommendations**: cold start, event-driven ranking, history, admin stats

## 17. Future LangGraph integration

Planned, without breaking existing contracts:

- `RecommendationService` internals swapped for a LangGraph agent with
  User Profile / Event History / Product Search / Vector Search / Ranking
  tools (Qdrant for vector search).
- `EventService` background persistence swapped for a Redis/Celery/Kafka
  pipeline for higher event throughput.
- Groq/OpenAI for agent reasoning, Langfuse for observability, Prometheus
  for metrics — all additive, none require changes to routers or schemas.

## Security notes

- Passwords hashed with argon2 (`pwdlib`), never returned in any response.
- JWTs signed with `SECRET_KEY` (set a long random value in production —
  never commit real secrets; `.env` is gitignored, `.env.example` has
  none).
- Role checked live from the database on every request, not trusted from
  a stale JWT claim.
- `/auth/login` and `/auth/register` are rate-limited
  (`AUTH_RATE_LIMIT_PER_MINUTE`); event endpoints are rate-limited
  (`EVENT_RATE_LIMIT_PER_MINUTE`) and capped in batch size
  (`EVENT_BATCH_MAX_SIZE`).
- All errors return a consistent envelope
  (`{"success": false, "message": ..., "error_code": ...}`) with no stack
  traces or raw DB errors leaked to the client.
- Clients can never set `created_by`/`created_at` on products — those
  schema fields don't exist on the write models at all.
