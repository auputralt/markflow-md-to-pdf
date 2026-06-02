# PDF Style Options Panel Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a modal-based style options panel with 9 categories, AI recommendation, client-side CSS builder, and optional AI CSS refinement to MarkFlow.

**Architecture:** Frontend modal collects user style picks. Client-side `style-builder.js` assembles CSS from picks. New `/recommend` backend endpoint uses AI to auto-populate picks. Optional AI refine sends built CSS through AI for polishing. Existing `/generate` endpoint gets a `refine` flag.

**Tech Stack:** Python 3.11+, FastAPI, httpx, vanilla JS, CSS (dark theme)

---

## File Map

| File | Responsibility | Status |
|---|---|---|
| `backend/recommender.py` | AI recommendation logic, provider chain, JSON parsing | **New** |
| `backend/main.py` | `/recommend` endpoint, `refine` field on `/generate` | Modify |
| `backend/ai_styler.py` | Refine mode: accept base CSS hint in AI prompt | Modify |
| `frontend/style-builder.js` | CSS template fragments + `buildCSS()` function | **New** |
| `frontend/index.html` | Style Options button + modal markup | Modify |
| `frontend/style.css` | Modal, controls, toggle styling | Modify |
| `frontend/app.js` | Modal state, AI Recommend call, generate flow integration | Modify |

---

### Task 1: Backend — `recommender.py` (AI Recommendation Module)

**Files:**
- Create: `markflow/backend/recommender.py`

- [ ] **Step 1: Create recommender.py with system prompt and constants**

```python
"""AI-powered style recommendation for PDF documents."""

import json
import logging
import os
import re
import time

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
BLUESMINDS_API_URL = "https://api.bluesminds.com/v1/chat/completions"

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

RECOMMEND_TIMEOUT = 15.0
PER_REQUEST_TIMEOUT = 12.0
```

- [ ] **Step 2: Add JSON parsing and validation functions**

Append to `recommender.py`:

```python
def parse_recommendation(text: str) -> dict:
    """Parse AI response into a validated recommendation dict."""
    text = text.strip()
    # Strip markdown fences if present
    text = re.sub(r"^```(?:json)?\s*\n?", "", text)
    text = re.sub(r"\n?```\s*$", "", text)

    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Try to extract JSON object from surrounding text
        match = re.search(r"\{[^}]+\}", text)
        if match:
            data = json.loads(match.group(0))
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


def _build_provider_headers(provider: dict, api_key: str) -> dict:
    """Build request headers for a provider."""
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if provider["name"] == "OpenRouter":
        headers["HTTP-Referer"] = "https://markflow.local"
        headers["X-Title"] = "MarkFlow"
    return headers
