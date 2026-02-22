"""
client/main.py
==============
The complete A2A Tutorial Client — demonstrates ALL A2A protocol features.

Run agents first (each in a separate terminal):
    python agents/flight_agent.py
    python agents/hotel_agent.py
    python agents/booking_agent.py
    python agents/weather_agent.py
    python orchestrator/travel_orchestrator.py
    python client/webhook_receiver.py

Then run this script:
    python client/main.py
"""

import asyncio
import base64
import json
import logging
from pathlib import Path
from uuid import uuid4

import httpx
from a2a.client import A2ACardResolver, A2AClient
from a2a.types import (
    CancelTaskRequest,
    DataPart,
    FilePart,
    FileWithBytes,
    GetTaskPushNotificationConfigRequest,
    GetTaskRequest,
    Message,
    MessageSendConfiguration,
    MessageSendParams,
    Part,
    PushNotificationConfig,
    Role,
    SendMessageRequest,
    SendStreamingMessageRequest,
    SetTaskPushNotificationConfigRequest,
    TaskArtifactUpdateEvent,
    TaskIdParams,
    TaskPushNotificationConfig,
    TaskQueryParams,
    TaskState,
    TaskStatusUpdateEvent,
    TextPart,
)

logging.basicConfig(level=logging.WARNING)

# ── Endpoints ─────────────────────────────────────────────────────────────────
FLIGHT_URL = "http://localhost:8001"
HOTEL_URL = "http://localhost:8002"
BOOKING_URL = "http://localhost:8003"
WEATHER_URL = "http://localhost:8004"
ORCHESTRATOR_URL = "http://localhost:8010"
WEBHOOK_URL = "http://localhost:9000"

FLIGHT_TOKEN = "flight-secret-token"
HOTEL_API_KEY = "hotel-api-key-12345"
WEBHOOK_TOKEN = "webhook-secret-token"

SAMPLES_DIR = Path(__file__).parent.parent / "samples"


# ── Formatting helpers ────────────────────────────────────────────────────────
def banner(title: str) -> None:
    print(f"\n{'═'*62}")
    print(f"  {title}")
    print(f"{'═'*62}\n")


def section(num: int, title: str) -> None:
    print(f"\n{'─'*62}")
    print(f"  Section {num}: {title}")
    print(f"{'─'*62}")


def info(msg: str) -> None:
    print(f"  [INFO] {msg}")


def ok(msg: str) -> None:
    print(f"  [ OK ] {msg}")


def warn(msg: str) -> None:
    print(f"  [WARN] {msg}")


def pretty(label: str, data: object) -> None:
    print(f"  {label}:")
    dumped = json.dumps(data, indent=4, default=str) if not isinstance(data, str) else data
    for line in dumped.splitlines():
        print(f"    {line}")


def _user_msg(text: str, task_id: str | None = None, context_id: str | None = None) -> Message:
    return Message(
        message_id=str(uuid4()),
        role=Role.user,
        task_id=task_id,
        context_id=context_id,
        parts=[Part(root=TextPart(text=text))],
    )


# ── Section 2: Agent Card Discovery ──────────────────────────────────────────
async def demo_section2_agent_cards() -> None:
    """
    Section 2 — Agent Cards

    Every A2A agent serves a machine-readable JSON document at
    /.well-known/agent.json. Clients fetch this to discover capabilities
    before sending any task.

    Key fields shown:
    - name, description, url, version
    - skills[].id, skills[].tags, skills[].examples
    - capabilities.streaming, capabilities.push_notifications
    - security_schemes (Bearer, API key)
    """
    section(2, "Agent Cards — Discovery via /.well-known/agent.json")

    agents = [
        ("Flight Agent", FLIGHT_URL, {"Authorization": f"Bearer {FLIGHT_TOKEN}"}),
        ("Hotel Agent", HOTEL_URL, {"X-Api-Key": HOTEL_API_KEY}),
        ("Booking Agent", BOOKING_URL, {}),
        ("Weather Agent", WEATHER_URL, {}),
    ]

    for name, url, headers in agents:
        try:
            async with httpx.AsyncClient(headers=headers, timeout=5.0) as http_client:
                resolver = A2ACardResolver(http_client, url)
                card = await resolver.get_agent_card()

            info(f"{name}: {card.name} v{card.version}")
            info(f"  URL: {card.url}")
            info(f"  Skills: {[s.id for s in (card.skills or [])]}")
            info(f"  Capabilities:")
            info(f"    streaming:          {card.capabilities.streaming}")
            info(f"    push_notifications: {card.capabilities.push_notifications}")
            info(f"    state_history:      {card.capabilities.state_transition_history}")
            if card.security_schemes:
                schemes = list(card.security_schemes.keys())
                info(f"  Security schemes:   {schemes}")
            ok(f"{name} card fetched successfully")
        except Exception as exc:
            warn(f"Could not reach {name} at {url}: {exc}")


