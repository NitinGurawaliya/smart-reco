"""Agent entrypoint — LangGraph behavioral agent (hackathon-aligned).

Flow:
  activity stream → summarize PATTERNS → retrieve by profile → grade/refine
  → persuasive narrative + catalog-grounded products → store/cache

NOT a 1:1 "each view → one related video" mapper.
The clustering module is only a retrieval guardrail — final picks are LLM + Chroma IDs.
"""

from __future__ import annotations

import logging
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app import vector_store
from app.agent.clustering import (
    build_source_summary,
    family_for_free_category,
    filter_chroma_hits_by_family,
    get_family_guardrail_hint,
)
from app.agent.graph import build_agent_graph
from app.config import settings
from app.models import Event, FreeResource, Recommendation

logger = logging.getLogger(__name__)


def _load_event_dicts(
    db: Session,
    user_id: int,
    *,
    since: datetime | None = None,
) -> list[dict]:
    """
    Load activity for the agent.

    When ``since`` is set (re-run after an existing recommendation), only events
    after that timestamp are used so a new FastAPI/ML streak is not drowned by
    older React browsing.
    """
    q = db.query(Event).filter(Event.user_id == user_id)
    if since is not None:
        q = q.filter(Event.created_at > since)
    rows = q.order_by(Event.created_at.asc()).limit(settings.AGENT_EVENT_LIMIT).all()
    # First-run / empty since-window: fall back to recent history
    if not rows and since is not None:
        rows = (
            db.query(Event)
            .filter(Event.user_id == user_id)
            .order_by(Event.created_at.desc())
            .limit(min(15, settings.AGENT_EVENT_LIMIT))
            .all()
        )
        rows = list(reversed(rows))
    return [
        {
            "event_type": row.event_type,
            "raw_metadata": row.raw_metadata or {},
        }
        for row in rows
    ]


def _latest_generated_at(db: Session, user_id: int) -> datetime | None:
    last = (
        db.query(Recommendation)
        .filter(Recommendation.user_id == user_id)
        .order_by(Recommendation.generated_at.desc())
        .first()
    )
    return last.generated_at if last else None


def _fallback_narrative(*, family: str | None, dominant: str, hero_title: str) -> str:
    """Varied copy when LLM is unavailable — still grounded in a real catalog title."""
    templates = {
        "frontend": [
            f"{hero_title} is a strong free next step if you're leveling up {dominant}.",
            f"Given your focus on {dominant}, start free with {hero_title}.",
            f"You're clearly leaning into {dominant} — {hero_title} matches that path without a paywall.",
        ],
        "design": [
            f"For {dominant}, {hero_title} is a free place to practice UI craft.",
            f"Your design-leaning trail points to {hero_title}.",
            f"Stay on {dominant} with {hero_title} as a free starting point.",
        ],
        "backend": [
            f"For {dominant}, {hero_title} is a solid free foundation to build on.",
            f"Your browsing points at {dominant}. Begin with {hero_title} — free and practical.",
            f"Stay on the {dominant} track with {hero_title} as your free starting point.",
        ],
        "python": [
            f"Python-curious from your activity — {hero_title} fits {dominant} well.",
            f"Double down on {dominant} with {hero_title}, free and structured.",
            f"{hero_title} lines up with how you've been exploring {dominant}.",
        ],
        "ml": [
            f"Your interest in {dominant} suggests {hero_title} as a free on-ramp.",
            f"Keep going on {dominant}: {hero_title} is a grounded free pick.",
            f"For {dominant}, start with {hero_title} before paid deep-dives.",
        ],
        "devops": [
            f"Tooling focus on {dominant}? {hero_title} is a free way to practice.",
            f"Your DevOps-leaning trail points to {hero_title} for {dominant}.",
            f"Build {dominant} skills next with {hero_title} — no paywall.",
        ],
        "data": [
            f"Data-minded browsing around {dominant} → try {hero_title} free.",
            f"{hero_title} matches the {dominant} thread in your activity.",
            f"Strengthen {dominant} with {hero_title} as a free first resource.",
        ],
    }
    pool = templates.get(
        family or "",
        [
            f"Based on {dominant}, {hero_title} is a free path worth starting with.",
            f"Your recent focus on {dominant} lines up with {hero_title}.",
            f"A clear free next step for {dominant}: {hero_title}.",
        ],
    )
    rng = random.Random(hero_title)
    return rng.choice(pool)


