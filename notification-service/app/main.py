import uuid

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="NuruShop Notification Service")

notifications: dict[str, dict] = {}


class NotificationRequest(BaseModel):
    order_id: str
    email: str
    message: str


@app.post(
    "/api/v1/notifications",
    status_code=201,
    responses={400: {"description": "Malformed request body"}},
)
def send_notification(notification: NotificationRequest):
    notification_id = str(uuid.uuid4())
    record = {
        "notification_id": notification_id,
        "order_id": notification.order_id,
        "email": notification.email,
        "message": notification.message,
        "channel": "email",       # simulated
        "delivered": True,        # simulated send
    }
    notifications[notification_id] = record
    print(f"[NOTIFICATION] To {notification.email}: {notification.message}")
    return record


@app.get(
    "/api/v1/notifications/{notification_id}",
    responses={404: {"description": "Notification not found"}},
)
def get_notification(notification_id: str):
    record = notifications.get(notification_id)
    if not record:
        raise HTTPException(status_code=404, detail="Notification not found")
    return record


@app.get("/health")
def health():
    return {"status": "healthy"}