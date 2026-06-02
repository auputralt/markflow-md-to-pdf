"""AI-powered style recommendation for PDF documents."""

import json
import logging
import re

from providers import (
    build_provider_headers,
    call_provider_chain,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a document design expert. Analyze the given content and recommend \
the best PDF style options. Return ONLY a JSON object with these exact keys \
and values from the allowed options:

{
  "theme": "light" | "dark" | "sepia" | "cream",
  "font": "sans-serif" | "serif" | "mono" | "academic",
  "layout": "single" | "two-column" | "compact" | "wide",
  "page_size": "a4" | "letter" | "legal",
  "header_footer": array of "page_numbers" | "title" | "date",
  "code_blocks": "highlighted" | "plain" | "bordered" | "minimal",
  "tables": "striped" | "clean" | "grid",
  "extras": array of "toc" | "watermark"
}

Rules:
- Code-heavy content → mono font, highlighted code blocks
- Academic/educational content → serif or academic font, toc in extras
- Data-heavy content → clean or grid tables
- Long documents → compact layout, page numbers + title in header_footer
- Creative/informal content → sans-serif, relaxed layout
- Output ONLY the JSON object, no markdown fences, no explanation.
"""

PROMPT_AWARE_SYSTEM_PROMPT = """\
You are a document design expert. Analyze the given content and the user's style \
description to recommend the best PDF style options.

IMPORTANT: Return ALL valid options for each category, with a "recommended" field \
indicating the AI's top pick based on the content and user's style preferences.

Return ONLY a JSON object with this exact structure:

{
  "theme": { "recommended": "light", "options": ["light", "dark", "sepia", "cream"] },
  "font": { "recommended": "sans-serif", "options": ["sans-serif", "serif", "mono", "academic"] },
  "layout": { "recommended": "single", "options": ["single", "two-column", "compact", "wide"] },
  "page_size": { "recommended": "a4", "options": ["a4", "letter", "legal"] },
  "header_footer": { "recommended": ["page_numbers"], "options": ["page_numbers", "title", "date"] },
  "code_blocks": { "recommended": "bordered", "options": ["highlighted", "plain", "bordered", "minimal"] },
  "tables": { "recommended": "striped", "options": ["striped", "clean", "grid"] },
  "extras": { "recommended": [], "options": ["toc", "watermark"] }
}

Rules:
- If the user provided a style description, heavily weight that in your recommendation.
- Code-heavy content → mono font, highlighted code blocks
- Academic/educational content → serif/academic font, toc
- Data-heavy content → clean or grid tables
- Long documents → compact, page numbers + title
- Creative/informal → sans-serif, relaxed
- Always include ALL options in each category.
- Output ONLY the JSON object, no markdown fences, no explanation.
"""

ALLOWED_VALUES = {
    "theme": ["light", "dark", "sepia", "cream"],
    "font": ["sans-serif", "serif", "mono", "academic"],
    "layout": ["single", "two-column", "compact", "wide"],
    "page_size": ["a4", "letter", "legal"],
    "header_footer": ["page_numbers", "title", "date"],
    "code_blocks": ["highlighted", "plain", "bordered", "minimal"],
    "tables": ["striped", "clean", "grid"],
    "extras": ["toc", "watermark"],
}

DEFAULT_RECOMMENDATION = {
    "theme": "light",
    "font": "sans-serif",
    "layout": "single",
    "page_size": "a4",
    "header_footer": ["page_numbers"],
    "code_blocks": "bordered",
    "tables": "striped",
    "extras": [],
}

RECOMMEND_TIMEOUT = 15.0
PER_REQUEST_TIMEOUT = 12.0


def parse_recommendation(text: str) -> dict:
    """Parse AI response into a validated recommendation dict."""
    text = text.strip()
    # Strip markdown fences if present
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON object — use balanced brace matching for nesting
        depth = 0
        start = text.find("{")
        if start >= 0:
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            data = json.loads(text[start : i + 1])
                            break
                        except json.JSONDecodeError:
                            break
            else:
                logger.warning("Failed to parse AI recommendation as JSON")
                return DEFAULT_RECOMMENDATION.copy()
        else:
            logger.warning("Failed to parse AI recommendation as JSON")
            return DEFAULT_RECOMMENDATION.copy()

    # Validate and sanitize each key
    result = {}
    for key, allowed in ALLOWED_VALUES.items():
        value = data.get(key)
        if isinstance(value, list):
            result[key] = [v for v in value if v in allowed]
        elif isinstance(value, str) and value in allowed:
            result[key] = value
        else:
            result[key] = DEFAULT_RECOMMENDATION[key]

    return result


def parse_prompt_aware_recommendation(text: str) -> dict:
    """Parse nested { category: { recommended, options } } format from AI response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)

    data = {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        depth = 0
        start = text.find("{")
        if start >= 0:
            for i in range(start, len(text)):
                if text[i] == "{":
                    depth += 1
                elif text[i] == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            data = json.loads(text[start : i + 1])
                            break
                        except json.JSONDecodeError:
                            break

    result = {}
    for key, allowed in ALLOWED_VALUES.items():
        cat_data = data.get(key)
        if isinstance(cat_data, dict):
            # Validate options list
            options = cat_data.get("options", [])
            valid_options = [v for v in options if v in allowed]
            if not valid_options:
                valid_options = list(allowed)

            # Validate recommended value
            recommended = cat_data.get("recommended", DEFAULT_RECOMMENDATION[key])
            if isinstance(recommended, list):
                recommended = [v for v in recommended if v in allowed]
            elif isinstance(recommended, str) and recommended in allowed:
                pass
            else:
                recommended = DEFAULT_RECOMMENDATION[key]

            result[key] = {"recommended": recommended, "options": valid_options}
        else:
            result[key] = {"recommended": DEFAULT_RECOMMENDATION[key], "options": list(allowed)}

    return result


def _flat_to_nested(flat: dict) -> dict:
    """Convert old flat recommendation dict to new nested format."""
    result = {}
    for key, value in flat.items():
        if key in ALLOWED_VALUES:
            result[key] = {"recommended": value, "options": list(ALLOWED_VALUES[key])}
    return result


async def _request_recommend(client, provider, model, timeout, user_message, system_prompt):
    """Request builder for style recommendations."""
    import os

    api_key = os.getenv(provider["key_env"])
    if not api_key:
        raise ValueError(f"{provider['key_env']} not set")

    headers = build_provider_headers(provider, api_key)
    body = {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "max_tokens": 800,
        "temperature": 0.3,
    }

    response = await client.post(provider["url"], headers=headers, json=body, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    if not data.get("choices") or not data["choices"][0].get("message"):
        raise ValueError(f"Unexpected response from {provider['name']}")

    return data["choices"][0]["message"]["content"]


async def recommend_styles(content: str, style_prompt: str = "") -> dict:
    """Get AI style recommendations. Returns nested dict or defaults."""
    snippet = content[:2000]
    has_prompt = bool(style_prompt.strip())

    if has_prompt:
        user_msg = (
            f'The user described their desired style as:\n"{style_prompt}"\n\n'
            f"Recommend PDF style options for this content:\n\n{snippet}"
        )
        system = PROMPT_AWARE_SYSTEM_PROMPT
    else:
        user_msg = f"Recommend PDF style options for this content:\n\n{snippet}"
        system = SYSTEM_PROMPT

    try:
        raw = await call_provider_chain(
            request_builder=lambda client, provider, model, timeout: _request_recommend(
                client, provider, model, timeout, user_msg, system
            ),
            chain_timeout=RECOMMEND_TIMEOUT,
            per_request_timeout=PER_REQUEST_TIMEOUT,
            min_remaining=3.0,
        )

        if has_prompt:
            result = parse_prompt_aware_recommendation(raw)
        else:
            flat = parse_recommendation(raw)
            result = _flat_to_nested(flat)

        logger.info("Recommendation: %s", result)
        return result
    except Exception as e:
        logger.warning("All providers failed for recommendation, using defaults: %s", e)
        return _flat_to_nested(DEFAULT_RECOMMENDATION.copy())
