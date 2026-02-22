# Weather Agent — Postman Testing Guide

- **Base URL:** `http://localhost:8004`
- **Authentication:** None required
- **Capabilities:** SSE Streaming
- **Output Format:** `DataPart` (structured JSON)

---

## Prerequisites

1. Start the Weather Agent: `python agents/weather_agent.py`
2. Confirm it is running by opening `http://localhost:8004/.well-known/agent.json` in a browser.

---

## Test Cases

### TC-W01: Agent Card Discovery

Verify that the agent card is served correctly at the well-known endpoint.

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8004/.well-known/agent.json` |
| Headers | None |

**Expected Response:**
- Status: `200 OK`
- Body contains `name`: `"Weather Agent"`
- Body contains `capabilities.streaming`: `true`
- Body contains `skills` array with skill id `"get_weather_forecast"`
- Body contains `defaultInputModes`: `["text/plain"]`
- Body contains `defaultOutputModes`: `["application/json"]`

---

### TC-W02: Basic Weather Query (Sync — message/send)

Send a synchronous weather query for a known city.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8004/` |
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
      "messageId": "msg-w02",
      "parts": [
        {
          "kind": "text",
          "text": "Weather in Tokyo"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.artifacts` array has 1 entry with name `"weather_forecast"`
- Artifact `parts` contain `DataPart` entries with fields: `date`, `city`, `condition`, `high_c`, `low_c`, `humidity_pct`
- City value is `"Tokyo"`
- 7 days of data present in the artifact parts

**Note:** Save the `result.id` (taskId) from the response — you will need it for TC-W05 and TC-W06.

---

### TC-W03: SSE Streaming (message/stream) — Known City

Stream a 7-day forecast, receiving one day per SSE event.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8004/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "message/stream",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-w03",
      "parts": [
        {
          "kind": "text",
          "text": "Weather forecast for Paris"
        }
      ]
    }
  }
}
```

**Expected Response (SSE stream):**
- Response header `Content-Type` is `text/event-stream`
- Receives multiple `data:` lines over time
- First events are `TaskStatusUpdateEvent` with states `submitted`, then `working`
- Then 7 `TaskArtifactUpdateEvent` events (one per day) with:
  - First chunk: `append: false`
  - Chunks 2–6: `append: true`
  - Last chunk (day 7): `lastChunk: true`
- Each chunk contains `DataPart` with `city: "Paris"` and matching Paris weather data (highs: 12,14,11,9,13,15,16)
- Final event is `TaskStatusUpdateEvent` with state `completed`

---

### TC-W04: SSE Streaming — Different Cities

Repeat TC-W03 with different city inputs to verify city parsing.

**Test Data:**

| Input Text | Expected City | Has Custom Data? |
|---|---|---|
| `"Weather in London"` | London | Yes — highs: 10,11,9,12,10,8,11 |
| `"Weather forecast for New York"` | New York | Yes — highs: 8,10,7,9,11,12,10 |
| `"Weather in Tokyo"` | Tokyo | Yes — highs: 18,20,19,22,21,23,20 |
| `"Weather in Mumbai"` | Mumbai | No — defaults: all highs = 20, all lows = 12, all "Sunny" |

Use the same request body format as TC-W03, changing only the `text` field.

**Expected:** Each response uses the correct city-specific data, or defaults for unknown cities.

---

### TC-W05: Get Task Status (tasks/get)

Poll for a completed task using the taskId from TC-W02.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8004/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "tasks/get",
  "params": {
    "id": "<taskId from TC-W02>",
    "historyLength": 10
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.artifacts` contains the weather forecast data
- If `historyLength` is provided, `result.history` contains the state transition entries

---

### TC-W06: Cancel a Task (tasks/cancel)

Cancel a task using a known taskId.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8004/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "4",
  "method": "tasks/cancel",
  "params": {
    "id": "<taskId from TC-W02>"
  }
}
```

**Expected Response:**
- `result.status.state` is `"canceled"`

---

### TC-W07: Error Handling — Non-existent Task ID

Request a task that does not exist.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8004/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "5",
  "method": "tasks/get",
  "params": {
    "id": "non-existent-task-id-12345"
  }
}
```

**Expected Response:**
- Response contains `error` object (not `result`)
- Error code indicates task not found

---

### TC-W08: Error Handling — Invalid JSON-RPC Method

Send a request with an unsupported method name.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8004/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "6",
  "method": "invalid/method",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-w08",
      "parts": [{"kind": "text", "text": "test"}]
    }
  }
}
```

**Expected Response:**
- Response contains `error` object
- Error code indicates method not found

---

## Test Summary Checklist

| # | Test Case | Status |
|---|---|---|
| TC-W01 | Agent Card Discovery | |
| TC-W02 | Basic Weather Query (message/send) | |
| TC-W03 | SSE Streaming — Paris | |
| TC-W04 | SSE Streaming — Multiple Cities | |
| TC-W05 | Get Task Status (tasks/get) | |
| TC-W06 | Cancel a Task (tasks/cancel) | |
| TC-W07 | Error — Non-existent Task ID | |
| TC-W08 | Error — Invalid JSON-RPC Method | |
