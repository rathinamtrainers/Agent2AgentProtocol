"""
agents/booking_agent.py
=======================
Section 7 (Input Required / Human-in-the-Loop) + Section 8 (Push Notifications)

Demonstrates:
- AgentCard with push_notifications=True and state_transition_history=True
- input-required state: agent pauses and asks a clarifying question
- Multi-turn conversation: client resumes the SAME task by reusing task_id
  in the Message.task_id field
- Task state machine: submitted -> working -> input-required (x3) -> completed
- Push notification support via InMemoryPushNotificationConfigStore
- In-memory session state keyed by task_id to track conversation step

Run:
    python agents/booking_agent.py
Endpoint: http://localhost:8003
"""

import logging
from datetime import datetime, timezone
from uuid import uuid4

import uvicorn
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AFastAPIApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryPushNotificationConfigStore, InMemoryTaskStore
from a2a.types import (
    AgentCapabilities,
    AgentCard,
    AgentSkill,
    Artifact,
    DataPart,
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

# Resolve the input-required TaskState value safely
INPUT_REQUIRED = next(s for s in TaskState if s.value == "input-required")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _agent_message(text: str) -> Message:
    """Helper to create an agent Message containing a single TextPart."""
    return Message(
        message_id=str(uuid4()),
        role=Role.agent,
        parts=[Part(root=TextPart(text=text))],
    )


# ── In-memory session state ───────────────────────────────────────────────────
# Keyed by task_id. Each session tracks conversation step and collected answers.
#
# Section 7 — Multi-turn conversation steps:
#   Step 0  (no session yet): Initial booking request → ask for seat class
#   Step 1  (session exists): Answer was seat class → ask for meal preference
#   Step 2  (session exists): Answer was meal preference → ask for loyalty number
#   Step 3  (session exists): Answer was loyalty number → complete booking
booking_sessions: dict[str, dict] = {}


# ── Agent Executor ────────────────────────────────────────────────────────────
class BookingAgentExecutor(AgentExecutor):
    """
    Multi-turn booking agent.

    Section 7 — Input Required:
        When the agent needs more information it emits a TaskStatusUpdateEvent
        with state=input-required. The status.message contains the question.
        The client detects this state and sends a follow-up message to
        message/send using the SAME task_id embedded in Message.task_id.

    Section 8 — Push Notifications:
        InMemoryPushNotificationConfigStore is passed to DefaultRequestHandler
        so clients can register webhooks via tasks/pushNotificationConfig/set.
        When the task completes, the server delivers a POST to the webhook URL.
    """

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id
        context_id = context.context_id
        user_input = context.get_user_input().strip()

        # Section 4: submitted
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.submitted, timestamp=_now()),
                final=False,
            )
        )

        # Section 4: working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.working, timestamp=_now()),
                final=False,
            )
        )

        session = booking_sessions.get(task_id)

        # ── Step 0: First message — ask for seat class ─────────────────────────
        if session is None:
            logger.info("[task %s] Step 0: New booking — asking for seat class", task_id)
            booking_sessions[task_id] = {"step": 1, "data": {"request": user_input}}

            # Section 7: Emit input-required — agent needs more info
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(
                        state=INPUT_REQUIRED,
                        timestamp=_now(),
                        message=_agent_message(
                            "What seat class would you prefer?\n"
                            "Options: economy / business / first"
                        ),
                    ),
                    final=True,  # final=True ends this execution turn
                )
            )
            return

        # ── Step 1: Received seat class — ask for meal preference ──────────────
        if session["step"] == 1:
            logger.info("[task %s] Step 1: Got seat class '%s'", task_id, user_input)
            session["data"]["seat_class"] = user_input
            session["step"] = 2

            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(
                        state=INPUT_REQUIRED,
                        timestamp=_now(),
                        message=_agent_message(
                            "What is your meal preference?\n"
                            "Options: standard / vegetarian / vegan / halal / kosher"
                        ),
                    ),
                    final=True,
                )
            )
            return

        # ── Step 2: Received meal preference — ask for loyalty number ──────────
        if session["step"] == 2:
            logger.info("[task %s] Step 2: Got meal preference '%s'", task_id, user_input)
            session["data"]["meal_preference"] = user_input
            session["step"] = 3

            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(
                        state=INPUT_REQUIRED,
                        timestamp=_now(),
                        message=_agent_message(
                            "Please provide your airline loyalty program number "
                            "(or type 'none' to skip):"
                        ),
                    ),
                    final=True,
                )
            )
            return

        # ── Step 3: Received loyalty number — complete booking ─────────────────
        if session["step"] == 3:
            logger.info("[task %s] Step 3: Got loyalty number '%s'", task_id, user_input)
            session["data"]["loyalty_number"] = user_input
            data = session["data"]

            booking_ref = f"BK{uuid4().hex[:8].upper()}"
            confirmation = {
                "booking_ref": booking_ref,
                "status": "confirmed",
                "original_request": data.get("request", ""),
                "seat_class": data.get("seat_class", "economy"),
                "meal_preference": data.get("meal_preference", "standard"),
                "loyalty_number": data.get("loyalty_number", "none"),
                "confirmation_message": (
                    f"Booking {booking_ref} confirmed! "
                    f"Your {data.get('seat_class','economy')} seat with "
                    f"{data.get('meal_preference','standard')} meal has been reserved."
                ),
                "confirmed_at": _now(),
            }

            # Emit artifact with booking confirmation
            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    artifact=Artifact(
                        artifact_id=str(uuid4()),
                        name="booking_confirmation",
                        description="Booking confirmation details",
                        parts=[Part(root=DataPart(data=confirmation))],
                    ),
                    append=False,
                    last_chunk=True,
                )
            )

            # Section 4: completed
            await event_queue.enqueue_event(
                TaskStatusUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    status=TaskStatus(state=TaskState.completed, timestamp=_now()),
                    final=True,
                )
            )

            # Clean up session
            del booking_sessions[task_id]
            logger.info("[task %s] Booking complete: %s", task_id, booking_ref)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        task_id = context.task_id
        # Clean up any in-progress session
        booking_sessions.pop(task_id, None)
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context.context_id,
                status=TaskStatus(state=TaskState.canceled, timestamp=_now()),
                final=True,
            )
        )