```

- [ ] **Step 3: Add provider call and main recommend function**

Append to `recommender.py`:

```python
async def _call_provider(
    client: httpx.AsyncClient, provider: dict, snippet: str, timeout: float = 12.0
) -> str:
    """Call a single provider and return raw text. Raises on failure."""
    api_key = os.getenv(provider["key_env"])
    if not api_key:
        raise ValueError(f"{provider['key_env']} not set")

    headers = _build_provider_headers(provider, api_key)
    body = {
        "model": provider["model"],
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Recommend PDF style options for this content:\n\n{snippet}",
            },
        ],
        "max_tokens": 500,
        "temperature": 0.3,
    }

    response = await client.post(provider["url"], headers=headers, json=body, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    if not data.get("choices") or not data["choices"][0].get("message"):
        raise ValueError(f"Unexpected response from {provider['name']}")

    return data["choices"][0]["message"]["content"]


async def recommend_styles(content: str) -> dict:
    """Get AI style recommendations. Returns validated dict or defaults."""
    snippet = content[:2000]
    last_error = None
    start = time.monotonic()

    async with httpx.AsyncClient(timeout=20.0) as client:
        for provider in PROVIDERS:
            elapsed = time.monotonic() - start
            remaining = RECOMMEND_TIMEOUT - elapsed
            if remaining < 3:
                break

            api_key = os.getenv(provider["key_env"])
            if not api_key:
                logger.info("Skipping %s — %s not set", provider["name"], provider["key_env"])
                continue

            try:
                request_timeout = min(PER_REQUEST_TIMEOUT, remaining)
                raw = await _call_provider(client, provider, snippet, timeout=request_timeout)
                result = parse_recommendation(raw)
                logger.info(
                    "Recommendation from %s (%.1fs): %s",
                    provider["name"],
                    time.monotonic() - start,
                    result,
                )
                return result
            except Exception as e:
                last_error = e
                logger.warning("%s failed: %s", provider["name"], e)

    logger.warning("All providers failed for recommendation, using defaults: %s", last_error)
    return DEFAULT_RECOMMENDATION.copy()
```

- [ ] **Step 4: Commit**

```bash
git add markflow/backend/recommender.py
git commit -m "feat: add AI style recommendation module"
```

---

### Task 2: Backend — Add `/recommend` endpoint to `main.py`

**Files:**
- Modify: `markflow/backend/main.py`

- [ ] **Step 1: Add imports and models**

Add after the existing imports (line 14):

```python
from recommender import recommend_styles
```

Add after `GenerateRequest` class (after line 57):

```python
class RecommendRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Content to analyze for style recommendations")
```

- [ ] **Step 2: Add `refine` field to GenerateRequest**

Change the existing `GenerateRequest` class (lines 55-57) to:

```python
class GenerateRequest(BaseModel):
    content: str = Field(..., min_length=1, description="Raw content to convert")
    custom_css: str = Field(default="", description="Optional CSS override")
    refine: bool = Field(default=False, description="If true, AI will polish the provided custom_css")
```

- [ ] **Step 3: Add `/recommend` endpoint**

Add before the `if __name__` block (before line 143):

```python
@app.post(
    "/recommend",
    responses={
        200: {"description": "Style recommendations"},
        500: {"model": ErrorResponse, "description": "Recommendation failed"},
    },
)
async def recommend(request: RecommendRequest):
    """Get AI-powered style recommendations for the given content."""
    try:
        recommendations = await recommend_styles(request.content)
        return recommendations
    except Exception as e:
        logger.error("Recommendation failed: %s", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail={"error": "Style recommendation failed", "detail": str(e)},
        )
```

- [ ] **Step 4: Pass `refine` flag to `get_stylesheet` in generate endpoint**

In the `generate` function, find this line (line 102):

```python
        css = await get_stylesheet(html_body, request.custom_css)
```

Replace with:

```python
        css = await get_stylesheet(html_body, request.custom_css, refine=request.refine)
```

- [ ] **Step 5: Commit**

```bash
git add markflow/backend/main.py
git commit -m "feat: add /recommend endpoint and refine flag to /generate"
```

---

### Task 3: Backend — Add refine support to `ai_styler.py`

**Files:**
- Modify: `markflow/backend/ai_styler.py`

- [ ] **Step 1: Add refine-specific system prompt constant**

Add after `SYSTEM_PROMPT` (after line 59):

```python
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
```

- [ ] **Step 2: Add refine CSS generation function**

Add after `_build_request_body` function (after line 121):

```python
async def generate_refined_css(html_content: str, base_css: str) -> str:
    """Use AI to refine a base CSS stylesheet. Returns refined CSS or raises."""
    snippet = html_content[:2000]
    last_error = None
    start = time.monotonic()

    async with httpx.AsyncClient(timeout=30.0) as client:
        for provider in PROVIDERS:
            elapsed = time.monotonic() - start
            remaining = CSS_CHAIN_TIMEOUT - elapsed
            if remaining < 5:
                break

            api_key = os.getenv(provider["key_env"])
            if not api_key:
                continue

            models_to_try = (
                BLUESMINDS_FALLBACK_MODELS
                if provider["name"] == "Bluesminds"
                else [provider["model"]]
            )

            for model in models_to_try:
                elapsed = time.monotonic() - start
                remaining = CSS_CHAIN_TIMEOUT - elapsed
                if remaining < 5:
                    break

                request_timeout = min(PER_REQUEST_TIMEOUT, remaining)

                try:
                    api_key_val = os.getenv(provider["key_env"])
                    headers = _build_provider_headers(provider, api_key_val)
                    body = {
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

                    response = await client.post(
                        provider["url"],
                        headers=headers,
                        json=body,
                        timeout=request_timeout,
                    )
                    response.raise_for_status()
                    data = response.json()

                    if not data.get("choices") or not data["choices"][0].get("message"):
                        raise ValueError(f"Unexpected response from {provider['name']}")

                    css = data["choices"][0]["message"]["content"]
                    css = strip_markdown_fences(css)

                    if not css or len(css) < 100:
                        raise ValueError(f"Refined CSS too short ({len(css)} chars)")

                    logger.info(
                        "Refined CSS from %s/%s: %d chars (%.1fs)",
                        provider["name"], model, len(css), time.monotonic() - start,
                    )
                    return css
                except Exception as e:
                    last_error = e
                    logger.warning("%s/%s refine failed: %s", provider["name"], model, e)

    raise last_error or ValueError("All AI providers failed for CSS refinement")
```

- [ ] **Step 3: Update `get_stylesheet` to accept `refine` parameter**

Replace the entire `get_stylesheet` function (lines 229-244) with:

```python
async def get_stylesheet(html: str, custom_css: str, refine: bool = False) -> str:
    """Get CSS: use custom if provided (optionally refined by AI), otherwise AI-generated or fallback."""
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
        return custom_css.strip()

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
```

- [ ] **Step 4: Commit**

```bash
git add markflow/backend/ai_styler.py
git commit -m "feat: add AI CSS refinement support"
```

---

### Task 4: Frontend — `style-builder.js` (CSS Template Builder)

**Files:**
- Create: `markflow/frontend/style-builder.js`

- [ ] **Step 1: Create style-builder.js with theme templates**

```javascript
/* ============================================================
   MarkFlow — Client-Side CSS Builder
   Builds WeasyPrint-compatible CSS from user style options.
   ============================================================ */

(function () {
  "use strict";

  // --- Theme Templates ---
  var themes = {
    light: {
      root: "background: #ffffff; color: #1a1a1a; heading-color: #111111; border-color: #cccccc; muted-color: #666666; link-color: #0066cc;",
      body: "background-color: #ffffff;",
    },
    dark: {
      root: "background: #1a1a2e; color: #e0e0e0; heading-color: #f0f0f0; border-color: #444466; muted-color: #999999; link-color: #6699ff;",
      body: "background-color: #1a1a2e; color: #e0e0e0;",
    },
    sepia: {
      root: "background: #f4ecd8; color: #5b4636; heading-color: #3b2f20; border-color: #d4c5a9; muted-color: #8b7355; link-color: #8b4513;",
      body: "background-color: #f4ecd8; color: #5b4636;",
    },
    cream: {
      root: "background: #faf8f0; color: #333333; heading-color: #1a1a1a; border-color: #e0dbd0; muted-color: #777777; link-color: #0055aa;",
      body: "background-color: #faf8f0; color: #333333;",
    },
  };

  // --- Font Templates ---
  var fonts = {
    "sans-serif": { body: "'Inter', system-ui, -apple-system, sans-serif;", heading: "'Inter', system-ui, sans-serif;" },
    serif: { body: "'Georgia', 'Times New Roman', serif;", heading: "'Georgia', serif;" },
    mono: { body: "'Fira Code', 'Courier New', monospace;", heading: "'Fira Code', monospace;" },
    academic: { body: "'Georgia', 'Times New Roman', serif;", heading: "'Inter', system-ui, sans-serif;" },
  };

  // --- Layout Templates ---
  var layouts = {
    single: { pageMargin: "2cm 2cm", bodyMaxWidth: "none", bodyPadding: "0", bodyColumns: "1", bodyColumnGap: "0" },
    "two-column": { pageMargin: "2cm 2cm", bodyMaxWidth: "none", bodyPadding: "0", bodyColumns: "2", bodyColumnGap: "24pt" },
    compact: { pageMargin: "1.5cm 1.5cm", bodyMaxWidth: "none", bodyPadding: "0", bodyColumns: "1", bodyColumnGap: "0" },
    wide: { pageMargin: "2cm 4cm", bodyMaxWidth: "none", bodyPadding: "0", bodyColumns: "1", bodyColumnGap: "0" },
  };

  // --- Page Sizes ---
  var pageSizes = {
    a4: "A4",
    letter: "letter",
    legal: "legal",
  };

  // --- Code Block Templates ---
  var codeBlocks = {
    highlighted: "background-color: #f5f5f5; border: 1px solid #ddd; color: #1a1a1a; padding: 10pt; font-size: 8.5pt; line-height: 1.5;",
    plain: "background-color: transparent; border: none; color: #333333; padding: 6pt 0; font-size: 9pt; line-height: 1.4;",
    bordered: "background-color: #f8f8f8; border: 1px solid #ccc; color: #333333; padding: 10pt; font-size: 8.5pt; line-height: 1.5;",
    minimal: "background-color: #fafafa; border: none; color: #444444; padding: 8pt; font-size: 8.5pt; line-height: 1.5;",
  };

  var inlineCode = {
    highlighted: "background-color: #f0f0f0; border: 1px solid #ddd; color: #1a1a1a; padding: 1pt 4pt; font-size: 0.9em;",
    plain: "background-color: transparent; border: none; color: #333333; padding: 0; font-size: 0.9em;",
    bordered: "background-color: #f0f0f0; border: 1px solid #ccc; color: #333333; padding: 1pt 4pt; font-size: 0.9em;",
    minimal: "background-color: #f5f5f5; border: none; color: #444444; padding: 1pt 3pt; font-size: 0.9em;",
  };

  // --- Table Templates ---
  var tables = {
    striped: "border-collapse: collapse; width: 100%; border: 1px solid #999; th { background-color: #333; color: white; font-weight: bold; padding: 6pt 8pt; font-size: 9pt; } td { padding: 6pt 8pt; font-size: 9pt; border: 1px solid #ccc; } tr:nth-child(even) { background-color: #f9f9f9; }",
    clean: "border-collapse: collapse; width: 100%; border-bottom: 2px solid #333; th { text-align: left; font-weight: bold; padding: 6pt 8pt; font-size: 9pt; border-bottom: 1px solid #999; } td { padding: 6pt 8pt; font-size: 9pt; border-bottom: 1px solid #eee; }",
    grid: "border-collapse: collapse; width: 100%; border: 1px solid #999; th { background-color: #333; color: white; font-weight: bold; padding: 6pt 8pt; font-size: 9pt; border: 1px solid #666; } td { padding: 6pt 8pt; font-size: 9pt; border: 1px solid #ccc; }",
  };

  // --- Build CSS ---
  function buildCSS(options) {
    var theme = themes[options.theme] || themes.light;
    var font = fonts[options.font] || fonts["sans-serif"];
    var layout = layouts[options.layout] || layouts.single;
    var pageSize = pageSizes[options.page_size] || pageSizes.a4;
    var headerFooter = options.header_footer || [];
    var codeStyle = codeBlocks[options.code_blocks] || codeBlocks.bordered;
    var codeInline = inlineCode[options.code_blocks] || inlineCode.bordered;
    var tableStyle = tables[options.tables] || tables.striped;
    var extras = options.extras || [];

    // Parse theme colors into parts
    var rootVars = theme.root;

    // Header/footer margin boxes
    var headerTopMargin = "1.5cm";
    var headerBottomMargin = "1.5cm";
    var marginBoxes = "";

    if (headerFooter.indexOf("title") !== -1 || headerFooter.indexOf("date") !== -1) {
      headerTopMargin = "2cm";
      marginBoxes += "@top-center { content: \"MarkFlow\"; font-size: 7pt; color: #999; text-transform: uppercase; letter-spacing: 1pt; }\n";
    }
    if (headerFooter.indexOf("page_numbers") !== -1) {
      headerBottomMargin = "2cm";
      marginBoxes += "@bottom-right { content: \"Page \" counter(page); font-size: 8pt; color: #999; }\n";
      marginBoxes += "@bottom-left { content: none; }\n";
    }
    if (headerFooter.indexOf("date") !== -1) {
      marginBoxes += "@bottom-center { content: \"Generated by MarkFlow\"; font-size: 7pt; color: #bbb; }\n";
    }

    // Extras
    var extrasCSS = "";
    if (extras.indexOf("toc") !== -1) {
      extrasCSS += "/* Table of Contents placeholder */\n";
      extrasCSS += ".toc { page-break-before: always; }\n";
      extrasCSS += ".toc h2 { font-size: 16pt; margin-bottom: 12pt; }\n";
      extrasCSS += ".toc ul { list-style: none; padding: 0; }\n";
      extrasCSS += ".toc li { padding: 4pt 0; border-bottom: 1px dotted #ccc; }\n";
      extrasCSS += ".toc a { text-decoration: none; color: inherit; }\n";
    }
    if (extras.indexOf("watermark") !== -1) {
      // WeasyPrint doesn't support ::before/::after on body well for watermarks,
      // but we add a hint in CSS that can be applied via content
      extrasCSS += "/* Watermark hint - applied via fixed positioning */\n";
    }

    // Assemble
    var css = "";
    css += "@page {\n";
    css += "  size: " + pageSize + ";\n";
    css += "  margin: " + layout.pageMargin + ";\n";
    css += "  margin-top: " + headerTopMargin + ";\n";
    css += "  margin-bottom: " + headerBottomMargin + ";\n";
    css += "}\n\n";
    css += marginBoxes + "\n";

    css += ":root {\n";
    css += "  " + rootVars + "\n";
    css += "}\n\n";

    css += "body {\n";
    css += "  " + theme.body + "\n";
    css += "  font-family: " + font.body + "\n";
    css += "  font-size: 10pt;\n";
    css += "  line-height: 1.5;\n";
    css += "  max-width: " + layout.bodyMaxWidth + ";\n";
    css += "  padding: " + layout.bodyPadding + ";\n";
    if (layout.bodyColumns !== "1") {
      css += "  column-count: " + layout.bodyColumns + ";\n";
      css += "  column-gap: " + layout.bodyColumnGap + ";\n";
    }
    css += "}\n\n";

    // Headings
    css += "h1 { font-family: " + font.heading + "; font-size: 18pt; font-weight: bold; color: #111; margin-top: 16pt; margin-bottom: 6pt; border-bottom: 1px solid #333; padding-bottom: 4pt; page-break-after: avoid; }\n";
    css += "h2 { font-family: " + font.heading + "; font-size: 14pt; font-weight: bold; text-transform: uppercase; letter-spacing: 0.5pt; color: #222; margin-top: 14pt; margin-bottom: 4pt; border-bottom: 1px solid #ccc; padding-bottom: 3pt; page-break-after: avoid; }\n";
    css += "h3 { font-family: " + font.heading + "; font-size: 12pt; font-weight: bold; color: #333; margin-top: 12pt; margin-bottom: 4pt; page-break-after: avoid; }\n";
    css += "h4, h5, h6 { font-family: " + font.heading + "; font-size: 10.5pt; font-weight: bold; color: #444; margin-top: 10pt; margin-bottom: 3pt; page-break-after: avoid; }\n\n";

    // Paragraphs
    css += "p { margin-top: 0; margin-bottom: 6pt; text-align: justify; }\n\n";

    // Code blocks
    css += "pre {\n  " + codeStyle + "\n  font-family: 'Fira Code', 'Courier New', monospace;\n  white-space: pre-wrap;\n  word-wrap: break-word;\n  page-break-inside: avoid;\n}\n\n";
    css += "code {\n  " + codeInline + "\n  font-family: 'Fira Code', 'Courier New', monospace;\n}\n";
    css += "pre code {\n  background: none; border: none; padding: 0; font-size: inherit; }\n\n";

    // Blockquotes
    css += "blockquote { border-left: 3px solid #666; background-color: #fafafa; padding: 8pt 12pt; margin: 8pt 0; font-style: normal; page-break-inside: avoid; }\n\n";

    // Tables
    css += "table { " + tableStyle + " }\n";
    css += "thead { display: table-header-group; }\n";
    css += "tr { page-break-inside: avoid; }\n\n";

    // Lists
    css += "ul, ol { margin-left: 18pt; margin-bottom: 6pt; line-height: 1.5; }\n";
    css += "li { margin-bottom: 3pt; }\n";
    css += "ul ul, ol ol, ul ol, ol ul { margin-left: 16pt; }\n\n";

    // Links
    css += "a { color: #0066cc; text-decoration: underline; }\n\n";

    // HR
    css += "hr { border: none; border-top: 1px solid #333; margin: 12pt 0; }\n\n";

    // Strong, em, mark
    css += "strong { font-weight: bold; color: #111; }\n";
    css += "em { font-style: italic; }\n";
    css += "mark { background-color: #fff3cd; padding: 1pt 2pt; }\n";
    css += "del { text-decoration: line-through; color: #999; }\n\n";

    // Images and figures
    css += "img { max-width: 100%; height: auto; }\n";
    css += "figure { margin: 12pt 0; page-break-inside: avoid; }\n";
    css += "figcaption { font-size: 8.5pt; color: #666; text-align: center; margin-top: 4pt; }\n\n";

    // Definition lists
    css += "dl { margin-left: 18pt; margin-bottom: 6pt; }\n";
    css += "dt { font-weight: bold; }\n";
    css += "dd { margin-left: 12pt; margin-bottom: 3pt; }\n\n";

    // Extras
    if (extrasCSS) {
      css += extrasCSS + "\n";
    }

    return css;
  }

  // Export
  window.MarkFlowStyleBuilder = { buildCSS: buildCSS };
})();
```

- [ ] **Step 2: Commit**

```bash
git add markflow/frontend/style-builder.js
git commit -m "feat: add client-side CSS builder with style templates"
```

---

### Task 5: Frontend — Modal HTML markup in `index.html`

**Files:**
- Modify: `markflow/frontend/index.html`

- [ ] **Step 1: Add style-builder.js script tag**

Add before the existing `<script src="app.js">` tag (before line 108):

```html
  <script src="style-builder.js"></script>
```

- [ ] **Step 2: Add "Style Options" button and modal markup**

Add after the CSS section `</div>` (after line 59, before the info-text `<p>`):

```html
      <!-- Style Options Button -->
      <button id="style-options-btn" class="style-options-btn" type="button">
        🎨 Style Options
      </button>

      <!-- Style Options Modal -->
      <div id="style-modal" class="modal-overlay hidden">
        <div class="modal">
          <div class="modal-header">
            <h2 class="modal-title">PDF Style Options</h2>
            <div class="modal-header-actions">
              <button id="ai-recommend-btn" class="ai-recommend-btn" type="button">
                ✨ AI Recommend
              </button>
              <button id="modal-close-btn" class="modal-close-btn" type="button">✕</button>
            </div>
          </div>

          <div class="modal-body">
            <!-- Theme -->
            <div class="option-group">
              <label class="option-group-label">Theme</label>
              <div class="option-row">
                <label class="option-item"><input type="radio" name="theme" value="light" checked><span>Light</span></label>
                <label class="option-item"><input type="radio" name="theme" value="dark"><span>Dark</span></label>
                <label class="option-item"><input type="radio" name="theme" value="sepia"><span>Sepia</span></label>
                <label class="option-item"><input type="radio" name="theme" value="cream"><span>Cream</span></label>
              </div>
            </div>

            <!-- Font -->
            <div class="option-group">
              <label class="option-group-label">Font</label>
              <div class="option-row">
                <label class="option-item"><input type="radio" name="font" value="sans-serif" checked><span>Sans-serif</span></label>
                <label class="option-item"><input type="radio" name="font" value="serif"><span>Serif</span></label>
                <label class="option-item"><input type="radio" name="font" value="mono"><span>Mono</span></label>
                <label class="option-item"><input type="radio" name="font" value="academic"><span>Academic</span></label>
              </div>
            </div>

            <!-- Layout -->
            <div class="option-group">
              <label class="option-group-label">Layout</label>
              <div class="option-row">
                <label class="option-item"><input type="radio" name="layout" value="single" checked><span>Single Column</span></label>
                <label class="option-item"><input type="radio" name="layout" value="two-column"><span>Two Column</span></label>
                <label class="option-item"><input type="radio" name="layout" value="compact"><span>Compact</span></label>
                <label class="option-item"><input type="radio" name="layout" value="wide"><span>Wide Margins</span></label>
              </div>
            </div>

            <!-- Page Size -->
            <div class="option-group">
              <label class="option-group-label">Page Size</label>
              <div class="option-row">
                <label class="option-item"><input type="radio" name="page_size" value="a4" checked><span>A4</span></label>
                <label class="option-item"><input type="radio" name="page_size" value="letter"><span>Letter</span></label>
                <label class="option-item"><input type="radio" name="page_size" value="legal"><span>Legal</span></label>
              </div>
            </div>

            <!-- Header/Footer -->
            <div class="option-group">
              <label class="option-group-label">Header / Footer</label>
              <div class="option-row">
                <label class="option-item"><input type="checkbox" name="header_footer" value="page_numbers" checked><span>Page Numbers</span></label>
                <label class="option-item"><input type="checkbox" name="header_footer" value="title"><span>Title</span></label>
                <label class="option-item"><input type="checkbox" name="header_footer" value="date"><span>Date</span></label>
              </div>
            </div>

            <!-- Code Blocks -->
            <div class="option-group">
              <label class="option-group-label">Code Blocks</label>
              <div class="option-row">
                <label class="option-item"><input type="radio" name="code_blocks" value="highlighted"><span>Highlighted</span></label>
                <label class="option-item"><input type="radio" name="code_blocks" value="plain"><span>Plain</span></label>
                <label class="option-item"><input type="radio" name="code_blocks" value="bordered" checked><span>Bordered</span></label>
                <label class="option-item"><input type="radio" name="code_blocks" value="minimal"><span>Minimal</span></label>
              </div>
            </div>

            <!-- Tables -->
            <div class="option-group">
              <label class="option-group-label">Tables</label>
              <div class="option-row">
                <label class="option-item"><input type="radio" name="tables" value="striped" checked><span>Striped Rows</span></label>
                <label class="option-item"><input type="radio" name="tables" value="clean"><span>Clean</span></label>
                <label class="option-item"><input type="radio" name="tables" value="grid"><span>Grid Borders</span></label>
              </div>
            </div>

            <!-- Extras -->
            <div class="option-group">
              <label class="option-group-label">Extras</label>
              <div class="option-row">
                <label class="option-item"><input type="checkbox" name="extras" value="toc"><span>Table of Contents</span></label>
                <label class="option-item"><input type="checkbox" name="extras" value="watermark"><span>Watermark</span></label>
              </div>
            </div>

            <!-- AI Refine Toggle -->
            <div class="option-group">
              <label class="option-group-label">AI Refine CSS</label>
              <div class="option-row">
                <label class="toggle-item">
                  <span class="toggle-label">Off</span>
                  <input type="checkbox" id="ai-refine-toggle" class="toggle-input">
                  <span class="toggle-label">On</span>
                </label>
                <span class="toggle-hint">AI polishes the CSS before generating PDF</span>
              </div>
            </div>
          </div>

          <div class="modal-footer">
            <button id="modal-reset-btn" class="modal-reset-btn" type="button">Reset Defaults</button>
            <button id="modal-apply-btn" class="modal-apply-btn" type="button">Apply</button>
          </div>
        </div>
      </div>
```

- [ ] **Step 3: Commit**

```bash
git add markflow/frontend/index.html
git commit -m "feat: add style options button and modal markup"
```

---

### Task 6: Frontend — Modal and controls CSS in `style.css`

**Files:**
- Modify: `markflow/frontend/style.css`

- [ ] **Step 1: Add style options button, modal overlay, and modal container styles**

Append at the end of `style.css`, before the responsive section:

```css
/* --- Style Options Button --- */
.style-options-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  width: 100%;
  padding: 12px 24px;
  font-family: var(--font-sans);
  font-size: 15px;
  font-weight: 500;
  color: var(--text);
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition), transform var(--transition);
}

