# Hotel Agent — Postman Testing Guide

- **Base URL:** `http://localhost:8002`
- **Authentication:** API Key via `X-Api-Key` header
- **Valid API Key:** `hotel-api-key-12345`
- **Capabilities:** Sync (no streaming), Multimodal (PDF input)
- **Output Format:** `DataPart` (structured JSON)

---

## Prerequisites

1. Start the Hotel Agent: `python agents/hotel_agent.py`
2. Confirm it is running by opening `http://localhost:8002/.well-known/agent.json` in a browser.

---

## Test Cases

### TC-H01: Agent Card Discovery

Verify that the agent card is served correctly.

| Field | Value |
|---|---|
| Method | `GET` |
| URL | `http://localhost:8002/.well-known/agent.json` |
| Headers | None |

**Expected Response:**
- Status: `200 OK`
- `name`: `"Hotel Search Agent"`
- `capabilities.streaming`: `false`
- `skills` array contains `"search_hotels"` and `"extract_brochure"`
- `defaultInputModes` includes `"text/plain"` and `"application/pdf"`
- `defaultOutputModes`: `["application/json"]`
- `securitySchemes` contains `"apiKey"` with `name: "X-Api-Key"` and `in: "header"`

---

### TC-H02: Hotel Search — Paris (Valid API Key)

Search for hotels in a known city with correct authentication.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8002/` |
| Headers | `Content-Type: application/json`, `X-Api-Key: hotel-api-key-12345` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "1",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-h02",
      "parts": [
        {
          "kind": "text",
          "text": "Hotels in Paris"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.artifacts[0].name` is `"hotel_results"`
- Artifact contains `DataPart` with a `hotels` array of 3 entries:
  - `Grand Paris Hotel` (5 stars, $320/night, H001)
  - `Hôtel Lumière` (4 stars, $185/night, H002)
  - `Le Marais Boutique` (3 stars, $110/night, H003)
- Each hotel object has: `hotel_id`, `name`, `city`, `stars`, `price_per_night_usd`, `amenities`, `available_rooms`

**Note:** Save the `result.id` (taskId) for TC-H07.

---

### TC-H03: Hotel Search — Different Cities

Repeat TC-H02 with different cities.

**Test Data:**

| Input Text | Expected Hotels | Count |
|---|---|---|
| `"Hotels in London"` | The Savoy, City Premier Inn, Shoreditch Boutique | 3 |
| `"Hotels in Tokyo"` | Park Hyatt Tokyo, Shinjuku Granbell, Asakusa Budget Inn | 3 |
| `"Hotels in Mumbai"` | City Central Hotel, Budget Stay (defaults) | 2 |

Use the same request format as TC-H02, changing only the `text` field. Remember to include the `X-Api-Key` header.

---

### TC-H04: Authentication Failure — Wrong API Key

Send a request with an incorrect API key.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8002/` |
| Headers | `Content-Type: application/json`, `X-Api-Key: wrong-key-999` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "2",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-h04",
      "parts": [
        {
          "kind": "text",
          "text": "Hotels in Paris"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"failed"`
- `result.status.message.parts[0].text` contains `"Unauthorized: invalid or missing API key"`

---

### TC-H05: Authentication Failure — Missing API Key Header

Send a request without the `X-Api-Key` header entirely.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8002/` |
| Headers | `Content-Type: application/json` (no X-Api-Key) |

**Request Body:** Same as TC-H04.

**Expected Response:**
- `result.status.state` is `"failed"`
- `result.status.message.parts[0].text` contains `"Unauthorized: invalid or missing API key"`

---

### TC-H06: Multimodal — PDF Brochure Extraction

Send a `FilePart` with a PDF mime type to trigger brochure extraction.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8002/` |
| Headers | `Content-Type: application/json`, `X-Api-Key: hotel-api-key-12345` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "3",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-h06",
      "parts": [
        {
          "kind": "text",
          "text": "Extract amenities from this brochure"
        },
        {
          "kind": "file",
          "file": {
            "bytes": "JVBERi0xLjQgZmFrZSBicm9jaHVyZSBieXRlcw==",
            "mimeType": "application/pdf",
            "name": "hotel_brochure.pdf"
          }
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.artifacts[0].name` is `"brochure_extraction"`
- Artifact `DataPart` contains:
  - `hotel_name`: `"Grand Paris Hotel"`
  - `stars`: `5`
  - `location`: `"8th Arrondissement, Paris, France"`
  - `amenities`: array of 11 items (WiFi, Pool, Spa, Restaurant, Rooftop Bar, etc.)
  - `room_types`: array of 4 entries (Superior Room, Deluxe Room, Junior Suite, Presidential Suite)
  - `extracted_from`: `"pdf_brochure"`
  - `extraction_confidence`: `0.97`

---

### TC-H07: Get Task Status (tasks/get)

Retrieve a previously completed task.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8002/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "4",
  "method": "tasks/get",
  "params": {
    "id": "<taskId from TC-H02>",
    "historyLength": 10
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.artifacts` contains the hotel results from the original query

---

### TC-H08: Error Handling — Non-existent Task ID

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8002/` |
| Headers | `Content-Type: application/json` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "5",
  "method": "tasks/get",
  "params": {
    "id": "non-existent-task-id-99999"
  }
}
```

**Expected Response:**
- Response contains `error` object (not `result`)
- Error code indicates task not found

---

### TC-H09: Multimodal — Text Only (No FilePart)

Confirm that when no PDF is sent, the agent performs a normal text search even if the text mentions brochures.

| Field | Value |
|---|---|
| Method | `POST` |
| URL | `http://localhost:8002/` |
| Headers | `Content-Type: application/json`, `X-Api-Key: hotel-api-key-12345` |

**Request Body:**
```json
{
  "jsonrpc": "2.0",
  "id": "6",
  "method": "message/send",
  "params": {
    "message": {
      "role": "user",
      "messageId": "msg-h09",
      "parts": [
        {
          "kind": "text",
          "text": "Extract amenities from the brochure"
        }
      ]
    }
  }
}
```

**Expected Response:**
- `result.status.state` is `"completed"`
- `result.artifacts[0].name` is `"hotel_results"` (NOT `"brochure_extraction"`)
- Agent treats this as a regular hotel search since no `FilePart` is present

---

## Test Summary Checklist

| # | Test Case | Status |
|---|---|---|
| TC-H01 | Agent Card Discovery | |
| TC-H02 | Hotel Search — Paris | |
| TC-H03 | Hotel Search — London, Tokyo, Unknown City | |
| TC-H04 | Auth Failure — Wrong API Key | |
| TC-H05 | Auth Failure — Missing API Key | |
| TC-H06 | Multimodal — PDF Brochure Extraction | |
| TC-H07 | Get Task Status (tasks/get) | |
| TC-H08 | Error — Non-existent Task ID | |
| TC-H09 | Multimodal — Text Only (no FilePart) | |
