"""Shared test fixtures for the English Inspector backend."""

from __future__ import annotations

from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models.user  # noqa: F401 — register User/ExamSet with Base.metadata
from app.models.question import Base


@pytest_asyncio.fixture()
async def test_engine(tmp_path):
    """Per-test SQLite engine using a temp file so all connections share the same data."""
    db_url = f"sqlite+aiosqlite:///{tmp_path}/test.db"
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture()
async def client(test_engine):
    """AsyncClient wired to the test db (lifespan patched to use test engine)."""
    import app.main as main_module
    from app.core.database import get_db
    from app.main import app

    session_factory = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db

    with patch.object(main_module, "engine", test_engine):
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            yield ac

    app.dependency_overrides.clear()


@pytest_asyncio.fixture()
async def auth_headers(client):
    """Register a test user and return bearer auth headers."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "user@example.com", "name": "Test User", "password": "testpass123"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture()
async def second_auth_headers(client):
    """Register a second test user and return bearer auth headers."""
    resp = await client.post(
        "/api/auth/register",
        json={"email": "other@example.com", "name": "Other User", "password": "otherpass123"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}
