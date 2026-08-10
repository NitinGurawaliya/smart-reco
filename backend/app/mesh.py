"""OpenAI-compatible LLM provider adapter (Mesh | Groq | Grok/xAI).

Agent nodes must call ``chat_completion`` / ``parse_json_object`` only.
Provider-specific keys, base URLs, model names, and 429 retries live HERE —
switching ``LLM_PROVIDER`` (+ matching API key) in ``.env`` requires no
changes in ``agent/nodes.py`` or the LangGraph graph.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from openai import OpenAI, RateLimitError

from app.config import settings

logger = logging.getLogger(__name__)


def get_llm_client() -> OpenAI:
    """Build a client from config — mesh | groq | grok are interchangeable."""
    key = settings.llm_api_key
    if not key:
        raise RuntimeError(
            f"Missing API key for LLM_PROVIDER={settings.LLM_PROVIDER!r}. "
            "Set MESH_API_KEY (mesh), GROQ_API_KEY (groq), or XAI_API_KEY (grok)."
        )
    logger.info(
        "LLM client provider=%s base_url=%s model=%s",
        settings.LLM_PROVIDER,
        settings.llm_base_url,
        settings.llm_model,
    )
    return OpenAI(api_key=key, base_url=settings.llm_base_url)


# Historical alias
get_mesh_client = get_llm_client


def chat_completion(
    *,
    system: str,
    user: str,
    temperature: float = 0.2,
    max_tokens: int = 800,
) -> str:
    """Provider-agnostic chat completion (retries on generic RateLimitError)."""
    client = get_llm_client()
    last_err: Exception | None = None
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=settings.llm_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = response.choices[0].message.content or ""
            return content.strip()
        except RateLimitError as exc:
            last_err = exc
            wait = 2.0 * (attempt + 1)
            logger.warning(
                "LLM rate limit provider=%s attempt=%s wait=%.1fs",
                settings.LLM_PROVIDER,
                attempt + 1,
                wait,
            )
            time.sleep(wait)
    assert last_err is not None
    raise last_err


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract a JSON object from model output (raw or fenced) — provider-agnostic."""
    text = text.strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, flags=re.DOTALL)
    if fence:
        return json.loads(fence.group(1))

    brace = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if brace:
        return json.loads(brace.group(0))

    raise ValueError(f"Model did not return valid JSON object: {text[:200]}")
