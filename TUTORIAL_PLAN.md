# Tutorial Plan: Agent-to-Agent (A2A) Protocol with Google ADK

**A single, end-to-end tutorial that covers every A2A feature**

---

## What We Build

A **Travel Planning Multi-Agent System** — one orchestrator agent that
coordinates four specialist agents. The scenario naturally exercises every A2A
protocol feature in a realistic context.

```
User
 └── Travel Orchestrator (ADK LlmAgent + A2A Client)
       ├── Flight Agent    — sync tasks, streaming, auth (Bearer)
       ├── Hotel Agent     — sync tasks, multimodal (PDF), auth (API Key)
       ├── Booking Agent   — input-required, push notifications
       └── Weather Agent   — streaming SSE
```

---

## Prerequisites

- Python 3.11+
- `google-adk`, `a2a-sdk`, `fastapi`, `uvicorn`, `httpx`, `httpx-sse`
- A Gemini API key

---

## Project Structure

```
a2a_tutorial/
├── agents/
│   ├── flight_agent.py       # Streaming + Bearer auth
│   ├── hotel_agent.py        # Sync + multimodal PDF + API key auth
│   ├── booking_agent.py      # Input-required + push notifications
│   └── weather_agent.py      # SSE streaming
├── orchestrator/
│   └── travel_orchestrator.py
├── client/
│   ├── main.py               # Entry point — runs the full scenario
│   └── webhook_receiver.py   # FastAPI server for push notifications
├── samples/
│   └── hotel_brochure.pdf
├── docker-compose.yml
├── pyproject.toml
└── README.md
```

---

## Tutorial Sections

---

### Section 1 — What Is A2A and Why Does It Matter

**Concept:** The interoperability problem. Before A2A, every multi-agent system
required custom glue code. A2A is an open HTTP-based standard so any compliant
agent — regardless of framework (ADK, LangChain, CrewAI, AutoGen) — can
communicate with any other.

**Covers:**
- The A2A protocol overview
- How ADK implements A2A (`A2AServer`, `A2AClient`)
- Relationship between ADK agents and A2A endpoints

---

### Section 2 — Agent Cards: How Agents Advertise Themselves

**Concept:** Every A2A agent serves a machine-readable JSON document at
`/.well-known/agent.json` called an **Agent Card**. Clients fetch this to
discover what an agent can do before sending any task.

**We build:** All four agents with explicit Agent Cards.

**Agent Card fields demonstrated:**

| Field | Where shown |
|---|---|
| `name`, `description`, `url`, `version` | All agents |
| `skills[].id`, `.name`, `.description` | All agents |
| `skills[].inputModes`, `.outputModes` | Hotel (PDF), Booking |
| `skills[].tags`, `.examples` | Flight, Weather |
| `capabilities.streaming` | Flight, Weather |
| `capabilities.pushNotifications` | Booking |
| `capabilities.stateTransitionHistory` | Booking |
| `authentication` (Bearer) | Flight |
| `authentication` (ApiKey) | Hotel |
| `defaultInputModes`, `defaultOutputModes` | All agents |

**Code walkthrough:** How ADK generates and customizes the Agent Card.
How to fetch and inspect a card from a running agent:

```python
import httpx
card = httpx.get("http://localhost:8001/.well-known/agent.json").json()
print(card["skills"])
```

---

### Section 3 — Tasks: The Core Unit of Work

**Concept:** Every interaction with an A2A agent is a **Task**. A client creates
a task by sending a `Message` to `tasks/send`. The agent returns a `Task`
object with `status` and optional `artifacts`.

**We build:** `hotel_agent.py` — synchronous hotel search.

**A2A objects demonstrated:**

- `TaskSendParams`: `id` (client-generated UUID), `message`, `sessionId`
- `Message`: `role` (`user` | `agent`), `parts: list[Part]`
- `Part` types:
  - `TextPart` — plain text content
  - `FilePart` — file with `mimeType` + either `bytes` (base64) or `uri`
  - `DataPart` — arbitrary structured JSON
- `Task`: `id`, `sessionId`, `status`, `artifacts`, `history`
- `Artifact`: `name`, `description`, `parts`, `index`, `lastChunk`
- `TaskStatus`: `state`, `message`, `timestamp`

**Code walkthrough:** Sending a text search query, receiving a `DataPart`
artifact with structured hotel results.

```python
task = await client.send_task(
    url="http://localhost:8002",
    payload=TaskSendParams(
        id=str(uuid4()),
        message=Message(role="user", parts=[TextPart(text="Hotels in Paris")])
    )
)
print(task.artifacts[0].parts[0].data)  # structured JSON results
```

