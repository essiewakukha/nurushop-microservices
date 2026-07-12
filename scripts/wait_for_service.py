"""Poll service health endpoints until all respond, or time out."""
import sys
import time

import requests

URLS = [
    "http://localhost:8000/health",
    "http://localhost:8001/health",
    "http://localhost:8002/health",
]

TIMEOUT_SECONDS = 60


def main() -> int:
    deadline = time.time() + TIMEOUT_SECONDS
    pending = list(URLS)

    while pending and time.time() < deadline:
        for url in list(pending):
            try:
                if requests.get(url, timeout=2).status_code == 200:
                    print(f"[WAIT] {url} is up")
                    pending.remove(url)
            except requests.RequestException:
                pass
        if pending:
            time.sleep(2)

    if pending:
        print(f"[WAIT] Timed out waiting for: {pending}")
        return 1
    print("[WAIT] All services ready")
    return 0


if __name__ == "__main__":
    sys.exit(main())