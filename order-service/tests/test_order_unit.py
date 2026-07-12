from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app, orders, verify_token

client = TestClient(app)

TEST_EMAIL = "test@example.com"


def fake_verify_token():
    return TEST_EMAIL


# Replace the real auth-service call with a fake for all unit tests
app.dependency_overrides[verify_token] = fake_verify_token


def setup_function():
    orders.clear()


def create_order(product="Laptop", quantity=1, price=800.0):
    with patch("app.main.send_notification") as mock_notify:
        response = client.post(
            "/api/v1/orders",
            json={"product": product, "quantity": quantity, "price": price},
        )
    return response, mock_notify


def test_health():
    response = client.get("/health")
    assert response.status_code == 200


def test_create_order_success():
    response, _ = create_order()
    assert response.status_code == 201
    body = response.json()
    assert body["product"] == "Laptop"
    assert body["total"] == 800.0
    assert body["status"] == "pending"
    assert body["email"] == TEST_EMAIL


def test_create_order_computes_total():
    response, _ = create_order(quantity=3, price=100.0)
    assert response.json()["total"] == 300.0


def test_create_order_triggers_notification():
    _, mock_notify = create_order()
    assert mock_notify.called


def test_create_order_zero_quantity_rejected():
    response, _ = create_order(quantity=0)
    assert response.status_code == 422


def test_create_order_negative_price_rejected():
    response, _ = create_order(price=-5.0)
    assert response.status_code == 422


def test_get_order_returns_created_order():
    response, _ = create_order()
    order_id = response.json()["order_id"]
    response = client.get(f"/api/v1/orders/{order_id}")
    assert response.status_code == 200
    assert response.json()["order_id"] == order_id


def test_get_missing_order_returns_404():
    response = client.get("/api/v1/orders/does-not-exist")
    assert response.status_code == 404


def test_update_order_status():
    response, _ = create_order()
    order_id = response.json()["order_id"]
    with patch("app.main.send_notification"):
        response = client.patch(
            f"/api/v1/orders/{order_id}", json={"status": "shipped"}
        )
    assert response.status_code == 200
    assert response.json()["status"] == "shipped"


def test_update_order_invalid_status_rejected():
    response, _ = create_order()
    order_id = response.json()["order_id"]
    with patch("app.main.send_notification"):
        response = client.patch(
            f"/api/v1/orders/{order_id}", json={"status": "teleported"}
        )
    assert response.status_code == 422