# ── Section 3: Basic Synchronous Task ─────────────────────────────────────────
async def demo_section3_basic_task() -> None:
    """
    Section 3 — Basic Tasks

    The simplest A2A interaction: send a Message, receive a completed Task
    with a DataPart Artifact.

    Objects demonstrated:
    - MessageSendParams: wraps the Message
    - Message: role=user, message_id, parts
    - TextPart: plain text content
    - Task: id, context_id, status.state, artifacts
    - Artifact: artifact_id, name, parts
    - DataPart: structured JSON output
    """
    section(3, "Basic Tasks — message/send → completed Task with DataPart artifact")

    try:
        async with httpx.AsyncClient(
            headers={"X-Api-Key": HOTEL_API_KEY}, timeout=15.0
        ) as http_client:
            resolver = A2ACardResolver(http_client, HOTEL_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            msg = _user_msg("Hotels in Paris")
            request = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=msg),
            )

            info("Sending: 'Hotels in Paris' to Hotel Agent")
            response = await client.send_message(request)
            task = response.root.result

            info(f"Task ID:       {task.id}")
            info(f"Context ID:    {task.context_id}")
            info(f"Status state:  {task.status.state.value}")
            info(f"Artifacts:     {len(task.artifacts or [])}")

            if task.artifacts:
                artifact = task.artifacts[0]
                info(f"Artifact name: {artifact.name}")
                for part in artifact.parts:
                    if isinstance(part.root, DataPart):
                        hotels = part.root.data
                        ok(f"Received {len(hotels)} hotels:")
                        for h in hotels[:2]:
                            info(f"  {h['name']} ({h['stars']}★) — ${h['price_per_night_usd']}/night")
    except Exception as exc:
        warn(f"Section 3 demo failed: {exc}")


# ── Section 4: Task Lifecycle ──────────────────────────────────────────────────
async def demo_section4_task_lifecycle() -> None:
    """
    Section 4 — Task Lifecycle

    Demonstrates:
    - tasks/get: poll a task after completion
    - tasks/cancel: cancel an in-flight task
    - stateTransitionHistory from the Task history field

    Task states: submitted → working → completed / canceled / failed
    """
    section(4, "Task Lifecycle — tasks/get polling and tasks/cancel")

    try:
        async with httpx.AsyncClient(
            headers={"X-Api-Key": HOTEL_API_KEY}, timeout=15.0
        ) as http_client:
            resolver = A2ACardResolver(http_client, HOTEL_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            # 4a: Send a task, then retrieve it with tasks/get
            req = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=_user_msg("Hotels in London")),
            )
            resp = await client.send_message(req)
            task = resp.root.result
            task_id = task.id
            ok(f"Task created: {task_id} — state: {task.status.state.value}")

            # Poll with tasks/get
            get_req = GetTaskRequest(
                id=str(uuid4()),
                params=TaskQueryParams(id=task_id, history_length=10),
            )
            get_resp = await client.get_task(get_req)
            fetched_task = get_resp.root.result
            info(f"tasks/get result — state: {fetched_task.status.state.value}")
            if fetched_task.history:
                info(f"History entries: {len(fetched_task.history)}")
                for h_entry in fetched_task.history:
                    info(f"  Role={h_entry.role.value}, parts={len(h_entry.parts)}")

        # 4b: Start a weather task and immediately cancel it
        info("")
        info("Demonstrating tasks/cancel — starting Weather task then canceling:")
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            resolver = A2ACardResolver(http_client, WEATHER_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            # Use non-blocking send for cancel demo
            req = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message=_user_msg("Weather in Paris"),
                    configuration=MessageSendConfiguration(blocking=False),
                ),
            )
            resp = await client.send_message(req)
            task = resp.root.result
            cancel_task_id = task.id
            info(f"Task submitted: {cancel_task_id} — state: {task.status.state.value}")

            # Immediately cancel
            cancel_req = CancelTaskRequest(
                id=str(uuid4()),
                params=TaskIdParams(id=cancel_task_id),
            )
            cancel_resp = await client.cancel_task(cancel_req)
            canceled_task = cancel_resp.root.result
            ok(f"tasks/cancel — new state: {canceled_task.status.state.value}")
    except Exception as exc:
        warn(f"Section 4 demo failed: {exc}")


