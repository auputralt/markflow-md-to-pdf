# PDF Rendering Overhaul — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give users full creative control over PDF styling via AI-generated CSS — remove rigid aesthetic restrictions, add style presets to the UI.

**Architecture:** Backend change in `ai_styler.py` rewrites 2 AI system prompts to remove hardcoded academic style and allow shadows/gradients/decorations. Frontend changes in 3 files add clickable style preset chips and make the style prompt panel visible by default. No new dependencies, no backend route changes.

**Tech Stack:** Python, FastAPI, WeasyPrint, vanilla HTML/CSS/JS

---

### Task 1: Rewrite AI System Prompt (default mode)

**Files:**
- Modify: `markflow/backend/ai_styler.py:15-61` (SYSTEM_PROMPT)

- [ ] **Step 1: Replace SYSTEM_PROMPT with style-agnostic version**

Replace lines 15-61 in `ai_styler.py` — the entire `SYSTEM_PROMPT` string — with:

```python
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
```

- [ ] **Step 2: Verify no syntax errors**

Run: `cd markflow/backend && python -c "from ai_styler import SYSTEM_PROMPT; print(f'OK: {len(SYSTEM_PROMPT)} chars')"`
Expected: `OK: <number> chars`

- [ ] **Step 3: Commit**

```bash
git add markflow/backend/ai_styler.py
git commit -m "refactor: rewrite SYSTEM_PROMPT to be style-agnostic and content-aware"
```

---

### Task 2: Rewrite AI Prompt-Driven System Prompt

**Files:**
- Modify: `markflow/backend/ai_styler.py:78-111` (PROMPT_DRIVEN_SYSTEM_PROMPT)

- [ ] **Step 1: Replace PROMPT_DRIVEN_SYSTEM_PROMPT with creative-freedom version**

Replace lines 78-111 in `ai_styler.py` — the entire `PROMPT_DRIVEN_SYSTEM_PROMPT` string — with:

```python
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
```

- [ ] **Step 2: Verify no syntax errors**

Run: `cd markflow/backend && python -c "from ai_styler import PROMPT_DRIVEN_SYSTEM_PROMPT; print(f'OK: {len(PROMPT_DRIVEN_SYSTEM_PROMPT)} chars')"`
Expected: `OK: <number> chars`

- [ ] **Step 3: Commit**

```bash
git add markflow/backend/ai_styler.py
git commit -m "refactor: rewrite PROMPT_DRIVEN_SYSTEM_PROMPT for full creative freedom"
```

---

### Task 3: Add Style Preset Chips to HTML

**Files:**
- Modify: `markflow/frontend/index.html:59-75` (style prompt section)

- [ ] **Step 1: Add preset chips and make panel open by default**

In `markflow/frontend/index.html`, replace the entire `<div class="style-prompt">` block (lines 59-75) with:

```html
      <div class="style-prompt">
        <button id="css-toggle" class="style-prompt__toggle" type="button">
          <span class="css-toggle-arrow">▾</span>
          <span class="style-prompt__label">Style</span>
        </button>
        <div id="css-panel" class="style-prompt__panel">
          <div class="style-presets">
            <button class="preset-chip" data-prompt="Clean academic paper style. Serif font (Georgia), single column, A4, page numbers, structured headings with borders, compact spacing, traditional formal typography.">Academic</button>
            <button class="preset-chip" data-prompt="Modern minimalist design. Sans-serif font (Inter or Helvetica), generous whitespace, thin borders, subtle gray accents, clean typography hierarchy with lots of breathing room between sections.">Modern</button>
            <button class="preset-chip" data-prompt="Ultra minimal. Black and white only, no decorations, no borders on headings, maximum whitespace, Helvetica font, content-focused, zero visual noise.">Minimal</button>
            <button class="preset-chip" data-prompt="Dark theme document. Dark gray background (#1a1a2e), light text (#e0e0e0), blue accents (#4fc3f7), code blocks with darker background, modern tech document feel, vibrant syntax highlighting.">Dark</button>
            <button class="preset-chip" data-prompt="Creative and vibrant design. Colorful section headers with gradient accents, playful but professional typography, magazine-style layout with visual flair, unique and eye-catching.">Creative</button>
            <button class="preset-chip" data-prompt="Professional business report. Corporate navy (#1a365d) headers, clean tables with alternating rows, executive summary style, formal but modern, data-focused layout.">Report</button>
          </div>
          <textarea
            id="style-prompt-input"
            class="style-prompt__textarea"
            placeholder="Pick a preset above or type your own style description…"
            spellcheck="true"
          ></textarea>
        </div>
      </div>
```

Key changes:
- Arrow default changed from `▸` to `▾` (open state)
- Panel div no longer has `collapsed` class (open by default)
- Added `<div class="style-presets">` with 6 preset chip buttons
- Updated placeholder text
- Label shortened from "Style Prompt" to "Style"

- [ ] **Step 2: Verify HTML structure**

Open `index.html` in browser or validate. Ensure no unclosed tags.

- [ ] **Step 3: Commit**

```bash
git add markflow/frontend/index.html
git commit -m "feat: add style preset chips and open style panel by default"
```

