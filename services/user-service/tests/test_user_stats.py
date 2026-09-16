# =============================================================================
# test_user_stats.py  -  GET /users/stats (admin activity dashboard)
# =============================================================================
import uuid


def _register(client, monkeypatch, role_email=None):
    """Registers a fresh account. Pass role_email to control whether it
    lands as admin (ADMIN_EMAILS) or a regular user."""
    if role_email:
        monkeypatch.setenv("ADMIN_EMAILS", role_email)
    email = role_email or f"traveller_{uuid.uuid4().hex[:8]}@example.cm"
    response = client.post(
        "/auth/register",
        json={"name": "Someone", "email": email, "password": "SuperSecret123"},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def test_stats_requires_admin(client, registered_user):
    response = client.get("/users/stats", headers=registered_user["headers"])
    assert response.status_code == 403


def test_stats_requires_auth(client):
    response = client.get("/users/stats")
    assert response.status_code in (401, 403)


def test_stats_counts_total_and_by_role(client, monkeypatch, registered_user):
    admin_token = _register(client, monkeypatch, role_email="theadmin@example.cm")
    headers = {"Authorization": f"Bearer {admin_token}"}

    body = client.get("/users/stats", headers=headers).json()
    assert body["total_users"] == 2  # the autouse registered_user + this admin
    assert body["by_role"]["admin"] == 1
    assert body["by_role"]["user"] == 1


def test_stats_recent_signups_have_created_at(client, monkeypatch):
    admin_token = _register(client, monkeypatch, role_email="theadmin@example.cm")
    headers = {"Authorization": f"Bearer {admin_token}"}

    body = client.get("/users/stats", headers=headers).json()
    assert len(body["recent_signups"]) >= 1
    assert all(s.get("created_at") for s in body["recent_signups"])
    assert body["accounts_missing_signup_date"] == 0


def test_stats_respects_recent_limit(client, monkeypatch):
    monkeypatch.setenv("ADMIN_EMAILS", "boss@example.cm")
    for i in range(4):
        client.post(
            "/auth/register",
            json={"name": f"User {i}", "email": f"user{i}@example.cm", "password": "SuperSecret123"},
        )
    admin_token = client.post(
        "/auth/register",
        json={"name": "Boss", "email": "boss@example.cm", "password": "SuperSecret123"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {admin_token}"}

    body = client.get("/users/stats?recent_limit=2", headers=headers).json()
    assert len(body["recent_signups"]) == 2
    assert body["total_users"] == 5
