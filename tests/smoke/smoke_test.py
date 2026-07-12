"""Smoke tests — verify all services started and report healthy."""
import sys

import requests

SERVICES = {
    "auth-service": "http://localhost:8000/health",
    "order-service": "http://localhost:8001/health",
    "notification-service": "http://localhost:8002/health",
}


def main() -> int:
    failures = 0
    for name, url in SERVICES.items():
        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200
            assert response.json()["status"] == "healthy"
            print(f"[SMOKE] {name}: healthy")
        except Exception as error:
            print(f"[SMOKE] {name}: FAILED ({error})")
            failures += 1
    return failures


if __name__ == "__main__":
    sys.exit(main())