---

### Section 4 — Task Lifecycle: States and Transitions

**Concept:** A task moves through a defined state machine. Understanding each
state is essential for robust clients.

**States demonstrated in this tutorial:**

| State | Where triggered |
|---|---|
| `submitted` | All tasks — immediately after `tasks/send` |
| `working` | All agents — while processing |
| `completed` | Normal termination |
| `failed` | Error path (Section 9) |
| `canceled` | Client calls `tasks/cancel` |
| `input-required` | Booking agent (Section 7) |

**We build:** A lifecycle inspector in the client that:
1. Polls `tasks/get` to observe state transitions on a slow task
2. Demonstrates `tasks/cancel` mid-flight
3. Reads `history` to see the state transition log

**Endpoints covered:**
- `tasks/send` — create/resume a task
- `tasks/get` — poll current status
- `tasks/cancel` — request cancellation

```python
# Poll until terminal state
while True:
    task = await client.get_task(TaskIdParams(id=task_id))
    print(f"State: {task.status.state}")
    if task.status.state in ("completed", "failed", "canceled"):
        break
    await asyncio.sleep(1)
```

---

### Section 5 — Streaming with Server-Sent Events (SSE)

**Concept:** For long-running tasks, agents can stream incremental updates back
to the client using Server-Sent Events via `tasks/sendSubscribe`. The client
receives a stream of events rather than waiting for a single response.

**We build:** `flight_agent.py` and `weather_agent.py` — both stream results
incrementally (one flight / one day at a time).

**SSE event types demonstrated:**

| Event | Description |
|---|---|
| `TaskStatusUpdateEvent` | State changes (`submitted` → `working` → `completed`) |
| `TaskArtifactUpdateEvent` | Incremental artifact chunks (`lastChunk: false/true`) |

**Endpoint:** `tasks/sendSubscribe`

```python
async with client.send_task_streaming(url, payload) as stream:
    async for event in stream:
        if isinstance(event, TaskArtifactUpdateEvent):
            print(event.artifact.parts[0].text, end="", flush=True)
            if event.artifact.lastChunk:
                break
        elif isinstance(event, TaskStatusUpdateEvent):
            print(f"\n[Status: {event.status.state}]")
```

**`capabilities.streaming: true`** must be declared in the Agent Card.

---

### Section 6 — Multimodal Content: Files and Structured Data

**Concept:** A2A messages are not limited to text. `FilePart` and `DataPart`
allow agents to exchange images, PDFs, binary files, and structured JSON.

**We build:** `hotel_agent.py` extended — accepts a PDF hotel brochure as input
and returns a structured `DataPart` with extracted amenities.

**`FilePart` variants demonstrated:**

| Variant | Use case | Example |
|---|---|---|
| `bytes` + `mimeType` | Small inline files (images, PDFs) | Passport scan |
| `uri` + `mimeType` | Large hosted files (S3, GCS URLs) | Hotel brochure URL |

**`DataPart` demonstrated:**
- Returning structured JSON results from hotel search
- `inputModes: ["application/pdf"]` declared in Agent Card skill

```python
# Sending a PDF as inline bytes
with open("samples/hotel_brochure.pdf", "rb") as f:
    pdf_bytes = base64.b64encode(f.read()).decode()

task = await client.send_task(url, TaskSendParams(
    id=str(uuid4()),
    message=Message(role="user", parts=[
        TextPart(text="Extract amenities from this brochure"),
        FilePart(file=FileWithBytes(bytes=pdf_bytes, mimeType="application/pdf"))
    ])
))
# Response is a DataPart with structured amenities
amenities = task.artifacts[0].parts[0].data
```

---

### Section 7 — Input Required: Human-in-the-Loop

**Concept:** An agent can pause mid-task and ask the client for more information
by returning `input-required` state. The client resumes the same task by
calling `tasks/send` again with the **same `taskId`**.

**We build:** `booking_agent.py` — a multi-step booking flow that asks for:
1. Preferred seat class (economy / business / first)
2. Meal preference
3. Loyalty program number

Each question causes an `input-required` pause. The client detects the state,
prompts the user, and sends a follow-up.

```python
task_id = str(uuid4())

# Initial request
task = await client.send_task(url, TaskSendParams(id=task_id, message=initial))

while task.status.state == "input-required":
    # Agent's question is in status.message
    question = task.status.message.parts[0].text
    user_answer = input(f"Agent asks: {question}\nYour answer: ")

    # Resume the SAME task by reusing task_id
    task = await client.send_task(url, TaskSendParams(
        id=task_id,
        message=Message(role="user", parts=[TextPart(text=user_answer)])
    ))
```

