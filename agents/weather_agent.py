"""
agents/weather_agent.py
=======================
Section 2 (Agent Cards) + Section 5 (SSE Streaming)

Demonstrates:
- AgentCard with capabilities.streaming=True
- Streaming a 7-day forecast via TaskArtifactUpdateEvent chunks
- append=True to signal the client that chunks belong to the same artifact
- last_chunk=True to signal the stream is complete
- No authentication (public agent)

Run:
    python agents/weather_agent.py
Endpoint: http://localhost:8004
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
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
    Part,
    TaskArtifactUpdateEvent,
    TaskState,
    TaskStatus,
    TaskStatusUpdateEvent,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Mock weather data generator ───────────────────────────────────────────────
_CONDITIONS = ["Sunny", "Partly Cloudy", "Cloudy", "Rainy", "Windy", "Thunderstorms"]
_CITY_WEATHER = {
    "paris": {"highs": [12, 14, 11, 9, 13, 15, 16], "lows": [5, 6, 4, 3, 5, 7, 8],
               "conditions": ["Cloudy", "Rainy", "Cloudy", "Sunny", "Partly Cloudy", "Sunny", "Sunny"]},
    "london": {"highs": [10, 11, 9, 12, 10, 8, 11], "lows": [4, 5, 3, 6, 4, 2, 5],
               "conditions": ["Rainy", "Cloudy", "Rainy", "Partly Cloudy", "Cloudy", "Rainy", "Cloudy"]},
    "tokyo": {"highs": [18, 20, 19, 22, 21, 23, 20], "lows": [10, 11, 10, 13, 12, 14, 11],
              "conditions": ["Sunny", "Sunny", "Partly Cloudy", "Sunny", "Sunny", "Cloudy", "Partly Cloudy"]},
    "new york": {"highs": [8, 10, 7, 9, 11, 12, 10], "lows": [1, 3, 0, 2, 4, 5, 3],
                 "conditions": ["Sunny", "Windy", "Cloudy", "Partly Cloudy", "Sunny", "Rainy", "Cloudy"]},
}
_DEFAULT_WEATHER = {"highs": [20]*7, "lows": [12]*7, "conditions": ["Sunny"]*7}


def _generate_forecast(city: str) -> list[dict]:
    city_key = city.lower().strip()
    data = _CITY_WEATHER.get(city_key, _DEFAULT_WEATHER)
    base_date = datetime(2026, 3, 15, tzinfo=timezone.utc)
    forecast = []
    for i in range(7):
        date = (base_date + timedelta(days=i)).strftime("%Y-%m-%d")
        forecast.append({
            "date": date,
            "city": city,
            "condition": data["conditions"][i],
            "high_c": data["highs"][i],
            "low_c": data["lows"][i],
            "humidity_pct": 60 + (i * 3 % 30),
        })
    return forecast


# ── Agent Executor ────────────────────────────────────────────────────────────
class WeatherAgentExecutor(AgentExecutor):
    """
    Handles weather forecast tasks.

    Section 5 — Streaming:
        Emits one TaskArtifactUpdateEvent per day of the forecast.
        Uses append=True for days 2-7 and last_chunk=True for day 7.
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

        # Section 4: working
        await event_queue.enqueue_event(
            TaskStatusUpdateEvent(
                task_id=task_id,
                context_id=context_id,
                status=TaskStatus(state=TaskState.working, timestamp=_now()),
                final=False,
            )
        )

        # Parse city from user input
        user_input = context.get_user_input().strip()
        city = "Paris"  # default
        found_city = False
        for keyword in ["for ", "in ", "at "]:
            if keyword in user_input.lower():
                city = user_input.lower().split(keyword, 1)[-1].strip().title()
                found_city = True
                break
        if not found_city and user_input:
            city = user_input.title()

        logger.info("Generating 7-day forecast for: %s", city)
        forecast = _generate_forecast(city)

        # Section 5: Stream one day at a time
        for i, day in enumerate(forecast):
            await asyncio.sleep(0.3)  # simulate per-day computation
            is_last = i == len(forecast) - 1

            await event_queue.enqueue_event(
                TaskArtifactUpdateEvent(
                    task_id=task_id,
                    context_id=context_id,
                    artifact=Artifact(
                        artifact_id=str(uuid4()),
                        name="weather_forecast",
                        description=f"7-day weather forecast for {city}",
                        parts=[Part(root=DataPart(data=day))],
                    ),
                    append=(i > 0),     # True for days 2–7 (same logical artifact)
                    last_chunk=is_last, # True only for the final day
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
        name="Weather Agent",
        description=(
            "Provides a 7-day weather forecast for a given city, "
            "streaming one day at a time as a Server-Sent Event stream."
        ),
        url="http://localhost:8004/",
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text/plain"],
        default_output_modes=["application/json"],
        skills=[
            AgentSkill(
                id="get_weather_forecast",
                name="7-Day Weather Forecast",
                description=(
                    "Get a 7-day weather forecast for any city. "
                    "Results are streamed one day at a time."
                ),
                tags=["weather", "forecast", "travel", "streaming"],
                examples=[
                    "Weather forecast for Paris",
                    "What's the weather like in Tokyo next week?",
                    "7 day weather in London",
                ],
                input_modes=["text/plain"],
                output_modes=["application/json"],
            )
        ],
    )


def create_app():
    agent_card = build_agent_card()
    handler = DefaultRequestHandler(
        agent_executor=WeatherAgentExecutor(),
        task_store=InMemoryTaskStore(),
    )
    return A2AFastAPIApplication(agent_card=agent_card, http_handler=handler).build()


app = create_app()

if __name__ == "__main__":
    logger.info("Starting Weather Agent on http://localhost:8004")
    uvicorn.run(app, host="0.0.0.0", port=8004, log_level="warning")
