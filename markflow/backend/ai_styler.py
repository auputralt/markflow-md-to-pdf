"""AI CSS generation with provider fallback chain and hardcoded fallback."""

import logging
import re
import time
from pathlib import Path

from providers import (
    build_provider_headers,
    call_provider_chain,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """\
You are a CSS expert specializing in print-optimized documents via WeasyPrint.
Create beautiful, professional PDF designs. Output ONLY raw CSS. No markdown fences, no comments.

CRITICAL: You generate CSS ONLY. The HTML structure is already correct — lists stack \
vertically, paragraphs are block, headings are block. Do NOT use CSS that changes \
element display from block to inline or that places block items side-by-side. \
Keep li as display: list-item. Keep p as display: block.

Analyze the content type and choose an appropriate default style:
- Technical docs / code-heavy → clean sans-serif, monospace code blocks, dark headers
- Academic / educational → structured headings, compact spacing, formal typography
- Business / reports → professional headers, clean tables, corporate feel
- General content → balanced, readable, modern design

Requirements:
1. @page { size: A4; margin: 2cm 2cm; } with @bottom-right showing counter(page) "Page X" \
in 8pt gray, @top-center showing document title or "MarkFlow" in 7pt uppercase light gray.
2. First page: standard margin, no header.
3. Use CSS custom properties (:root tokens) for colors, spacing, fonts.
4. Typography: clear hierarchy with appropriate font choices for the content type. \
h1: 18pt bold, h2: 14pt bold, h3: 12pt bold. h4-h6: 10.5pt bold.
5. Body: font-size 10pt, line-height 1.5, tight paragraph spacing (6pt).
6. Style ALL elements: h1-h6, p, code, pre, blockquote, table, th, td, ul, ol, li, \
img, a, hr, strong, em, del, mark, figure, figcaption, dl, dt, dd.
7. Style .callout-box with variants: .warning, .success, .danger, .info.
8. Code blocks: appropriate background, 1px border, monospace font 8.5pt, padding 10pt.
9. Tables: full width, collapsed borders, dark header, alternating rows, compact padding.
10. Blockquotes: left border accent, light background.
11. Lists: compact indentation, 1.5 line-height. \
Keep li as display: list-item — NEVER set li to inline or flex.
12. All headings: page-break-after: avoid.
13. Tables, figures, pre, blockquote, .callout-box, tr: page-break-inside: avoid.
14. thead { display: table-header-group; } for repeated table headers.
15. WeasyPrint compatible. CSS Paged Media. No CSS Grid. Flexbox OK for internal layout.
16. You may use: shadows, gradients, colored accents, decorative borders, \
background colors, and any visual styling that serves the design. \
Be creative and make it look professional.
"""

REFINE_PROMPT = """\
You are a CSS expert specializing in print-optimized documents via WeasyPrint.
You will receive a base CSS stylesheet that was assembled from user preferences. \
Your job is to refine and polish it into a production-quality PDF stylesheet.

Rules:
1. Keep the overall structure and design direction of the provided CSS.
2. Improve: spacing, typography scale, color harmony, print-specific details.
3. Ensure @page rules are correct for WeasyPrint Paged Media.
4. Ensure ALL HTML elements are styled (h1-h6, p, code, pre, blockquote, table, etc).
5. No CSS Grid. Flexbox OK. No shadows, no gradients, no decorative elements.
6. Output ONLY raw CSS. No markdown fences, no comments.
7. The CSS must be valid WeasyPrint CSS.
"""

PROMPT_DRIVEN_SYSTEM_PROMPT = """\
You are a CSS expert specializing in print-optimized documents via WeasyPrint.
You will receive a user's style description and an HTML snippet for reference only.
Your ONLY job is to generate raw CSS. You must NEVER modify, restructure, or \
rewrite the HTML content in any way.

CRITICAL RULES — THE DOCUMENT STRUCTURE IS SACROSANCT:
- The HTML content is already correctly structured from the user's Markdown. \
Do NOT alter it. Do NOT reorder, flatten, inline, or combine elements.
- If the Markdown has list items (A, B, C, D on separate lines), they MUST \
remain as separate stacked <li> elements — one per line, block display. \
NEVER use display: inline, float, flex-row, or any layout that would place \
list items side-by-side when the source has them on separate lines.
- NEVER add CSS that changes element display type from block to inline, or \
that would cause block-level elements to sit next to each other horizontally.
- NEVER use CSS columns on list items (<li>, <ol>, <ul>) unless explicitly asked.
- Paragraphs (<p>) must remain block. List items (<li>) must stack vertically.

STYLE FREEDOM:
- The user's style description is your PRIMARY direction. Follow it fully.
- You may use: shadows, gradients, colored accents, decorative borders, \
background colors, custom fonts, creative layouts, and any visual styling \
the user requests. No aesthetic restrictions.
- Be creative and make it look beautiful. The user wants something unique.

CSS REQUIREMENTS:
1. @page rules with proper margin boxes for WeasyPrint Paged Media.
2. Use CSS custom properties (:root tokens) for colors, spacing, fonts.
3. Style ALL elements: h1-h6, p, code, pre, blockquote, table, th, td, ul, ol, li, \
img, a, hr, strong, em, del, mark, figure, figcaption, dl, dt, dd.
4. No CSS Grid. Flexbox OK only for internal element layout, NOT for list/item \
flow direction.
5. Output ONLY raw CSS. No markdown fences, no comments, no HTML, no explanations.
6. WeasyPrint compatible CSS Paged Media only.
7. All headings: page-break-after: avoid.
8. Tables, figures, pre, blockquote, tr: page-break-inside: avoid.
9. thead { display: table-header-group; } for repeated table headers.
10. Keep li, ol, ul as display: list-item / block. Do NOT override to inline.
11. Keep p as display: block. Do NOT override to inline or flex.
"""

# Timeout constants
CSS_CHAIN_TIMEOUT = 50.0
PER_REQUEST_TIMEOUT = 20.0


# CSS properties that must never appear on list elements
_LIST_UNSAFE_PROPS = re.compile(
    r"(?:display\s*:\s*(?:inline|inline-block|inline-flex|flex|grid)"
    r"|flex-direction\s*:.*?row"
    r"|float\s*:)"
)

# Patterns for rules targeting list/table/block elements
# Selector text is already extracted without { — match element names
# preceded by start-of-string or combinator and followed by word boundary.
_STRUCTURAL_SELECTOR_RE = re.compile(
    r"(?:^|[,>+~\s])(?:ul|ol|li|dl|dt|dd|table|tr|td|th|blockquote)\b"
    r"|(?<![a-zA-Z-])p(?![a-zA-Z-])",
    re.IGNORECASE,
)


def _enforce_css_safety(css: str) -> str:
    """Strip CSS rules that would break document structure.

    LLMs sometimes return CSS that makes lists inline, adds flex-row to
    block elements, or otherwise breaks the vertical stacking that
    markdown-derived HTML relies on.  This post-processes the AI output
    and removes dangerous property values from structural selectors.
    """
    def _clean_rule(m):
        selector = m.group(1)
        props = m.group(2)
        # Only inspect rules that target structural elements
        if _STRUCTURAL_SELECTOR_RE.search(selector):
            lines = props.split(";")
            safe_lines = []
            for line in lines:
                stripped = line.strip()
                if _LIST_UNSAFE_PROPS.search(stripped):
                    logger.debug(
                        "CSS safety: removed unsafe property from [%s]: %s",
                        selector.strip(), stripped,
                    )
                    continue
                safe_lines.append(line)
            props = ";".join(safe_lines)
        return f"{selector}{{{props}}}"

    # re.DOTALL so . in selector pattern also matches newlines
    css = re.sub(r"([^{}]+?)\{([^{}]*)\}", _clean_rule, css, flags=re.DOTALL)

    # Append non-overridable safety rules at the end (highest specificity via
    # being last in the stylesheet — WeasyPrint respects source order).
    safety_block = """
/* === CSS SAFETY: never break document structure === */
ul, ol { display: block !important; }
li { display: list-item !important; }
p, blockquote, div, h1, h2, h3, h4, h5, h6, section, article, main { display: block !important; }
dl { display: block !important; }
dt { display: block !important; }
dd { display: block !important; }
table { display: table !important; }
tr { display: table-row !important; }
td, th { display: table-cell !important; }
"""
    return css + safety_block


def strip_markdown_fences(css: str) -> str:
    """Remove ```css ... ``` or ``` ... ``` wrapping from AI response."""
    css = css.strip()
    # Remove outermost fence wrapper only (start/end of string)
    css = re.sub(r"^```(?:css)?\s*\n?", "", css)
    css = re.sub(r"\n?```\s*$", "", css)
    css = css.strip()
    # If still has fences at boundaries, strip them (no greedy inner removal)
    css = re.sub(r"^```\s*\n?", "", css)
    css = re.sub(r"\n?```\s*$", "", css)
    css = css.strip()
    # Extract CSS content: match @-rules and rule blocks (handles nested braces)
    css_match = re.search(
        r"((?:@[\w-]+\s*(?:\{[^{}]*\}|\([^)]*\))\s*)*"  # @-rules
        r"(?:[^{}@]*\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\})*"  # regular rule blocks
        r")",
        css,
    )
    if css_match:
        css = css_match.group(0)
    return css.strip()


def _build_generate_request_body(model: str, snippet: str) -> dict:
    """Build the chat completion request body for CSS generation."""
    return {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Generate a complete CSS stylesheet for this HTML content:\n\n{snippet}",
            },
        ],
        "max_tokens": 4096,
        "temperature": 0.7,
    }


