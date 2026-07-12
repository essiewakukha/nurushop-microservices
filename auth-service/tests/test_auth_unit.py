from fastapi.testclient import TestClient

# Import your Flask app instance from your app.py file
from app.main import app, users, tokens

client = TestClient(app)

def setup_function():
    """Reset state before every test so tests can't affect each other."""
    users.clear()
    tokens.clear()


def register(email="test@example.com", password="Password123"):
    return client.post("/api/v1/register", json={"email": email, "password": password})


def login(email="test@example.com", password="Password123"):
    return client.post("/api/v1/login", json={"email": email, "password": password})


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_register_success():
    response = register()
    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"


def test_register_duplicate_user_rejected():
    register()
    response = register()
    assert response.status_code == 409


def test_register_short_password_rejected():
    response = register(password="short")
    assert response.status_code == 422


def test_register_invalid_email_rejected():
    response = register(email="not-an-email")
    assert response.status_code == 422


def test_login_success_returns_token():
    register()
    response = login()
    assert response.status_code == 200
    body = response.json()
    assert "access_token" in body
    assert body["token_type"] == "bearer"


def test_login_wrong_password_rejected():
    register()
    response = login(password="WrongPassword")
    assert response.status_code == 401


def test_login_unknown_user_rejected():
    response = login(email="ghost@example.com")
    assert response.status_code == 401


def test_validate_accepts_valid_token():
    register()
    token = login().json()["access_token"]
    response = client.get(
        "/api/v1/validate",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_validate_rejects_invalid_token():
    response = client.get(
        "/api/v1/validate",
        headers={"Authorization": "Bearer bogus-token"},
    )
    assert response.status_code == 401