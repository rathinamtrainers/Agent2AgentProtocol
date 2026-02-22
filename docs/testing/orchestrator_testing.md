# Travel Orchestrator — Postman Testing Guide

- **Base URL:** `http://localhost:8010`
- **Authentication:** None required (orchestrator handles auth to downstream agents internally)
- **Capabilities:** SSE Streaming
- **Output Format:** `TextPart` (progress logs) + `DataPart` (final travel plan)
- **Depends On:** Flight Agent (:8001), Hotel Agent (:8002), Weather Agent (:8004)

---

## Prerequisites

1. Start **all four specialist agents first** (order does not matter):
   - `python agents/flight_agent.py` (port 8001)
   - `python agents/hotel_agent.py` (port 8002)
   - `python agents/weather_agent.py` (port 8004)
2. Then start the orchestrator: `python orchestrator/travel_orchestrator.py` (port 8010)
3. Confirm all services are running:
   - `http://localhost:8001/.well-known/agent.json`
   - `http://localhost:8002/.well-known/agent.json`
   - `http://localhost:8004/.well-known/agent.json`
   - `http://localhost:8010/.well-known/agent.json`

---

## Test Cases

### TC-O01: Agent Card Discovery

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8010/.well-known/agent.json` |
| Headers | None |

**Expected Response:**
- Status: `200 OK`
- `name`: `"Travel Orchestrator"`
- `capabilities.streaming`: `true`
- `skills` array contains `"plan_travel"`
- `defaultInputModes`: `["text/plain"]`
- `defaultOutputModes`: `["application/json"]`
- No `securitySchemes` (public agent)

---

### TC-O02: Full Travel Plan — Sync (message/send)

Send a travel planning request and receive the aggregated result.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8010/` |
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
      "messageId": "msg-o02",
      "parts": [
        {
          "kind": "text",
          "text": "Plan a trip to Paris"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.artifacts` contains an artifact named `"travel_plan"` with a `DataPart` containing:
  - `destination`: `"Paris"`
  - `original_request`: `"Plan a trip to Paris"`
  - `agents_used`: array containing `"flight"`, `"hotel"`, `"weather"`
  - `summary`: string mentioning counts of flights, hotels, and weather days
  - `flights`: array of 3 flights (BA117, AA101, AF006)
  - `hotels`: array of 3 Paris hotels (Grand Paris Hotel, Hotel Lumiere, Le Marais Boutique)
  - `weather_forecast`: array of 7 daily forecasts for Paris
  - `generated_at`: ISO timestamp

**Note:** Save the `result.id` (taskId) for TC-O05.

---

### TC-O03: Full Travel Plan — SSE Streaming (message/stream)

Stream the orchestration progress with live updates.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8010/` |
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
      "messageId": "msg-o03",
      "parts": [
        {
          "kind": "text",
          "text": "I want to travel from NYC to London next month"
        }
      ]
    }
  }
}
```

**Expected Response (SSE stream):**
- `TaskStatusUpdateEvent` with state `submitted`
- `TaskStatusUpdateEvent` with state `working`
- `TaskArtifactUpdateEvent` — progress log: `"[1/4] Discovering specialist agents for trip to London..."`
- `TaskArtifactUpdateEvent` — progress log: `"[2/4] Dispatching parallel requests: flights, hotels, weather..."`
- `TaskArtifactUpdateEvent` — progress log: `"[3/4] Aggregating results: 3 flights, 3 hotels, 7 weather days."`
- `TaskArtifactUpdateEvent` — final `travel_plan` artifact with `lastChunk: true` containing the complete aggregated data for London
- `TaskStatusUpdateEvent` with state `completed`

---

### TC-O04: Travel Plan — Different Cities

Repeat TC-O02 with different destinations to verify city extraction.

**Test Data:**

| Input Text | Expected Destination | Expected Hotels |
|---|---|---|
| `"Plan a trip to Tokyo"` | Tokyo | Park Hyatt Tokyo, Shinjuku Granbell, Asakusa Budget Inn |
| `"Help me plan a trip to London"` | London | The Savoy, City Premier Inn, Shoreditch Boutique |
| `"I want to visit Paris"` | Paris | Grand Paris Hotel, Hotel Lumiere, Le Marais Boutique |

Use the same request format as TC-O02, changing only the `text` field.

**Expected:** Each response contains city-specific hotels and weather, while flights are always the same 3 mock flights.

---

### TC-O05: Get Task Status (tasks/get)

Retrieve a previously completed orchestration task.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8010/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "tasks/get",
  "params": {
    "id": "<taskId from TC-O02>",
    "historyLength": 10
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.artifacts` contains the travel plan data

---

### TC-O06: Cancel an Orchestration Task

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8010/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "4",
  "method": "tasks/cancel",
  "params": {
    "id": "<taskId from TC-O02>"
  }
}
```

**Expected Response:**
- `result.status.state` is `"canceled"`

---

### TC-O07: Error Handling — Non-existent Task ID

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8010/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "5",
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

### TC-O08: Graceful Degradation — Agent Down

Test orchestrator behavior when one downstream agent is unavailable.

**Setup:** Stop the Weather Agent (kill the process on port 8004), keep Flight and Hotel agents running.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8010/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "6",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-o08",
      "parts": [
        {
          "kind": "text",
          "text": "Plan a trip to Paris"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"` (orchestrator does not fail entirely)
- `result.artifacts[0]` travel plan contains:
  - `flights`: array of 3 flights (from Flight Agent — still running)
  - `hotels`: array of 3 hotels (from Hotel Agent — still running)
  - `weather_forecast`: empty array `[]` (Weather Agent was down)
- Summary reflects `0` weather days

**Cleanup:** Restart the Weather Agent after this test.

---

### TC-O09: Graceful Degradation — All Agents Down

Stop all three specialist agents, keep only the orchestrator running.

**Request Body:** Same as TC-O08.

**Expected Response:**
- `result.status.state` is `"completed"`
- Travel plan contains:
  - `flights`: `[]`
  - `hotels`: `[]`
  - `weather_forecast`: `[]`
- Summary reflects 0 flights, 0 hotels, 0 weather days

**Cleanup:** Restart all agents after this test.

---

## Test Summary Checklist

| # | Test Case | Status |
|---|---|---|
| TC-O01 | Agent Card Discovery | |
| TC-O02 | Full Travel Plan — Sync (message/send) | |
| TC-O03 | Full Travel Plan — SSE Streaming (message/stream) | |
| TC-O04 | Travel Plan — Different Cities | |
| TC-O05 | Get Task Status (tasks/get) | |
| TC-O06 | Cancel Orchestration Task | |
| TC-O07 | Error — Non-existent Task ID | |
| TC-O08 | Graceful Degradation — One Agent Down | |
| TC-O09 | Graceful Degradation — All Agents Down | |
