import os
import uuid
import httpx
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials   

app = FastAPI(title="Nurushop Order service")
security = HTTPBearer()

#service urls configured via environment variables and Docker Compose
AUTH_SERVICE_URL = os.getenv("AUTH_SERVICE_URL", "http://localhost:8000")
NOTIFICATION_SERVICE_URL = os.getenv("NOTIFICATION_SERVICE_URL", "http://localhost:8002")

orders: dict[str, dict] = {}  # order_id -> order details

VALID_STATUSES = {"pending", "confirmed", "shipped", "delivered", "cancelled"}

#class to represent an order
class OrderRequest(BaseModel):
    product: str
    quantity: int
    price: float

class StatusUpdate(BaseModel):
    status: str



#dependency to validate the token with the auth service
def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify the token with the auth service and return the associated email."""
    try: 
        response = httpx.get(
            f"{AUTH_SERVICE_URL}/api/v1/validate", headers={"Authorization": f"Bearer {credentials.credentials}"}, 
            timeout=5.0
        )
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Auth service unavailable")
    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Invalid token")
    return response.json().get("email")    
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


@app.post("/api/v1/orders", status_code=201)
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


@app.get("/api/v1/orders/{order_id}")
def get_order(order_id: str, email: str = Depends(verify_token)):
    order = orders.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.patch("/api/v1/orders/{order_id}")
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