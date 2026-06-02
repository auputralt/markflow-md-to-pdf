"""Content detection, format conversion, and HTML document assembly."""

import json
import re
from html import escape, unescape
from markdown_it import MarkdownIt
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import guess_lexer, TextLexer
from lxml_html_clean import Cleaner

# Allowed CSS property prefixes for sanitization
_ALLOWED_CSS_PREFIXES = (
    "font", "color", "background", "border", "margin", "padding",
    "line-height", "text-align", "text-decoration", "text-transform",
    "letter-spacing", "word-spacing", "white-space", "page-break",
    "orphans", "widows", "display", "width", "height", "max-width",
    "float", "clear", "list-style", "column", "content", "size",
    "overflow", "position", "top", "bottom", "left", "right",
    "opacity", "visibility", "vertical-align", "direction",
    "box-sizing", "flex", "justify", "align", "indent", "gap",
    # Custom properties (CSS variables) used by fallback CSS
    "var(--",
)

_BLOCKED_CSS_PATTERNS = (
    re.compile(r"@import\b", re.IGNORECASE),
    re.compile(r"url\s*\(", re.IGNORECASE),
    re.compile(r"expression\s*\(", re.IGNORECASE),
    re.compile(r"-moz-binding\b", re.IGNORECASE),
    re.compile(r"behavior\s*:", re.IGNORECASE),
    re.compile(r"@\s*charset\b", re.IGNORECASE),
)


def _highlight_code(code: str, language: str = "") -> str:
    """Apply Pygments syntax highlighting to code blocks."""
    try:
        if language:
            from pygments.lexers import get_lexer_by_name
            lexer = get_lexer_by_name(language, stripall=True)
        else:
            lexer = guess_lexer(code)
    except Exception:
        lexer = TextLexer()

    formatter = HtmlFormatter(nowrap=True, style="monokai")
    return highlight(code, lexer, formatter)


def sanitize_html(html_content: str) -> str:
    """Sanitize HTML to prevent XSS/SSRF. Removes scripts, dangerous attributes, external resources."""
    cleaner = Cleaner(
        safe_attrs_only=True,
        page_structure=True,
        forms=False,
        remove_unknown_tags=False,
        style=False,
        links=False,
        javascript=True,
        scripts=True,
        inline_style=False,
        embedded=False,
    )
    return cleaner.clean_html(html_content)


def sanitize_css(css: str) -> str:
    """Sanitize CSS to prevent SSRF via @import or url(). Removes dangerous directives."""
    lines = css.split("\n")
    safe_lines = []
    for line in lines:
        # Skip blocked patterns
        blocked = False
        for pattern in _BLOCKED_CSS_PATTERNS:
            if pattern.search(line):
                blocked = True
                break
        if blocked:
            continue
        safe_lines.append(line)
    return "\n".join(safe_lines)


def convert_markdown(content: str) -> str:
    """Convert Markdown to HTML using markdown-it-py with syntax highlighting."""
    md = (
        MarkdownIt("commonmark", {"html": False, "breaks": True})
        .enable("table")
        .enable("strikethrough")
    )

    html = md.render(content)

    # Apply syntax highlighting to fenced code blocks
    # markdown-it-py outputs: <pre><code class="language-python">...</code></pre>
    def _highlight_match(match):
        full_match = match.group(0)
        code_match = re.search(
            r'<code(?:\s+class="language-(\w+)")?>(.*?)</code>',
            full_match,
            re.DOTALL,
        )
        if not code_match:
            return full_match

        language = code_match.group(1) or ""
        raw_code = code_match.group(2)

        # Use stdlib unescape instead of manual entity replacement
        raw_code = unescape(raw_code)

        highlighted = _highlight_code(raw_code, language)

        # Wrap highlighted code back in pre > code structure with language label
        lang_attr = f' data-language="{language}"' if language else ""
        return f'<pre{lang_attr}><code class="highlighted">{highlighted}</code></pre>'

    html = re.sub(r'<pre><code(?:\s+class="language-\w+")?>.*?</code></pre>', _highlight_match, html, flags=re.DOTALL)

    # Sanitize to remove dangerous HTML
    html = sanitize_html(html)

    return html


def detect_content_type(text: str) -> str:
    """Detect content type: json, html, markdown, or text."""
    stripped = text.strip()

    # Try JSON first
    try:
        json.loads(stripped)
        return "json"
    except (json.JSONDecodeError, ValueError):
        pass

    # Check for HTML tags
    if re.search(
        r"<(html|div|p|span|h[1-6]|table|ul|ol|section|article|header|footer|main)\b",
        stripped,
        re.IGNORECASE,
    ):
        return "html"

    # Check for Markdown markers
    if re.search(
        r"^#{1,6}\s|^[-*+]\s|^\d+\.\s|\*\*.*\*\*|`[^`]+`|^>",
        stripped,
        re.MULTILINE,
    ):
        return "markdown"

    return "text"