def _build_refine_request_body(model: str, snippet: str, base_css: str) -> dict:
    """Build the chat completion request body for CSS refinement."""
    return {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": REFINE_PROMPT},
            {
                "role": "user",
                "content": f"Refine this CSS stylesheet for optimal PDF output.\n\nContent snippet:\n{snippet}\n\nBase CSS:\n{base_css}",
            },
        ],
        "max_tokens": 4096,
        "temperature": 0.5,
    }


def _build_prompt_driven_request_body(model: str, snippet: str, style_prompt: str) -> dict:
    """Build the chat completion request body for prompt-driven CSS generation."""
    return {
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": PROMPT_DRIVEN_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Style description from the user:\n{style_prompt}\n\n"
                    f"Generate a complete CSS stylesheet for this HTML content:\n\n{snippet}"
                ),
            },
        ],
        "max_tokens": 4096,
        "temperature": 0.7,
    }


def _parse_css_response(data: dict, provider_name: str) -> str:
    """Extract and validate CSS from a provider response."""
    if not data.get("choices") or not data["choices"][0].get("message"):
        raise ValueError(f"Unexpected response from {provider_name}: {data}")

    css = data["choices"][0]["message"]["content"]
    css = strip_markdown_fences(css)

    if not css or len(css) < 100:
        raise ValueError(f"{provider_name} returned CSS too short ({len(css)} chars)")

    return _enforce_css_safety(css)


