"""
agents/hotel_agent.py
=====================
Section 2 (Agent Cards) + Section 3 (Tasks) + Section 6 (Multimodal) + Section 9 (API Key Auth)

Demonstrates:
- AgentCard with API Key security scheme and multimodal inputModes
- Synchronous task: submitted -> working -> completed in one response
- FilePart handling: detecting PDF input vs plain-text search
- DataPart output: returning structured JSON data as Artifacts
- TextPart + FilePart in the same message (multimodal request)
- API key validation from X-Api-Key request header

Run:
    python agents/hotel_agent.py
Endpoint: http://localhost:8002
Auth:     X-Api-Key: hotel-api-key-12345
"""

import base64
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
    APIKeySecurityScheme,
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Artifact,
    DataPart,
    FilePart,
    In,
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

API_KEY = "hotel-api-key-12345"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Mock hotel data ───────────────────────────────────────────────────────────
_HOTELS = {
    "paris": [
        {"hotel_id": "H001", "name": "Grand Paris Hotel", "city": "Paris", "stars": 5,
         "price_per_night_usd": 320, "amenities": ["WiFi", "Pool", "Spa", "Restaurant"], "available_rooms": 3},
        {"hotel_id": "H002", "name": "Hôtel Lumière", "city": "Paris", "stars": 4,
         "price_per_night_usd": 185, "amenities": ["WiFi", "Gym", "Bar"], "available_rooms": 8},
        {"hotel_id": "H003", "name": "Le Marais Boutique", "city": "Paris", "stars": 3,
         "price_per_night_usd": 110, "amenities": ["WiFi", "Breakfast"], "available_rooms": 15},
    ],
    "london": [
        {"hotel_id": "H011", "name": "The Savoy", "city": "London", "stars": 5,
         "price_per_night_usd": 580, "amenities": ["WiFi", "Pool", "Spa", "Fine Dining"], "available_rooms": 2},
        {"hotel_id": "H012", "name": "City Premier Inn", "city": "London", "stars": 3,
         "price_per_night_usd": 130, "amenities": ["WiFi", "Restaurant"], "available_rooms": 20},
        {"hotel_id": "H013", "name": "Shoreditch Boutique", "city": "London", "stars": 4,
         "price_per_night_usd": 210, "amenities": ["WiFi", "Bar", "Gym"], "available_rooms": 6},
    ],
    "tokyo": [
        {"hotel_id": "H021", "name": "Park Hyatt Tokyo", "city": "Tokyo", "stars": 5,
         "price_per_night_usd": 490, "amenities": ["WiFi", "Pool", "Spa", "Sky Bar"], "available_rooms": 5},
        {"hotel_id": "H022", "name": "Shinjuku Granbell", "city": "Tokyo", "stars": 4,
         "price_per_night_usd": 175, "amenities": ["WiFi", "Gym"], "available_rooms": 12},
        {"hotel_id": "H023", "name": "Asakusa Budget Inn", "city": "Tokyo", "stars": 2,
         "price_per_night_usd": 65, "amenities": ["WiFi"], "available_rooms": 30},
    ],
}
_DEFAULT_HOTELS = [
    {"hotel_id": "H099", "name": "City Central Hotel", "city": "Unknown", "stars": 3,
     "price_per_night_usd": 120, "amenities": ["WiFi", "Breakfast", "Parking"], "available_rooms": 10},
    {"hotel_id": "H098", "name": "Budget Stay", "city": "Unknown", "stars": 2,
     "price_per_night_usd": 75, "amenities": ["WiFi"], "available_rooms": 25},
]

# Result for PDF brochure extraction (Section 6)
_BROCHURE_EXTRACTION = {
    "hotel_name": "Grand Paris Hotel",
    "stars": 5,
    "location": "8th Arrondissement, Paris, France",
    "amenities": [
        "Complimentary High-Speed WiFi",
        "Heated Outdoor Swimming Pool",
        "Full-Service Spa & Wellness Centre",
        "Michelin-starred Restaurant",
        "Rooftop Bar with Eiffel Tower views",
        "24-Hour Fitness Centre",
        "24-Hour Room Service",
        "Valet Parking & Chauffeur Service",
        "Concierge & Multilingual Staff",
        "Business Centre",
        "Laundry & Dry Cleaning Service",
    ],
    "room_types": [
        {"type": "Superior Room", "size_sqm": 32, "price_from_eur": 280},
        {"type": "Deluxe Room with Balcony", "size_sqm": 40, "price_from_eur": 380},
        {"type": "Junior Suite", "size_sqm": 55, "price_from_eur": 520},
        {"type": "Presidential Suite", "size_sqm": 120, "price_from_eur": 1200},
    ],
    "extracted_from": "pdf_brochure",
    "extraction_confidence": 0.97,
}


