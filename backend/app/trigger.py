from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.agent.runner import run_agent
from app.agent.clustering import get_family_guardrail_hint
from app.config import settings
from app.models import Event, Recommendation
from app.pipeline_log import pipe

logger = logging.getLogger(__name__)


@dataclass
class TriggerDecision:
    should_run: bool
    reason: str | None
    skip_reason: str | None
    new_event_count: int
    last_recommendation: Recommendation | None
    cooldown_remaining: float
    confident: bool | None
    family_counts: dict | None
    family: str | None


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def get_latest_recommendation(db: Session, user_id: int) -> Recommendation | None:
    return (
        db.query(Recommendation)
        .filter(Recommendation.user_id == user_id)
        .order_by(Recommendation.generated_at.desc())
        .first()
    )


def evaluate_trigger(db: Session, user_id: int) -> TriggerDecision:
    """Decide whether the agent should re-run. Never calls the LLM itself."""
    now = datetime.now(timezone.utc)
    logger.info("EVALUATE_TRIGGER start user=%s ts=%s", user_id, now.isoformat())
    last = get_latest_recommendation(db, user_id)
    cooldown = float(settings.EVENT_COOLDOWN_SECONDS)
    threshold = settings.EVENT_TRIGGER_THRESHOLD

    if last is None:
        new_count = (
            db.query(func.count(Event.id)).filter(Event.user_id == user_id).scalar() or 0
        )
        logger.info(
            "EVALUATE_TRIGGER no_last user=%s new_count=%s threshold=%s",
            user_id,
            new_count,
            threshold,
        )
        if new_count >= threshold:
            return TriggerDecision(
                True, "initial_threshold", None, new_count, None, 0.0, None, None, None
            )
        return TriggerDecision(
            False,
            None,
            "below_threshold",
            new_count,
            None,
            0.0,
            None,
            None,
            None,
        )

    expires_at = _aware(last.expires_at)
    generated_at = _aware(last.generated_at)
    assert expires_at is not None and generated_at is not None

    new_count = (
        db.query(func.count(Event.id))
        .filter(Event.user_id == user_id, Event.created_at > generated_at)
        .scalar()
        or 0
    )

    elapsed = (now - generated_at).total_seconds()
    cooldown_remaining = max(0.0, cooldown - elapsed) if elapsed < cooldown else 0.0

    if expires_at <= now:
        logger.info(
            "EVALUATE_TRIGGER expired user=%s now=%s expires_at=%s",
            user_id,
            now.isoformat(),
            expires_at.isoformat(),
        )
        return TriggerDecision(
            True, "expired", None, new_count, last, cooldown_remaining, None, None, None
        )

    threshold_ok = new_count >= threshold
    cooldown_ok = elapsed >= cooldown

    if threshold_ok and cooldown_ok:
        logger.info(
            "EVALUATE_TRIGGER threshold_and_cooldown user=%s new_count=%s elapsed=%s",
            user_id,
            new_count,
            elapsed,
        )
        return TriggerDecision(
            True,
            "threshold_and_cooldown",
            None,
            new_count,
            last,
            0.0,
            None,
            None,
            None,
        )

    if not threshold_ok:
        skip = "below_threshold"
    elif not cooldown_ok:
        skip = "cooldown"
    else:
        skip = "unknown"

    return TriggerDecision(
        False, None, skip, new_count, last, cooldown_remaining, None, None, None
    )


def get_agent_status(db: Session, user_id: int) -> dict:
    """
    Explain where the user sits relative to the next agent run.
    Pure DB + settings — never calls the LLM.
    """
    decision = evaluate_trigger(db, user_id)
    last = decision.last_recommendation
    threshold = settings.EVENT_TRIGGER_THRESHOLD
    new_count = decision.new_event_count
    cooldown_remaining = decision.cooldown_remaining
    blocked_by_cooldown = decision.skip_reason == "cooldown" and new_count >= threshold

    events_until = max(0, threshold - new_count)

    confident = True
    family_counts = None
    if decision.should_run:
        hint = get_family_guardrail_hint(
            _events_for_confidence(db, user_id, last)
        )
        confident = bool(hint.get("confident"))
        family_counts = hint.get("family_counts")
        if not confident:
            label = "Still getting a feel for what you're into"
        else:
            label = "Agent ready — next browse flush will refresh your free path"
    elif last is None and new_count == 0:
        label = "Browse courses — the agent learns from your activity"
    elif last is None:
        label = f"{events_until} more signal{'s' if events_until != 1 else ''} until first free path"
    elif blocked_by_cooldown:
        label = f"Signals ready — agent cooldown ~{int(cooldown_remaining)}s"
    elif events_until > 0:
        label = f"{events_until} more signal{'s' if events_until != 1 else ''} until free path updates"
    else:
        label = "Watching your activity"

    return {
        "has_recommendation": last is not None,
        "new_event_count": new_count,
        "threshold": threshold,
        "events_until_next": events_until,
        "cooldown_seconds": int(settings.EVENT_COOLDOWN_SECONDS),
        "cooldown_remaining_seconds": round(cooldown_remaining, 1),
        "ready_to_run": bool(decision.should_run and confident),
        "blocked_by_cooldown": blocked_by_cooldown,
        "skip_reason": decision.skip_reason,
        "last_generated_at": last.generated_at if last else None,
        "last_trigger_reason": last.trigger_reason if last else None,
        "expires_at": last.expires_at if last else None,
        "resource_ids": list(last.resource_ids or []) if last else [],
        "status_label": label,
        "family_counts": family_counts,
    }


