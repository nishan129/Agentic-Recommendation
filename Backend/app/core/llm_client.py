"""
Thin, swappable LLM client. Groq today (fast + cheap, good enough for
both reasoning and narrative generation); swap providers by editing only
this file — every caller just uses `complete_json` / `complete_text`.
"""
import json
import logging

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from app.core.config import settings

logger = logging.getLogger(__name__)

MODEL = "openai/gpt-4o-mini"
MESHAPI_OPENAI_BASE_URL = f"{settings.MESHAPI_BASE_URL}/v1"

_client: ChatOpenAI | None = None


def get_llm_client(temperature: float = 0.3) -> ChatOpenAI:
    """Build (or reuse) a ChatOpenAI client pointed at MeshAPI's
    OpenAI-compatible endpoint.

    Note: temperature is bound per-call rather than cached globally, since
    complete_json and complete_text use different defaults (0.3 vs 0.7).
    """
    if not settings.MESHAPI_API_KEY:
        raise RuntimeError(
            "MESHAPI_API_KEY is not set. Add it to your environment "
            "(see .env.example) before calling the LLM client."
        )
    return ChatOpenAI(
        base_url=MESHAPI_OPENAI_BASE_URL,
        api_key=settings.MESHAPI_API_KEY,
        model=MODEL,
        temperature=temperature,
        timeout=settings.LLM_TIMEOUT_SECONDS,
    )


def complete_json(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.3,
) -> dict:
    """Call the LLM and parse a JSON object out of its response. Used for
    the intent-reasoning step, where we need structured output (interest
    summary + search terms), not free-form prose."""
    client = get_llm_client(temperature=temperature)
    if model:
        client = client.bind(model=model)

    client = client.bind(response_format={"type": "json_object"})

    response = client.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )
    raw = response.content
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.error("LLM did not return valid JSON: %r", raw)
        raise ValueError(f"LLM returned non-JSON output: {exc}") from exc


def complete_text(
    system_prompt: str,
    user_prompt: str,
    model: str | None = None,
    temperature: float = 0.7,
) -> str:
    """Call the LLM for free-form text — used for the persuasive
    narrative, where we want natural prose, not JSON."""
    client = get_llm_client(temperature=temperature)
    if model:
        client = client.bind(model=model)

    response = client.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]
    )
    return response.content.strip()