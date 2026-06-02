"""Shared AI provider configuration, headers, and fallback chain logic."""

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

# --- Provider URLs ---
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
BLUESMINDS_API_URL = "https://api.bluesminds.com/v1/chat/completions"

# Provider configs: (url, key_env_name, model, name)
PROVIDERS = [
    {
        "name": "Bluesminds",
        "url": BLUESMINDS_API_URL,
        "key_env": "BLUESMINDS_API_KEY",
        "model": "gpt-4o-mini",
    },
    {
        "name": "OpenRouter",
        "url": OPENROUTER_API_URL,
        "key_env": "OPENROUTER_API_KEY",
        "model": "openrouter/free",
    },
]

# Fallback models for Bluesminds if primary fails
BLUESMINDS_FALLBACK_MODELS = ["gpt-4o-mini", "qwen3.6-27b"]


def build_provider_headers(provider: dict, api_key: str) -> dict:
    """Build request headers for a provider."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider["name"] == "OpenRouter":
        headers["HTTP-Referer"] = "https://markflow.local"
        headers["X-Title"] = "MarkFlow"
    return headers


def get_models_for_provider(provider: dict) -> list:
    """Return the list of models to try for a given provider."""
    if provider["name"] == "Bluesminds":
        return BLUESMINDS_FALLBACK_MODELS
    return [provider["model"]]


async def call_provider_chain(
    request_builder,
    chain_timeout: float,
    per_request_timeout: float,
    min_remaining: float = 5.0,
    http_timeout: float = 30.0,
) -> str:
    """Run the provider fallback chain with timeout budget.

    Args:
        request_builder: async callable(client, provider, model, timeout) -> str
            Builds and sends the request for one provider/model attempt.
        chain_timeout: max wall-clock time for the entire chain.
        per_request_timeout: max time for a single request.
        min_remaining: stop trying if less than this time remains.
        http_timeout: httpx.AsyncClient connect/total timeout.

    Returns:
        The successful response string.

    Raises:
        The last exception encountered, or ValueError if all skipped.
    """
    last_error = None
    start = time.monotonic()

    async with httpx.AsyncClient(timeout=http_timeout) as client:
        for provider in PROVIDERS:
            elapsed = time.monotonic() - start
            remaining = chain_timeout - elapsed
            if remaining < min_remaining:
                logger.warning("Chain timeout approaching (%.1fs elapsed), skipping remaining providers", elapsed)
                break

            api_key = os.getenv(provider["key_env"])
            if not api_key:
                logger.info("Skipping %s — %s not set", provider["name"], provider["key_env"])
                continue

            models = get_models_for_provider(provider)

            for model in models:
                elapsed = time.monotonic() - start
                remaining = chain_timeout - elapsed
                if remaining < min_remaining:
                    break

                request_timeout = min(per_request_timeout, remaining)

                try:
                    result = await request_builder(client, provider, model, request_timeout)
                    logger.info(
                        "Success from %s/%s (%.1fs)",
                        provider["name"], model, time.monotonic() - start,
                    )
                    return result
                except httpx.HTTPStatusError as e:
                    last_error = e
                    logger.warning(
                        "%s/%s HTTP %d: %s",
                        provider["name"], model, e.response.status_code, str(e),
                    )
                    if e.response.status_code in (401, 403):
                        break
                except (httpx.TimeoutException, httpx.ConnectError) as e:
                    last_error = e
                    logger.warning("%s/%s timeout/connection: %s", provider["name"], model, str(e))
                except Exception as e:
                    last_error = e
                    logger.warning("%s/%s error: %s", provider["name"], model, str(e))

    raise last_error or ValueError("All AI providers failed")