# ── Section 2: Agent Card ─────────────────────────────────────────────────────
def build_agent_card() -> AgentCard:
    return AgentCard(
        name="Booking Agent",
        description=(
            "Books flights and hotels using a multi-turn conversation. "
            "Asks for seat class, meal preference, and loyalty number before confirming."
        ),
        url="http://localhost:8003/",
        version="1.0.0",
        capabilities=AgentCapabilities(
            streaming=False,
            push_notifications=True,       # Section 8: supports push notifications
            state_transition_history=True, # Section 4: exposes full state history
        ),
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id="book_travel",
                name="Book Travel",
                description=(
                    "Book a flight and hotel package. Engages in a 3-step conversation "
                    "to collect seat class, meal preference, and loyalty number, "
                    "then returns a booking confirmation."
                ),
                tags=["booking", "reservation", "travel", "multi-turn"],
                input_modes=["text/plain"],
                output_modes=["application/json"],
                examples=[
                    "Book flight FL001 and hotel H001 in Paris",
                    "I want to book a trip to London",
                    "Reserve a business class seat to Tokyo",
                ],
            )
        ],
    )


def create_app():
    agent_card = build_agent_card()
    handler = DefaultRequestHandler(
        agent_executor=BookingAgentExecutor(),
        task_store=InMemoryTaskStore(),
        # Section 8: Push notification store enables tasks/pushNotificationConfig/set
        push_config_store=InMemoryPushNotificationConfigStore(),
    )
    return A2AFastAPIApplication(agent_card=agent_card, http_handler=handler).build()


app = create_app()

if __name__ == "__main__":
    logger.info("Starting Booking Agent on http://localhost:8003")
    logger.info("Supports: input-required multi-turn + push notifications")
    uvicorn.run(app, host="0.0.0.0", port=8003, log_level="warning")
