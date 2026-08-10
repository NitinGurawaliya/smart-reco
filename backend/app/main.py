from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.database import Base, engine
from app.routers import auth as auth_router
from app.routers import catalog as catalog_router
from app.routers import events as events_router
from app.routers import recommendations as recommendations_router
import app.models  # noqa: F401 — register models on Base.metadata
from app import observability
import logging
from starlette.requests import Request
from app.pipeline_log import pipe
import json

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from app.config import settings

    logger.info(
        "[SmartReco] LLM_PROVIDER=%s model=%s key_set=%s",
        settings.LLM_PROVIDER,
        settings.llm_model,
        bool(settings.llm_api_key),
    )
    Base.metadata.create_all(bind=engine)
    # Additive column for existing Neon DBs (create_all won't alter)
    with engine.begin() as conn:
        # Only attempt Postgres/Neon-specific ALTERs when the DB dialect
        # supports them. SQLite will error on `IF NOT EXISTS ... JSONB`.
        try:
            dialect_name = engine.dialect.name
        except Exception:
            dialect_name = None

        if dialect_name and dialect_name.startswith("postgres"):
            conn.execute(
                text(
                    "ALTER TABLE recommendations "
                    "ADD COLUMN IF NOT EXISTS match_meta JSONB DEFAULT '[]'::jsonb"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE recommendations "
                    "ADD COLUMN IF NOT EXISTS source_summary JSONB DEFAULT '{}'::jsonb"
                )
            )
    # Warm embedding model + Chroma so first Refresh isn't stuck on HF download
    try:
        from app.vector_store import get_collection, get_embedding_model

        get_embedding_model()
        n = get_collection().count()
        logger.info("[SmartReco] embeddings ready chroma_docs=%s", n)
    except Exception as exc:  # noqa: BLE001 — startup should not die on RAG warm-up
        logger.warning("[SmartReco] embedding warm-up skipped: %s", exc)
    yield


app = FastAPI(title="SmartReco", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    try:
        method = request.method
        path = request.url.path
        # attempt to read JSON body (non-blocking) and truncate
        body_bytes = await request.body()
        body_text = None
        if body_bytes:
            try:
                parsed = json.loads(body_bytes.decode("utf-8"))
                body_text = str(parsed)
            except Exception:
                body_text = body_bytes.decode("utf-8", errors="ignore")
        pipe("HTTP_REQUEST", method=method, path=path, body=(body_text[:500] if body_text else None))
    except Exception:
        # never fail the request due to logging
        pass
    response = await call_next(request)
    return response

# Allow Figma Make preview + local Vite during hackathon/dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router.router)
app.include_router(catalog_router.router)
app.include_router(events_router.router)
app.include_router(recommendations_router.router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"db": "connected"}
