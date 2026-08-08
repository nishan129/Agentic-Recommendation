"""
Shared pytest fixtures.

Tests run against an isolated in-memory-per-test SQLite database (via
aiosqlite) rather than Postgres, so the suite has no external
dependencies. The app's models/queries are simple enough that SQLite
behaves equivalently for everything exercised here.
"""
import asyncio
from typing import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.db.session as db_session_module
from app.core.limiter import limiter
from app.db.base import Base, base_import_all_models
from app.db.session import get_db
from app.main import app
from app.models.user import User, UserRole
from app.core.security import hash_password

base_import_all_models()

TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Rate-limit storage is process-global and keyed by client IP; without
    a reset every test would share one bucket (all requests originate from
    the same httpx ASGITransport "127.0.0.1"), causing unrelated tests to
    trip each other's limits.
    """
    limiter.reset()
    yield
    limiter.reset()


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # StaticPool keeps a single shared connection alive for the whole engine,
    # which is required for an in-memory SQLite DB: each new pooled
    # connection would otherwise see its own empty database, and the
    # BackgroundTask that persists events opens its own session from this
    # same engine after the request session has closed.
    engine = create_async_engine(
        TEST_DB_URL,
        future=True,
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def _override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db

    # Event ingestion persists via a BackgroundTask that opens its own
    # session directly from `AsyncSessionLocal` (see app/api/v1/events.py),
    # bypassing the `get_db` dependency override above. Patch the module-level
    # session factory too so background-persisted events land in the same
    # test database and are visible to assertions made after the request.
    original_session_local = db_session_module.AsyncSessionLocal
    db_session_module.AsyncSessionLocal = session_factory

    async with session_factory() as session:
        yield session

    db_session_module.AsyncSessionLocal = original_session_local
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def admin_user(db_session: AsyncSession) -> User:
    user = User(
        name="Admin",
        email="admin@example.com",
        password_hash=hash_password("adminpass123"),
        role=UserRole.ADMIN,
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


async def get_auth_headers(client: AsyncClient, email: str, password: str) -> dict:
    resp = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
