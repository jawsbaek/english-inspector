"""Tests for /api/exams endpoints — no LLM required."""

from __future__ import annotations


class TestCreateExam:
    async def test_create_exam_requires_auth(self, client):
        resp = await client.post(
            "/api/exams",
            json={"title": "Test Exam", "grade_level": "middle", "question_count": 0},
        )
        assert resp.status_code == 401

    async def test_create_exam_success(self, client, auth_headers):
        resp = await client.post(
            "/api/exams",
            json={"title": "Mid-term Exam", "grade_level": "high", "question_count": 10},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Mid-term Exam"
        assert data["grade_level"] == "high"
        assert data["question_count"] == 10
        assert "id" in data
        assert "user_id" in data

    async def test_create_exam_returns_exam_set(self, client, auth_headers):
        resp = await client.post(
            "/api/exams",
            json={"title": "Vocab Quiz", "grade_level": "elementary_high"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Vocab Quiz"
        assert data["question_count"] == 0  # default


class TestListExams:
    async def test_list_exams_requires_auth(self, client):
        resp = await client.get("/api/exams")
        assert resp.status_code == 401

    async def test_list_exams_returns_only_own_exams(
        self, client, auth_headers, second_auth_headers
    ):
        # user1 creates 2 exams
        await client.post(
            "/api/exams",
            json={"title": "Exam A", "grade_level": "middle"},
            headers=auth_headers,
        )
        await client.post(
            "/api/exams",
            json={"title": "Exam B", "grade_level": "high"},
            headers=auth_headers,
        )
        # user2 creates 1 exam
        await client.post(
            "/api/exams",
            json={"title": "Other Exam", "grade_level": "phonics"},
            headers=second_auth_headers,
        )

        resp1 = await client.get("/api/exams", headers=auth_headers)
        assert resp1.status_code == 200
        titles = [e["title"] for e in resp1.json()]
        assert "Exam A" in titles
        assert "Exam B" in titles
        assert "Other Exam" not in titles

        resp2 = await client.get("/api/exams", headers=second_auth_headers)
        assert resp2.status_code == 200
        titles2 = [e["title"] for e in resp2.json()]
        assert "Other Exam" in titles2
        assert "Exam A" not in titles2

    async def test_list_exams_empty_for_new_user(self, client, auth_headers):
        resp = await client.get("/api/exams", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []


class TestDeleteExam:
    async def test_delete_exam_owner_succeeds(self, client, auth_headers):
        create_resp = await client.post(
            "/api/exams",
            json={"title": "To Delete", "grade_level": "middle"},
            headers=auth_headers,
        )
        exam_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/exams/{exam_id}", headers=auth_headers)
        assert del_resp.status_code == 204

        # Confirm it's gone
        get_resp = await client.get(f"/api/exams/{exam_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    async def test_delete_exam_non_owner_returns_403(
        self, client, auth_headers, second_auth_headers
    ):
        create_resp = await client.post(
            "/api/exams",
            json={"title": "Owner Exam", "grade_level": "high"},
            headers=auth_headers,
        )
        exam_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/exams/{exam_id}", headers=second_auth_headers)
        assert del_resp.status_code == 403

    async def test_delete_exam_requires_auth(self, client, auth_headers):
        create_resp = await client.post(
            "/api/exams",
            json={"title": "Auth Needed", "grade_level": "middle"},
            headers=auth_headers,
        )
        exam_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/exams/{exam_id}")
        assert del_resp.status_code == 401

    async def test_delete_nonexistent_exam_returns_404(self, client, auth_headers):
        resp = await client.delete("/api/exams/99999", headers=auth_headers)
        assert resp.status_code == 404