# ── Section 5: SSE Streaming ──────────────────────────────────────────────────
async def demo_section5_streaming() -> None:
    """
    Section 5 — SSE Streaming

    message/stream returns a Server-Sent Event stream.
    The client receives TaskStatusUpdateEvent and TaskArtifactUpdateEvent
    objects incrementally, without waiting for the full response.

    Key concepts:
    - TaskStatusUpdateEvent: state changes (submitted → working → completed)
    - TaskArtifactUpdateEvent: incremental artifact chunks
    - last_chunk=True: signals the stream is complete
    - append=True: chunks belong to the same logical artifact
    """
    section(5, "SSE Streaming — message/stream with TaskArtifactUpdateEvent chunks")

    # 5a: Weather forecast (7 daily chunks)
    info("Streaming 7-day weather forecast for Tokyo:")
    try:
        async with httpx.AsyncClient(timeout=30.0) as http_client:
            resolver = A2ACardResolver(http_client, WEATHER_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            req = SendStreamingMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=_user_msg("Weather forecast for Tokyo")),
            )
            chunk_count = 0
            async for resp in client.send_message_streaming(req):
                result = resp.root.result
                if isinstance(result, TaskStatusUpdateEvent):
                    info(f"  [Status] {result.status.state.value}")
                elif isinstance(result, TaskArtifactUpdateEvent):
                    chunk_count += 1
                    for part in result.artifact.parts:
                        if isinstance(part.root, DataPart):
                            d = part.root.data
                            info(
                                f"  [Chunk {chunk_count}] {d['date']}: "
                                f"{d['condition']}, {d['high_c']}°C / {d['low_c']}°C"
                                + (" [LAST]" if result.last_chunk else "")
                            )
            ok(f"Received {chunk_count} streaming chunks")
    except Exception as exc:
        warn(f"Weather streaming failed: {exc}")

    # 5b: Flight search (3 flight chunks, requires Bearer auth)
    info("")
    info("Streaming flight search NYC → London (Bearer auth):")
    try:
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {FLIGHT_TOKEN}"}, timeout=30.0
        ) as http_client:
            resolver = A2ACardResolver(http_client, FLIGHT_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            req = SendStreamingMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message=_user_msg("Find flights from New York to London")
                ),
            )
            chunk_count = 0
            async for resp in client.send_message_streaming(req):
                result = resp.root.result
                if isinstance(result, TaskArtifactUpdateEvent):
                    chunk_count += 1
                    for part in result.artifact.parts:
                        if isinstance(part.root, DataPart):
                            f = part.root.data
                            info(
                                f"  [Flight {chunk_count}] {f['airline']} {f['iata_code']} "
                                f"— ${f['price_usd']} ({f['seats_available']} seats)"
                                + (" [LAST]" if result.last_chunk else "")
                            )
            ok(f"Received {chunk_count} flight chunks via SSE")
    except Exception as exc:
        warn(f"Flight streaming failed: {exc}")


