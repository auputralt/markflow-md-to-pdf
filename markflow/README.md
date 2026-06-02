# MarkFlow

Transform any text into beautiful, styled PDFs with AI-powered design.

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.95.0-green)](https://fastapi.tiangolo.com/)
[![WeasyPrint](https://img.shields.io/badge/WeasyPrint-60.0-orange)](https://weasyprint.org/)
[![OpenRouter](https://img.shields.io/badge/OpenRouter-API-important)](https://openrouter.ai/)

MarkFlow converts raw text content — Markdown, JSON, HTML, or plain text — into professionally styled, multi-page PDFs. Leveraging AI via OpenRouter, it generates unique CSS designs tailored to each document, ensuring your content looks exceptional without manual styling.

## ✨ Features

- **Multi-format Input**: Seamlessly handle Markdown, JSON, HTML, and plain text.
- **AI-Powered Styling**: OpenRouter creates custom CSS for every document (fallback to professional hardcoded styles available).
- **Custom CSS Override**: Inject your own CSS to fine-tune or completely replace AI-generated styles.
- **Production-Ready PDF Output**: Includes typography hierarchy, page numbers, headers, code blocks, tables, and callout boxes.
- **Responsive State Machine UI**: Clear loading, success, and error states with instant PDF preview.
- **Zero-Dependency Frontend**: Pure HTML, CSS, and vanilla JavaScript for maximum compatibility.

## 📋 Table of Contents
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Usage](#usage)
- [API Reference](#api-reference)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Contribution Guidelines](#contribution-guidelines)
- [Support](#support)

## 🔧 Prerequisites

Before you begin, ensure you have the following installed:
- [Python 3.11+](https://www.python.org/downloads/)
- [pip](https://pip.pypa.io/en/stable/installation/)
- An [OpenRouter API key](https://openrouter.ai/) (optional for fallback styling)

## 🚀 Installation

Follow these steps to set up MarkFlow locally:

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone https://github.com/your-username/markflow.git
   cd markflow
   ```

2. **Install backend dependencies**:
   ```bash
   cd backend
   pip install -r requirements.txt
   ```

3. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and add your OpenRouter API key:
   ```env
   OPENROUTER_API_KEY=your_key_here
   ```
   > **Note**: If you don't provide an API key, MarkFlow will use a built-in fallback CSS stylesheet.

4. **Start the development server**:
   ```bash
   uvicorn main:app --reload --port 8000
   ```
   The backend will be available at `http://localhost:8000`.

5. **Open the frontend**:
   - Open `frontend/index.html` in your browser, or
   - Use a live server extension (e.g., Live Server for VS Code) for automatic reloads.

## 💻 Usage

### Via Web Interface
1. Navigate to the frontend (typically `http://localhost:8000/frontend/index.html` if served via backend, or open `frontend/index.html` directly).
2. Paste your content into the text area (Markdown, JSON, HTML, or plain text).
3. Optionally, add custom CSS in the provided field.
4. Press `Ctrl+Enter` (or `Cmd+Enter` on Mac) or click the "Generate PDF" button.
5. Download the generated PDF from the preview pane.

### Via API (cURL Example)
```bash
curl -X POST "http://localhost:8000/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "content": "# Hello World\n\nThis is a test PDF generated via the MarkFlow API.",
    "custom_css": "h1 { color: #2c3e50; border-bottom: 2px solid #3498db; }"
  }' \
  -o output.pdf
```

### Via API (Python Example)
```python
import requests

url = "http://localhost:8000/generate"
payload = {
    "content": "# Hello World\n\nGenerated from Python script.",
    "custom_css": "body { font-family: 'Georgia', serif; }"
}
response = requests.post(url, json=payload)

if response.status_code == 200:
    with open("output.pdf", "wb") as f:
        f.write(response.content)
    print("PDF saved as output.pdf")
else:
    print(f"Error: {response.status_code} - {response.text}")
```

## 📚 API Reference

### Generate PDF
**Endpoint**: `POST /generate`  
**Description**: Converts input content to a styled PDF.

**Request Body**:
| Field        | Type   | Required | Description                          |
|--------------|--------|----------|--------------------------------------|
| `content`    | string | Yes      | Raw content to convert (Markdown, JSON, HTML, or plain text) |
| `custom_css` | string | No       | Custom CSS to override AI-generated styles |

**Response**:
- **Success**: Binary PDF (`application/pdf`) with header `Content-Disposition: attachment; filename="markflow-output.pdf"`
- **Errors**:
  - `422 Unprocessable Entity`: Empty input content
  - `500 Internal Server Error`: PDF generation failed (details in response body)

### Health Check
**Endpoint**: `GET /health`  
**Description**: Verifies service availability.

**Response**:
```json
{"status": "ok", "service": "markflow"}
```

## 🗂️ Project Structure

```
markflow/
├── backend/
│   ├── main.py              # FastAPI application setup and routes
│   ├── converter.py         # Content detection and format conversion
│   ├── ai_styler.py         # OpenRouter integration and CSS generation
│   ├── pdf_renderer.py      # PDF rendering via WeasyPrint
│   ├── styles/
│   │   └── fallback.css     # Hardcoded default stylesheet
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── index.html           # Main UI template
│   ├── app.js               # Application logic and state management
│   └── style.css            # Frontend-specific styling
└── README.md
```

## ⚙️ Tech Stack

- **Backend**:
  - Python 3.11+
  - [FastAPI](https://fastapi.tiangolo.com/) - High-performance web framework
  - [WeasyPrint](https://weasyprint.org/) - HTML/CSS to PDF conversion
  - [markdown-it-py](https://github.com/explosion/markdown-it-py) - Markdown parsing
  - [httpx](https://www.python-httpx.org/) - HTTP client for OpenRouter
  - [python-dotenv](https://pypi.org/project/python-dotenv/) - Environment variable management
  - [uvicorn](https://www.uvicorn.org/) - ASGI server

- **Frontend**:
  - HTML5
  - CSS3
  - Vanilla JavaScript (no frameworks or dependencies)

- **AI Integration**:
  - [OpenRouter](https://openrouter.ai/) - Access to LLMs for CSS generation
  - Model: `openrouter/free` (configurable in `ai_styler.py`)

## 🤝 Contribution Guidelines

We welcome contributions to make MarkFlow better! Please follow these guidelines:

1. **Fork the repository** and create a new branch for your feature or bugfix.
2. **Keep changes focused** and ensure they align with the project's scope.
3. **Write clear, descriptive commit messages** following [Conventional Commits](https://www.conventionalcommits.org/).
4. **Update documentation** as needed, especially if changing APIs or usage.
5. **Submit a pull request** with a detailed explanation of your changes.
6. **Respect the code style**: 
   - Backend: Follow [PEP 8](https://peps.python.org/pep-0008/) with [Black](https://black.dev/) formatting.
   - Frontend: Maintain consistent indentation and comment complex logic.

### Reporting Issues
Please use the [issue tracker](https://github.com/your-username/markflow/issues) to report bugs or request features. Include:
- A clear title and description
- Steps to reproduce (for bugs)
- Expected vs. actual behavior
- Screenshots or logs if applicable

## 🙋‍♂️ Support

If you encounter any issues or have questions, please:
- Check the [existing issues](https://github.com/your-username/markflow/issues) first
- Open a new issue with the label `question` or `bug`
- For urgent matters, you may reach out to the maintainers directly

---

Made with ❤️ by the MarkFlow Team

*Transforming text into beauty, one PDF at a time.*