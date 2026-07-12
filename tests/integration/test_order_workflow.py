"""Integration tests — run against the real docker-compose stack."""
import os
import uuid

import requests

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8000")
ORDER_URL = os.getenv("ORDER_URL", "http://localhost:8001")
NOTIFICATION_URL = os.getenv("NOTIFICATION_URL", "http://localhost:8002")


def unique_email() -> str:
    """Each test run uses a fresh user so reruns never collide."""
    return f"qa-{uuid.uuid4().hex[:8]}@example.com"


def register_and_login() -> str:
    email = unique_email()
    password = "Password123"

    response = requests.post(
        f"{AUTH_URL}/api/v1/register",
        json={"email": email, "password": password},
        timeout=10,
    )
    assert response.status_code == 201

    response = requests.post(
        f"{AUTH_URL}/api/v1/login",
        json={"email": email, "password": password},
        timeout=10,
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_complete_order_workflow():
    """Register -> login -> create order -> verify order -> verify auth chain."""
    token = register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    # Create an order (order-service calls auth-service internally here)
    response = requests.post(
        f"{ORDER_URL}/api/v1/orders",
        headers=headers,
        json={"product": "Laptop", "quantity": 2, "price": 800},
        timeout=10,
    )
    assert response.status_code == 201
    order = response.json()
    assert order["total"] == 1600.0
    assert order["status"] == "pending"

    # Retrieve it back
    response = requests.get(
        f"{ORDER_URL}/api/v1/orders/{order['order_id']}",
        headers=headers,
        timeout=10,
    )
    assert response.status_code == 200
    assert response.json()["order_id"] == order["order_id"]


def test_order_rejected_without_token():
    response = requests.post(
        f"{ORDER_URL}/api/v1/orders",
        json={"product": "Laptop", "quantity": 1, "price": 800},
        timeout=10,
    )
    assert response.status_code in (401, 403)


def test_order_rejected_with_invalid_token():
    response = requests.post(
        f"{ORDER_URL}/api/v1/orders",
        headers={"Authorization": "Bearer forged-token"},
        json={"product": "Laptop", "quantity": 1, "price": 800},
        timeout=10,
    )
    assert response.status_code == 401


def test_order_status_update_flow():
    token = register_and_login()
    headers = {"Authorization": f"Bearer {token}"}

    order_id = requests.post(
        f"{ORDER_URL}/api/v1/orders",
        headers=headers,
        json={"product": "Phone", "quantity": 1, "price": 300},
        timeout=10,
    ).json()["order_id"]

    response = requests.patch(
        f"{ORDER_URL}/api/v1/orders/{order_id}",
        headers=headers,
        json={"status": "shipped"},
        timeout=10,
    )
    assert response.status_code == 200
    assert response.json()["status"] == "shipped"


def test_notification_service_records_notifications():
    response = requests.post(
        f"{NOTIFICATION_URL}/api/v1/notifications",
        json={"order_id": "test-order", "email": "qa@example.com", "message": "test"},
        timeout=10,
    )
    assert response.status_code == 201
    notification_id = response.json()["notification_id"]

    response = requests.get(
        f"{NOTIFICATION_URL}/api/v1/notifications/{notification_id}",
        timeout=10,
    )
    assert response.status_code == 200
    assert response.json()["delivered"] is True