def _pattern_fallback(db: Session, *, user_id: int, trigger_reason: str) -> Recommendation | None:
    """
    Embedding-only fallback when the LLM graph fails.

    Still uses the family *guardrail* to scope Chroma — does not pick from a
    hardcoded playlist. Applies a non-LLM family sanity check before store:
    hero must match the dominant family or we skip storing (keep stale-consistent).
    """
    logger.warning("LangGraph/LLM unavailable — pattern embedding fallback user_id=%s", user_id)

    if trigger_reason == "manual_refresh":
        events = _load_event_dicts(db, user_id, since=None)
        if len(events) > 15:
            events = events[-15:]
    elif trigger_reason in ("initial_threshold", "expired"):
        events = _load_event_dicts(db, user_id, since=None)
    else:
        # Re-run: only activity since the previous recommendation
        events = _load_event_dicts(db, user_id, since=_latest_generated_at(db, user_id))

    hint = get_family_guardrail_hint(events)
    required_family = hint.get("family")
    themes = list(hint.get("themes") or [])[:2]
    query = str(hint.get("search_query") or "programming")
    free_categories = hint.get("free_categories")
    prefer = list(hint.get("prefer_tokens") or [])
    reject = list(hint.get("reject_tokens") or [])

    hits = vector_store.query_similar(query, top_k=settings.AGENT_TOP_K)
    if free_categories:
        for cat in list(free_categories)[:2]:
            try:
                hits.extend(vector_store.query_similar(query, top_k=4, category=cat))
            except Exception:
                pass

    by_id: dict[int, dict] = {}
    for h in hits:
        rid = int(h["resource_id"])
        if rid not in by_id:
            by_id[rid] = h

    filtered = filter_chroma_hits_by_family(
        list(by_id.values()),
        free_categories=set(free_categories) if free_categories else None,
        prefer_tokens=prefer,
        reject_tokens=reject,
        limit=settings.AGENT_TOP_K,
        required_family=str(required_family) if required_family else None,
    )

    # Non-LLM sanity: keep only candidates whose free category maps to dominant family
    sane: list[dict] = []
    for hit in filtered:
        rid = int(hit["resource_id"])
        row = db.get(FreeResource, rid)
        if row is None:
            continue
        hit_fam = family_for_free_category(row.category)
        if required_family and hit_fam and hit_fam != required_family:
            logger.info(
                "fallback skip off-family id=%s cat=%s want=%s",
                rid,
                row.category,
                required_family,
            )
            continue
        sane.append(hit)

    if not sane:
        logger.warning(
            "fallback aborted — no family-consistent candidates user_id=%s family=%s "
            "(keeping prior recommendation if any)",
            user_id,
            required_family,
        )
        return None

    picked: list[int] = []
    for hit in sane:
        rid = int(hit["resource_id"])
        if rid in picked:
            continue
        picked.append(rid)
        if len(picked) >= min(3, settings.AGENT_TARGET_RESOURCES):
            break

    if not picked:
        return None

    # Hero family must match — otherwise refuse to store a contradictory row
    hero = db.get(FreeResource, picked[0])
    hero_fam = family_for_free_category(hero.category) if hero else None
    if required_family and hero_fam and hero_fam != required_family:
        logger.warning(
            "fallback aborted — hero family mismatch hero=%s hero_fam=%s want=%s",
            picked[0],
            hero_fam,
            required_family,
        )
        return None

    dominant = str(hint.get("dominant_pattern") or "what you've been exploring")
    hero_title = hero.title if hero else "this free path"
    narrative = _fallback_narrative(
        family=hint.get("family") if isinstance(hint.get("family"), str) else None,
        dominant=dominant,
        hero_title=hero_title,
    )

    source_summary = build_source_summary(events, hint)

    now = datetime.now(timezone.utc)
    rec = Recommendation(
        user_id=user_id,
        narrative=narrative,
        resource_ids=picked,
        match_meta=[{"theme": t} for t in themes] + [{"dominant_pattern": dominant}],
        source_summary=source_summary,
        trigger_reason=f"{trigger_reason}+pattern_fallback",
        generated_at=now,
        expires_at=now + timedelta(hours=settings.RECOMMENDATION_TTL_HOURS),
    )
    db.add(rec)
    db.commit()
    db.refresh(rec)
    logger.info(
        "pattern fallback stored id=%s resources=%s themes=%s family=%s summary=%s",
        rec.id,
        picked,
        themes,
        hint.get("family"),
        source_summary.get("top_categories"),
    )
    return rec


def run_agent(db: Session, *, user_id: int, trigger_reason: str) -> Recommendation | None:
    """
    Primary: LangGraph (summarize → retrieve → grade → refine → generate → store).
    Fallback: family-scoped embedding retrieval + varied template narrative.
    """
    from app.pipeline_log import pipe
    from app.observability import agent_run_config

    start_ts = datetime.now(timezone.utc).isoformat()
    logger.info("AGENT_START user=%s reason=%s ts=%s", user_id, trigger_reason, start_ts)
    pipe("AGENT_START", user_id=user_id, trigger_reason=trigger_reason, ts=start_ts)
    since = None
    if trigger_reason not in ("initial_threshold", "manual_refresh", "expired"):
        since = _latest_generated_at(db, user_id)
    try:
        graph = build_agent_graph(db)
        logger.info("AGENT_INVOKE graph user=%s reason=%s", user_id, trigger_reason)
        final = graph.invoke(
            {
                "user_id": user_id,
                "trigger_reason": trigger_reason,
                "retry_count": 0,
                "grade_pass": False,
                "retrieved": [],
                "resource_ids": [],
                "themes": [],
                "activity_since": since.isoformat() if since else None,
            },
            config=agent_run_config(user_id=user_id, trigger_reason=trigger_reason),
        )
        rec_id = final.get("recommendation_id")
        if not rec_id:
            logger.info("AGENT_PATH pattern_fallback user=%s why=no_recommendation_id", user_id)
            pipe("AGENT_PATH", user_id=user_id, path="pattern_fallback", why="no_recommendation_id")
            return _pattern_fallback(db, user_id=user_id, trigger_reason=trigger_reason)
        logger.info(
            "AGENT_PATH langgraph user=%s rec_id=%s resources=%s",
            user_id,
            rec_id,
            final.get("resource_ids"),
        )
        pipe(
            "AGENT_PATH",
            user_id=user_id,
            path="langgraph",
            recommendation_id=rec_id,
            resource_ids=final.get("resource_ids"),
        )
        return db.get(Recommendation, rec_id)
    except Exception:
        logger.exception("LangGraph agent failed user_id=%s — pattern fallback", user_id)
        pipe("AGENT_PATH", user_id=user_id, path="pattern_fallback", why="langgraph_exception")
        db.rollback()
        try:
            return _pattern_fallback(db, user_id=user_id, trigger_reason=trigger_reason)
        except Exception:
            logger.exception("pattern fallback failed user_id=%s", user_id)
            db.rollback()
            return None
