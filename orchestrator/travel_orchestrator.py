"""
orchestrator/travel_orchestrator.py
====================================
Section 11 — Multi-Agent Orchestration

Demonstrates:
- Using A2AClient inside an AgentExecutor to call remote A2A agents
- Dynamic agent discovery via fetching Agent Cards from known URLs
- Parallel fan-out using asyncio.gather to dispatch simultaneous tasks
- Sequential task dependency (booking handled after flight+hotel data are available)
- Result aggregation from heterogeneous agents (sync, streaming)
- Exposing the orchestrator itself as an A2A server

Run:
    python orchestrator/travel_orchestrator.py
Endpoint: http://localhost:8010
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

import httpx
import uvicorn
from a2a.client import A2ACardResolver, A2AClient
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Artifact,
    DataPart,
    Message,
    MessageSendParams,
    Part,
    Role,
    SendMessageRequest,
    SendStreamingMessageRequest,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Agent registry ────────────────────────────────────────────────────────────
AGENT_URLS = {
    "flight": "http://localhost:8001",
    "hotel": "http://localhost:8002",
    "weather": "http://localhost:8004",
}
FLIGHT_TOKEN = "flight-secret-token"
HOTEL_API_KEY = "hotel-api-key-12345"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _user_msg(text: str) -> Message:
    return Message(
        message_id=str(uuid4()),
        role=Role.user,
        parts=[Part(root=TextPart(text=text))],
    )


# ── Section 11: Per-agent helper coroutines ───────────────────────────────────

async def discover_agent(name: str, url: str, headers: dict) -> tuple[str, AgentCard | None]:
    """Fetch an Agent Card from a remote agent (Section 2 — Agent Cards)."""
    try:
        async with httpx.AsyncClient(headers=headers, timeout=5.0) as http_client:
            resolver = A2ACardResolver(http_client, url)
            card = await resolver.get_agent_card()
            return name, card
    except Exception as exc:
        logger.warning("Could not discover agent '%s' at %s: %s", name, url, exc)
        return name, None


async def call_flight_agent(query: str) -> list[dict]:
    """
    Call the Flight Agent using SSE streaming (Section 5).
    Collects all DataPart chunks and returns a list of flight dicts.
    """
    results: list[dict] = []
    try:
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {FLIGHT_TOKEN}"}, timeout=30.0
        ) as http_client:
            resolver = A2ACardResolver(http_client, AGENT_URLS["flight"])
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            req = SendStreamingMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=_user_msg(query)),
            )
            async for resp in client.send_message_streaming(req):
                result = resp.root.result
                if isinstance(result, TaskArtifactUpdateEvent):
                    for part in result.artifact.parts:
                        if isinstance(part.root, DataPart):
                            results.append(part.root.data)
    except Exception as exc:
        logger.warning("Flight agent call failed: %s", exc)
    return results


async def call_hotel_agent(query: str) -> list[dict]:
    """
    Call the Hotel Agent synchronously (Section 3).
    Returns a list of hotel dicts from the DataPart artifact.
    """
    try:
        async with httpx.AsyncClient(
            headers={"X-Api-Key": HOTEL_API_KEY}, timeout=15.0
        ) as http_client:
            resolver = A2ACardResolver(http_client, AGENT_URLS["hotel"])
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            req = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=_user_msg(query)),
            )
            response = await client.send_message(req)
            task = response.root.result

            if hasattr(task, "artifacts") and task.artifacts:
                for part in task.artifacts[0].parts:
                    if isinstance(part.root, DataPart):
                        data = part.root.data
                        if isinstance(data, dict) and "hotels" in data:
                            return data["hotels"]
                        return data if isinstance(data, list) else [data]
    except Exception as exc:
        logger.warning("Hotel agent call failed: %s", exc)
    return []


async def call_weather_agent(city: str) -> list[dict]:
    """
    Call the Weather Agent using SSE streaming (Section 5).
    Collects all daily forecast DataParts and returns them as a list.
    """
    results: list[dict] = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            resolver = A2ACardResolver(http_client, AGENT_URLS["weather"])
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            req = SendStreamingMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message=_user_msg(f"Weather forecast for {city}")
                ),
            )
            async for resp in client.send_message_streaming(req):
                result = resp.root.result
                if isinstance(result, TaskArtifactUpdateEvent):
                    for part in result.artifact.parts:
                        if isinstance(part.root, DataPart):
                            results.append(part.root.data)
    except Exception as exc:
        logger.warning("Weather agent call failed: %s", exc)
    return results


def _extract_city(user_input: str) -> str:
    """Simple heuristic to extract destination city from a travel request."""
    lower = user_input.lower()
    for kw in ["to ", "in ", "for ", "visit "]:
        if kw in lower:
            candidate = lower.split(kw, 1)[-1].strip().split()[0]
            return candidate.rstrip(".,!?").title()
    # Fall back to last capitalised word or 'Paris'
    words = user_input.split()
    for word in reversed(words):
        if word[0].isupper():
            return word.rstrip(".,!?")
    return "Paris"


# ── Agent Executor ────────────────────────────────────────────────────────────
class TravelOrchestratorExecutor(AgentExecutor):
    """
    Section 11 — Multi-Agent Orchestration

    1. Receives a natural-language travel request.
    2. Discovers all specialist agents by fetching their Agent Cards.
    3. Dispatches flight, hotel, and weather queries in parallel.
    4. Aggregates results into a unified travel plan.
    5. Emits the plan as a streaming artifact.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id
        context_id = context.context_id

        # Section 4: submitted
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.submitted, timestamp=_now()),
                final=False,
            )
        )

        user_input = context.get_user_input().strip() or "Plan a trip to Paris"
        city = _extract_city(user_input)
        logger.info("Orchestrator received: '%s' (city=%s)", user_input, city)

        # Section 4: working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.working, timestamp=_now()),
                final=False,
            )
        )

        # ── Step 1: Discover agents in parallel (Section 2 — Agent Cards) ──────
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                artifact=Artifact(
                    artifact_id=str(uuid4()),
                    name="orchestration_log",
                    parts=[Part(root=TextPart(
                        text=f"[1/4] Discovering specialist agents for trip to {city}..."
                    ))],
                ),
                append=False,
                last_chunk=False,
            )
        )

        discover_tasks = [
            discover_agent("flight", AGENT_URLS["flight"], {"Authorization": f"Bearer {FLIGHT_TOKEN}"}),
            discover_agent("hotel", AGENT_URLS["hotel"], {"X-Api-Key": HOTEL_API_KEY}),
            discover_agent("weather", AGENT_URLS["weather"], {}),
        ]
        discovery_results = await asyncio.gather(*discover_tasks, return_exceptions=True)
        discovered = {}
        for res in discovery_results:
            if isinstance(res, tuple):
                name, card = res
                discovered[name] = card
                status = f"✓ {card.name}" if card else "✗ unreachable"
                logger.info("Agent '%s': %s", name, status)

        # ── Step 2: Parallel fan-out to all specialist agents ──────────────────
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                artifact=Artifact(
                    artifact_id=str(uuid4()),
                    name="orchestration_log",
                    parts=[Part(root=TextPart(
                        text="[2/4] Dispatching parallel requests: flights, hotels, weather..."
                    ))],
                ),
                append=True,
                last_chunk=False,
            )
        )

        flight_results, hotel_results, weather_results = await asyncio.gather(
            call_flight_agent(f"Find flights from New York to {city} on 2026-03-15"),
            call_hotel_agent(f"Hotels in {city}"),
            call_weather_agent(city),
            return_exceptions=True,
        )

        # Normalise exception results to empty lists
        if isinstance(flight_results, Exception):
            logger.warning("Flight agent error: %s", flight_results)
            flight_results = []
        if isinstance(hotel_results, Exception):
            logger.warning("Hotel agent error: %s", hotel_results)
            hotel_results = []
        if isinstance(weather_results, Exception):
            logger.warning("Weather agent error: %s", weather_results)
            weather_results = []

        # ── Step 3: Aggregate results ──────────────────────────────────────────
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                artifact=Artifact(
                    artifact_id=str(uuid4()),
                    name="orchestration_log",
                    parts=[Part(root=TextPart(
                        text=(
                            f"[3/4] Aggregating results: "
                            f"{len(flight_results)} flights, "
                            f"{len(hotel_results)} hotels, "
                            f"{len(weather_results)} weather days."
                        )
                    ))],
                ),
                append=True,
                last_chunk=False,
            )
        )

        travel_plan = {
            "destination": city,
            "original_request": user_input,
            "generated_at": _now(),
            "agents_used": list(discovered.keys()),
            "summary": (
                f"Found {len(flight_results)} flight(s), "
                f"{len(hotel_results)} hotel(s), "
                f"and a {len(weather_results)}-day weather forecast for {city}."
            ),
            "flights": flight_results,
            "hotels": hotel_results,
            "weather_forecast": weather_results,
        }

        # ── Step 4: Emit final travel plan artifact ────────────────────────────
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                artifact=Artifact(
                    artifact_id=str(uuid4()),
                    name="travel_plan",
                    description=f"Complete travel plan for {city}",
                    parts=[Part(root=DataPart(data=travel_plan))],
                ),
                append=False,
                last_chunk=True,
            )
        )

        logger.info("Travel plan generated for %s", city)

        # Section 4: completed
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.completed, timestamp=_now()),
                final=True,
            )
        )

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=context.task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.canceled, timestamp=_now()),
                final=True,
            )
        )


