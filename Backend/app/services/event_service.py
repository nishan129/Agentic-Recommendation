"""
Event ingestion service.

Design notes (see README "Event tracking architecture" for the full picture):

    Frontend -> Event Collector API -> fast Pydantic validation
             -> EventService (builds ORM objects, no I/O)
             -> persisted via BackgroundTasks after the response is sent
             -> DB (Postgres)

This keeps the request/response path for POST /events and POST /events/batch
fast and non-blocking: validation happens synchronously (cheap), but the
actual INSERT happens in a FastAPI BackgroundTask so the frontend never waits
on database latency. The same `EventRepository.create_many` bulk-insert path
is reused for single and batch events, so swapping this for a
Redis/Celery/Kafka worker later only means changing how `persist_events` is
invoked - not the service/repository contracts.
"""
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ValidationAppError
from app.models.event import UserEvent
from app.repositories.event_repository import EventRepository
from app.schemas.event import EventCreateRequest

logger = logging.getLogger("app.events")


class EventService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.events = EventRepository(db)

    def build_event(self, payload: EventCreateRequest, user_id: str) -> UserEvent:
        """Construct an ORM event object without touching the DB.

        `user_id` and `timestamp` are always derived from the authenticated
        request context (server-assigned `default=func.now()`), never
        trusted from the client payload.
        """
        return UserEvent(
            user_id=user_id,
            session_id=payload.session_id,
            event_type=payload.event_type.strip().lower(),
            product_id=payload.product_id,
            page=payload.page,
            search_query=payload.search_query,
            event_metadata=payload.metadata,
        )

    def build_batch(self, payloads: list[EventCreateRequest], user_id: str) -> list[UserEvent]:
        if len(payloads) > settings.EVENT_BATCH_MAX_SIZE:
            raise ValidationAppError(
                f"Batch too large: max {settings.EVENT_BATCH_MAX_SIZE} events per request",
                "BATCH_TOO_LARGE",
                status_code=400,
            )
        return [self.build_event(p, user_id) for p in payloads]

    async def persist_events(self, events: list[UserEvent]) -> None:
        """Intended to run inside a BackgroundTask so it never blocks the
        HTTP response. Errors are logged, not raised, since the client has
        already received a 2xx by the time this runs.
        """
        if not events:
            return
        try:
            await self.events.create_many(events)
            logger.info("Persisted %d event(s) for user_id=%s", len(events), events[0].user_id)
        except Exception:
            logger.exception("Failed to persist %d event(s)", len(events))
