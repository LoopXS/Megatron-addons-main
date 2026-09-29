"""Shared, defensive helpers for Megatron inline addons."""

from html import escape
from urllib.parse import quote_plus

from telethon.tl.types import InputWebDocument


DEFAULT_IMAGE = "https://graph.org/file/5eee0c3b21849601906ea.mp4"


def html_text(value, *, quote=False):
    """Safely convert arbitrary API text into HTML-safe text."""
    if value is None:
        return ""
    return escape(str(value), quote=quote)


def compact(value, limit=300):
    """Normalize whitespace and keep a value within a UI-friendly limit."""
    value = " ".join(str(value or "").split())
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def chunk_text(text, limit=3000):
    """Split text without producing empty chunks."""
    text = str(text or "")
    if not text:
        return [""]
    return [text[i : i + limit] for i in range(0, len(text), limit)]


def web_document(url, mime="image/jpeg"):
    if not url:
        return None
    try:
        return InputWebDocument(str(url), 0, mime, [])
    except Exception:
        return None


def query_url(base, query):
    return f"{base}{quote_plus(str(query).strip())}"


def query_from_event(event, command):
    """Return text after an inline command, or an empty string."""
    raw = str(getattr(event, "text", "") or "").strip()
    if not raw:
        return ""
    parts = raw.split(None, 1)
    if len(parts) == 1:
        return ""
    return parts[1].strip()
