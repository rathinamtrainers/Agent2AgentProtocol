# Booking Agent — Postman Testing Guide

- **Base URL:** `http://localhost:8003`
- **Authentication:** None required
- **Capabilities:** Sync (no streaming), Push Notifications, State Transition History
- **Output Format:** `DataPart` (structured JSON)
- **Special Feature:** Multi-turn conversation via `input-required` state (3 questions before completion)

---

## Prerequisites

1. Start the Booking Agent: `python agents/booking_agent.py`
2. Confirm it is running by opening `http://localhost:8003/.well-known/agent.json` in a browser.
3. For push notification tests (TC-B06, TC-B07), also start the Webhook Receiver: `python client/webhook_receiver.py` (port 9000).

---

## Important: Multi-Turn Conversation Flow

The Booking Agent uses a 3-step conversation. Each step returns `input-required` state until the final step returns `completed`. To continue the conversation, you must reuse the **same taskId** from the first response by including it in `message.taskId`.

```
Step 0: Initial request        → Agent asks: "What seat class?"       (input-required)
Step 1: Send seat class        → Agent asks: "What meal preference?"  (input-required)
Step 2: Send meal preference   → Agent asks: "Loyalty number?"        (input-required)
Step 3: Send loyalty number    → Agent returns booking confirmation   (completed)
```

---

## Test Cases

### TC-B01: Agent Card Discovery

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8003/.well-known/agent.json` |
| Headers | None |

**Expected Response:**
- Status: `200 OK`
- `name`: `"Booking Agent"`
- `capabilities.streaming`: `false`
- `capabilities.pushNotifications`: `true`
- `capabilities.stateTransitionHistory`: `true`
- `skills` array contains `"book_travel"`

---

### TC-B02: Multi-Turn Booking — Step 0 (Initial Request)

Start a new booking conversation.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8003/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-b02-step0",
      "parts": [
        {
          "kind": "text",
          "text": "Book flight FL001 and hotel H001 in Paris"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"input-required"`
- `result.status.message.parts[0].text` contains `"What seat class would you prefer?"` with options: economy / business / first
- No artifacts yet

**Save the `result.id` value — this is the `taskId` you must reuse for all subsequent steps.**

---

### TC-B03: Multi-Turn Booking — Step 1 (Seat Class)

Continue the conversation with seat class answer. Use the **taskId from TC-B02**.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8003/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-b03-step1",
      "taskId": "<taskId from TC-B02>",
      "parts": [
        {
          "kind": "text",
          "text": "business"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"input-required"`
- `result.status.message.parts[0].text` contains `"What is your meal preference?"` with options: standard / vegetarian / vegan / halal / kosher

---

### TC-B04: Multi-Turn Booking — Step 2 (Meal Preference)

Continue with meal preference. Use the **same taskId**.

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-b04-step2",
      "taskId": "<taskId from TC-B02>",
      "parts": [
        {
          "kind": "text",
          "text": "vegetarian"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"input-required"`
- `result.status.message.parts[0].text` contains `"Please provide your airline loyalty program number"` with option to type `"none"` to skip

---

### TC-B05: Multi-Turn Booking — Step 3 (Loyalty Number → Completion)

Final step — provide loyalty number. Use the **same taskId**.

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "4",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-b05-step3",
      "taskId": "<taskId from TC-B02>",
      "parts": [
        {
          "kind": "text",
          "text": "FFN-123456"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.artifacts[0].name` is `"booking_confirmation"`
- Artifact `DataPart` contains:
  - `booking_ref`: starts with `"BK"` followed by 8 hex characters (e.g., `"BK1A2B3C4D"`)
  - `status`: `"confirmed"`
  - `original_request`: `"Book flight FL001 and hotel H001 in Paris"`
  - `seat_class`: `"business"`
  - `meal_preference`: `"vegetarian"`
  - `loyalty_number`: `"FFN-123456"`
  - `confirmation_message`: Human-readable confirmation string
  - `confirmed_at`: ISO timestamp

---

### TC-B06: Push Notification — Register Webhook

Register a webhook to receive push notifications for a task. Start a **new** booking first (repeat TC-B02 to get a fresh taskId).

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8003/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "5",
  "method": "tasks/pushNotificationConfig/set",
  "params": {
    "id": "<new taskId>",
    "pushNotificationConfig": {
      "url": "http://localhost:9000/webhook",
      "token": "webhook-secret-token"
    }
  }
}
```

**Expected Response:**
- Response confirms the push notification config was set
- Contains the `pushNotificationConfig` with the URL and token

**Then complete the booking** by sending steps 1-3 (TC-B03 → TC-B05) with this taskId. After the task completes, check the Webhook Receiver terminal or `http://localhost:9000/notifications` — it should have received a POST with the completed task payload and header `X-A2A-Notification-Token: webhook-secret-token`.

---

### TC-B07: Push Notification — Verify Webhook Received

After completing TC-B06 (webhook registration + full booking), verify the notification was delivered.

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:9000/notifications` |
| Headers | None |

**Expected Response:**
- JSON array containing at least one notification
- Each notification has the completed task data with `booking_confirmation` artifact

---

### TC-B08: Get Task Status with History (tasks/get)

After completing a full booking (TC-B02 through TC-B05), retrieve the task with full state history.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8003/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "6",
  "method": "tasks/get",
  "params": {
    "id": "<taskId from TC-B02>",
    "historyLength": 20
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.history` contains state transitions: `submitted` → `working` → `input-required` → `submitted` → `working` → `input-required` → ... → `completed`

---

### TC-B09: Cancel a Booking Mid-Conversation

Start a new booking (repeat TC-B02), then cancel before completing all steps.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8003/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "7",
  "method": "tasks/cancel",
  "params": {
    "id": "<taskId from the new booking>"
  }
}
```

**Expected Response:**
- `result.status.state` is `"canceled"`
- The in-progress booking session is cleaned up

---

### TC-B10: Multi-Turn — Skip Loyalty Number

Run the full 4-step flow but send `"none"` as the loyalty number in step 3.

**Request Body (Step 3 only):**
```json
{
  "jsonrpc": "2.0",
  "id": "8",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-b10-step3",
      "taskId": "<taskId>",
      "parts": [
        {
          "kind": "text",
          "text": "none"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `loyalty_number` in confirmation is `"none"`

---

### TC-B11: Error Handling — Non-existent Task ID

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8003/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "9",
  "method": "tasks/get",
  "params": {
    "id": "non-existent-task-id-00000"
  }
}
```

**Expected Response:**
- Response contains `error` object (not `result`)
- Error code indicates task not found

---

## Test Summary Checklist

| # | Test Case | Status |
|---|---|---|
| TC-B01 | Agent Card Discovery | |
| TC-B02 | Multi-Turn Step 0 — Initial Request (input-required) | |
| TC-B03 | Multi-Turn Step 1 — Seat Class (input-required) | |
| TC-B04 | Multi-Turn Step 2 — Meal Preference (input-required) | |
| TC-B05 | Multi-Turn Step 3 — Loyalty Number (completed) | |
| TC-B06 | Push Notification — Register Webhook | |
| TC-B07 | Push Notification — Verify Webhook Received | |
| TC-B08 | Get Task Status with History | |
| TC-B09 | Cancel Booking Mid-Conversation | |
| TC-B10 | Multi-Turn — Skip Loyalty Number | |
| TC-B11 | Error — Non-existent Task ID | |
