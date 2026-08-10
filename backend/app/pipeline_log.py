"""Pipeline trace helpers — timestamped INFO logs for trigger debugging."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

logger = logging.getLogger("smartreco.pipeline")


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")[:-3]


def pipe(stage: str, **fields: object) -> None:
    parts = " ".join(f"{k}={v!r}" for k, v in fields.items())
    msg = f"[PIPE {_ts()}] {stage} {parts}".rstrip()
    logger.info(msg)
    # Also print so uvicorn console always shows traces during demos
    print(msg, flush=True)
