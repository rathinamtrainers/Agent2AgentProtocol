"""
client/webhook_receiver.py
==========================
Section 8 — Push Notifications: Webhook Receiver

This FastAPI server receives push notification callbacks from the Booking Agent
when a task completes asynchronously. It validates the secret token, parses the
Task payload, and logs the result.

The A2A server sends push notifications as HTTP POST requests to the URL
registered via tasks/pushNotificationConfig/set. The notification body is the
full Task JSON. The token is sent in the X-A2A-Notification-Token header.

Run:
    python client/webhook_receiver.py
Listens on: http://localhost:9000/webhook
"""

import logging
from datetime import datetime, timezone
from typing import Optional

import uvicorn
from a2a.types import DataPart, Task
from fastapi import FastAPI, Header, HTTPException, Request

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

WEBHOOK_SECRET_TOKEN = "webhook-secret-token"

app = FastAPI(
    title="A2A Push Notification Receiver",
    description="Section 8: Receives task completion webhooks from A2A agents.",
)

# In-memory store of received notifications (for the tutorial demo)
received_notifications: list[dict] = []


@app.post("/webhook")
async def receive_push_notification(
    request: Request,
    x_a2a_notification_token: Optional[str] = Header(None),
):
    """
    Section 8 — Push Notification Endpoint

    Called by the A2A server when a task registered with a push notification
    config reaches a terminal state (completed, failed, canceled).

    Steps:
    1. Validate the token from X-A2A-Notification-Token header
    2. Parse the Task JSON from the request body
    3. Log the booking confirmation result
    """
    # Step 1: Token validation
    if x_a2a_notification_token != WEBHOOK_SECRET_TOKEN:
        logger.warning(
            "Rejected webhook with invalid token: %r", x_a2a_notification_token
        )
        raise HTTPException(status_code=401, detail="Invalid notification token")

    body = await request.json()
    received_at = datetime.now(timezone.utc).isoformat()

    notification_record = {"received_at": received_at, "body": body}
    received_notifications.append(notification_record)

    task_id = body.get("id", "unknown")
    logger.info("Received push notification for task: %s", task_id)

    # Step 2 + 3: Parse and log
    try:
        task = Task.model_validate(body)
        state = task.status.state.value if task.status else "unknown"
        logger.info("  Task %s reached state: %s", task.id, state)

        if task.artifacts:
            for artifact in task.artifacts:
                for part in artifact.parts:
                    if isinstance(part.root, DataPart):
                        data = part.root.data
                        if isinstance(data, dict) and "booking_ref" in data:
                            logger.info(
                                "  Booking confirmed: %s — %s",
                                data["booking_ref"],
                                data.get("confirmation_message", ""),
                            )
                        else:
                            logger.info("  Artifact data: %s", data)
    except Exception as exc:
        logger.warning("Could not parse push notification body as Task: %s", exc)
        logger.info("  Raw body: %s", body)

    return {"status": "received", "task_id": task_id, "received_at": received_at}


@app.get("/notifications")
async def list_notifications():
    """List all received push notifications (for inspection during the tutorial)."""
    return {
        "count": len(received_notifications),
        "notifications": received_notifications,
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "received_count": len(received_notifications)}


if __name__ == "__main__":
    logger.info("Starting Webhook Receiver on http://localhost:9000")
    logger.info("Token: %s", WEBHOOK_SECRET_TOKEN)
    uvicorn.run(app, host="0.0.0.0", port=9000, log_level="warning")
