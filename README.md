# A2A Protocol Tutorial — Travel Planning Multi-Agent System

A complete, single tutorial demonstrating **every feature** of the
[Agent-to-Agent (A2A) protocol](https://google.github.io/A2A/) using
[Google ADK](https://google.github.io/adk-docs/).

See [`TUTORIAL_PLAN.md`](TUTORIAL_PLAN.md) for the full design document.

---

## What Is A2A?

A2A is an open HTTP-based standard (open-sourced by Google in April 2025) that
lets AI agents built on **different frameworks** talk to each other. Without A2A,
every multi-agent system requires custom glue code. With A2A, any compliant
agent — LangChain, CrewAI, ADK, AutoGen — can delegate tasks to any other.

---

## System Architecture

```
User / Tutorial Client
  └── Travel Orchestrator  :8010  (Section 11 — orchestration)
        ├── Flight Agent   :8001  (Sections 2, 5, 9 — streaming, Bearer auth)
        ├── Hotel Agent    :8002  (Sections 2, 3, 6, 9 — sync, multimodal, API key)
        ├── Booking Agent  :8003  (Sections 7, 8 — input-required, push notifications)
        └── Weather Agent  :8004  (Sections 2, 5 — streaming)

Webhook Receiver           :9000  (Section 8 — push notification handler)
```

---

## A2A Features Covered

| Feature | Section | File |
|---|---|---|
| Agent Card (`/.well-known/agent.json`) | 2 | all agents |
| `AgentSkill`, `AgentCapabilities` | 2 | all agents |
| Bearer token auth | 2, 9 | `flight_agent.py` |
| API Key auth | 2, 9 | `hotel_agent.py` |
| `message/send` (sync) | 3 | `hotel_agent.py` |
| `TextPart`, `DataPart`, `Artifact` | 3 | `hotel_agent.py` |
| Task lifecycle: submitted→working→completed | 4 | all agents |
| `tasks/get` polling | 4 | `client/main.py` |
| `tasks/cancel` | 4, 10 | `client/main.py` |
| `message/stream` SSE | 5 | `flight_agent.py`, `weather_agent.py` |
| `TaskStatusUpdateEvent` | 5 | all agents |
| `TaskArtifactUpdateEvent` + `last_chunk` | 5 | `flight_agent.py`, `weather_agent.py` |
| `FilePart` (inline bytes) | 6 | `hotel_agent.py` |
| `DataPart` structured output | 3, 6 | `hotel_agent.py` |
| `input-required` state | 7 | `booking_agent.py` |
| Multi-turn task resumption (`task_id` in `Message`) | 7 | `client/main.py` |
| `sessionId` / `context_id` | 7 | `booking_agent.py` |
| `stateTransitionHistory` | 4, 7 | `booking_agent.py` |
| Push notifications (`pushNotification/set`) | 8 | `booking_agent.py` |
| `PushNotificationConfig` + token validation | 8 | `webhook_receiver.py` |
| JSON-RPC error codes | 10 | `client/main.py` |
| `failed` task state | 10 | `client/main.py` |
| Multi-agent orchestration | 11 | `travel_orchestrator.py` |
| Parallel fan-out (`asyncio.gather`) | 11 | `travel_orchestrator.py` |
| Dynamic agent discovery | 11 | `travel_orchestrator.py` |

---

## Quick Start

### Option A — Run agents directly (recommended for development)

```bash
# 1. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Start each agent in a separate terminal
python agents/flight_agent.py    # Terminal 1 — port 8001
python agents/hotel_agent.py     # Terminal 2 — port 8002
python agents/booking_agent.py   # Terminal 3 — port 8003
python agents/weather_agent.py   # Terminal 4 — port 8004
python orchestrator/travel_orchestrator.py  # Terminal 5 — port 8010
python client/webhook_receiver.py           # Terminal 6 — port 9000

# 4. Run the tutorial client
python client/main.py
```

### Option B — Docker Compose

```bash
docker-compose up --build
# Then in another terminal:
source .venv/bin/activate
python client/main.py
```

---

## Project Structure

```
a2a/
├── TUTORIAL_PLAN.md            Design document
├── README.md                   This file
├── requirements.txt            Python dependencies
├── .env.example                Environment variable template
├── Dockerfile                  Container image
├── docker-compose.yml          Multi-service launcher
│
├── agents/
│   ├── flight_agent.py         SSE streaming + Bearer auth       (port 8001)
│   ├── hotel_agent.py          Sync + multimodal PDF + API key   (port 8002)
│   ├── booking_agent.py        Input-required + push notifs      (port 8003)
│   └── weather_agent.py        SSE streaming                     (port 8004)
│
├── orchestrator/
│   └── travel_orchestrator.py  Multi-agent orchestrator          (port 8010)
│
├── client/
│   ├── main.py                 Full tutorial runner
│   └── webhook_receiver.py     Push notification handler         (port 9000)
│
└── samples/
    └── hotel_brochure.txt      Sample hotel brochure (Section 6)
```

---

## Verifying Each Section Manually

### Section 2 — Agent Card
```bash
curl http://localhost:8004/.well-known/agent.json | python3 -m json.tool
```

### Section 3 — Basic Task (Hotel Agent)
```bash
curl -s -X POST http://localhost:8002/ \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: hotel-api-key-12345" \
  -d '{
    "jsonrpc": "2.0", "id": "1", "method": "message/send",
    "params": {
      "message": {
        "role": "user", "messageId": "msg-1",
        "parts": [{"kind": "text", "text": "Hotels in Paris"}]
      }
    }
  }' | python3 -m json.tool
```

### Section 5 — SSE Streaming (Weather Agent)
```bash
curl -s -N -X POST http://localhost:8004/ \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0", "id": "1", "method": "message/stream",
    "params": {
      "message": {
        "role": "user", "messageId": "msg-2",
        "parts": [{"kind": "text", "text": "Weather in Tokyo"}]
      }
    }
  }'
```

### Section 9 — Auth failure (wrong token)
```bash
curl -s -X POST http://localhost:8001/ \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer wrong-token" \
  -d '{
    "jsonrpc": "2.0", "id": "1", "method": "message/send",
    "params": {
      "message": {
        "role": "user", "messageId": "msg-3",
        "parts": [{"kind": "text", "text": "flights NYC to London"}]
      }
    }
  }' | python3 -m json.tool
```

---

## Tutorial Sections Reference

| # | Title | Key Concept | Agent |
|---|---|---|---|
| 1 | Introduction | What is A2A? | — |
| 2 | Agent Cards | `/.well-known/agent.json` discovery | All |
| 3 | Basic Tasks | `message/send`, TextPart, DataPart | Hotel |
| 4 | Task Lifecycle | states, `tasks/get`, `tasks/cancel` | Weather |
| 5 | Streaming | `message/stream`, SSE events | Flight, Weather |
| 6 | Multimodal | FilePart (PDF), DataPart | Hotel |
| 7 | Input Required | `input-required` state, multi-turn | Booking |
| 8 | Push Notifications | webhooks, `pushNotification/set` | Booking |
| 9 | Authentication | Bearer token, API key | Flight, Hotel |
| 10 | Error Handling | failed state, JSON-RPC errors, retry | All |
| 11 | Orchestration | fan-out, parallel dispatch | Orchestrator |
| 12 | Full System | everything together | All |

---

## Port Reference

| Service | Port | Auth |
|---|---|---|
| Flight Agent | 8001 | `Authorization: Bearer flight-secret-token` |
| Hotel Agent | 8002 | `X-Api-Key: hotel-api-key-12345` |
| Booking Agent | 8003 | None |
| Weather Agent | 8004 | None |
| Travel Orchestrator | 8010 | None |
| Webhook Receiver | 9000 | Token: `webhook-secret-token` |
