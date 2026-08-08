from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

import app.db.session as db_session_module
from app.core.dependencies import get_current_user
from app.core.limiter import limiter
from app.db.session import get_db
from app.models.event import UserEvent
from app.models.user import User
from app.schemas.event import EventBatchRequest, EventBatchResponse, EventCreateRequest
from app.services.event_service import EventService

router = APIRouter(prefix="/events", tags=["Events"])


async def _persist_in_background(events: list[UserEvent]) -> None:
    """Runs after the HTTP response has been sent. Opens its own session
    since the request-scoped session from `get_db` is closed by then.
    """
    async with db_session_module.AsyncSessionLocal() as session:
        service = EventService(session)
        await service.persist_events(events)


@router.post("", status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("120/minute")
async def create_event(
    request: Request,
    payload: EventCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = EventService(db)
    event = service.build_event(payload, user_id=current_user.id)
    background_tasks.add_task(_persist_in_background, [event])
    return {"success": True, "message": "Event accepted"}


@router.post("/batch", response_model=EventBatchResponse, status_code=status.HTTP_202_ACCEPTED)
@limiter.limit("60/minute")
async def create_events_batch(
    request: Request,
    payload: EventBatchRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    service = EventService(db)
    events = service.build_batch(payload.events, user_id=current_user.id)
    background_tasks.add_task(_persist_in_background, events)
    return EventBatchResponse(accepted=len(events), rejected=0, errors=[])
