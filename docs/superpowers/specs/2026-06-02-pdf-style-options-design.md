# PDF Style Options Panel — Design Spec

**Date:** 2026-06-02
**Status:** Approved
**Approach:** B — New `/recommend` endpoint + client-side CSS builder + hybrid AI refine

## Problem

Currently, MarkFlow generates PDFs with either AI-generated CSS or a hardcoded fallback. Users have no control over the PDF appearance beyond manually writing raw CSS. They need a visual interface to pick style options and optionally get AI-powered recommendations.

## Solution

A modal-based style options panel with 9 categories of visual choices, an AI recommendation feature that auto-selects options based on content analysis, and a client-side CSS builder that assembles WeasyPrint-compatible CSS from user picks. Optional AI refinement polishes the assembled CSS.

## Architecture

### Data Flow

```
User enters content
  → Clicks "Style Options" button → Modal opens
  → [Manual] Picks options → Apply
  → [AI] Clicks "AI Recommend" → POST /recommend → Picks populate → Tweaks → Apply
  → Modal closes, options stored in JS
  → Clicks "Generate PDF"
  → [AI Refine OFF] buildCSS(options) → custom_css to POST /generate
  → [AI Refine ON]  buildCSS(options) + content → POST /generate (AI polishes) → PDF
  → Preview/download (unchanged)
```

## UI Design — Modal

**Trigger:** "🎨 Style Options" button between CSS panel and "Generate PDF" button.

**Modal structure:**
- Top bar: "PDF Style Options" title + "AI Recommend ✨" button + close (X)
- Body: 9 category sections with radio buttons and checkboxes
- Footer: "Apply" (closes modal, saves selections) + "Reset to Defaults"

**Categories:**

| Category | Control Type | Options |
|---|---|---|
| Theme | Radio | Light, Dark, Sepia, Cream |
| Font | Radio | Sans-serif, Serif, Mono, Academic |
| Layout | Radio | Single column, Two column, Compact, Wide margins |
| Page size | Radio | A4, Letter, Legal |
| Header/Footer | Checkboxes | Page numbers, Title, Date |
| Code blocks | Radio | Highlighted, Plain, Bordered, Minimal |
| Tables | Radio | Striped rows, Clean, Grid borders |
| Extras | Checkboxes | Table of contents, Watermark |
| AI Refine CSS | Toggle | Off / On |

**AI Recommend UX:** Click → spinner on button → POST `/recommend` → auto-populate all checkboxes/radios → user can tweak → Apply.

## Backend — `/recommend` Endpoint

**Endpoint:** `POST /recommend`
**Timeout:** 15s max

**Request:**
```json
{ "content": "markdown or text..." }
```

**Response:**
```json
{
  "theme": "light",
  "font": "serif",
  "layout": "single",
  "page_size": "a4",
  "header_footer": ["page_numbers", "title"],
  "code_blocks": "highlighted",
  "tables": "striped",
  "extras": ["toc"]
}
```

**Implementation:** New file `backend/recommender.py`. Uses existing AI provider chain (Bluesminds → OpenRouter) with a dedicated system prompt instructing AI to analyze content and return a JSON style recommendation object. Snippet limited to 2000 chars for speed.

**Fallback defaults:**
```json
{
  "theme": "light",
  "font": "sans-serif",
  "layout": "single",
  "page_size": "a4",
  "header_footer": ["page_numbers"],
  "code_blocks": "bordered",
  "tables": "striped",
  "extras": []
}
```

## Client-Side CSS Builder

**New file:** `frontend/style-builder.js` — pure function, zero dependencies.

**API:**
```
buildCSS(styleOptions: object) → string
```

**Template mapping per category:**