async def _request_generate(client, provider, model, timeout, snippet):
    """Request builder for CSS generation."""
    api_key = provider.get("_api_key")
    if not api_key:
        import os as _os
        api_key = _os.getenv(provider["key_env"])
    headers = build_provider_headers(provider, api_key)
    body = _build_generate_request_body(model, snippet)
    response = await client.post(provider["url"], headers=headers, json=body, timeout=timeout)
    response.raise_for_status()
    return _parse_css_response(response.json(), provider["name"])


async def _request_refine(client, provider, model, timeout, snippet, base_css):
    """Request builder for CSS refinement."""
    api_key = provider.get("_api_key")
    if not api_key:
        import os as _os
        api_key = _os.getenv(provider["key_env"])
    headers = build_provider_headers(provider, api_key)
    body = _build_refine_request_body(model, snippet, base_css)
    response = await client.post(provider["url"], headers=headers, json=body, timeout=timeout)
    response.raise_for_status()
    return _parse_css_response(response.json(), provider["name"])


async def _request_prompt_driven(client, provider, model, timeout, snippet, style_prompt):
    """Request builder for prompt-driven CSS generation."""
    api_key = provider.get("_api_key")
    if not api_key:
        import os as _os
        api_key = _os.getenv(provider["key_env"])
    headers = build_provider_headers(provider, api_key)
    body = _build_prompt_driven_request_body(model, snippet, style_prompt)
    response = await client.post(provider["url"], headers=headers, json=body, timeout=timeout)
    response.raise_for_status()
    return _parse_css_response(response.json(), provider["name"])