# ── Section 2: Agent Card ─────────────────────────────────────────────────────
def build_agent_card() -> AgentCard:
    return AgentCard(
        name="Travel Orchestrator",
        description=(
            "Coordinates flight search, hotel search, and weather forecast agents "
            "to produce a complete travel plan from a single natural-language request."
        ),
        url="http://localhost:8010/",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id="plan_travel",
                name="Plan Travel",
                description=(
                    "Create a complete travel plan by coordinating specialist agents. "
                    "Streams orchestration progress, then returns a full plan with "
                    "flights, hotels, and weather."
                ),
                tags=["orchestration", "travel", "planning", "multi-agent"],
                input_modes=["text/plain"],
                output_modes=["application/json"],
                examples=[
                    "Plan a 5-day trip to Paris",
                    "I want to travel from NYC to London next month",
                    "Help me plan a trip to Tokyo",
                ],
            )
        ],
    )


def create_app():
    agent_card = build_agent_card()
    handler = DefaultRequestHandler(
        agent_executor=TravelOrchestratorExecutor(),
        task_store=InMemoryTaskStore(),
    )
    return A2AFastAPIApplication(agent_card=agent_card, http_handler=handler).build()


app = create_app()

if __name__ == "__main__":
    logger.info("Starting Travel Orchestrator on http://localhost:8010")
    logger.info("Coordinates: flight (:8001), hotel (:8002), weather (:8004)")
    uvicorn.run(app, host="0.0.0.0", port=8010, log_level="warning")