# ── Section 6: Multimodal ──────────────────────────────────────────────────────
async def demo_section6_multimodal() -> None:
    """
    Section 6 — Multimodal Content

    FilePart allows sending files (images, PDFs, etc.) as part of a message.
    Two variants:
    - FileWithBytes: inline base64-encoded content
    - FileWithUri: reference to a hosted file URL

    The Hotel Agent accepts a PDF brochure and extracts structured amenity data.
    """
    section(6, "Multimodal — FilePart (PDF bytes) + DataPart response")

    # Read sample brochure (use .txt as a stand-in for a real PDF)
    brochure_path = SAMPLES_DIR / "hotel_brochure.txt"
    if not brochure_path.exists():
        warn(f"Sample brochure not found at {brochure_path} — skipping")
        return

    brochure_bytes = brochure_path.read_bytes()
    b64_content = base64.b64encode(brochure_bytes).decode("utf-8")

    info(f"Sending PDF brochure ({len(brochure_bytes)} bytes) to Hotel Agent")
    info("Message contains: TextPart + FilePart (application/pdf)")

    try:
        async with httpx.AsyncClient(
            headers={"X-Api-Key": HOTEL_API_KEY}, timeout=15.0
        ) as http_client:
            resolver = A2ACardResolver(http_client, HOTEL_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            # Multimodal message: TextPart instruction + FilePart PDF
            multimodal_msg = Message(
                message_id=str(uuid4()),
                role=Role.user,
                parts=[
                    Part(root=TextPart(text="Extract amenities from this hotel brochure")),
                    Part(
                        root=FilePart(
                            file=FileWithBytes(
                                bytes=b64_content,
                                mime_type="application/pdf",
                                name="hotel_brochure.pdf",
                            )
                        )
                    ),
                ],
            )

            req = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=multimodal_msg),
            )
            response = await client.send_message(req)
            task = response.root.result

            if task.artifacts:
                for part in task.artifacts[0].parts:
                    if isinstance(part.root, DataPart):
                        data = part.root.data
                        ok(f"Extracted from PDF: {data.get('hotel_name')}")
                        amenities = data.get("amenities", [])
                        info(f"  Amenities ({len(amenities)}):")
                        for a in amenities[:5]:
                            info(f"    - {a}")
                        if len(amenities) > 5:
                            info(f"    ... and {len(amenities)-5} more")
    except Exception as exc:
        warn(f"Section 6 demo failed: {exc}")


# ── Section 7: Input Required ─────────────────────────────────────────────────
async def demo_section7_input_required() -> None:
    """
    Section 7 — Input Required (Human-in-the-Loop)

    When an agent needs clarification, it returns a task in 'input-required' state.
    The status.message contains the agent's question.

    To continue the conversation, the client sends a NEW message/send request
    with the SAME task_id embedded in Message.task_id. This resumes the task.

    This demo auto-answers the booking questions (no real user input needed).
    """
    section(7, "Input Required — multi-turn booking with task resumption")

    # Pre-configured answers for the tutorial
    auto_answers = {
        "seat class": "business",
        "meal preference": "vegetarian",
        "loyalty": "AA123456",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            resolver = A2ACardResolver(http_client, BOOKING_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            # Initial request — no task_id yet (new task)
            initial_msg = _user_msg("Book flight FL001 and hotel H001 in Paris")
            req = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=initial_msg),
            )

            info("Sending initial booking request...")
            response = await client.send_message(req)
            task = response.root.result

            # Remember IDs for multi-turn resumption
            task_id = task.id
            context_id = task.context_id
            info(f"Task ID: {task_id}")

            turn = 1
            while task.status.state.value == "input-required":
                question = ""
                if task.status.message and task.status.message.parts:
                    question = task.status.message.parts[0].root.text

                info(f"[Turn {turn}] Agent asks: {question}")

                # Auto-answer based on keyword matching
                answer = "none"
                lower_q = question.lower()
                if "seat" in lower_q:
                    answer = auto_answers["seat class"]
                elif "meal" in lower_q:
                    answer = auto_answers["meal preference"]
                elif "loyalty" in lower_q:
                    answer = auto_answers["loyalty"]

                info(f"[Turn {turn}] Auto-answer: '{answer}'")

                # Resume the SAME task by setting task_id in the Message
                follow_up = _user_msg(answer, task_id=task_id, context_id=context_id)
                req = SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(message=follow_up),
                )
                response = await client.send_message(req)
                task = response.root.result
                turn += 1

            info(f"Final state: {task.status.state.value}")
            if task.artifacts:
                for part in task.artifacts[0].parts:
                    if isinstance(part.root, DataPart):
                        booking = part.root.data
                        ok(f"Booking confirmed: {booking.get('booking_ref')}")
                        info(f"  Seat class:      {booking.get('seat_class')}")
                        info(f"  Meal:            {booking.get('meal_preference')}")
                        info(f"  Loyalty number:  {booking.get('loyalty_number')}")
                        info(f"  Message:         {booking.get('confirmation_message')}")
    except Exception as exc:
        warn(f"Section 7 demo failed: {exc}")


