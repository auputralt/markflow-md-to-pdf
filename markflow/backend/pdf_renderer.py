"""WeasyPrint PDF rendering with timeout guard."""

import logging
from concurrent.futures import TimeoutError as FuturesTimeoutError

from weasyprint import HTML

logger = logging.getLogger(__name__)

PDF_RENDER_TIMEOUT = 60  # seconds


def render_pdf(html_document: str, timeout: int = PDF_RENDER_TIMEOUT) -> bytes:
    """Render an HTML document string to PDF bytes with timeout protection."""
    try:
        # Run WeasyPrint in a thread pool to allow timeout enforcement
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_render, html_document)
            pdf_bytes = future.result(timeout=timeout)

        logger.info("PDF rendered: %d bytes", len(pdf_bytes))
        return pdf_bytes
    except FuturesTimeoutError:
        logger.error("PDF render timed out after %ds", timeout)
        raise RuntimeError(f"PDF rendering timed out after {timeout}s — document may be too complex")
    except Exception as e:
        logger.error("PDF render failed: %s", exc_info=True)
        raise RuntimeError(f"PDF generation failed: {e}") from e


def _do_render(html_document: str) -> bytes:
    """Actual WeasyPrint render — runs in thread pool."""
    pdf_bytes = HTML(string=html_document).write_pdf()
    if pdf_bytes is None:
        raise RuntimeError("WeasyPrint returned None instead of PDF bytes")
    return pdf_bytes
