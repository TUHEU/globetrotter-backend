# =============================================================================
# test_activity.py  -  GET /destinations/activity (admin dashboard feed)
# =============================================================================


def test_activity_requires_admin(client, registered_user):
    response = client.get("/destinations/activity", headers=registered_user["headers"])
    assert response.status_code == 403


def test_activity_requires_auth_at_all(client):
    response = client.get("/destinations/activity")
    assert response.status_code in (401, 403)


def test_activity_includes_comment_and_request_events(client, registered_user, admin_user):
    destinations = client.get("/destinations").json()
    destination_id = destinations[0]["id"]

    client.post(
        f"/destinations/{destination_id}/comments",
        json={"text": "Loved this place!"},
        headers=registered_user["headers"],
    )
    client.post(
        "/destinations/requests",
        json={"type": "create", "destination_id": None, "payload": {"name": "A brand new spot"}},
        headers=registered_user["headers"],
    )

    response = client.get("/destinations/activity", headers=admin_user["headers"])
    assert response.status_code == 200
    body = response.json()

    types = {e["type"] for e in body["events"]}
    assert "comment" in types
    assert "place_create_request" in types
    assert body["total_comments"] >= 1
    assert body["pending_requests"] >= 1
    assert body["total_destinations"] == len(destinations)


def test_activity_created_destination_appears(client, admin_user):
    payload = {"name": "Freshly Created Place"}
    created = client.post("/destinations", json=payload, headers=admin_user["headers"]).json()
    assert created.get("created_at")  # the field this whole feature relies on

    body = client.get("/destinations/activity", headers=admin_user["headers"]).json()
    matching = [e for e in body["events"] if e["type"] == "place_created" and e["destination_id"] == created["id"]]
    assert len(matching) == 1
    assert matching[0]["name"] == "Freshly Created Place"


def test_activity_respects_limit(client, admin_user):
    for i in range(5):
        client.post("/destinations", json={"name": f"Place {i}"}, headers=admin_user["headers"])

    body = client.get("/destinations/activity?limit=2", headers=admin_user["headers"]).json()
    assert len(body["events"]) == 2