# ── Section 8: Push Notifications ─────────────────────────────────────────────
async def demo_section8_push_notifications() -> None:
    """
    Section 8 — Push Notifications

    The client registers a webhook URL via tasks/pushNotificationConfig/set.
    When the task reaches a terminal state, the A2A server POSTs the full
    Task JSON to that URL with the secret token in X-A2A-Notification-Token.

    This demo:
    1. Starts a booking task
    2. Registers a push notification callback
    3. Reads the config back with tasks/pushNotificationConfig/get
    4. Continues the booking to trigger the webhook
    """
    section(8, "Push Notifications — tasks/pushNotificationConfig/set + webhook")

    try:
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            resolver = A2ACardResolver(http_client, BOOKING_URL)
            card = await resolver.get_agent_card()

            # Check agent supports push notifications
            if not card.capabilities.push_notifications:
                warn("Booking agent does not advertise push_notifications capability")
                return

            info(f"Booking agent supports push_notifications: {card.capabilities.push_notifications}")

            client = A2AClient(httpx_client=http_client, agent_card=card)

            # Step 1: Start a task
            req = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=_user_msg("Book a trip to London")),
            )
            response = await client.send_message(req)
            task = response.root.result
            task_id = task.id
            context_id = task.context_id
            info(f"Task created: {task_id} — state: {task.status.state.value}")

            # Step 2: Register push notification webhook
            push_cfg = TaskPushNotificationConfig(
                task_id=task_id,
                push_notification_config=PushNotificationConfig(
                    url=f"{WEBHOOK_URL}/webhook",
                    token=WEBHOOK_TOKEN,
                ),
            )
            set_req = SetTaskPushNotificationConfigRequest(
                id=str(uuid4()),
                params=push_cfg,
            )
            await client.set_task_callback(set_req)
            ok(f"Push notification registered: {WEBHOOK_URL}/webhook")

            # Step 3: Read back the registered config
            get_cfg_req = GetTaskPushNotificationConfigRequest(
                id=str(uuid4()),
                params=TaskIdParams(id=task_id),
            )
            get_cfg_resp = await client.get_task_callback(get_cfg_req)
            stored_cfg = get_cfg_resp.root.result
            if stored_cfg and stored_cfg.push_notification_config:
                info(f"Stored webhook URL: {stored_cfg.push_notification_config.url}")

            # Step 4: Drive the booking to completion (trigger webhook)
            info("Completing booking to trigger push notification...")
            auto_answers = ["business", "vegetarian", "BA999111"]
            current_task = task

            for answer in auto_answers:
                if current_task.status.state.value != "input-required":
                    break
                follow_up = _user_msg(answer, task_id=task_id, context_id=context_id)
                req = SendMessageRequest(
                    id=str(uuid4()),
                    params=MessageSendParams(message=follow_up),
                )
                resp = await client.send_message(req)
                current_task = resp.root.result

            info(f"Final task state: {current_task.status.state.value}")
            info(f"Check webhook logs at: GET {WEBHOOK_URL}/notifications")
            ok("Push notification should have been delivered to the webhook receiver")
    except Exception as exc:
        warn(f"Section 8 demo failed: {exc}")


