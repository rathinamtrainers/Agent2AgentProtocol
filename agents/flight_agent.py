"""
agents/flight_agent.py
======================
Section 2 (Agent Cards) + Section 5 (SSE Streaming) + Section 9 (Bearer Auth)

Demonstrates:
- AgentCard with skills, capabilities.streaming=True, Bearer security scheme
- Streaming results via TaskArtifactUpdateEvent with append + last_chunk flags
- Bearer token validation from request headers
- Task lifecycle: submitted -> working -> completed (or failed on bad auth)

Run:
    python agents/flight_agent.py
Endpoint: http://localhost:8001
Auth:     Authorization: Bearer flight-secret-token
"""

import asyncio
import logging
from datetime import datetime, timezone
from uuid import uuid4

import uvicorn
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
    HTTPAuthSecurityScheme,
    Message,
    Part,
    Role,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
    TextPart,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── Auth ──────────────────────────────────────────────────────────────────────
VALID_TOKEN = "flight-secret-token"

# ── Mock flight data ──────────────────────────────────────────────────────────
MOCK_FLIGHTS = [
    {
        "flight_id": "FL001",
        "airline": "British Airways",
        "iata_code": "BA117",
        "origin": "JFK",
        "destination": "LHR",
        "departure": "2026-03-15T08:00:00Z",
        "arrival": "2026-03-15T20:00:00Z",
        "duration_h": 7.0,
        "price_usd": 850,
        "seats_available": 14,
        "class": "economy",
    },
    {
        "flight_id": "FL002",
        "airline": "American Airlines",
        "iata_code": "AA101",
        "origin": "JFK",
        "destination": "LHR",
        "departure": "2026-03-15T11:30:00Z",
        "arrival": "2026-03-15T23:45:00Z",
        "duration_h": 7.25,
        "price_usd": 780,
        "seats_available": 6,
        "class": "economy",
    },
    {
        "flight_id": "FL003",
        "airline": "Air France",
        "iata_code": "AF006",
        "origin": "JFK",
        "destination": "CDG",
        "departure": "2026-03-15T22:00:00Z",
        "arrival": "2026-03-16T11:30:00Z",
        "duration_h": 7.5,
        "price_usd": 920,
        "seats_available": 22,
        "class": "economy",
    },
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Agent Executor ────────────────────────────────────────────────────────────
class FlightAgentExecutor(AgentExecutor):
    """
    Handles flight search tasks.

    Section 5 — Streaming:
        Each flight is emitted as a separate TaskArtifactUpdateEvent chunk.
        The first chunk has append=False; subsequent chunks have append=True.
        The final chunk has last_chunk=True.

    Section 9 — Bearer Auth:
        Reads the Authorization header from the request context and validates
        the Bearer token before processing any request.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id
        context_id = context.context_id

        # ── Section 9: Validate Bearer token ──────────────────────────────────
        headers: dict = {}
        if context.call_context:
            headers = context.call_context.state.get("headers", {})

        auth_header = headers.get("authorization", "")
        token = auth_header.removeprefix("Bearer ").strip()

        if token != VALID_TOKEN:
            logger.warning("Unauthorized request to flight agent")
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(
                        state=TaskState.failed,
                        timestamp=_now(),
                        message=Message(
                            message_id=str(uuid4()),
                            role=Role.agent,
                            parts=[
                                Part(
                                    root=TextPart(
                                        text="Unauthorized: invalid or missing Bearer token. "
                                        "Use 'Authorization: Bearer flight-secret-token'."
                                    )
                                )
                            ],
                        ),
                    ),
                    final=True,
                )
            )
            return

        # ── Section 4: submitted ───────────────────────────────────────────────
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.submitted, timestamp=_now()),
                final=False,
            )
        )

        # ── Section 4: working ────────────────────────────────────────────────
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.working, timestamp=_now()),
                final=False,
            )
        )

        user_query = context.get_user_input()
        logger.info("Flight search query: %s", user_query)

        # ── Section 5: Stream one flight at a time ────────────────────────────
        for i, flight in enumerate(MOCK_FLIGHTS):
            await asyncio.sleep(0.5)  # simulate work per flight
            is_last = i == len(MOCK_FLIGHTS) - 1

            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    artifact=Artifact(
                        artifact_id=str(uuid4()),
                        name="flight_results",
                        description="Streaming flight search results",
                        parts=[Part(root=DataPart(data=flight))],
                    ),
                    append=(i > 0),       # first chunk: append=False
                    last_chunk=is_last,   # last chunk signals stream end
                )
            )

        # ── Section 4: completed ──────────────────────────────────────────────
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
    """
    Section 2 — Agent Cards

    The Agent Card is served at /.well-known/agent.json and describes:
    - What this agent does (name, description)
    - How to reach it (url, version)
    - What it can do (skills with inputModes/outputModes)
    - What protocol features it supports (capabilities)
    - How to authenticate (security_schemes)
    """
    return AgentCard(
        name="Flight Search Agent",
        description=(
            "Searches for available flights between two cities, "
            "streaming results one flight at a time."
        ),
        url="http://localhost:8001/",
        version="1.0.0",
        # Section 5: streaming=True tells clients this agent supports SSE
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        # Section 9: Declare Bearer token requirement so clients can discover it
        security_schemes={
            "bearerAuth": HTTPAuthSecurityScheme(
                type="http",
                scheme="bearer",
                description=(
                    "Bearer token required. "
                    "Use 'flight-secret-token' for this tutorial."
                ),
            )
        },
        skills=[
            AgentSkill(
                id="search_flights",
                name="Search Flights",
                description=(
                    "Search for available flights given origin, destination, "
                    "and travel date. Returns results as a streaming artifact."
                ),
                tags=["flights", "travel", "search"],
                examples=[
                    "Find flights from New York to London on 2026-03-15",
                    "Search flights LHR to CDG tomorrow",
                    "Cheap flights NYC to PAR next week",
                ],
                input_modes=["text/plain"],
                output_modes=["application/json"],
            ),
            AgentSkill(
                id="get_flight_details",
                name="Get Flight Details",
                description="Retrieve detailed information about a specific flight by ID.",
                tags=["flights", "details"],
                examples=["Get details for flight FL001"],
                input_modes=["text/plain"],
                output_modes=["application/json"],
            ),
        ],
    )


# ── App factory ───────────────────────────────────────────────────────────────
def create_app():
    agent_card = build_agent_card()
    handler = DefaultRequestHandler(
        agent_executor=FlightAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    return A2AFastAPIApplication(agent_card=agent_card, http_handler=handler).build()


app = create_app()

if __name__ == "__main__":
    logger.info("Starting Flight Agent on http://localhost:8001")
    logger.info("Auth: Authorization: Bearer %s", VALID_TOKEN)
    uvicorn.run(app, host="0.0.0.0", port=8001, log_level="warning")
