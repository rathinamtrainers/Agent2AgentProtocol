# Flight Agent — Postman Testing Guide

- **Base URL:** `http://localhost:8001`
- **Authentication:** Bearer Token via `Authorization` header
- **Valid Token:** `flight-secret-token`
- **Capabilities:** SSE Streaming
- **Output Format:** `DataPart` (structured JSON)

---

## Prerequisites

1. Start the Flight Agent: `python agents/flight_agent.py`
2. Confirm it is running by opening `http://localhost:8001/.well-known/agent.json` in a browser.

---

## Test Cases

### TC-F01: Agent Card Discovery

Verify that the agent card is served correctly.

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8001/.well-known/agent.json` |
| Headers | None |

**Expected Response:**
- Status: `200 OK`
- `name`: `"Flight Search Agent"`
- `capabilities.streaming`: `true`
- `skills` array contains `"search_flights"` and `"get_flight_details"`
- `defaultInputModes`: `["text/plain"]`
- `defaultOutputModes`: `["application/json"]`
- `securitySchemes` contains `"bearerAuth"` with `type: "http"` and `scheme: "bearer"`

---

### TC-F02: Flight Search — Sync (message/send)

Send a synchronous flight search with valid Bearer token.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8001/` |
| Headers | `Content-Type: application/json`, `Authorization: Bearer flight-secret-token` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-f02",
      "parts": [
        {
          "kind": "text",
          "text": "Find flights from New York to London on 2026-03-15"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.artifacts` contains flight data with 3 flights:
  - BA117 — British Airways, JFK→LHR, $850
  - AA101 — American Airlines, JFK→LHR, $780
  - AF006 — Air France, JFK→CDG, $920
- Each flight object has: `flight_id`, `airline`, `iata_code`, `origin`, `destination`, `departure`, `arrival`, `duration_h`, `price_usd`, `seats_available`, `class`

**Note:** Save the `result.id` (taskId) for TC-F06.

---

### TC-F03: Flight Search — SSE Streaming (message/stream)

Stream flight results, receiving one flight per SSE event.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8001/` |
| Headers | `Content-Type: application/json`, `Authorization: Bearer flight-secret-token` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "message/stream",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-f03",
      "parts": [
        {
          "kind": "text",
          "text": "Search flights LHR to CDG tomorrow"
        }
      ]
    }
  }
}
```

**Expected Response (SSE stream):**
- Response header `Content-Type` is `text/event-stream`
- First events: `TaskStatusUpdateEvent` with states `submitted`, then `working`
- Then 3 `TaskArtifactUpdateEvent` events (one per flight):
  - Flight 1 (BA117): `append: false`
  - Flight 2 (AA101): `append: true`
  - Flight 3 (AF006): `append: true`, `lastChunk: true`
- Each chunk contains a `DataPart` with one flight object
- Final event: `TaskStatusUpdateEvent` with state `completed`
- Events arrive with ~0.5 second delay between flights

---

### TC-F04: Authentication Failure — Wrong Bearer Token

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8001/` |
| Headers | `Content-Type: application/json`, `Authorization: Bearer wrong-token` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-f04",
      "parts": [
        {
          "kind": "text",
          "text": "flights NYC to London"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"failed"`
- `result.status.message.parts[0].text` contains `"Unauthorized: invalid or missing Bearer token"`

---

### TC-F05: Authentication Failure — Missing Authorization Header

Send a request without any `Authorization` header.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8001/` |
| Headers | `Content-Type: application/json` (no Authorization) |

**Request Body:** Same as TC-F04.

**Expected Response:**
- `result.status.state` is `"failed"`
- `result.status.message.parts[0].text` contains `"Unauthorized: invalid or missing Bearer token"`

---

### TC-F06: Get Task Status (tasks/get)

Retrieve a previously completed task.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8001/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "4",
  "method": "tasks/get",
  "params": {
    "id": "<taskId from TC-F02>",
    "historyLength": 10
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.artifacts` contains the flight data from the original query

---

### TC-F07: Cancel a Task (tasks/cancel)

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8001/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "5",
  "method": "tasks/cancel",
  "params": {
    "id": "<taskId from TC-F02>"
  }
}
```

**Expected Response:**
- `result.status.state` is `"canceled"`

---

### TC-F08: Error Handling — Non-existent Task ID

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8001/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "6",
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

### TC-F09: Streaming Auth Failure

Verify that authentication is enforced on the streaming endpoint too.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8001/` |
| Headers | `Content-Type: application/json`, `Authorization: Bearer bad-token` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "7",
  "method": "message/stream",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-f09",
      "parts": [
        {
          "kind": "text",
          "text": "flights to Paris"
        }
      ]
    }
  }
}
```

**Expected Response:**
- SSE stream emits a `TaskStatusUpdateEvent` with `state: "failed"`
- Message text contains `"Unauthorized: invalid or missing Bearer token"`
- No flight data is returned

---

## Test Summary Checklist

| # | Test Case | Status |
|---|---|---|
| TC-F01 | Agent Card Discovery | |
| TC-F02 | Flight Search — Sync (message/send) | |
| TC-F03 | Flight Search — SSE Streaming (message/stream) | |
| TC-F04 | Auth Failure — Wrong Bearer Token | |
| TC-F05 | Auth Failure — Missing Authorization Header | |
| TC-F06 | Get Task Status (tasks/get) | |
| TC-F07 | Cancel a Task (tasks/cancel) | |
| TC-F08 | Error — Non-existent Task ID | |
| TC-F09 | Streaming Auth Failure | |