.style-options-btn:hover {
  border-color: var(--primary);
  background: var(--surface-raised);
  transform: translateY(-1px);
}

/* --- Modal Overlay --- */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}

/* --- Modal Container --- */
.modal {
  background: var(--surface);
  border: 1.5px solid var(--border);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 560px;
  max-height: 85vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border);
  flex-shrink: 0;
}

.modal-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text);
}

.modal-header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-recommend-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 600;
  color: white;
  background: var(--primary);
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
  transition: background var(--transition), opacity var(--transition);
}

.ai-recommend-btn:hover:not(:disabled) {
  background: var(--primary-hover);
}

.ai-recommend-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ai-recommend-btn.loading {
  position: relative;
  color: transparent;
}

.ai-recommend-btn.loading::after {
  content: "";
  position: absolute;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

.modal-close-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  font-size: 16px;
  color: var(--text-secondary);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius);
  cursor: pointer;
  transition: color var(--transition), background var(--transition), border-color var(--transition);
}

.modal-close-btn:hover {
  color: var(--text);
  background: var(--surface-raised);
  border-color: var(--border);
}

/* --- Modal Body --- */
.modal-body {
  padding: 16px 20px;
  overflow-y: auto;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.option-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.option-group-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.option-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

/* --- Option Items (radio + checkbox) --- */
.option-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
  transition: border-color var(--transition), background var(--transition);
  font-size: 13px;
  color: var(--text-secondary);
  user-select: none;
}

