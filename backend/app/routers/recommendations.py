from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
import logging

from app.agent.runner import run_agent
from app.auth import get_current_user
from app.database import get_db
from app.models import FreeResource, User
from app.schemas import (
    AgentStatusOut,
    FreeResourceOut,
    LatestRecommendationResponse,
    RecommendationOut,
    RecommendedResourceOut,
)
from app.trigger import get_agent_status, get_latest_recommendation as fetch_latest_recommendation

router = APIRouter(prefix="/recommendations", tags=["recommendations"])

logger = logging.getLogger(__name__)


def hydrate_recommendation(db: Session, rec) -> RecommendationOut:
    resource_ids = rec.resource_ids or []
    meta_list = getattr(rec, "match_meta", None) or []
    because_by_id: dict[int, str] = {}
    for item in meta_list:
        if not isinstance(item, dict):
            continue
        try:
            because_by_id[int(item["resource_id"])] = str(item.get("because") or "")
        except (KeyError, TypeError, ValueError):
            continue

    resources: list[RecommendedResourceOut] = []
    if resource_ids:
        rows = db.query(FreeResource).filter(FreeResource.id.in_(resource_ids)).all()
        by_id = {r.id: r for r in rows}
        for rid in resource_ids:
            row = by_id.get(rid)
            if row is None:
                continue
            base = FreeResourceOut.model_validate(row)
            resources.append(
                RecommendedResourceOut(
                    **base.model_dump(),
                    because=because_by_id.get(rid) or None,
                )
            )

    summary = getattr(rec, "source_summary", None) or {}
    if not isinstance(summary, dict):
        summary = {}

    return RecommendationOut(
        id=rec.id,
        user_id=rec.user_id,
        narrative=rec.narrative,
        resource_ids=resource_ids,
        trigger_reason=rec.trigger_reason,
        generated_at=rec.generated_at,
        expires_at=rec.expires_at,
        resources=resources,
        match_meta=list(meta_list) if isinstance(meta_list, list) else [],
        source_summary=summary,
    )


@router.get("/status", response_model=AgentStatusOut)
def recommendation_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Progress toward next agent run — instant, no LLM."""
    logger.debug("RECOMMENDATION_STATUS user=%s", current_user.id)
    return AgentStatusOut(**get_agent_status(db, current_user.id))


@router.get("/latest", response_model=LatestRecommendationResponse)
def latest_recommendation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Serve the cached recommendation instantly — never calls the LLM."""
    logger.debug("LATEST_RECOMMENDATION user=%s", current_user.id)
    rec = fetch_latest_recommendation(db, current_user.id)
    if rec is None:
        return LatestRecommendationResponse(recommendation=None)
    return LatestRecommendationResponse(recommendation=hydrate_recommendation(db, rec))


@router.post("/refresh", response_model=LatestRecommendationResponse)
def refresh_recommendation(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Force a new recommendation from latest activity (demo / manual refresh)."""
    logger.info("REFRESH_RECOMMENDATION manual user=%s", current_user.id)
    rec = run_agent(db, user_id=current_user.id, trigger_reason="manual_refresh")
    if rec is None:
        existing = fetch_latest_recommendation(db, current_user.id)
        if existing is None:
            return LatestRecommendationResponse(recommendation=None)
        return LatestRecommendationResponse(recommendation=hydrate_recommendation(db, existing))
    return LatestRecommendationResponse(recommendation=hydrate_recommendation(db, rec))