---

### Task 4: Add Preset Chip Click Handlers in JS

**Files:**
- Modify: `markflow/frontend/app.js:184-215` (add handlers before event listeners section)

- [ ] **Step 1: Add preset chip click logic**

In `markflow/frontend/app.js`, add the following code BEFORE the `// --- Event Listeners ---` comment (before line 203). Insert after the `resetApp` function and before the event listeners section:

```javascript
  // --- Style Preset Chips ---
  var presetChips = document.querySelectorAll(".preset-chip");
  var activePreset = null;

  presetChips.forEach(function (chip) {
    chip.addEventListener("click", function () {
      var prompt = chip.getAttribute("data-prompt");

      // Toggle off if clicking active preset
      if (activePreset === chip) {
        chip.classList.remove("preset-chip--active");
        stylePromptInput.value = "";
        activePreset = null;
        return;
      }

      // Deactivate previous
      if (activePreset) {
        activePreset.classList.remove("preset-chip--active");
      }

      // Activate this one
      chip.classList.add("preset-chip--active");
      stylePromptInput.value = prompt;
      activePreset = chip;
    });
  });

  // Clear active preset when user types custom text
  if (stylePromptInput) {
    stylePromptInput.addEventListener("input", function () {
      // Check if current text matches any preset
      var matchesPreset = false;
      presetChips.forEach(function (chip) {
        if (chip.getAttribute("data-prompt") === stylePromptInput.value) {
          matchesPreset = true;
        }
      });

      if (!matchesPreset && activePreset) {
        activePreset.classList.remove("preset-chip--active");
        activePreset = null;
      }
    });
  }
```

- [ ] **Step 2: Verify JS syntax**

Run: `node -c markflow/frontend/app.js`
Expected: No syntax errors

- [ ] **Step 3: Commit**

```bash
git add markflow/frontend/app.js
git commit -m "feat: add preset chip click handlers with toggle and custom text detection"
```

---

### Task 5: Style Preset Chips in CSS

**Files:**
- Modify: `markflow/frontend/style.css:286-359` (style prompt section)

- [ ] **Step 1: Add preset chip styles and update panel styles**

In `markflow/frontend/style.css`, add the following CSS block AFTER the `.style-prompt__panel:not(.collapsed)` rule (after line 341) and BEFORE the `.style-prompt__textarea` rule (line 343):

```css
/* --- Style Presets --- */
.style-presets {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  padding: 10px 14px 8px;
}

.preset-chip {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
  font-family: var(--font-sans);
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
  background: var(--surface-hover);
  border: 1px solid var(--border);
  border-radius: 100px;
  cursor: pointer;
  transition:
    background var(--transition),
    color var(--transition),
    border-color var(--transition);
  white-space: nowrap;
}

.preset-chip:hover {
  background: var(--surface-raised);
  color: var(--text-dim);
  border-color: var(--border-hover);
}

.preset-chip--active {
  background: var(--accent-muted);
  color: var(--accent);
  border-color: var(--accent);
}
```

Also update `.style-prompt__panel:not(.collapsed)` max-height to accommodate presets + textarea:

Change line 338-341 from:
```css
.style-prompt__panel:not(.collapsed) {
  max-height: 220px;
  opacity: 1;
}
```

To:
```css
.style-prompt__panel:not(.collapsed) {
  max-height: 320px;
  opacity: 1;
}
```

- [ ] **Step 2: Verify no CSS errors**

Open in browser or use CSS validator. Ensure no unclosed rules.

- [ ] **Step 3: Commit**

```bash
git add markflow/frontend/style.css
git commit -m "feat: add preset chip styling with active/hover states"
```

---

### Task 6: Integration Test — Manual Verification

**Files:** None (testing only)

- [ ] **Step 1: Start the server**

Run: `cd markflow/backend && pip install -r requirements.txt && python main.py`
Expected: Server starts on `http://localhost:8000`

- [ ] **Step 2: Open frontend in browser**

Open `markflow/frontend/index.html` (or serve via backend static files).
Verify:
- Style panel is open by default (arrow points down ▾)
- 6 preset chips are visible: Academic, Modern, Minimal, Dark, Creative, Report
- Clicking a chip fills the textarea with the preset prompt
- Clicking the same chip again clears it
- Clicking a different chip switches the active state
- Typing custom text clears the active chip highlight

- [ ] **Step 3: Generate a PDF with a preset**

1. Paste sample markdown content
2. Click "Dark" preset
3. Click "Generate PDF"
4. Verify: PDF has dark theme styling (dark background, light text, blue accents)

- [ ] **Step 4: Generate a PDF with custom prompt**

1. Clear the style input
2. Type "make it look like a colorful magazine with gradient headers"
3. Click "Generate PDF"
4. Verify: PDF has colorful/gradient styling, not the old academic-only look

- [ ] **Step 5: Generate a PDF with no style prompt**

1. Clear the style input completely
2. Click "Generate PDF"
3. Verify: PDF looks professional and appropriate for the content type (not broken, not necessarily academic)

- [ ] **Step 6: Final commit if any fixes needed**

```bash
git add -A
git commit -m "fix: integration test fixes"
```