- **Theme:** `:root` color tokens (background, text, heading, border colors). Light = white/dark. Dark = dark/light. Sepia = warm tones. Cream = off-white.
- **Font:** `body { font-family }` + heading stack. Sans = system-ui. Serif = Georgia. Mono = Fira Code. Academic = serif body + sans headings.
- **Layout:** `@page` margins, `body` width rules. Two-column uses CSS multi-column. Compact = tighter margins + smaller font.
- **Page size:** `@page { size: a4|letter|legal }`.
- **Header/Footer:** Conditional `@page` margin boxes for selected items.
- **Code blocks:** `pre, code` styles per variant. Highlighted = Pygments-friendly. Plain = no bg. Bordered = border + bg. Minimal = subtle bg.
- **Tables:** `table, th, td` per variant. Striped = nth-child. Clean = minimal borders. Grid = full borders.
- **Extras:** ToC = placeholder page hints. Watermark = fixed-position element.

**AI Refine integration:** When ON, frontend sends `{ content, custom_css: builtCSS, refine: true }` to `/generate`. Backend's `get_stylesheet` detects `refine=true` and passes the built CSS as a hint in the AI prompt. AI returns polished CSS. When OFF, built CSS sent as `custom_css` directly — backend skips AI.

## Backend Changes

### `backend/main.py`
- Add `POST /recommend` endpoint routed to `recommender.recommend_styles()`
- Add `refine: bool = False` field to `GenerateRequest` model
- Pass `refine` flag to `get_stylesheet()`

### `backend/ai_styler.py`
- `get_stylesheet()` signature: `async def get_stylesheet(html, custom_css, refine=False)`
- When `refine=True` and `custom_css` provided: use custom_css as a base hint in the AI prompt, asking AI to refine/polish the provided CSS rather than generate from scratch
- When `refine=False` and `custom_css` provided: return custom_css directly (unchanged behavior)

### `backend/recommender.py` (new)
- `async def recommend_styles(content: str) -> dict` — calls AI with recommendation prompt
- System prompt: analyze content, return JSON style picks
- Fallback: returns default style dict on AI failure
- JSON response parsing with validation against allowed option values

## Frontend Changes

### `frontend/index.html`
- Add "🎨 Style Options" button after CSS section
- Add modal markup with all 9 category sections
- Add `<script src="style-builder.js">` before `app.js`

### `frontend/style.css`
- Modal overlay and container styles
- Category section layout
- Radio button and checkbox custom styling (consistent with dark theme)
- Toggle switch for AI Refine
- AI Recommend button states (idle, loading spinner, done)
- Responsive modal (full-width on mobile)

### `frontend/app.js`
- Modal open/close state management
- Style options state object (default values)
- AI Recommend click handler: calls `/recommend`, populates UI
- Apply handler: saves options, closes modal
- Modified `generatePDF()`: calls `buildCSS(options)` instead of reading css-input
- Backward compat: if user typed in CSS textarea, that overrides style options

### `frontend/style-builder.js` (new)
- `buildCSS(options)` function
- CSS template fragments per category
- Template assembler that combines fragments into valid WeasyPrint CSS

## Files Changed

| File | Type | Change |
|---|---|---|
| `frontend/index.html` | Modify | Add Style Options button, modal markup |
| `frontend/style.css` | Modify | Modal, controls, toggle styling |
| `frontend/app.js` | Modify | Modal logic, generate flow with style options |
| `frontend/style-builder.js` | New | CSS template fragments + buildCSS() |
| `backend/main.py` | Modify | Add /recommend endpoint, refine param |
| `backend/ai_styler.py` | Modify | Accept refine flag + base CSS hint |
| `backend/recommender.py` | New | AI recommendation logic |

**Unchanged:** `converter.py`, `pdf_renderer.py`, `fallback.css`, `styles/` directory.

## Backward Compatibility

- Existing `custom_css` textarea still functional
- If user types CSS manually, it overrides style options (same as today)
- `/generate` endpoint accepts existing `{ content, custom_css }` without change
- `refine` field defaults to `false` — no behavior change for old clients

## Constraints

- WeasyPrint CSS compatibility: no CSS Grid, no gradients, no shadows in PDF CSS
- CSS Paged Media for headers/footers/page numbers
- AI recommendation timeout: 15s (fast, no PDF rendering)
- AI refine uses existing 50s chain timeout
- All frontend vanilla JS — no framework dependencies
