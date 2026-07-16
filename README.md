# NuruShop Microservices Test Automation Platform

A microservices-based e-commerce demo built to show how **automated testing integrates into a DevOps CI/CD pipeline**. Three independent FastAPI services run in Docker containers, and a GitHub Actions pipeline validates every push with nine categories of automated testing — from linting to load testing — before anything could ever reach a deployment stage.

**Every failure blocks the pipeline.** During development, this pipeline caught real defects: known CVEs in a transitive dependency, six API contract violations, and a missing dependency that only surfaced inside containers. Details in [Lessons Learned](#lessons-learned-real-defects-caught-by-this-pipeline).

---

## Table of Contents

- [Architecture](#architecture)
- [The Services](#the-services)
- [The Pipeline](#the-pipeline)
- [Testing Strategy, Stage by Stage](#testing-strategy-stage-by-stage)
- [Repository Structure](#repository-structure)
- [Running Locally](#running-locally)
- [Evidence](#evidence)
- [Lessons Learned: Real Defects Caught by This Pipeline](#lessons-learned-real-defects-caught-by-this-pipeline)
- [Design Decisions](#design-decisions)

---

## Architecture

```
                                  ┌──────────────────────────┐
   POST /register, /login         │      Auth Service        │
   GET  /validate                 │      (port 8000)         │
  ───────────────────────────▶    │  users / tokens store    │
                                  └────────────▲─────────────┘
                                               │ GET /validate
                                               │ (token check)
                                  ┌────────────┴─────────────┐
   POST /orders                   │      Order Service       │
   GET  /orders/{id}              │      (port 8001)         │
   PATCH /orders/{id}     ──────▶ │  validates via auth,     │
                                  │  stores orders           │
                                  └────────────┬─────────────┘
                                               │ POST /notifications
                                               │ (order events)
                                  ┌────────────▼─────────────┐
   GET /notifications/{id}        │  Notification Service    │
                          ──────▶ │      (port 8002)         │
                                  │  simulated email/SMS     │
                                  └──────────────────────────┘
```

All three services are containerized and orchestrated with Docker Compose. Inside the compose network, services address each other by service name (`http://auth-service:8000`); locally they fall back to `localhost` via environment variables, so the same code runs unmodified in both environments.

### Technology stack

| Layer | Tools |
|---|---|
| Services | Python 3.12, FastAPI, Pydantic v2, Uvicorn |
| Containers | Docker, Docker Compose |
| CI/CD | GitHub Actions |
| Code quality | Ruff |
| Unit / integration / regression tests | PyTest, FastAPI TestClient, requests |
| Contract testing | Schemathesis (OpenAPI-driven fuzzing + stateful testing) |
| Security | pip-audit (dependencies), Trivy (container images) |
| Performance | k6 (load testing with hard thresholds) |

---

## The Services

### Auth Service (port 8000)
Registration, login, and bearer-token validation. Tokens are issued on login and validated by other services via `GET /api/v1/validate`. Password policy (`minLength: 8`) is enforced in the Pydantic model so the OpenAPI contract and runtime behavior always agree.

### Order Service (port 8001)
Creates and manages orders. **Every request is authenticated by calling the Auth Service** — real service-to-service communication, not a mock. After creating or updating an order, it emits an event to the Notification Service (best-effort: a notification failure never fails an order).

### Notification Service (port 8002)
Receives order events and records simulated email/SMS notifications, retrievable by ID.

All services expose `GET /health` for smoke testing and orchestration readiness checks, and auto-generate OpenAPI specs at `/openapi.json` — which the contract-testing stage consumes directly.

---

## The Pipeline

Defined in `.github/workflows/automated-testing.yml`. Triggered on every push to `main`, `dev`, or `feature/**`, and on pull requests.

```
lint ──┬── unit-tests (×3, parallel matrix) ── integration-tests ── contract-tests ── regression-tests ── performance-tests
       │
       └── security-scan (runs in parallel — no reason for scans to wait on tests)
```

| Stage | What it does | Fails the pipeline when |
|---|---|---|
| **Lint** | Ruff across all three services | Code quality violations |
| **Unit tests** | PyTest per service via a matrix strategy (3 parallel jobs); results uploaded as JUnit XML artifacts | Any test fails |
| **Security scan** | pip-audit on every requirements.txt; Trivy on every built image | Known CVE in a dependency, or a **fixable** CRITICAL/HIGH in an image |
| **Integration & smoke** | Builds the real containers, waits for health, runs cross-service workflow tests | A service fails to start, or the workflow breaks |
| **Contract tests** | Schemathesis fuzzes hundreds of generated requests against the live OpenAPI specs | Any response violates the documented contract |
| **Regression tests** | Re-verifies established behaviors against the running stack | Any previously-working behavior regresses |
| **Performance tests** | k6, 20 virtual users for 30s | p95 latency ≥ 800 ms or error rate ≥ 2% |

Test reports are uploaded as pipeline artifacts on **every run, including failures** (`if: always()`), so evidence is retained exactly when it matters most.

---

## Testing Strategy, Stage by Stage

### Unit tests (26 tests)
Each service is tested in isolation using FastAPI's `TestClient` — no servers, no network. The Order Service's external calls are **mocked**: `app.dependency_overrides` replaces the auth check, and `unittest.mock.patch` intercepts notification sends. State is reset before every test so tests cannot influence one another. Coverage includes happy paths, duplicate registration, invalid credentials, malformed orders, and unknown-resource 404s.

### Integration tests
The opposite philosophy: **nothing is mocked**. The real containers run, and tests exercise the full chain — register → login → create order (which internally round-trips to the auth service) → retrieve order — plus negative paths (no token, forged token). Each test run generates unique user emails so reruns never collide with leftover state.

### Smoke tests
A fast post-startup gate: every service's `/health` endpoint must return `200 {"status": "healthy"}`. A `wait_for_services.py` script polls health endpoints (60s budget) before any test stage runs, because containers report "started" before Uvicorn is actually accepting connections.

### Contract tests
Schemathesis loads each service's live OpenAPI spec and generates hundreds of test cases per run — including malformed bytes, boundary values, and **stateful chains** (it inferred that the notification POST's returned ID feeds the GET endpoint and validated 79+ create-then-retrieve scenarios automatically). The rule it enforces is simple and strict: *the API must do exactly what its spec says, and the spec must document everything the API does.*

### Regression tests
The behaviors that must never silently break, re-verified against the live stack on every push: registration works, login returns tokens, wrong passwords are rejected, authenticated users can order, unauthenticated users cannot, existing orders remain retrievable, invalid order data returns 422.

### Security scanning
Two layers: **pip-audit** checks every Python dependency (including transitive ones) against known-vulnerability databases; **Trivy** scans the built container images — both the OS packages in the base image and the installed Python packages. Policy: fail on anything with an available fix; report-but-don't-block findings with no upstream fix yet (see Design Decisions).

### Performance tests
k6 simulates 20 concurrent virtual users for 30 seconds hammering health, registration, and login. Thresholds are hard gates, not reports: 95th-percentile response time must stay under 800 ms and the error rate under 2%, or the run exits non-zero and the pipeline fails.

---

## Repository Structure

```
nurushop-microservices/
├── auth-service/
│   ├── app/main.py               # FastAPI app: register, login, validate, health
│   ├── tests/test_auth_unit.py   # 10 unit tests
│   ├── conftest.py               # makes app/ importable for pytest
│   ├── requirements.txt
│   └── Dockerfile
├── order-service/
│   ├── app/main.py               # orders CRUD + auth round-trip + notify events
│   ├── tests/test_order_unit.py  # 10 unit tests (auth & notify mocked)
│   ├── conftest.py
│   ├── requirements.txt
│   └── Dockerfile
├── notification-service/
│   ├── app/main.py               # notification records (simulated delivery)
│   ├── tests/test_notifications_unit.py
│   ├── conftest.py
│   ├── requirements.txt
│   └── Dockerfile
├── tests/
│   ├── integration/test_order_workflow.py   # cross-service workflow tests
│   ├── regression/test_regression.py        # regression suite
│   ├── smoke/smoke_test.py                  # health-check gate
│   └── performance/load-test.js             # k6 scenario + thresholds
├── scripts/
│   └── wait_for_services.py      # polls health endpoints before test stages
├── docker-compose.yml            # one-command local stack
├── .github/workflows/
│   └── automated-testing.yml     # the entire pipeline
├── screenshots/                  # pipeline evidence
└── README.md
```

---

## Running Locally

### Prerequisites
Python 3.12+, Docker + Docker Compose, Git.

### Start the full stack

```bash
docker compose up --build -d
curl http://localhost:8000/health   # auth
curl http://localhost:8001/health   # orders
curl http://localhost:8002/health   # notifications
```

Interactive API docs: `http://localhost:8000/docs`, `:8001/docs`, `:8002/docs`.

### Try the workflow

```bash
# Register + login
curl -X POST http://localhost:8000/api/v1/register \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "Password123"}'

TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/login \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "Password123"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

# Create an order (order-service validates the token via auth-service)
curl -X POST http://localhost:8001/api/v1/orders \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"product": "Laptop", "quantity": 1, "price": 800}'

# See the notification event it triggered
docker compose logs notification-service | grep NOTIFICATION
```

### Run the test suites locally

```bash
# Unit tests (per service, inside its venv)
cd auth-service && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt pytest httpx
pytest tests/ -v

# Integration + smoke (stack must be running)
pip install requests
python scripts/wait_for_services.py
python tests/smoke/smoke_test.py
pytest tests/integration/ -v

# Contract fuzzing
pip install schemathesis
st run http://localhost:8000/openapi.json --checks all --max-examples 25
st run http://localhost:8002/openapi.json --checks all --max-examples 25
```

### CI
No setup required beyond the repository itself — GitHub Actions picks up `.github/workflows/automated-testing.yml` automatically. Every push to `main` runs the full pipeline.

---

## Evidence

### Full pipeline run — all stages green
![Pipeline success](screenshots/pipeline-success.png)

Lint → unit tests (×3 parallel) → integration → contract → regression → performance, with security scanning in parallel. Any red stage halts everything downstream.

### Test reports retained as artifacts
![Pipeline artifacts](screenshots/pipeline-artifacts.png)

JUnit XML results from all three services, uploaded on every run — including failed ones.

### Contract testing verdict
After iterative fixes, Schemathesis reports zero violations across both fuzzed services — e.g. **369 generated, 369 passed** on the notification service, including 79 stateful create-then-retrieve chains it inferred and executed automatically.

---

## Lessons Learned: Real Defects Caught by This Pipeline

These are not hypothetical — each row is an actual failure this pipeline produced during development, and what fixing it taught.

| # | What the pipeline caught | Stage | Root cause | Fix |
|---|---|---|---|---|
| 1 | **8 known CVEs** (PYSEC-2026-x) in `starlette 0.41.3` | pip-audit | Transitive dependency: `fastapi==0.115.6` pinned a vulnerable starlette; we never installed starlette directly | Upgraded FastAPI to 0.135.0 in all three services, pulling patched starlette 1.3.1 |
| 2 | **Undocumented 401s** on `/login` and `/validate` | Schemathesis | Code returned 401 for bad credentials but the OpenAPI spec never declared it | Added `responses={401: ...}` declarations |
| 3 | **Schema-violating 422 body** + **valid input rejected** on `/register` | Schemathesis | Password length was checked in hand-written code, invisible to the contract; error shape didn't match FastAPI's documented 422 format | Moved the rule into the Pydantic model (`Field(min_length=8)`) so spec and behavior are one source of truth |
| 4 | **403 instead of 401** on missing Authorization header | Schemathesis | FastAPI's `HTTPBearer` default short-circuits with 403; HTTP semantics require 401 for missing credentials | `HTTPBearer(auto_error=False)` + explicit 401 with `WWW-Authenticate: Bearer` header |
| 5 | **Undocumented 400** on malformed (unparseable) request bodies | Schemathesis (fuzzer sent literal garbage bytes) | Framework-level 400 wasn't declared on any body-accepting endpoint | Documented 400 on every POST/PATCH across all services |
| 6 | **Auth container crash-looped** while local dev worked fine | Docker / integration | `pydantic[email]` extra was dropped from requirements.txt during an edit; the local venv still had `email-validator` from an earlier install, masking the problem — the container, built strictly from requirements.txt, exposed it | Restored `pydantic[email]`; lesson: containers are the truth, venvs accumulate state |
| 7 | **Lambda-style "works on my machine" drift**: CI kept failing on the old starlette after the "fix" | pip-audit (repeatedly) | `pip install --upgrade` changed the venv but not requirements.txt; later, edited files were left unstaged so commits shipped without them | Pin versions in the file, not the venv; verify with `git status` before and `git show HEAD --stat` after every commit |
| 8 | **22 CRITICAL/HIGH OS-level CVEs** in the Debian base image | Trivy | Findings in perl, gzip, ncurses, util-linux — with **no fixed versions released upstream** | Adopted `ignore-unfixed: true`: fail on fixable vulnerabilities, report-but-don't-block unfixable ones (see Design Decisions) |

---

## Design Decisions

**In-memory storage instead of PostgreSQL.** The project's goal is the *testing pipeline*, not persistence. In-memory dict stores keep services trivially fast, stateless between runs (each CI run starts clean), and free of database fixtures. The API surface is identical, so a real database could be swapped in without changing a single test.

**Fail only on fixable vulnerabilities.** Trivy runs with `ignore-unfixed: true`. The Debian base image carries CVEs for which no patch exists yet; blocking every deploy on defects the upstream hasn't fixed would leave the pipeline permanently red with no action available. The policy mirrors standard DevSecOps triage: *a fix exists and we haven't applied it* → pipeline fails; *the world hasn't fixed it yet* → reported and monitored, not blocking. All findings still appear in full in the scan logs.

**Contract tests as a two-way gate.** Schemathesis enforces both directions: the API may not behave in ways the spec doesn't document, and the spec may not promise things the API doesn't do. Every constraint (password length, valid statuses, error codes) lives in the Pydantic models and route declarations, so the OpenAPI spec is generated from the same source of truth the runtime enforces.

**Security scans run parallel to tests, not after.** There is no dependency between "the code works" and "the dependencies are safe" — running them concurrently shortens the pipeline without weakening any gate.

**pytest for regression instead of Postman/Newman.** One toolchain, versioned in the repo, reviewed like any other code, no external collection files to drift out of sync.

**k6 over JMeter.** Single binary, JavaScript config in-repo, and native threshold support that turns performance targets into hard pass/fail pipeline gates rather than reports someone has to read.

---

## Kubernetes Deployment

The `kubernetes/` directory contains production-style manifests: one Deployment per service and a `services.yml` defining their cluster network identities. Each Deployment includes:

- **Readiness probes** on `/health` — Kubernetes routes traffic to a pod only after its probe passes (the cluster-native equivalent of the pipeline's `wait_for_services.py`)
- **Liveness probes** — a hung container is automatically restarted (self-healing)
- **Resource requests and limits** — bounded CPU/memory per pod
- **Cluster DNS wiring** — the order service reaches its peers via Service names (`AUTH_SERVICE_URL=http://auth-service:8000`), the same environment-variable mechanism used by Docker Compose, so the application code is identical in both environments

### Deploying to a local cluster (minikube)

```bash
minikube start --driver=docker

# Build images inside minikube's Docker daemon —
# the manifests use imagePullPolicy: Never, so images must exist in-cluster
eval $(minikube docker-env)
docker compose build

kubectl apply -f kubernetes/
kubectl get pods        # wait for 1/1 Running on all three
```

### Verifying the deployment

```bash
kubectl port-forward service/auth-service 9000:8000 &
kubectl port-forward service/order-service 9001:8001 &

# register → login → create order against 9000/9001, then:
kubectl logs deployment/notification-service | grep NOTIFICATION
```

A successful order proves two in-cluster hops over Kubernetes DNS: order→auth (token validation) and order→notification (event delivery). The port-forwards are only the laptop's window into the cluster; inter-service traffic never leaves it.

### Known limitation

With in-memory storage, each Deployment runs `replicas: 1` by design: a token issued by one auth pod would be unknown to a second replica. Horizontal scaling would require externalizing state (e.g. PostgreSQL for records, Redis for tokens) — the API surface is already compatible.



*Built as a DevOps portfolio project demonstrating CI/CD pipeline engineering, automated testing across nine categories, microservices architecture, containerization, DevSecOps scanning policy, and — perhaps most importantly — the debugging discipline of keeping local state, repository state, and CI state in agreement.*