async def generate_css(html_content: str) -> str:
    """Try providers in order with fallback chain. Returns CSS or raises."""
    snippet = html_content[:3000]
    return await call_provider_chain(
        request_builder=lambda client, provider, model, timeout: _request_generate(
            client, provider, model, timeout, snippet
        ),
        chain_timeout=CSS_CHAIN_TIMEOUT,
        per_request_timeout=PER_REQUEST_TIMEOUT,
    )


async def generate_prompt_driven_css(html_content: str, style_prompt: str) -> str:
    """Generate CSS from a natural language style prompt + content. Returns CSS or raises."""
    snippet = html_content[:3000]
    return await call_provider_chain(
        request_builder=lambda client, provider, model, timeout: _request_prompt_driven(
            client, provider, model, timeout, snippet, style_prompt
        ),
        chain_timeout=CSS_CHAIN_TIMEOUT,
        per_request_timeout=PER_REQUEST_TIMEOUT,
    )


async def generate_refined_css(html_content: str, base_css: str) -> str:
    """Use AI to refine a base CSS stylesheet. Returns refined CSS or raises."""
    snippet = html_content[:2000]
    return await call_provider_chain(
        request_builder=lambda client, provider, model, timeout: _request_refine(
            client, provider, model, timeout, snippet, base_css
        ),
        chain_timeout=CSS_CHAIN_TIMEOUT,
        per_request_timeout=PER_REQUEST_TIMEOUT,
    )


def _load_fallback() -> str:
    """Load the hardcoded fallback CSS from file."""
    fallback_path = Path(__file__).parent / "styles" / "fallback.css"
    if fallback_path.exists():
        return fallback_path.read_text(encoding="utf-8")
    logger.warning("Fallback CSS file not found at %s", fallback_path)
    return "body { font-family: Georgia, serif; font-size: 11pt; line-height: 1.7; }"


async def get_stylesheet(html: str, custom_css: str = "", style_prompt: str = "", refine: bool = False) -> str:
    """Get CSS: use custom if provided, else prompt-driven, else AI-generated, else fallback."""
    # Legacy path: raw CSS override
    if custom_css and custom_css.strip():
        if refine:
            try:
                refined = await generate_refined_css(html, custom_css)
                if refined and len(refined) > 100:
                    logger.info("AI-refined CSS: %d chars", len(refined))
                    return refined
                logger.warning("AI refined CSS too short, using provided CSS")
            except Exception as e:
                logger.error("AI CSS refinement failed, using provided CSS: %s", e)
        return _enforce_css_safety(custom_css.strip())

    # Prompt-driven path: AI generates CSS from user's natural language style description
    if style_prompt:
        try:
            css = await generate_prompt_driven_css(html, style_prompt)
            if css and len(css) > 100:
                logger.info("Prompt-driven CSS: %d chars", len(css))
                return css
            logger.warning("Prompt-driven CSS too short (%d chars), falling back", len(css))
        except Exception as e:
            logger.error("Prompt-driven CSS generation failed: %s", e)

    # Generic AI-generated CSS
    try:
        css = await generate_css(html)
        if css and len(css) > 100:
            logger.info("AI-generated CSS: %d chars", len(css))
            return css
        logger.warning("AI CSS too short (%d chars), using fallback", len(css))
    except Exception as e:
        logger.error("All AI providers failed, using fallback: %s", e)

    logger.info("Using fallback CSS")
    return _load_fallback()