# ── Section 9: Authentication ──────────────────────────────────────────────────
async def demo_section9_authentication() -> None:
    """
    Section 9 — Authentication

    Shows how to:
    1. Read security_schemes from an Agent Card
    2. Inject the correct credentials into requests
    3. Handle 401 / failed state on bad credentials
    """
    section(9, "Authentication — Bearer token and API key")

    # 9a: Read the security scheme from the Agent Card
    info("Reading security scheme from Flight Agent card:")
    try:
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {FLIGHT_TOKEN}"}, timeout=5.0
        ) as http_client:
            resolver = A2ACardResolver(http_client, FLIGHT_URL)
            card = await resolver.get_agent_card()

        if card.security_schemes:
            for scheme_id, scheme in card.security_schemes.items():
                info(f"  scheme id: {scheme_id}")
                info(f"  type:      {scheme.root.type}")
                info(f"  scheme:    {getattr(scheme.root, 'scheme', 'N/A')}")
                info(f"  desc:      {scheme.root.description}")
        ok("Client reads auth requirements from Agent Card before making requests")
    except Exception as exc:
        warn(f"Could not fetch flight card: {exc}")

    # 9b: Successful call with correct Bearer token
    info("")
    info("Successful request with correct Bearer token:")
    try:
        async with httpx.AsyncClient(
            headers={"Authorization": f"Bearer {FLIGHT_TOKEN}"}, timeout=15.0
        ) as http_client:
            resolver = A2ACardResolver(http_client, FLIGHT_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)
            req = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=_user_msg("flights NYC to London")),
            )
            response = await client.send_message(req)
            task = response.root.result
            ok(f"Request succeeded — task state: {task.status.state.value}")
    except Exception as exc:
        warn(f"Auth success demo failed: {exc}")

    # 9c: Failed call with wrong Bearer token → task state = failed
    info("")
    info("Request with WRONG Bearer token (expect failed state):")
    try:
        async with httpx.AsyncClient(
            headers={"Authorization": "Bearer wrong-token"}, timeout=15.0
        ) as http_client:
            resolver = A2ACardResolver(http_client, FLIGHT_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)
            req = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=_user_msg("flights NYC to London")),
            )
            response = await client.send_message(req)
            task = response.root.result
            state = task.status.state.value
            if state == "failed":
                msg_text = ""
                if task.status.message and task.status.message.parts:
                    msg_text = task.status.message.parts[0].root.text
                ok(f"Got expected 'failed' state. Agent message: '{msg_text}'")
            else:
                warn(f"Unexpected state: {state}")
    except Exception as exc:
        warn(f"Auth failure demo failed: {exc}")


# ── Section 10: Error Handling ────────────────────────────────────────────────
async def demo_section10_error_handling() -> None:
    """
    Section 10 — Error Handling and Resilience

    Demonstrates:
    - 'failed' terminal state with error message in status.message
    - tasks/cancel on an in-flight task
    - tasks/get on an unknown task_id (TaskNotFound error)
    - Graceful degradation when an agent is unreachable
    """
    section(10, "Error Handling — failed state, cancellation, TaskNotFound")

    # 10a: Failed task (bad API key to hotel agent)
    info("Triggering 'failed' state with wrong API key on Hotel Agent:")
    try:
        async with httpx.AsyncClient(
            headers={"X-Api-Key": "wrong-key"}, timeout=10.0
        ) as http_client:
            resolver = A2ACardResolver(http_client, HOTEL_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)
            req = SendMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(message=_user_msg("Hotels in Paris")),
            )
            response = await client.send_message(req)
            task = response.root.result
            if task.status.state.value == "failed":
                error_msg = ""
                if task.status.message and task.status.message.parts:
                    error_msg = task.status.message.parts[0].root.text
                ok(f"Task failed as expected: '{error_msg[:60]}...'")
    except Exception as exc:
        warn(f"Error handling demo (failed state) failed: {exc}")

    # 10b: tasks/get with a non-existent task_id
    info("")
    info("Calling tasks/get with a non-existent task_id:")
    try:
        async with httpx.AsyncClient(
            headers={"X-Api-Key": HOTEL_API_KEY}, timeout=10.0
        ) as http_client:
            resolver = A2ACardResolver(http_client, HOTEL_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)
            fake_id = str(uuid4())
            get_req = GetTaskRequest(
                id=str(uuid4()),
                params=TaskQueryParams(id=fake_id),
            )
            get_resp = await client.get_task(get_req)
            result = get_resp.root
            # The response should contain a JSON-RPC error
            if hasattr(result, "error"):
                ok(f"Got JSON-RPC error: code={result.error.code}, msg='{result.error.message}'")
            else:
                info(f"Unexpected response: {result}")
    except Exception as exc:
        ok(f"Got expected exception for unknown task_id: {type(exc).__name__}: {exc}")

    # 10c: Graceful degradation — agent unreachable
    info("")
    info("Graceful degradation — trying unreachable agent:")
    try:
        async with httpx.AsyncClient(timeout=2.0) as http_client:
            resolver = A2ACardResolver(http_client, "http://localhost:9999")
            await resolver.get_agent_card()
    except Exception as exc:
        ok(f"Caught connection error gracefully: {type(exc).__name__}")


