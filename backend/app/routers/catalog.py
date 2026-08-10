from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models import FreeResource, User
from app.schemas import FreeResourceCreate, FreeResourceOut, FreeResourceUpdate
from app import vector_store

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/catalog", tags=["catalog"])


def _sync_to_chroma(resource: FreeResource) -> str:
    """Upsert resource into Chroma. Returns sync_status: synced | failed."""
    try:
        vector_store.upsert_resource(
            resource_id=resource.id,
            title=resource.title,
            description=resource.description,
            topic_tags=resource.topic_tags or [],
            level=resource.level,
            category=resource.category,
            youtube_url=resource.youtube_url,
        )
        return "synced"
    except Exception:
        logger.exception("Chroma upsert failed for resource_id=%s", resource.id)
        return "failed"


@router.get("", response_model=list[FreeResourceOut])
def list_resources(
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return db.query(FreeResource).order_by(FreeResource.id.asc()).all()


@router.get("/{resource_id}", response_model=FreeResourceOut)
def get_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    resource = db.get(FreeResource, resource_id)
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")
    return resource


@router.post("", response_model=FreeResourceOut, status_code=status.HTTP_201_CREATED)
def create_resource(
    body: FreeResourceCreate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    resource = FreeResource(
        title=body.title,
        description=body.description,
        topic_tags=body.topic_tags,
        youtube_url=body.youtube_url,
        level=body.level,
        category=body.category,
        sync_status="pending",
    )
    db.add(resource)
    db.commit()
    db.refresh(resource)

    resource.sync_status = _sync_to_chroma(resource)
    db.commit()
    db.refresh(resource)
    return resource


@router.put("/{resource_id}", response_model=FreeResourceOut)
def update_resource(
    resource_id: int,
    body: FreeResourceUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    resource = db.get(FreeResource, resource_id)
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    data = body.model_dump(exclude_unset=True)
    for key, value in data.items():
        setattr(resource, key, value)

    resource.sync_status = "pending"
    db.commit()
    db.refresh(resource)

    resource.sync_status = _sync_to_chroma(resource)
    db.commit()
    db.refresh(resource)
    return resource


@router.delete("/{resource_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    resource = db.get(FreeResource, resource_id)
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    try:
        vector_store.delete_resource(resource_id)
    except Exception:
        logger.exception("Chroma delete failed for resource_id=%s (Postgres delete continues)", resource_id)

    db.delete(resource)
    db.commit()
    return None


@router.post("/{resource_id}/resync", response_model=FreeResourceOut)
def resync_resource(
    resource_id: int,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    resource = db.get(FreeResource, resource_id)
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resource not found")

    resource.sync_status = _sync_to_chroma(resource)
    db.commit()
    db.refresh(resource)
    return resource