**`sessionId`** usage: grouping multiple related tasks under one session.

---

### Section 8 — Push Notifications: Fire-and-Forget Async Tasks

**Concept:** For very long-running tasks (price monitoring, batch processing),
the client registers a webhook URL. The agent calls the webhook when the task
completes — the client does not need to poll or hold an open connection.

**We build:**
- `booking_agent.py` extended — supports push notifications for booking
  confirmation (simulates a 10-second delay)
- `webhook_receiver.py` — a FastAPI server that receives and validates the
  incoming push notification

**Endpoints covered:**
- `tasks/pushNotification/set` — register a webhook for a task
- `tasks/pushNotification/get` — retrieve current webhook config

**`PushNotificationConfig` fields:**
- `url` — the webhook endpoint
- `token` — optional secret for HMAC/JWT validation
- `authentication` — optional auth scheme for the webhook call

```python
# 1. Start the task
task = await client.send_task(url, TaskSendParams(id=task_id, message=msg))

# 2. Register webhook — agent will POST here on completion
await client.set_push_notification(url, PushNotificationConfig(
    id=task_id,
    pushNotificationConfig=PushNotificationConfig(
        url="http://localhost:9000/webhook",
        token="my-secret-token"
    )
))

# 3. Client exits — webhook_receiver.py handles the callback
print("Task submitted. Will be notified via webhook.")
```

```python
# webhook_receiver.py (FastAPI)
@app.post("/webhook")
async def receive_notification(task: Task, x_token: str = Header(None)):
    assert x_token == "my-secret-token"
    print(f"Task {task.id} completed: {task.artifacts[0].parts[0].text}")
```

**`capabilities.pushNotifications: true`** must be declared in the Agent Card.

---

### Section 9 — Authentication and Security

**Concept:** Agent Cards declare their authentication requirements. Clients
read these requirements and inject credentials before sending tasks.

**Authentication schemes demonstrated:**

| Scheme | Agent | Mechanism |
|---|---|---|
| HTTP Bearer Token | Flight Agent | `Authorization: Bearer <token>` header |
| API Key | Hotel Agent | `X-Api-Key: <key>` header |

**Server side (ADK middleware):**

```python
# In flight_agent.py — validate Bearer token on every request
async def auth_middleware(request: Request, call_next):
    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if token != VALID_TOKEN:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)
```

**Client side (reading Agent Card → injecting credentials):**

```python
# Read auth requirements from Agent Card
card = await client.get_agent_card("http://localhost:8001")
scheme = card.authentication.schemes[0]  # "bearer"

# Inject credentials
headers = {"Authorization": f"Bearer {os.environ['FLIGHT_API_TOKEN']}"}
task = await client.send_task(url, payload, headers=headers)
```

**Error handling for 401/403:**

```python
try:
    task = await client.send_task(url, payload)
except A2AClientHTTPError as e:
    if e.status_code == 401:
        print("Auth failed — check your credentials")
```

---

### Section 10 — Error Handling and Resilience

**Concept:** Robust A2A clients must handle all error conditions: agent
failures, invalid requests, network issues, and task cancellation.

**A2A JSON-RPC error codes covered:**

| Code | Name | Triggered by |
|---|---|---|
| `-32700` | Parse error | Malformed JSON |
| `-32600` | Invalid request | Missing required fields |
| `-32601` | Method not found | Unknown RPC method |
| `-32602` | Invalid params | Wrong parameter types |
| `-32603` | Internal error | Agent exception |
| `TaskNotFound` | A2A-specific | `tasks/get` with unknown ID |
| `TaskNotCancelable` | A2A-specific | Cancel on completed task |
| `PushNotificationNotSupported` | A2A-specific | Agent lacks capability |
| `UnsupportedOperation` | A2A-specific | Operation not implemented |
| `ContentTypeNotSupported` | A2A-specific | Wrong MIME type in FilePart |

**Patterns demonstrated:**
- Detecting `failed` terminal state and reading `status.message`
- Exponential backoff retry for transient network errors
- Timeout → cancel: set a deadline, then call `tasks/cancel`
- Graceful degradation in the orchestrator when one agent is unavailable

