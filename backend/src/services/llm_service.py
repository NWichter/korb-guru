"""LLM service — chat completions via OpenRouter.

Primary: Apify OpenRouter proxy (cheaper, uses APIFY_TOKEN).
Fallback: Direct OpenRouter API (uses OPENROUTER_API_KEY).
"""

import json
import logging
import re

import httpx
from fastapi import HTTPException

from ..config import get_settings

logger = logging.getLogger(__name__)

_APIFY_URL = "https://openrouter.apify.actor/api/v1/chat/completions"
_OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
_TIMEOUT = 30.0

VALID_CATEGORIES = frozenset(
    {
        "dairy",
        "meat",
        "fish",
        "vegetables",
        "fruits",
        "bakery",
        "frozen",
        "beverages",
        "snacks",
        "pantry",
        "household",
        "personal_care",
        "other",
    }
)


def _sanitize(text: str) -> str:
    """Strip control characters and limit length."""
    cleaned = re.sub(r"[\x00-\x1f\x7f]", "", text)
    return cleaned[:200]


async def _chat_completion(
    messages: list[dict[str, str]],
    model: str,
    max_tokens: int | None = None,
) -> str:
    """Try Apify proxy first, fall back to direct OpenRouter."""
    settings = get_settings()
    payload: dict = {"model": model, "messages": messages}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens

    # Primary: Apify proxy
    if settings.apify_token:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    _APIFY_URL,
                    headers={
                        "Authorization": f"Bearer {settings.apify_token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except Exception as exc:
            logger.warning("Apify proxy failed, trying direct OpenRouter: %s", exc)

    # Fallback: direct OpenRouter
    if settings.openrouter_api_key:
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
                resp = await client.post(
                    _OPENROUTER_URL,
                    headers={
                        "Authorization": f"Bearer {settings.openrouter_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                resp.raise_for_status()
                return resp.json()["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            logger.error(
                "OpenRouter HTTP %s: %s",
                exc.response.status_code,
                exc.response.text,
            )
        except (httpx.RequestError, KeyError, IndexError, json.JSONDecodeError) as exc:
            logger.error("OpenRouter request error: %s", exc)

    if not settings.apify_token and not settings.openrouter_api_key:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured (APIFY_TOKEN / OPENROUTER_API_KEY)",
        )

    raise HTTPException(
        status_code=503,
        detail="All LLM providers are temporarily unavailable",
    )


async def ask_llm(
    prompt: str,
    system: str = "",
    model: str | None = None,
) -> str:
    """Send a chat completion and return the reply text."""
    settings = get_settings()
    resolved_model = model or settings.openrouter_default_model

    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    return await _chat_completion(messages, resolved_model)


async def categorize_product(
    product_name: str, product_description: str | None = None
) -> str:
    """Categorize a product into a grocery category using LLM."""
    name = _sanitize(product_name)
    desc = ""
    if product_description:
        desc = f"\nDescription: {_sanitize(product_description)}"
    prompt = (
        "Categorize this Swiss grocery product into exactly one category.\n"
        "Categories: dairy, meat, fish, vegetables, fruits, bakery, "
        "frozen, beverages, snacks, pantry, household, personal_care, other\n\n"
        f"Product: {name}{desc}\n\n"
        "Reply with ONLY the category name, nothing else."
    )
    try:
        result = await ask_llm(prompt, model="anthropic/claude-3-haiku")
        # Normalize: strip whitespace, quotes, punctuation the LLM may add
        category = re.sub(r"[\"'`.,;:!?\s]+", "", result).lower()
        return category if category in VALID_CATEGORIES else "other"
    except Exception as e:
        logger.warning("LLM categorization failed for %r: %s", product_name, e)
        return "other"


async def enrich_product_description(product_name: str, retailer: str) -> str:
    """Generate a short product description using LLM."""
    name = _sanitize(product_name)
    ret = _sanitize(retailer)
    prompt = (
        "Write a one-sentence product description (max 20 words) "
        "for this Swiss grocery product.\n\n"
        f"Product: {name}\nRetailer: {ret}\n\n"
        "Reply with ONLY the description, nothing else."
    )
    try:
        return await ask_llm(prompt, model="anthropic/claude-3-haiku")
    except Exception as e:
        logger.warning("LLM enrichment failed for %r: %s", product_name, e)
        return ""


async def extract_ingredients(product_name: str) -> list[str]:
    """Extract likely ingredients from a product name using LLM."""
    name = _sanitize(product_name)
    prompt = (
        "Extract the main food ingredients from this product name. "
        "Return as comma-separated list.\n"
        'If it\'s not a food product, return "none".\n\n'
        f"Product: {name}\n\n"
        "Reply with ONLY the comma-separated ingredients, nothing else."
    )
    try:
        result = await ask_llm(prompt, model="anthropic/claude-3-haiku")
        if result.strip().lower() == "none":
            return []
        return [i.strip() for i in result.split(",") if i.strip()]
    except Exception as e:
        logger.warning("LLM ingredient extraction failed for %r: %s", product_name, e)
        return []
