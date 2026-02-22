# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A2A (Agent-to-Agent) protocol tutorial: a Travel Planning Multi-Agent System demonstrating every feature of Google's open HTTP-based A2A standard using Google ADK. One orchestrator coordinates four specialist agents, each showcasing different protocol features.

## Running the System

**Setup:**
```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

**Start all services (each in a separate terminal):**
```bash
python agents/flight_agent.py           # Port 8001
python agents/hotel_agent.py            # Port 8002
python agents/booking_agent.py          # Port 8003
python agents/weather_agent.py          # Port 8004
python orchestrator/travel_orchestrator.py  # Port 8010
python client/webhook_receiver.py       # Port 9000
```

**Run the full tutorial client:**
```bash
python client/main.py
```

**Docker alternative:** `docker-compose up --build`, then run `python client/main.py` separately.

**Verify a single agent (agent card discovery):**
```bash
curl http://localhost:8004/.well-known/agent.json | python3 -m json.tool
```

There is no test suite or linter configured. The tutorial client (`client/main.py`) serves as the integration test, exercising all 12 protocol sections sequentially.

## Architecture

```
client/main.py (tutorial runner)
  └── orchestrator/travel_orchestrator.py  :8010
        ├── agents/flight_agent.py    :8001  [SSE streaming, Bearer auth]
        ├── agents/hotel_agent.py     :8002  [sync, multimodal PDF, API key auth]
        ├── agents/booking_agent.py   :8003  [input-required, push notifications]
        └── agents/weather_agent.py   :8004  [SSE streaming]

client/webhook_receiver.py :9000  (push notification handler)
```

**Each agent** is a standalone FastAPI app implementing `AgentExecutor` from `google.adk.agents.a2a`. The executor's `execute()` method receives a `RequestContext` and emits events (`TaskStatusUpdateEvent`, `TaskArtifactUpdateEvent`) via an `EventQueue`. State is managed via `InMemoryTaskStore`.

**The orchestrator** is dual-role: it acts as an A2A agent (server) while also consuming other A2A agents as a client using `A2AClient` from `a2a-sdk`. It fans out requests to specialist agents in parallel via `asyncio.gather()`.

**The client** (`client/main.py`) uses `A2ACardResolver` for agent discovery and `A2AClient` for JSON-RPC calls. It demonstrates every protocol method: `message/send`, `message/stream`, `tasks/get`, `tasks/cancel`, and `tasks/pushNotificationConfig/set`.

## Key A2A Protocol Patterns

- **Agent Cards**: Every agent serves `/.well-known/agent.json` describing skills, capabilities, and security schemes.
- **Task States**: `submitted → working → completed|failed|canceled|input-required`.
- **Streaming**: SSE via `message/stream`. Artifacts use `append=False` for first chunk, `True` for subsequent, `last_chunk=True` for final.
- **Input-Required**: Agent emits `input-required` state; client resumes with same `task_id` in `Message.task_id` (booking agent does a 3-step conversation).
- **Push Notifications**: Client registers webhook via `tasks/pushNotificationConfig/set`; agent POSTs completed task to webhook URL with `X-A2A-Notification-Token` header.
- **Auth**: Flight agent uses Bearer token (`Authorization: Bearer flight-secret-token`), Hotel agent uses API key (`X-Api-Key: hotel-api-key-12345`). Auth is validated from `RequestContext.call_context.state["headers"]`.

## Dependencies

- `google-adk[a2a]` — Google Agent Development Kit with A2A support
- `a2a-sdk` — A2A protocol SDK (provides `A2AClient`, `A2ACardResolver`, task/message models)
- `fastapi` + `uvicorn` — Web framework and ASGI server
- `httpx` + `httpx-sse` — Async HTTP client with SSE support

Python 3.11+ required.

## Conventions

- All agents use mock/simulated data (no real APIs or LLM calls).
- All I/O is async (`asyncio`, `httpx.AsyncClient`).
- Every directory must have a `README.md` explaining its purpose.