```python
# Retry with exponential backoff
for attempt in range(3):
    try:
        task = await asyncio.wait_for(
            client.send_task(url, payload),
            timeout=10.0
        )
        break
    except asyncio.TimeoutError:
        if attempt == 2:
            await client.cancel_task(url, TaskIdParams(id=task_id))
            raise
        await asyncio.sleep(2 ** attempt)
    except A2AClientJSONError as e:
        print(f"JSON-RPC error {e.error.code}: {e.error.message}")
        raise
```

---

### Section 11 — Multi-Agent Orchestration

**Concept:** The orchestrator is itself an ADK agent that uses `A2AClient` as
a tool to delegate tasks to the specialist agents. It fans out work in parallel,
aggregates results, and returns a unified response to the user.

**We build:** `travel_orchestrator.py` — an `LlmAgent` that:
1. Receives a natural-language travel request
2. Fetches Agent Cards from all known specialist agents
3. Routes subtasks to the right agents based on skill matching
4. Dispatches flight search + hotel search + weather in parallel
5. Sends the booking agent a sequential task (requires confirmation)
6. Aggregates all results into a formatted itinerary

```python
# Parallel fan-out
flight_task, hotel_task, weather_task = await asyncio.gather(
    flight_client.send_task_streaming(...),
    hotel_client.send_task(...),
    weather_client.send_task_streaming(...),
)

# Sequential booking (needs prior flight/hotel data)
booking_task = await booking_client.send_task(
    url=BOOKING_AGENT_URL,
    payload=TaskSendParams(
        id=str(uuid4()),
        message=Message(role="user", parts=[
            TextPart(text=f"Book flight {flight_id} and hotel {hotel_id}")
        ])
    )
)
```

**Demonstrates:**
- `A2AClient` as a tool inside an ADK `LlmAgent`
- Dynamic agent discovery via Agent Card inspection
- Parallel task dispatch with `asyncio.gather`
- Sequential task dependency management
- Result aggregation from heterogeneous response formats

---

### Section 12 — Running the Complete System

**Concept:** Launch all agents and the orchestrator together, run the full
end-to-end scenario, and observe every A2A feature in action.

**Steps:**

1. **Start all agents** via `docker-compose up`
2. **Run the client**: `python client/main.py "Plan a 5-day trip to Paris"`
3. **Observe the full flow:**
   - Agent Card discovery for all four agents
   - Parallel SSE streaming from flight + weather agents
   - Sync + multimodal call to hotel agent (PDF input)
   - `input-required` loop with booking agent
   - Push notification webhook fires when booking confirms

**Port map:**

| Agent | Port | Auth |
|---|---|---|
| Flight Agent | 8001 | Bearer |
| Hotel Agent | 8002 | API Key |
| Booking Agent | 8003 | None |
| Weather Agent | 8004 | None |
| Travel Orchestrator | 8010 | None |
| Webhook Receiver | 9000 | Token |

---

## Complete A2A Feature Coverage

| A2A Feature | Section |
|---|---|
| Agent Card — full schema | 2 |
| `/.well-known/agent.json` discovery | 2 |
| `AgentSkill` with `inputModes`/`outputModes` | 2, 6 |
| `AgentCapabilities` flags | 2 |
| `tasks/send` | 3 |
| `TextPart` | 3 |
| `DataPart` | 3, 6 |
| `FilePart` (inline bytes) | 6 |
| `FilePart` (URI reference) | 6 |
| `Artifact` with `index` and `lastChunk` | 3, 5 |
| `submitted` → `working` → `completed` | 4 |
| `failed` state | 10 |
| `canceled` state | 10 |
| `input-required` state | 7 |
| `tasks/get` (polling) | 4 |
| `tasks/cancel` | 4, 10 |
| `stateTransitionHistory` | 4 |
| `tasks/sendSubscribe` (SSE) | 5 |
| `TaskStatusUpdateEvent` | 5 |
| `TaskArtifactUpdateEvent` | 5 |
| `tasks/pushNotification/set` | 8 |
| `tasks/pushNotification/get` | 8 |
| `PushNotificationConfig` | 8 |
| Multi-turn task resumption | 7 |
| `sessionId` | 7 |
| Bearer token authentication | 9 |
| API Key authentication | 9 |
| JSON-RPC error codes | 10 |
| `TaskNotFound` / `TaskNotCancelable` | 10 |
| `ContentTypeNotSupported` | 10 |
| Retry / timeout / cancellation patterns | 10 |
| Multi-agent orchestration | 11 |
| Parallel task fan-out | 11 |
| Dynamic agent discovery | 11 |
| `A2AClient` as ADK agent tool | 11 |

---

*Tutorial version 1.0 — 2026-02-22*
