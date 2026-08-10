from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app import vector_store
from app.agent import prompts
from app.agent.clustering import (
    build_source_summary,
    family_for_free_category,
    filter_chroma_hits_by_family,
    get_family_guardrail_hint,
)
from app.config import settings
from app.mesh import chat_completion, parse_json_object
from app.models import Event, FreeResource, Recommendation

logger = logging.getLogger(__name__)


class AgentState(TypedDict, total=False):
    user_id: int
    trigger_reason: str
    activity_since: str | None
    events: list[dict[str, Any]]
    profile: str
    themes: list[str]
    search_query: str
    secondary_query: str
    udemy_signal: str
    retrieved: list[dict[str, Any]]
    grade_pass: bool
    grade_reason: str
    retry_count: int
    narrative: str
    resource_ids: list[int]
    match_meta: list[dict[str, Any]]
    source_summary: dict[str, Any]
    recommendation_id: int | None
    error: str | None


def _parse_since(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        return None


def _load_events(
    db: Session,
    user_id: int,
    *,
    since: datetime | None = None,
) -> list[dict[str, Any]]:
    q = db.query(Event).filter(Event.user_id == user_id)
    if since is not None:
        q = q.filter(Event.created_at > since)
    rows = q.order_by(Event.created_at.desc()).limit(settings.AGENT_EVENT_LIMIT).all()
    if not rows and since is not None:
        rows = (
            db.query(Event)
            .filter(Event.user_id == user_id)
            .order_by(Event.created_at.desc())
            .limit(min(15, settings.AGENT_EVENT_LIMIT))
            .all()
        )
    events: list[dict[str, Any]] = []
    for row in reversed(rows):
        events.append(
            {
                "event_type": row.event_type,
                "source": row.source,
                "raw_metadata": row.raw_metadata or {},
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
        )
    return events


def _hydrate_retrieved(db: Session, hits: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    seen: set[int] = set()
    for hit in hits:
        rid = int(hit["resource_id"])
        if rid in seen:
            continue
        row = db.get(FreeResource, rid)
        if row is None:
            continue
        seen.add(rid)
        out.append(
            {
                "id": row.id,
                "title": row.title,
                "description": row.description,
                "category": row.category,
                "level": row.level,
                "youtube_url": row.youtube_url,
                "topic_tags": row.topic_tags or [],
                "distance": hit.get("distance"),
            }
        )
    return out


def make_nodes(db: Session):
    def summarize_activity(state: AgentState) -> AgentState:
        since = _parse_since(state.get("activity_since"))
        reason = state.get("trigger_reason") or ""
        if reason in ("manual_refresh", "initial_threshold", "expired"):
            since = None
        events = state.get("events") or _load_events(db, state["user_id"], since=since)
        if reason == "manual_refresh" and len(events) > 15:
            events = events[-15:]
        # Guardrail hint only — does not pick free resources
        clustered = get_family_guardrail_hint(events)
        source_summary = build_source_summary(events, clustered)

        try:
            # LLM CALL — this is where reasoning/decision-making actually happens
            raw = chat_completion(
                system=prompts.SUMMARIZE_SYSTEM,
                user=str(
                    {
                        "events": events,
                        "deterministic_hint": {
                            "dominant_pattern": clustered["dominant_pattern"],
                            "themes": clustered["themes"],
                            "family_weights": clustered.get("family_weights"),
                            "instruction": (
                                "Prefer the majority family from deterministic_hint unless "
                                "event evidence clearly contradicts it."
                            ),
                        },
                    }
                ),
                temperature=0.1,
                max_tokens=550,
            )
            data = parse_json_object(raw)
        except Exception:
            logger.exception("summarize LLM failed — using deterministic cluster")
            data = {}

        themes = data.get("themes") or clustered["themes"]
        if not isinstance(themes, list):
            themes = clustered["themes"]
        themes = [str(t).strip() for t in themes if str(t).strip()][:2] or list(clustered["themes"])

        dominant = str(data.get("dominant_pattern") or "").strip() or str(
            clustered["dominant_pattern"]
        )
        # Always prefer deterministic search query for retrieval precision
        search_query = str(clustered["search_query"])
        llm_q = str(data.get("search_query") or "").strip()
        # Allow LLM query only if it still mentions a dominant theme token
        if llm_q and any(t.lower() in llm_q.lower() for t in themes[:2]):
            search_query = f"{clustered['search_query']} {llm_q}"

        profile = str(data.get("profile") or "").strip() or str(clustered["profile"])

        return {
            **state,
            "events": events,
            "profile": profile,
            "themes": themes[:2],
            "search_query": search_query.strip(),
            "secondary_query": "",
            "udemy_signal": str(data.get("udemy_signal") or "").strip(),
            "retry_count": int(state.get("retry_count") or 0),
            "error": None,
            "match_meta": (
                [{"theme": t} for t in themes[:2]]
                + [{"dominant_pattern": dominant}]
                + [
                    {
                        "free_categories": sorted(clustered["free_categories"] or []),
                        "prefer_tokens": clustered.get("prefer_tokens") or [],
                        "reject_tokens": clustered.get("reject_tokens") or [],
                        "family": clustered.get("family"),
                    }
                ]
            ),
            "source_summary": source_summary,
        }

    def retrieve(state: AgentState) -> AgentState:
        primary = state.get("search_query") or state.get("profile") or "free learning resources"
        # Recover cluster filters from match_meta
        free_categories: set[str] | None = None
        prefer_tokens: list[str] = []
        reject_tokens: list[str] = []
        required_family: str | None = None
        for item in state.get("match_meta") or []:
            if not isinstance(item, dict):
                continue
            if "free_categories" in item:
                free_categories = set(item.get("free_categories") or [])
                prefer_tokens = list(item.get("prefer_tokens") or [])
                reject_tokens = list(item.get("reject_tokens") or [])
                fam = item.get("family")
                required_family = str(fam) if fam else None

        raw_hits = vector_store.query_similar(primary, top_k=max(settings.AGENT_TOP_K, 8))
        # Optional category-constrained pass for precision
        if free_categories:
            for cat in list(free_categories)[:2]:
                try:
                    raw_hits.extend(
                        vector_store.query_similar(primary, top_k=4, category=cat)
                    )
                except Exception:
                    logger.debug("category filter query failed cat=%s", cat)

        # Dedupe by resource_id
        by_id: dict[int, dict] = {}
        for h in raw_hits:
            rid = int(h["resource_id"])
            if rid not in by_id:
                by_id[rid] = h
        filtered = filter_chroma_hits_by_family(
            list(by_id.values()),
            free_categories=free_categories,
            prefer_tokens=prefer_tokens,
            reject_tokens=reject_tokens,
            limit=settings.AGENT_TOP_K,
            required_family=required_family,
        )
        retrieved = _hydrate_retrieved(db, filtered)
        return {**state, "retrieved": retrieved}

    def grade_retrieval(state: AgentState) -> AgentState:
        catalog = [
            {
                "id": r["id"],
                "title": r["title"],
                "category": r["category"],
                "level": r["level"],
            }
            for r in (state.get("retrieved") or [])
        ]
        if not catalog:
            return {
                **state,
                "grade_pass": False,
                "grade_reason": "no_resources_retrieved",
                "search_query": (state.get("search_query") or "") + " free tutorials courses",
            }

        # LLM CALL — this is where reasoning/decision-making actually happens
        raw = chat_completion(
            system=prompts.GRADE_SYSTEM,
            user=str(
                {
                    "profile": state.get("profile"),
                    "themes": state.get("themes"),
                    "search_query": state.get("search_query"),
                    "retrieved": catalog,
                }
            ),
            temperature=0.0,
            max_tokens=300,
        )
        data = parse_json_object(raw)
        relevant = bool(data.get("relevant"))
        refined = str(data.get("refined_query") or state.get("search_query") or "").strip()
        updates: AgentState = {
            **state,
            "grade_pass": relevant,
            "grade_reason": str(data.get("reason") or ""),
        }
        if not relevant and refined:
            updates["search_query"] = refined
            updates["secondary_query"] = ""
        return updates

    def refine(state: AgentState) -> AgentState:
        return {
            **state,
            "retry_count": int(state.get("retry_count") or 0) + 1,
            "grade_pass": False,
        }

    def generate_recommendation(state: AgentState) -> AgentState:
        retrieved = state.get("retrieved") or []
        required_family: str | None = None
        for item in state.get("match_meta") or []:
            if isinstance(item, dict) and item.get("family"):
                required_family = str(item["family"])
                break
        # Drop off-family candidates before the LLM sees them
        if required_family:
            retrieved = [
                r
                for r in retrieved
                if family_for_free_category(str(r.get("category") or "")) == required_family
            ]
        allowed_ids = {int(r["id"]) for r in retrieved}
        catalog = [
            {
                "id": r["id"],
                "title": r["title"],
                "description": r["description"][:280],
                "category": r["category"],
                "level": r["level"],
            }
            for r in retrieved
        ]

        if not catalog:
            return {
                **state,
                "narrative": "",
                "resource_ids": [],
                "match_meta": state.get("match_meta") or [],
                "error": "no_family_consistent_candidates",
            }

        # LLM CALL — this is where reasoning/decision-making actually happens
        # Selects among Chroma-returned catalog IDs only — never from the family map
        raw = chat_completion(
            system=prompts.GENERATE_SYSTEM,
            user=str(
                {
                    "profile": state.get("profile"),
                    "themes": state.get("themes"),
                    "udemy_signal": state.get("udemy_signal"),
                    "catalog": catalog,
                }
            ),
            temperature=0.4,
            max_tokens=500,
        )
        data = parse_json_object(raw)
        narrative = str(data.get("narrative") or "").strip()
        # Models sometimes leak "(id: 6)" into prose — strip for UI
        narrative = re.sub(r"\s*\(id:\s*\d+\)", "", narrative, flags=re.IGNORECASE)
        narrative = re.sub(r"\bid:\s*\d+\b", "", narrative, flags=re.IGNORECASE)
        narrative = re.sub(r"\s{2,}", " ", narrative).strip()
        grounded: list[int] = []
        for item in data.get("resource_ids") or []:
            try:
                rid = int(item)
            except (TypeError, ValueError):
                continue
            if rid in allowed_ids and rid not in grounded:
                grounded.append(rid)

        target = min(settings.AGENT_TARGET_RESOURCES, len(retrieved))
        # 1 hero + up to 2 secondary — never a full coverage set
        target = max(1, min(target, 3))
        if not grounded:
            grounded = [int(r["id"]) for r in retrieved[:target]]
        else:
            for r in retrieved:
                if len(grounded) >= target:
                    break
                rid = int(r["id"])
                if rid not in grounded:
                    grounded.append(rid)
        grounded = grounded[:target]

        rows = db.query(FreeResource).filter(FreeResource.id.in_(grounded)).all() if grounded else []
        by_id = {row.id: row for row in rows}
        # Family sanity on final picks (hero must match)
        sane: list[int] = []
        for rid in grounded:
            row = by_id.get(rid)
            if row is None:
                continue
            hit_fam = family_for_free_category(row.category)
            if required_family and hit_fam and hit_fam != required_family:
                continue
            sane.append(rid)
        grounded = sane

        if not grounded:
            return {
                **state,
                "narrative": "",
                "resource_ids": [],
                "match_meta": state.get("match_meta") or [],
                "error": "hero_family_mismatch",
            }

        dominant = str(data.get("dominant_pattern") or "").strip()
        summary = state.get("source_summary") or {}
        if not dominant:
            dominant = str(summary.get("dominant_pattern") or "") or " and ".join(
                (state.get("themes") or [])[:2]
            )

        if not narrative:
            hero_title = next(
                (str(r.get("title") or "") for r in retrieved if int(r["id"]) == grounded[0]),
                "this free path",
            )
            focus = dominant or "what you've been exploring"
            narrative = (
                f"Start with {hero_title} — it matches how you've been digging into {focus}."
            )
        else:
            # Ensure the narrative references the chosen hero title to avoid UI mismatch
            try:
                hero_row = next((r for r in retrieved if int(r["id"]) == grounded[0]), None)
                hero_title = hero_row.get("title") if hero_row else None
                if hero_title and hero_title not in narrative:
                    # Prepend a short hero-focused clause to anchor the narrative
                    narrative = f"Start with {hero_title}. " + narrative
            except Exception:
                # Don't let post-processing break the agent flow
                pass
        if len(narrative) > 240:
            narrative = narrative[:237].rsplit(" ", 1)[0] + "…"

        # Themes + dominant pattern for delivery UX (toast copy)
        match_meta: list[dict[str, Any]] = [{"theme": t} for t in (state.get("themes") or [])[:2]]
        if dominant:
            match_meta.append({"dominant_pattern": dominant})
        for item in state.get("match_meta") or []:
            if isinstance(item, dict) and "free_categories" in item:
                match_meta.append(item)

        return {
            **state,
            "narrative": narrative,
            "resource_ids": grounded,
            "match_meta": match_meta,
        }

    def store(state: AgentState) -> AgentState:
        ids = state.get("resource_ids") or []
        if not ids:
            logger.warning(
                "store skipped — empty resource_ids user=%s error=%s",
                state.get("user_id"),
                state.get("error"),
            )
            return {**state, "recommendation_id": None}

        now = datetime.now(timezone.utc)
        rec = Recommendation(
            user_id=state["user_id"],
            narrative=state.get("narrative") or "",
            resource_ids=ids,
            match_meta=state.get("match_meta") or [],
            source_summary=state.get("source_summary") or {},
            trigger_reason=state.get("trigger_reason") or "",
            generated_at=now,
            expires_at=now + timedelta(hours=settings.RECOMMENDATION_TTL_HOURS),
        )
        db.add(rec)
        db.commit()
        db.refresh(rec)
        logger.info(
            "agent stored id=%s user=%s resources=%s themes=%s summary=%s",
            rec.id,
            rec.user_id,
            rec.resource_ids,
            state.get("themes"),
            (state.get("source_summary") or {}).get("top_categories"),
        )
        return {**state, "recommendation_id": rec.id}

    return {
        "summarize_activity": summarize_activity,
        "retrieve": retrieve,
        "grade_retrieval": grade_retrieval,
        "refine": refine,
        "generate_recommendation": generate_recommendation,
        "store": store,
    }
