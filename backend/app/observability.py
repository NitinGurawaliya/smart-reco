"""Minimal observability shim for local tests.

Configures Python logging for the backend and provides `agent_run_config`
used by the agent runner. Importing this module will configure a sensible
console logger for local development so pipeline traces are visible.
"""
from __future__ import annotations

import logging
from typing import Dict


THIRD_PARTY_LOGGERS = (
    "chromadb",
    "chromadb.config",
    "huggingface_hub",
    "huggingface_hub.utils._http",
    "httpcore",
    "httpcore.connection",
    "httpcore.http11",
    "httpx",
    "openai",
    "openai._base_client",
    "sentence_transformers",
    "sentence_transformers.base.model",
    "sentence_transformers.base.modules.transformer",
    "urllib3",
)


def configure_logging(level: int | str = logging.DEBUG) -> None:
    """Configure root logging if not already configured."""
    fmt = "%(asctime)s %(levelname)s %(name)s: %(message)s"
    # BasicConfig is idempotent for handlers — guard to avoid duplicate handlers
    if not logging.getLogger().handlers:
        logging.basicConfig(level=level, format=fmt)
    logging.getLogger().setLevel(level)
    for logger_name in THIRD_PARTY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


configure_logging()


def agent_run_config(*, user_id: int, trigger_reason: str) -> Dict:
    """Shim for attaching tracing/telemetry context to agent runs.

    In production this would return tracing context; for local tests we keep
    it simple and return an empty dict.
    """
    return {}
