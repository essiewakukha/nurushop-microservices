from fastapi.testclient import TestClient

from app.main import app, notifications

client = TestClient(app)


def setup_function():
    notifications.clear()


def send(order_id="order-1", email="test@example.com", message="Order created"):
    return client.post(
        "/api/v1/notifications",
        json={"order_id": order_id, "email": email, "message": message},
    )


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


def test_send_notification_success():
    response = send()
    assert response.status_code == 201
    body = response.json()
    assert body["delivered"] is True
    assert body["email"] == "test@example.com"


def test_get_notification_by_id():
    notification_id = send().json()["notification_id"]
    response = client.get(f"/api/v1/notifications/{notification_id}")
    assert response.status_code == 200
    assert response.json()["order_id"] == "order-1"


def test_get_missing_notification_returns_404():
    response = client.get("/api/v1/notifications/does-not-exist")
    assert response.status_code == 404


def test_send_notification_missing_fields_rejected():
    response = client.post("/api/v1/notifications", json={"email": "x@example.com"})
    assert response.status_code == 422