.option-item:hover {
  border-color: var(--primary);
  background: var(--surface-raised);
}

.option-item:has(input:checked) {
  border-color: var(--primary);
  background: var(--primary-light);
  color: var(--text);
}

.option-item input[type="radio"],
.option-item input[type="checkbox"] {
  accent-color: var(--primary);
  width: 14px;
  height: 14px;
  cursor: pointer;
}

/* --- Toggle Switch --- */
.toggle-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 6px 12px;
  background: var(--bg);
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  user-select: none;
}

.toggle-label {
  font-size: 13px;
  color: var(--text-secondary);
}

.toggle-input {
  accent-color: var(--primary);
  width: 16px;
  height: 16px;
  cursor: pointer;
}

.toggle-hint {
  font-size: 11px;
  color: var(--text-secondary);
  opacity: 0.7;
}

/* --- Modal Footer --- */
.modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  padding: 12px 20px;
  border-top: 1px solid var(--border);
  flex-shrink: 0;
}

.modal-reset-btn {
  font-family: var(--font-sans);
  font-size: 13px;
  font-weight: 500;
  color: var(--text-secondary);
  background: transparent;
  border: 1.5px solid var(--border);
  border-radius: var(--radius);
  padding: 8px 16px;
  cursor: pointer;
  transition: border-color var(--transition), color var(--transition);
}

