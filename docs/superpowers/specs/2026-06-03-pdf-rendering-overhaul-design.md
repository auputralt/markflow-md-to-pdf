# PDF Rendering Overhaul — Design Spec

**Date:** 2026-06-03
**Status:** Approved
**Scope:** AI CSS generation quality + style preset UI

## Problem

MarkFlow's PDF output is constrained to a single "academic study guide" aesthetic. The AI system prompt hardcodes this style and explicitly forbids shadows, gradients, decorative elements, and colored accents. Users can write style prompts, but the panel is collapsed by default — most users never discover it. Result: every PDF looks the same regardless of user intent.

## Goal

Users paste any content (Markdown, JSON, HTML, text), describe the style they want (via presets or custom prompt), and get a beautifully styled PDF that matches their description. Content is preserved exactly as written — only CSS changes.

## Changes

### 1. AI System Prompt Overhaul (`markflow/backend/ai_styler.py`)

**Replace `SYSTEM_PROMPT`** (used when no style prompt given):
- Remove rigid "academic study guide" direction
- Make AI analyze content and choose appropriate default style
- Keep WeasyPrint constraints: no CSS Grid, CSS Paged Media, structural element safety
- Remove aesthetic restrictions: shadows, gradients, decorative elements now allowed
- AI should produce a clean, professional default that adapts to content type

**Replace `PROMPT_DRIVEN_SYSTEM_PROMPT`** (used when user provides style prompt):
- User's style description takes FULL priority over any default
- Remove "no shadows, no gradients, no decorative elements" rule
- Keep WeasyPrint technical constraints only (no CSS Grid, no layout-breaking properties)
- Keep structural safety rules (lists stack vertically, tables stay tables, paragraphs stay block)
- AI should interpret user's aesthetic direction creatively and fully

**Keep unchanged:**
- `REFINE_PROMPT` — already flexible
- `_enforce_css_safety()` — structural safety is separate from aesthetic freedom
- `strip_markdown_fences()` — works fine
- All request builders, provider chain, fallback logic

### 2. Style Preset UI (`markflow/frontend/`)

**Add preset chips** in [index.html](markflow/frontend/index.html):
- Row of clickable chips above the style prompt textarea
- Presets: `Academic`, `Modern`, `Minimal`, `Dark`, `Creative`, `Report`
- Each chip is a `<button>` with a data attribute containing the preset prompt text

**Preset prompt texts** (in [app.js](markflow/frontend/app.js)):
- `Academic`: "Clean academic paper style. Serif font (Georgia), single column, A4, page numbers, structured headings with borders, compact spacing, traditional footnotes style."
- `Modern`: "Modern minimalist design. Sans-serif font, generous whitespace, thin borders, subtle gray accents, clean typography hierarchy, lots of breathing room."
- `Minimal`: "Ultra minimal. Black and white only, no decorations, no borders on headings, maximum whitespace, Helvetica font, content-focused."
- `Dark`: "Dark theme. Dark gray background (#1a1a2e), light text (#e0e0e0), blue accents (#4fc3f7), code blocks with darker background, modern tech document feel."
- `Creative`: "Creative and vibrant. Colorful section headers, gradient accents, playful typography, rounded elements where possible, magazine-style layout."
- `Report`: "Professional business report. Corporate blue (#1a365d) headers, clean tables with alternating rows, executive summary style, formal but modern."

**Behavior** (in [app.js](markflow/frontend/app.js)):
- Clicking a preset fills the style prompt textarea with the preset text
- Clicking the same preset again clears it
- Active preset gets highlighted state
- Generate button sends `style_prompt` as before — backend unchanged

**Style prompt panel** in [index.html](markflow/frontend/index.html):
- Default to **open/visible** instead of collapsed
- Keep toggle functionality but change default state

**Styling** in [style.css](markflow/frontend/style.css):
- Preset chips: pill-shaped buttons, horizontal row, gap between
- Active state: filled background matching brand color
- Hover state: subtle background change

### 3. What Stays Unchanged

- `markflow/backend/converter.py` — content detection and HTML conversion
- `markflow/backend/pdf_renderer.py` — WeasyPrint rendering
- `markflow/backend/providers.py` — AI provider chain
- `markflow/backend/main.py` — API routes and middleware
- `markflow/backend/recommender.py` — style recommendations
- `markflow/backend/styles/fallback.css` — fallback stylesheet
- `render.yaml`, `Procfile`, deployment config

## Technical Constraints

- WeasyPrint CSS Paged Media — no CSS Grid
- Flexbox allowed only for internal element layout
- Structural elements must keep default display (li=list-item, p=block, table=table)
- No external resources (fonts, images) in AI-generated CSS
- CSS sanitization prevents @import and url()
- Content length limit: 500k chars
- CSS response minimum: 100 chars

## Files Changed

| File | Change |
|------|--------|
| `markflow/backend/ai_styler.py` | Rewrite SYSTEM_PROMPT and PROMPT_DRIVEN_SYSTEM_PROMPT |
| `markflow/frontend/index.html` | Add preset chips, open style panel by default |
| `markflow/frontend/app.js` | Add preset click handlers |
| `markflow/frontend/style.css` | Style preset chips |

## Success Criteria

1. User clicks "Dark" preset → gets dark-themed PDF
2. User types "make it look like a GitHub README" → gets appropriate styling
3. User leaves prompt empty → gets a clean, content-appropriate default (not always academic)
4. Lists still stack vertically, tables still work — no layout breaks
5. AI CSS passes safety checks
