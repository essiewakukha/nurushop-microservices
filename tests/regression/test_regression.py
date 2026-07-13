"""Regression suite — verifies established behaviors still work after changes."""
import os
import uuid

import requests

AUTH_URL = os.getenv("AUTH_URL", "http://localhost:8000")
ORDER_URL = os.getenv("ORDER_URL", "http://localhost:8001")


def make_user():
    email = f"reg-{uuid.uuid4().hex[:8]}@example.com"
    password = "Password123"
    requests.post(f"{AUTH_URL}/api/v1/register", json={"email": email, "password": password}, timeout=10)
    return email, password


def get_token(email, password):
    return requests.post(
        f"{AUTH_URL}/api/v1/login", json={"email": email, "password": password}, timeout=10
    ).json()["access_token"]


def test_registration_still_works():
    email = f"reg-{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{AUTH_URL}/api/v1/register", json={"email": email, "password": "Password123"}, timeout=10)
    assert r.status_code == 201


def test_login_still_returns_token():
    email, password = make_user()
    r = requests.post(f"{AUTH_URL}/api/v1/login", json={"email": email, "password": password}, timeout=10)
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_invalid_password_still_rejected():
    email, password = make_user()
    r = requests.post(f"{AUTH_URL}/api/v1/login", json={"email": email, "password": "WrongPass99"}, timeout=10)
    assert r.status_code == 401


def test_authenticated_order_creation_still_works():
    email, password = make_user()
    token = get_token(email, password)
    r = requests.post(
        f"{ORDER_URL}/api/v1/orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"product": "Tablet", "quantity": 1, "price": 250},
        timeout=10,
    )
    assert r.status_code == 201


def test_unauthorized_order_creation_still_rejected():
    r = requests.post(
        f"{ORDER_URL}/api/v1/orders",
        json={"product": "Tablet", "quantity": 1, "price": 250},
        timeout=10,
    )
    assert r.status_code in (401, 403)


def test_existing_orders_still_retrievable():
    email, password = make_user()
    token = get_token(email, password)
    headers = {"Authorization": f"Bearer {token}"}
    order_id = requests.post(
        f"{ORDER_URL}/api/v1/orders", headers=headers,
        json={"product": "Monitor", "quantity": 1, "price": 150}, timeout=10,
    ).json()["order_id"]
    r = requests.get(f"{ORDER_URL}/api/v1/orders/{order_id}", headers=headers, timeout=10)
    assert r.status_code == 200


def test_invalid_order_data_still_returns_422():
    email, password = make_user()
    token = get_token(email, password)
    r = requests.post(
        f"{ORDER_URL}/api/v1/orders",
        headers={"Authorization": f"Bearer {token}"},
        json={"product": "Ghost", "quantity": 0, "price": 100},
        timeout=10,
    )
    assert r.status_code == 422