# ── Agent Executor ────────────────────────────────────────────────────────────
class HotelAgentExecutor(AgentExecutor):
    """
    Handles hotel search tasks (sync) and PDF brochure extraction (multimodal).

    Section 3 — Basic Tasks:
        Demonstrates the simplest A2A task flow: one message in, one artifact out.

    Section 6 — Multimodal:
        Checks for a FilePart in the message. If a PDF is found, it simulates
        extraction of hotel amenities from the brochure bytes.

    Section 9 — API Key Auth:
        Validates the X-Api-Key header before processing any request.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id
        context_id = context.context_id

        # ── Section 9: Validate API key ────────────────────────────────────────
        headers: dict = {}
        if context.call_context:
            headers = context.call_context.state.get("headers", {})

        provided_key = headers.get("x-api-key", "")
        if provided_key != API_KEY:
            logger.warning("Unauthorized request to hotel agent (bad API key)")
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
                                        text="Unauthorized: invalid or missing API key. "
                                        "Add header 'X-Api-Key: hotel-api-key-12345'."
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

        # ── Section 6: Check for FilePart (PDF brochure) ──────────────────────
        result_data = None
        artifact_name = "hotel_results"

        if context.message and context.message.parts:
            for part in context.message.parts:
                if isinstance(part.root, FilePart):
                    file = part.root.file
                    mime = getattr(file, "mime_type", "") or ""
                    if "pdf" in mime.lower():
                        logger.info("Processing PDF brochure (FilePart with bytes)")
                        # In a real agent, you'd parse the PDF bytes here.
                        # We return mock extracted data for the tutorial.
                        result_data = _BROCHURE_EXTRACTION
                        artifact_name = "brochure_extraction"
                        break

        if result_data is None:
            # ── Section 3: Text search ─────────────────────────────────────────
            user_input = context.get_user_input().strip().lower()
            city = "paris"  # default
            for known_city in _HOTELS:
                if known_city in user_input:
                    city = known_city
                    break

            hotels = _HOTELS.get(city, _DEFAULT_HOTELS)
            # Patch city name into default hotels
            if hotels is _DEFAULT_HOTELS:
                for h in hotels:
                    h = dict(h)
                    h["city"] = user_input.title() or "Unknown"
            result_data = hotels
            logger.info("Hotel search for city: %s — found %d hotels", city, len(hotels))

        # ── Emit artifact (DataPart) ──────────────────────────────────────────
        await event_queue.enqueue_event(
            TaskArtifactUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                artifact=Artifact(
                    artifact_id=str(uuid4()),
                    name=artifact_name,
                    description="Hotel search results or brochure extraction",
                    parts=[Part(root=DataPart(data=result_data))],
                ),
                append=False,
                last_chunk=True,
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
    return AgentCard(
        name="Hotel Search Agent",
        description=(
            "Search for hotels by city (returns structured JSON) or extract "
            "amenities from a hotel brochure PDF (multimodal input)."
        ),
        url="http://localhost:8002/",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=False),
        # Section 6: advertise PDF as a supported input mode
        default_input_modes=["text/plain", "application/pdf"],
        default_output_modes=["application/json"],
        # Section 9: API key scheme declaration
        security_schemes={
            "apiKey": APIKeySecurityScheme(
                type="apiKey",
                name="X-Api-Key",
                in_=In.header,
                description=(
                    "API key required. "
                    "Use 'hotel-api-key-12345' for this tutorial."
                ),
            )
        },
        skills=[
            AgentSkill(
                id="search_hotels",
                name="Search Hotels",
                description="Search for available hotels in a city. Returns structured hotel data.",
                tags=["hotels", "accommodation", "search"],
                input_modes=["text/plain"],
                output_modes=["application/json"],
                examples=["Hotels in Paris", "Find me a hotel in Tokyo", "Accommodation in London"],
            ),
            AgentSkill(
                id="extract_brochure",
                name="Extract Hotel Brochure",
                description=(
                    "Extract hotel name, amenities, and room types from a PDF brochure. "
                    "Send a FilePart with mime_type='application/pdf' alongside your text request."
                ),
                tags=["hotels", "multimodal", "pdf", "extraction"],
                input_modes=["text/plain", "application/pdf"],
                output_modes=["application/json"],
                examples=["Extract amenities from this brochure"],
            ),
        ],
    )


def create_app():
    agent_card = build_agent_card()
    handler = DefaultRequestHandler(
        agent_executor=HotelAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    return A2AFastAPIApplication(agent_card=agent_card, http_handler=handler).build()


app = create_app()

if __name__ == "__main__":
    logger.info("Starting Hotel Agent on http://localhost:8002")
    logger.info("Auth: X-Api-Key: %s", API_KEY)
    uvicorn.run(app, host="0.0.0.0", port=8002, log_level="warning")
