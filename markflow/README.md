<p align="center">
  <img src="https://raw.githubusercontent.com/auputralt/markflow-md-to-pdf/main/markflow/backend/favicon.svg" alt="MarkFlow" width="80" height="80">
</p>

<h1 align="center">MarkFlow</h1>

<p align="center">
  AI-powered Markdown to PDF converter with intelligent styling
</p>

<p align="center">
  <a href="https://github.com/auputralt/markflow-md-to-pdf/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.11%2B-blue.svg" alt="Python"></a>
  <a href="https://fastapi.tiangolo.com/"><img src="https://img.shields.io/badge/FastAPI-0.129+-green.svg" alt="FastAPI"></a>
  <a href="https://weasyprint.org/"><img src="https://img.shields.io/badge/WeasyPrint-68+-orange.svg" alt="WeasyPrint"></a>
</p>

---

MarkFlow converts raw content — **Markdown, JSON, HTML, or plain text** — into professionally styled PDFs. It uses AI to analyze your content and generate unique CSS designs for each document, so your PDFs look polished without manual formatting.

## ✨ Features

- **Multi-format input** — Markdown, JSON, HTML, plain text. Auto-detected.
- **AI-powered styling** — Natural language style prompts. Describe what you want, AI writes the CSS.
- **AI style recommendations** — Content-aware suggestions for theme, font, layout, page size, headers/footers, code block style, and table style.
- **Provider fallback chain** — Bluesminds → OpenRouter. If one fails, the other takes over.
- **CSS safety enforcement** — AI output is sanitized to prevent broken layouts (lists going inline, etc.).
- **Custom CSS override** — Bring your own CSS or refine AI-generated styles.
- **Production PDF output** — Page numbers, headers, syntax-highlighted code blocks, tables, callout boxes.
- **4-state UI** — Clear idle → loading → success → error transitions.
- **Zero-dependency frontend** — Pure HTML/CSS/vanilla JS. No build step.

## 🚀 Quick Start

```bash
# 1. Clone
git clone https://github.com/auputralt/markflow-md-to-pdf.git
cd markflow-md-to-pdf

# 2. Install backend dependencies
pip install -r markflow/backend/requirements.txt

# 3. Configure API keys (optional — fallback CSS works without keys)
cp markflow/backend/.env.example markflow/backend/.env
# Edit .env with your keys

# 4. Run
cd markflow/backend
uvicorn main:app --reload --port 8000
```

Open `markflow/frontend/index.html` in your browser. That's it.

## 📖 Usage

### Web Interface

1. Paste content into the editor (Markdown, JSON, HTML, or text)
2. Optionally describe your desired style in the prompt field (e.g. *"clean academic style with blue headers"*)
3. Press **Ctrl+Enter** or click **Generate PDF**
4. Preview and download

### API

```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "# Hello World\n\nThis is **bold** and *italic* text.",
    "style_prompt": "minimalist dark theme"
  }' \
  -o output.pdf
```

```python
import requests

response = requests.post("http://localhost:8000/generate", json={
    "content": "# Report\n\n## Summary\n\nKey findings go here.",
    "style_prompt": "corporate report style"
})

if response.status_code == 200:
    with open("report.pdf", "wb") as f:
        f.write(response.content)
```

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/generate` | POST | Convert content to styled PDF |
| `/recommend` | POST | Get AI style recommendations for content |
| `/health` | GET | Health check |

**POST `/generate`** body:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Raw content (Markdown, JSON, HTML, text) |
| `custom_css` | string | No | Override CSS entirely |
| `style_prompt` | string | No | Natural language style description |

**POST `/recommend`** body:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `content` | string | Yes | Content to analyze |
| `style_prompt` | string | No | User's style preference to factor in |

Returns recommended options for: theme, font, layout, page size, headers/footers, code blocks, tables, extras (TOC, watermark).

## ⚙️ Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | No | OpenRouter API key for AI CSS generation |
| `BLUESMINDS_API_KEY` | No | Bluesminds API key (primary provider) |
| `CORS_ORIGINS` | No | Comma-separated allowed origins (default: `*`) |

Without API keys, MarkFlow uses a built-in fallback stylesheet. All AI features are gracefully skipped.

## 🗂️ Project Structure

```
markflow-md-to-pdf/
├── markflow/
│   ├── backend/
│   │   ├── main.py              # FastAPI app, routes, middleware
│   │   ├── converter.py         # Content detection & format conversion
│   │   ├── ai_styler.py         # AI CSS generation with prompt/refine modes
│   │   ├── pdf_renderer.py      # WeasyPrint PDF rendering with timeout
│   │   ├── providers.py         # AI provider config & fallback chain
│   │   ├── recommender.py       # AI style recommendation engine
│   │   ├── styles/
│   │   │   └── fallback.css     # Built-in stylesheet when AI unavailable
│   │   ├── favicon.svg
│   │   ├── requirements.txt
│   │   └── .env.example
│   └── frontend/
│       ├── index.html           # Main UI
│       ├── app.js               # State machine & API client
│       └── style.css            # Frontend styling
├── render.yaml                  # Render.com deployment config
├── LICENSE                      # MIT
└── README.md
```

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| PDF Engine | WeasyPrint (CSS Paged Media) |
| Markdown | markdown-it-py |
| Syntax Highlighting | Pygments |
| HTML Sanitization | lxml_html_clean |
| AI Integration | httpx → Bluesminds / OpenRouter (OpenAI-compatible API) |
| Frontend | Vanilla HTML, CSS, JavaScript |

## 🌐 Deploy to Render (Free)

1. Push to GitHub
2. Go to [render.com](https://render.com) → **New** → **Web Service**
3. Connect your repo
4. Set **Build Command**:
   ```
   pip install -r markflow/backend/requirements.txt
   ```
5. Set **Start Command**:
   ```
   cd markflow/backend && uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
6. Set environment variables (`OPENROUTER_API_KEY`, `BLUESMINDS_API_KEY`)
7. Choose **Free** instance type → Deploy

Or use the included `render.yaml` Blueprint for automatic config detection.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Commit with [Conventional Commits](https://www.conventionalcommits.org/)
4. Open a pull request

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/auputralt">auputra</a>
</p>
