from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

import chromadb
from chromadb.api.models.Collection import Collection
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

COLLECTION_NAME = "free_resources"


@lru_cache(maxsize=1)
def get_embedding_model() -> SentenceTransformer:
    return SentenceTransformer(settings.EMBEDDING_MODEL)


@lru_cache(maxsize=1)
def get_chroma_client() -> chromadb.PersistentClient:
    return chromadb.PersistentClient(path=settings.CHROMA_PATH)


def get_collection() -> Collection:
    return get_chroma_client().get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def build_document_text(
    *,
    title: str,
    description: str,
    topic_tags: list[str] | None,
    level: str,
    category: str,
) -> str:
    tags = ", ".join(topic_tags or [])
    return (
        f"{title}\n{description}\n"
        f"Topics: {tags}\nLevel: {level}\nCategory: {category}"
    )


def embed_texts(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    vectors = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vectors]


def upsert_resource(
    *,
    resource_id: int,
    title: str,
    description: str,
    topic_tags: list[str] | None,
    level: str,
    category: str,
    youtube_url: str,
) -> None:
    doc = build_document_text(
        title=title,
        description=description,
        topic_tags=topic_tags,
        level=level,
        category=category,
    )
    embedding = embed_texts([doc])[0]
    get_collection().upsert(
        ids=[str(resource_id)],
        embeddings=[embedding],
        documents=[doc],
        metadatas=[
            {
                "resource_id": resource_id,
                "title": title[:500],
                "category": category,
                "level": level,
                "youtube_url": youtube_url[:500],
            }
        ],
    )


def delete_resource(resource_id: int) -> None:
    collection = get_collection()
    rid = str(resource_id)
    existing = collection.get(ids=[rid])
    if existing and existing.get("ids"):
        collection.delete(ids=[rid])


def query_similar(
    query: str,
    *,
    top_k: int = 5,
    category: str | None = None,
    level: str | None = None,
) -> list[dict[str, Any]]:
    where: dict[str, Any] | None = None
    filters: list[dict[str, Any]] = []
    if category:
        filters.append({"category": category})
    if level:
        filters.append({"level": level})
    if len(filters) == 1:
        where = filters[0]
    elif len(filters) > 1:
        where = {"$and": filters}

    embedding = embed_texts([query])[0]
    kwargs: dict[str, Any] = {
        "query_embeddings": [embedding],
        "n_results": top_k,
        "include": ["documents", "metadatas", "distances"],
    }
    if where:
        kwargs["where"] = where

    result = get_collection().query(**kwargs)
    ids = (result.get("ids") or [[]])[0]
    docs = (result.get("documents") or [[]])[0]
    metas = (result.get("metadatas") or [[]])[0]
    dists = (result.get("distances") or [[]])[0]

    hits: list[dict[str, Any]] = []
    for i, rid in enumerate(ids):
        hits.append(
            {
                "id": rid,
                "resource_id": int(metas[i].get("resource_id", rid)) if metas else int(rid),
                "document": docs[i] if docs else "",
                "metadata": metas[i] if metas else {},
                "distance": dists[i] if dists else None,
            }
        )
    return hits