.modal-reset-btn:hover {
  border-color: var(--text-secondary);
  color: var(--text);
}

.modal-apply-btn {
  font-family: var(--font-sans);
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: var(--primary);
  border: none;
  border-radius: var(--radius);
  padding: 8px 24px;
  cursor: pointer;
  transition: background var(--transition), box-shadow var(--transition);
}

.modal-apply-btn:hover {
  background: var(--primary-hover);
  box-shadow: var(--shadow-sm);
}
```

- [ ] **Step 2: Add modal responsive styles**

Append inside the existing `@media (max-width: 640px)` block:

```css
  .modal {
    max-height: 90vh;
    max-width: 100%;
    margin: 12px;
  }

  .modal-header {
    flex-wrap: wrap;
    gap: 8px;
  }

  .option-row {
    gap: 6px;
  }

  .option-item {
    padding: 5px 10px;
    font-size: 12px;
  }
```

- [ ] **Step 3: Commit**

```bash
git add markflow/frontend/style.css
git commit -m "feat: add modal and style options control styling"
```

---

### Task 7: Frontend — Modal logic and generate flow in `app.js`

**Files:**
- Modify: `markflow/frontend/app.js`

- [ ] **Step 1: Add new DOM references and style options state**

Add after the existing DOM references block (after line 33, before the `// --- State Machine ---` comment):