# ── Section 11: Orchestration ─────────────────────────────────────────────────
async def demo_section11_orchestration() -> None:
    """
    Section 11 — Multi-Agent Orchestration

    The Travel Orchestrator is itself an A2A agent. Sending it a single
    natural-language request triggers:
    1. Agent Card discovery for all specialist agents
    2. Parallel fan-out: flight + hotel + weather requests dispatched simultaneously
    3. Result aggregation into a single travel plan DataPart artifact
    """
    section(11, "Multi-Agent Orchestration — single request → multiple agents")

    info("Sending travel request to orchestrator: 'Plan a 5-day trip to Paris'")
    info("The orchestrator will call: Flight + Hotel + Weather agents in parallel")

    try:
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            resolver = A2ACardResolver(http_client, ORCHESTRATOR_URL)
            card = await resolver.get_agent_card()
            client = A2AClient(httpx_client=http_client, agent_card=card)

            req = SendStreamingMessageRequest(
                id=str(uuid4()),
                params=MessageSendParams(
                    message=_user_msg("Plan a 5-day trip to Paris")
                ),
            )

            plan_received = False
            async for resp in client.send_message_streaming(req):
                result = resp.root.result
                if isinstance(result, TaskStatusUpdateEvent):
                    info(f"  [Status] {result.status.state.value}")
                elif isinstance(result, TaskArtifactUpdateEvent):
                    for part in result.artifact.parts:
                        if isinstance(part.root, DataPart) and not plan_received:
                            plan = part.root.data
                            plan_received = True
                            ok(f"Travel plan received for: {plan.get('destination')}")
                            info(f"  Flights:  {len(plan.get('flights', []))}")
                            info(f"  Hotels:   {len(plan.get('hotels', []))}")
                            info(f"  Weather days: {len(plan.get('weather_forecast', []))}")
                            info(f"  Summary: {plan.get('summary')}")

            if not plan_received:
                warn("No DataPart travel plan received from orchestrator")
    except Exception as exc:
        warn(f"Section 11 demo failed: {exc}")


# ── Main ──────────────────────────────────────────────────────────────────────
async def main() -> None:
    banner("A2A Protocol Tutorial — Complete Feature Demonstration")
    print("  This script exercises every A2A protocol feature in sequence.")
    print("  Agents must be running before this script is executed.\n")
    print("  Required agents:")
    print(f"    Flight Agent   {FLIGHT_URL}   (Bearer: {FLIGHT_TOKEN})")
    print(f"    Hotel Agent    {HOTEL_URL}   (API key: {HOTEL_API_KEY})")
    print(f"    Booking Agent  {BOOKING_URL}   (no auth)")
    print(f"    Weather Agent  {WEATHER_URL}   (no auth)")
    print(f"    Orchestrator   {ORCHESTRATOR_URL}  (no auth)")
    print(f"    Webhook        {WEBHOOK_URL}   (token: {WEBHOOK_TOKEN})")

    await demo_section2_agent_cards()
    await demo_section3_basic_task()
    await demo_section4_task_lifecycle()
    await demo_section5_streaming()
    await demo_section6_multimodal()
    await demo_section7_input_required()
    await demo_section8_push_notifications()
    await demo_section9_authentication()
    await demo_section10_error_handling()
    await demo_section11_orchestration()

    banner("Tutorial Complete!")
    print("  All A2A protocol features have been demonstrated.")
    print("  See TUTORIAL_PLAN.md for the full feature coverage matrix.\n")


if __name__ == "__main__":
    asyncio.run(main())
