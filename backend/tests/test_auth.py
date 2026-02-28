"""Tests for /api/auth endpoints — no LLM required."""

from __future__ import annotations

import pytest


class TestRegister:
    async def test_register_success(self, client):
        resp = await client.post(
            "/api/auth/register",
            json={"email": "new@example.com", "name": "New User", "password": "pass1234"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "token" in data
        assert "user" in data
        assert data["user"]["email"] == "new@example.com"
        assert data["user"]["name"] == "New User"
        assert "hashed_password" not in data["user"]

    async def test_register_duplicate_email_returns_409(self, client):
        payload = {"email": "dup@example.com", "name": "User", "password": "pass1234"}
        resp1 = await client.post("/api/auth/register", json=payload)
        assert resp1.status_code == 201
        resp2 = await client.post("/api/auth/register", json=payload)
        assert resp2.status_code == 409

    async def test_register_invalid_email_returns_422(self, client):
        resp = await client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "name": "User", "password": "pass1234"},
        )
        assert resp.status_code == 422


class TestLogin:
    async def test_login_success_returns_token_and_user(self, client):
        await client.post(
            "/api/auth/register",
            json={"email": "login@example.com", "name": "Login User", "password": "mypassword"},
        )
        resp = await client.post(
            "/api/auth/login",
            json={"email": "login@example.com", "password": "mypassword"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert isinstance(data["token"], str)
        assert len(data["token"]) > 10
        assert data["user"]["email"] == "login@example.com"

    async def test_login_wrong_password_returns_401(self, client):
        await client.post(
            "/api/auth/register",
            json={"email": "wp@example.com", "name": "WP User", "password": "correct"},
        )
        resp = await client.post(
            "/api/auth/login",
            json={"email": "wp@example.com", "password": "wrong"},
        )
        assert resp.status_code == 401

    async def test_login_unknown_email_returns_401(self, client):
        resp = await client.post(
            "/api/auth/login",
            json={"email": "ghost@example.com", "password": "anything"},
        )
        assert resp.status_code == 401


class TestMe:
    async def test_me_with_valid_token_returns_user(self, client, auth_headers):
        resp = await client.get("/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "user@example.com"
        assert "id" in data
        assert "role" in data

    async def test_me_without_token_returns_401(self, client):
        resp = await client.get("/api/auth/me")
        assert resp.status_code == 401

    async def test_me_with_invalid_token_returns_401(self, client):
        resp = await client.get(
            "/api/auth/me", headers={"Authorization": "Bearer invalid.token.here"}
        )
        assert resp.status_code == 401