```javascript
  // --- Style Options State ---
  const styleOptionsBtn = document.getElementById("style-options-btn");
  const styleModal = document.getElementById("style-modal");
  const modalCloseBtn = document.getElementById("modal-close-btn");
  const aiRecommendBtn = document.getElementById("ai-recommend-btn");
  const aiRefineToggle = document.getElementById("ai-refine-toggle");
  const modalApplyBtn = document.getElementById("modal-apply-btn");
  const modalResetBtn = document.getElementById("modal-reset-btn");

  const RECOMMEND_API_URL = "http://localhost:8000/recommend";

  const defaultStyleOptions = {
    theme: "light",
    font: "sans-serif",
    layout: "single",
    page_size: "a4",
    header_footer: ["page_numbers"],
    code_blocks: "bordered",
    tables: "striped",
    extras: [],
    refine: false,
  };

  let currentStyleOptions = JSON.parse(JSON.stringify(defaultStyleOptions));
```

- [ ] **Step 2: Add modal open/close functions**

Add after the state machine code, before `// --- Generate PDF ---`:

```javascript
  // --- Modal ---
  function openModal() {
    // Sync modal controls to currentStyleOptions
    syncModalToOptions(currentStyleOptions);
    styleModal.classList.remove("hidden");
    document.body.style.overflow = "hidden";
  }

  function closeModal() {
    styleModal.classList.add("hidden");
    document.body.style.overflow = "";
  }

  function syncModalToOptions(opts) {
    // Radio buttons
    ["theme", "font", "layout", "page_size", "code_blocks", "tables"].forEach(function (name) {
      var radios = styleModal.querySelectorAll('input[name="' + name + '"]');
      radios.forEach(function (radio) {
        radio.checked = radio.value === opts[name];
      });
    });

    // Checkboxes: header_footer
    var hfCheckboxes = styleModal.querySelectorAll('input[name="header_footer"]');
    hfCheckboxes.forEach(function (cb) {
      cb.checked = opts.header_footer.indexOf(cb.value) !== -1;
    });

    // Checkboxes: extras
    var extraCheckboxes = styleModal.querySelectorAll('input[name="extras"]');
    extraCheckboxes.forEach(function (cb) {
      cb.checked = opts.extras.indexOf(cb.value) !== -1;
    });

    // Toggle
    aiRefineToggle.checked = opts.refine || false;
  }

  function readOptionsFromModal() {
    var opts = {};

    // Radio buttons
    ["theme", "font", "layout", "page_size", "code_blocks", "tables"].forEach(function (name) {
      var selected = styleModal.querySelector('input[name="' + name + '"]:checked');
      opts[name] = selected ? selected.value : defaultStyleOptions[name];
    });

    // Checkbox groups
    opts.header_footer = [];
    styleModal.querySelectorAll('input[name="header_footer"]:checked').forEach(function (cb) {
      opts.header_footer.push(cb.value);
    });

    opts.extras = [];
    styleModal.querySelectorAll('input[name="extras"]:checked').forEach(function (cb) {
      opts.extras.push(cb.value);
    });

    // Toggle
    opts.refine = aiRefineToggle.checked;

    return opts;
  }

  function resetOptionsToDefaults() {
    currentStyleOptions = JSON.parse(JSON.stringify(defaultStyleOptions));
    syncModalToOptions(currentStyleOptions);
  }
```

