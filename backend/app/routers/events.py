from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.config import settings
from app.database import get_db
from app.models import Event, User
from app.routers.recommendations import hydrate_recommendation
from app.schemas import (
    EventBatchRequest,
    EventBatchResponse,
    EventOut,
    RecommendationOut,
)
from app.trigger import maybe_run_agent
from app.pipeline_log import pipe

router = APIRouter(prefix="/events", tags=["events"])

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def _recommendation_out(db: Session, rec) -> RecommendationOut | None:
    if rec is None:
        return None
    return hydrate_recommendation(db, rec)


def _is_duplicate_view(db: Session, user_id: int, metadata: dict) -> bool:
    """Ignore repeat views of the same course within the dedupe window."""
    course_id = metadata.get("courseId")
    if not course_id:
        return False
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=settings.EVENT_VIEW_DEDUPE_SECONDS)
    recent = (
        db.query(Event)
        .filter(
            Event.user_id == user_id,
            Event.event_type == "view",
            Event.created_at >= cutoff,
        )
        .order_by(Event.created_at.desc())
        .limit(40)
        .all()
    )
    cid = str(course_id)
    for row in recent:
        meta = row.raw_metadata or {}
        if str(meta.get("courseId") or "") == cid:
            return True
    return False


@router.post("", response_model=EventBatchResponse)
def ingest_events(
    body: EventBatchRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Bulk-insert behavioral events. No embeddings / no Mesh calls here."""
    now_ts = datetime.now(timezone.utc).isoformat()
    logger.info("EVENTS_POST_RECEIVED user=%s ts=%s count=%s", current_user.id, now_ts, len(body.events))
    logger.debug("EVENTS_POST_PAYLOAD user=%s payload=%s", current_user.id, [e.dict() for e in body.events])
    summaries = []
    for item in body.events:
        meta = item.raw_metadata or {}
        summaries.append(
            {
                "type": item.event_type,
                "courseId": meta.get("courseId"),
                "category": meta.get("category"),
                "title": (str(meta.get("title") or ""))[:40],
            }
        )
    pipe(
        "EVENTS_POST",
        user_id=current_user.id,
        batch_n=len(body.events),
        events=summaries,
    )

    rows: list[Event] = []
    seen_in_batch: set[str] = set()
    skipped_dedupe = 0
    for item in body.events:
        meta = item.raw_metadata or {}
        if item.event_type == "view":
            cid = str(meta.get("courseId") or "")
            if cid and cid in seen_in_batch:
                skipped_dedupe += 1
                continue
            if _is_duplicate_view(db, current_user.id, meta):
                skipped_dedupe += 1
                continue
            if cid:
                seen_in_batch.add(cid)
        rows.append(
            Event(
                user_id=current_user.id,
                event_type=item.event_type,
                source=item.source,
                raw_metadata=meta,
            )
        )

    if rows:
        db.add_all(rows)
        db.commit()
        logger.info(
            "EVENTS_INSERTED user=%s inserted=%s skipped_dedupe=%s ts=%s",
            current_user.id,
            len(rows),
            skipped_dedupe,
            datetime.now(timezone.utc).isoformat(),
        )

    pipe(
        "EVENTS_INSERTED",
        user_id=current_user.id,
        inserted=len(rows),
        skipped_dedupe=skipped_dedupe,
    )

    # Evaluate trigger and (possibly) run the agent. Log decision/outputs for tracing.
    triggered, reason, rec = maybe_run_agent(db, current_user.id) if rows else (False, None, None)
    # Ensure Recommendation object is fresh in this DB session before hydrating
    if rec is not None:
        try:
            db.refresh(rec)
        except Exception:
            # best-effort: if refresh fails, continue — hydration will still attempt to read
            pass
    logger.info(
        "EVENTS_POST_RESULT user=%s inserted=%s triggered=%s reason=%s rec_id=%s ts=%s",
        current_user.id,
        len(rows),
        triggered,
        reason,
        rec.id if rec else None,
        datetime.now(timezone.utc).isoformat(),
    )
    pipe(
        "EVENTS_RESPONSE",
        user_id=current_user.id,
        inserted=len(rows),
        triggered=triggered,
        trigger_reason=reason,
        rec_id=rec.id if rec else None,
        rec_generated_at=rec.generated_at.isoformat() if rec and rec.generated_at else None,
    )
    return EventBatchResponse(
        inserted=len(rows),
        triggered=triggered,
        trigger_reason=reason,
        recommendation=_recommendation_out(db, rec),
    )


@router.get("", response_model=list[EventOut])
def list_my_events(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (
        db.query(Event)
        .filter(Event.user_id == current_user.id)
        .order_by(Event.created_at.desc())
        .limit(limit)
        .all()
    )
