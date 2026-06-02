"""MarkFlow — FastAPI application for content-to-PDF conversion."""

import asyncio
import logging
import os
import re
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from ai_styler import get_stylesheet
from converter import assemble_document, convert_to_html, detect_content_type
from pdf_renderer import render_pdf

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Global request timeout (seconds) — caps the entire /generate pipeline
REQUEST_TIMEOUT_SECONDS = 120

# Maximum content length (chars) — prevents OOM on huge payloads
MAX_CONTENT_LENGTH = 500_000

app = FastAPI(title="MarkFlow", version="1.0.0", description="Content to styled PDF")

# CORS: use specific origins in production; wildcard without credentials for dev
_allowed_origins = os.getenv("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def timeout_middleware(request: Request, call_next):
    """Guard every request with a global timeout."""
    if request.url.path == "/health":
        return await call_next(request)

    try:
        return await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT_SECONDS)
    except asyncio.TimeoutError:
        logger.error("Request timed out after %ds: %s %s", REQUEST_TIMEOUT_SECONDS, request.method, request.url.path)
        return JSONResponse(
            status_code=504,
            content={"error": "Server timeout", "detail": f"Request exceeded {REQUEST_TIMEOUT_SECONDS}s limit. Try shorter content."},
        )


class GenerateRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=MAX_CONTENT_LENGTH, description="Raw content to convert")
    custom_css: str = Field(default="", max_length=50_000, description="Optional CSS override (legacy)")
    style_prompt: str = Field(default="", max_length=10_000, description="Natural language style prompt")


class ErrorResponse(BaseModel):
    error: str
    detail: str = ""


def _error_response(status_code: int, error: str, detail: str = "") -> JSONResponse:
    """Return a consistent error response shape."""
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "detail": detail},
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "markflow"}


@app.get("/favicon.svg")
async def favicon():
    """Serve the favicon to suppress 404 noise in browser dev tools."""
    favicon_path = Path(__file__).parent / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(str(favicon_path), media_type="image/svg+xml")
    return Response(status_code=204)


@app.post(
    "/generate",
    responses={
        200: {"content": {"media_type": "application/pdf"}},
        422: {"model": ErrorResponse, "description": "Empty input"},
        500: {"model": ErrorResponse, "description": "Generation failure"},
    },
)
async def generate(request: GenerateRequest) -> Response:
    content = request.content

    if not content.strip():
        return _error_response(422, "Input content cannot be empty")

    logger.info(
        "Generate request: %d chars content, %d chars custom_css, %d chars style_prompt",
        len(content),
        len(request.custom_css),
        len(request.style_prompt),
    )

    try:
        # 1. Detect content type and convert to HTML
        content_type = detect_content_type(content)
        logger.info("Detected content type: %s", content_type)

        html_body = convert_to_html(content, content_type)
        logger.info("HTML body: %d chars", len(html_body))

        # 2. Get CSS (custom, prompt-driven, AI-generated, or fallback)
        style_prompt = request.style_prompt.strip() if request.style_prompt else ""
        custom_css = request.custom_css.strip() if request.custom_css else ""
        css = await get_stylesheet(html_body, custom_css=custom_css, style_prompt=style_prompt)
        logger.info("CSS: %d chars", len(css))

        # 3. Assemble full HTML document
        document = assemble_document(html_body, css)
        logger.info("Full document: %d chars", len(document))

        # 4. Render to PDF
        pdf_bytes = render_pdf(document)
        logger.info("PDF generated: %d bytes", len(pdf_bytes))

        # 5. Return binary PDF response
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": 'attachment; filename="markflow-output.pdf"',
                "Content-Length": str(len(pdf_bytes)),
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Generation failed: %s", exc_info=True)
        # Don't leak internal details — log them, return generic message
        raise HTTPException(
            status_code=500,
            detail={"error": "PDF generation failed", "detail": _safe_error_message(e)},
        )


def _safe_error_message(exc: Exception) -> str:
    """Return a user-safe error message that doesn't leak internals."""
    msg = str(exc)
    # Hide API keys, file paths, and internal URLs
    msg = re.sub(r'(key["\s:=]+)["\']?\w{8,}["\']?', '***', msg, flags=re.IGNORECASE)
    msg = re.sub(r'/[\w/.-]+\.py', '[path]', msg)
    msg = re.sub(r'https?://[^\s"\']+', '[url]', msg)
    # Truncate long messages
    if len(msg) > 200:
        msg = msg[:200] + "..."
    return msg


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all so client always gets a JSON error, never a bare timeout."""
    logger.error("Unhandled exception: %s", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "detail": _safe_error_message(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