- [ ] **Step 3: Add AI Recommend handler**

Add after the reset function:

```javascript
  // --- AI Recommend ---
  async function aiRecommend() {
    var content = contentInput.value.trim();
    if (!content) {
      alert("Enter some content first so AI can analyze it for recommendations.");
      return;
    }

    aiRecommendBtn.disabled = true;
    aiRecommendBtn.classList.add("loading");

    try {
      var response = await fetch(RECOMMEND_API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: content }),
      });

      if (!response.ok) {
        throw new Error("Server returned " + response.status);
      }

      var recommendations = await response.json();
      currentStyleOptions = recommendations;
      currentStyleOptions.refine = aiRefineToggle.checked;
      syncModalToOptions(currentStyleOptions);
    } catch (error) {
      alert("AI recommendation failed: " + error.message + "\n\nYou can still pick options manually.");
    } finally {
      aiRecommendBtn.disabled = false;
      aiRecommendBtn.classList.remove("loading");
    }
  }
```

- [ ] **Step 4: Modify `generatePDF` to use style options**

Replace the existing `generatePDF` function (lines 91-159) with:

```javascript
  // --- Generate PDF ---
  async function generatePDF() {
    var content = contentInput.value;
    var customCssOverride = cssInput.value;

    if (!content.trim()) {
      setState(states.ERROR, {
        message: "Please enter some content to convert.",
      });
      return;
    }

    setState(states.LOADING);

    // Build CSS from style options (unless user typed custom CSS)
    var finalCss = "";
    var refine = false;

    if (customCssOverride.trim()) {
      // User manually typed CSS — use it, skip style options
      finalCss = customCssOverride.trim();
      refine = false;
    } else {
      // Build CSS from style options
      finalCss = window.MarkFlowStyleBuilder.buildCSS(currentStyleOptions);
      refine = currentStyleOptions.refine || false;
    }

    var controller = new AbortController();
    var timeoutId = setTimeout(function () {
      controller.abort();
    }, TIMEOUT_MS);

    try {
      var response = await fetch(API_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: content, custom_css: finalCss, refine: refine }),
        signal: controller.signal,
      });

      clearTimeout(timeoutId);

      if (!response.ok) {
        var errorData;
        try {
          errorData = await response.json();
        } catch (_) {
          errorData = {};
        }
        var detail = (errorData.detail && errorData.detail.detail) || "";
        var errorMsg =
          (errorData.detail && errorData.detail.error) ||
          errorData.error ||
          "Request failed (HTTP " + response.status + ")";

        if (response.status === 504) {
          errorMsg = "Server took too long to generate your PDF. Try shorter content or disable AI Refine.";
        } else if (response.status === 500 && /timed out/i.test(detail)) {
          errorMsg = "PDF rendering timed out — your document may be too complex. Try shorter content.";
        }
        throw new Error(errorMsg);
      }

      var blob = await response.blob();
      var blobUrl = URL.createObjectURL(blob);
      setState(states.SUCCESS, { blobUrl: blobUrl });
    } catch (error) {
      clearTimeout(timeoutId);

      if (error.name === "AbortError") {
        setState(states.ERROR, {
          message: "Request timed out. The server is taking too long. Try shorter content or disable AI Refine.",
        });
      } else {
        setState(states.ERROR, {
          message:
            error.message ||
            "Something went wrong. Please check your input and try again.",
        });
      }
    }
  }
```