def _events_for_confidence(db: Session, user_id: int, last: Recommendation | None) -> list[dict]:
    """
    Activity window for re-trigger confidence.

    After a recommendation exists, ONLY events since generated_at — never a
    fixed last-N window that mixes pre- and post-rec history and dilutes a
    clear new pattern.
    """
    q = db.query(Event).filter(Event.user_id == user_id)
    if last is not None and last.generated_at is not None:
        q = q.filter(Event.created_at > last.generated_at)
    rows = q.order_by(Event.created_at.asc()).limit(settings.AGENT_EVENT_LIMIT).all()
    return [
        {"event_type": r.event_type, "raw_metadata": r.raw_metadata or {}}
        for r in rows
    ]


def maybe_run_agent(db: Session, user_id: int) -> tuple[bool, str | None, Recommendation | None]:
    """
    Evaluate trigger rules and invoke the agent at most once.

    Returns (triggered, trigger_reason, recommendation_if_created).
    """
    decision = evaluate_trigger(db, user_id)
    logger.info(
        "MAYBE_RUN_AGENT decision user=%s should_run=%s reason=%s skip=%s new_event_count=%s",
        user_id,
        decision.should_run,
        decision.reason,
        decision.skip_reason,
        decision.new_event_count,
    )
    last = decision.last_recommendation
    last_id = last.id if last else None
    last_gen = last.generated_at.isoformat() if last and last.generated_at else None

    # Always compute confidence window for logging (even when not should_run)
    conf_events = _events_for_confidence(db, user_id, last)
    hint = get_family_guardrail_hint(conf_events) if conf_events else {
        "confident": False,
        "family_counts": {},
        "family": None,
        "confidence_reason": "no_events",
    }
    confident = bool(hint.get("confident")) if decision.should_run else None

    pipe(
        "TRIGGER_CHECK",
        user_id=user_id,
        should_run=decision.should_run,
        reason=decision.reason,
        skip_reason=decision.skip_reason,
        new_event_count=decision.new_event_count,
        threshold=settings.EVENT_TRIGGER_THRESHOLD,
        cooldown_remaining=round(decision.cooldown_remaining, 1),
        last_rec_id=last_id,
        last_generated_at=last_gen,
        conf_event_n=len(conf_events),
        family_counts=hint.get("family_counts"),
        family=hint.get("family"),
        confident=hint.get("confident") if decision.should_run else "n/a",
        confidence_reason=hint.get("confidence_reason"),
    )

    if not decision.should_run:
        logger.info(
            "MAYBE_RUN_AGENT skip user=%s skip_reason=%s new_event_count=%s",
            user_id,
            decision.skip_reason,
            decision.new_event_count,
        )
        return False, decision.skip_reason, None

    if not hint.get("confident"):
        reason = "insufficient_confidence"
        logger.info(
            "MAYBE_RUN_AGENT skip_confidence user=%s family_counts=%s family=%s",
            user_id,
            hint.get("family_counts"),
            hint.get("family"),
        )
        pipe(
            "TRIGGER_SKIP",
            user_id=user_id,
            reason=reason,
            family_counts=hint.get("family_counts"),
            family=hint.get("family"),
        )
        return False, reason, None

    reason = decision.reason or "unknown"
    logger.info(
        "MAYBE_RUN_AGENT fire user=%s reason=%s new_events=%s family=%s ts=%s",
        user_id,
        reason,
        decision.new_event_count,
        hint.get("family"),
        datetime.now(timezone.utc).isoformat(),
    )
    pipe(
        "TRIGGER_FIRE",
        user_id=user_id,
        reason=reason,
        new_events=decision.new_event_count,
        family=hint.get("family"),
    )
    rec = run_agent(db, user_id=user_id, trigger_reason=reason)
    if rec is None:
        pipe("AGENT_NO_REC", user_id=user_id, reason=reason)
        return True, reason, None
    pipe(
        "REC_STORED",
        user_id=user_id,
        rec_id=rec.id,
        generated_at=rec.generated_at.isoformat() if rec.generated_at else None,
        trigger_reason=rec.trigger_reason,
        resource_ids=rec.resource_ids,
    )
    return True, reason, rec
