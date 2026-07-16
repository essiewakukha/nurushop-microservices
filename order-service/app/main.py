import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

app = FastAPI(title="NuruShop Order Service")
security = HTTPBearer()

# Service URLs come from env vars so the same code works locally AND in Docker
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8002")

orders: dict[str, dict] = {}

VALID_STATUSES = {"pending", "confirmed", "shipped", "delivered", "cancelled"}


class OrderRequest(BaseModel):
    product: str
    quantity: int
    price: float


class StatusUpdate(BaseModel):
    status: str


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Call the auth service to validate the token. Returns the user's email."""
    try:
        response = httpx.get(
            f"{AUTH_SERVICE_URL}/api/v1/validate",
            headers={"Authorization": f"Bearer {credentials.credentials}"},
            timeout=5,
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Auth service unavailable")
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")
    return response.json()["email"]


def send_notification(order_id: str, email: str, message: str) -> None:
    """Notify the notification service. Failure to notify must not fail the order."""
    try:
        httpx.post(
            f"{NOTIFICATION_SERVICE_URL}/api/v1/notifications",
            json={"order_id": order_id, "email": email, "message": message},
            timeout=5,
        )
    except httpx.RequestError:
        pass  # notifications are best-effort


@app.post(
    "/api/v1/orders",
    status_code=201,
    responses={
        400: {"description": "Malformed request body"},
        401: {"description": "Invalid token"},
        503: {"description": "Auth service unavailable"},
    },
)
def create_order(order: OrderRequest, email: str = Depends(verify_token)):
    if order.quantity < 1:
        raise HTTPException(status_code=422, detail="Quantity must be at least 1")
    if order.price < 0:
        raise HTTPException(status_code=422, detail="Price cannot be negative")

    order_id = str(uuid.uuid4())
    record = {
        "order_id": order_id,
        "email": email,
        "product": order.product,
        "quantity": order.quantity,
        "price": order.price,
        "total": order.quantity * order.price,
        "status": "pending",
    }
    orders[order_id] = record
    send_notification(order_id, email, f"Order created for {order.product}")
    return record


@app.get(
    "/api/v1/orders/{order_id}",
    responses={
        401: {"description": "Invalid token"},
        404: {"description": "Order not found"},
        503: {"description": "Auth service unavailable"},
    },
)
def get_order(order_id: str, email: str = Depends(verify_token)):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.patch(
    "/api/v1/orders/{order_id}",
    responses={
        400: {"description": "Malformed request body"},
        401: {"description": "Invalid token"},
        404: {"description": "Order not found"},
        503: {"description": "Auth service unavailable"},
    },
)
def update_order_status(order_id: str, update: StatusUpdate, email: str = Depends(verify_token)):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if update.status not in VALID_STATUSES:
        raise HTTPException(status_code=422, detail=f"Status must be one of {sorted(VALID_STATUSES)}")
    order["status"] = update.status
    send_notification(order_id, order["email"], f"Order status changed to {update.status}")
    return order


@app.get("/health")
def health():
    return {"status": "healthy"}