def _json_value_to_html(value, depth=0) -> str:
    """Recursively convert a JSON value to HTML."""
    if isinstance(value, dict):
        if not value:
            return '<p><em>{}</em></p>'
        html = '<dl>\n'
        for k, v in value.items():
            html += f"<dt>{escape(str(k))}</dt>\n"
            html += f"<dd>{_json_value_to_html(v, depth + 1)}</dd>\n"
        html += "</dl>"
        return html

    if isinstance(value, list):
        if not value:
            return '<p><em>[]</em></p>'
        # Check if list of dicts → table
        if all(isinstance(item, dict) for item in value):
            keys = []
            for item in value:
                for k in item:
                    if k not in keys:
                        keys.append(k)
            html = '<table class="json-table">\n<thead>\n<tr>'
            for k in keys:
                html += f"<th>{escape(str(k))}</th>"
            html += "</tr>\n</thead>\n<tbody>\n"
            for item in value:
                html += "<tr>"
                for k in keys:
                    val = item.get(k, "")
                    if isinstance(val, (dict, list)):
                        html += f"<td>{escape(json.dumps(val))}</td>"
                    else:
                        html += f"<td>{escape(str(val))}</td>"
                html += "</tr>\n"
            html += "</tbody>\n</table>"
            return html

        # Regular list → nested <ul>
        html = '<ul>\n'
        for item in value:
            if isinstance(item, (dict, list)):
                html += f"<li>{_json_value_to_html(item, depth + 1)}</li>\n"
            else:
                html += f"<li>{escape(str(item))}</li>\n"
        html += "</ul>"
        return html

    if value is None:
        return '<em>null</em>'
    if isinstance(value, bool):
        return f"<strong>{'true' if value else 'false'}</strong>"
    if isinstance(value, (int, float)):
        return f"<code>{escape(str(value))}</code>"
    return f"<p>{escape(str(value))}</p>"


def convert_json(content: str) -> str:
    """Convert JSON to HTML (tables, lists, or definition lists)."""
    data = json.loads(content.strip())
    return _json_value_to_html(data)


def convert_html(content: str) -> str:
    """Strip outer HTML wrappers and sanitize inner content."""
    cleaned = content.strip()

    # Remove <!DOCTYPE>, <html>, <head>, <body> wrappers
    cleaned = re.sub(r"<!DOCTYPE[^>]*>\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<html[^>]*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</html>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<head>.*?</head>", "", cleaned, flags=re.IGNORECASE | re.DOTALL)
    cleaned = re.sub(r"<body[^>]*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"</body>", "", cleaned, flags=re.IGNORECASE)

    # Sanitize to prevent XSS/SSRF
    cleaned = sanitize_html(cleaned.strip())

    return cleaned


def convert_text(content: str) -> str:
    """Convert plain text to HTML with paragraph wrapping."""
    lines = content.split("\n")
    paragraphs = []
    current_lines = []

    for line in lines:
        # Detect indented code blocks (4+ spaces or tab)
        if line.startswith("    ") or line.startswith("\t"):
            if current_lines:
                paragraphs.append("\n".join(current_lines))
                current_lines = []
            # Strip the full indentation level (4 spaces or 1 tab)
            if line.startswith("    "):
                code_text = line[4:]
            else:
                code_text = line[1:]
                # Also strip additional tab levels
                while code_text.startswith("\t"):
                    code_text = code_text[1:]
            paragraphs.append(f"<pre><code>{escape(code_text)}</code></pre>")
        elif line.strip() == "":
            if current_lines:
                paragraphs.append("\n".join(current_lines))
                current_lines = []
        else:
            current_lines.append(line)

    if current_lines:
        paragraphs.append("\n".join(current_lines))

    html_parts = []
    for p in paragraphs:
        if p.startswith("<pre>"):
            html_parts.append(p)
        else:
            # Convert single newlines to <br>
            escaped = escape(p)
            escaped = escaped.replace("\n", "<br>")
            html_parts.append(f"<p>{escaped}</p>")

    return '<div class="plain-text">\n' + "\n".join(html_parts) + "\n</div>"


def convert_to_html(content: str, content_type: str) -> str:
    """Route content to the appropriate converter."""
    converters = {
        "markdown": convert_markdown,
        "json": convert_json,
        "html": convert_html,
        "text": convert_text,
    }
    converter = converters.get(content_type, convert_text)
    return converter(content)


def assemble_document(html_body: str, css: str) -> str:
    """Assemble a complete HTML document with embedded CSS."""
    # Sanitize CSS to prevent SSRF via @import or url()
    css = sanitize_css(css)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
{css}
</style>
</head>
<body>
<div class="document">
{html_body}
</div>
</body>
</html>"""