- [ ] **Step 5: Add modal event listeners**

Add after the existing event listeners block (after the keyboard shortcut handler at line 192):

```javascript
  // --- Modal Event Listeners ---
  styleOptionsBtn.addEventListener("click", openModal);
  modalCloseBtn.addEventListener("click", closeModal);
  modalApplyBtn.addEventListener("click", function () {
    currentStyleOptions = readOptionsFromModal();
    closeModal();
  });
  modalResetBtn.addEventListener("click", resetOptionsToDefaults);
  aiRecommendBtn.addEventListener("click", aiRecommend);

  // Close modal on overlay click
  styleModal.addEventListener("click", function (e) {
    if (e.target === styleModal) {
      closeModal();
    }
  });

  // Close modal on Escape
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && !styleModal.classList.contains("hidden")) {
      closeModal();
    }
  });
```

- [ ] **Step 6: Commit**

```bash
git add markflow/frontend/app.js
git commit -m "feat: integrate style options modal with PDF generate flow"
```

---

### Task 8: Integration Test — Full Round Trip

**Files:**
- No file changes — manual verification

- [ ] **Step 1: Start backend server**

```bash
cd markflow/backend
uvicorn main:app --reload --port 8000
```

- [ ] **Step 2: Open frontend in browser**

Open `markflow/frontend/index.html` in browser (or serve with `python -m http.server 3000` from `markflow/frontend/`).

- [ ] **Step 3: Verify modal opens and closes**

- Click "🎨 Style Options" button → modal appears
- Click "✕" → modal closes
- Press Escape → modal closes
- Click outside modal → modal closes

- [ ] **Step 4: Verify manual option picking**

- Open modal
- Select "Dark" theme, "Serif" font, "Grid" tables
- Click "Apply"
- Click "Generate PDF" with some markdown content
- Verify PDF renders with dark theme, serif font, grid tables

- [ ] **Step 5: Verify AI Recommend (requires API keys)**

- Open modal
- Enter content in textarea
- Click "✨ AI Recommend" → spinner appears → options auto-populate
- Tweak any option
- Click "Apply"
- Generate PDF → verify style matches picks

- [ ] **Step 6: Verify AI Refine toggle**

- Open modal, enable "AI Refine CSS" toggle
- Pick options, Apply
- Generate PDF → verify AI-refined CSS output (check backend logs for "AI-refined CSS" message)

- [ ] **Step 7: Verify backward compatibility**

- Type raw CSS in the "Custom CSS" textarea
- Generate PDF → verify raw CSS is used, style options ignored

- [ ] **Step 8: Final commit**

```bash
git add -A
git commit -m "feat: complete PDF style options panel with AI recommendation and CSS builder"
```
