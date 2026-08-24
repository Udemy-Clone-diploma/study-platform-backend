"""HTML sanitization for teacher-authored rich text.

Fields like ``Course.full_description``, ``LessonItem.body_html`` and
``Article.body_html`` accept HTML (typically from a Tiptap editor on the
frontend) and are rendered back to other users, so storing them raw is a
stored-XSS vector. We strip them to a safe allowlist on write with nh3 (the
Rust ``ammonia`` binding; ``bleach`` is deprecated).

Apply ``sanitize_html`` in the ``validate_<field>`` of any serializer that
accepts authored HTML. When you add a new rich-text field, sanitize it here too.
"""

import nh3

# Keep in sync with the frontend allowlist in `src/shared/lib/sanitizeCourseHtml.ts`.
# The table tags are what the Tiptap editor emits; dropping them here would
# silently delete every table an author inserted.
ALLOWED_TAGS = {
    "p",
    "br",
    "span",
    "div",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "mark",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "blockquote",
    "pre",
    "code",
    "hr",
    "a",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
}

ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "target"},
    "img": {"src", "alt", "title"},
    "span": {"class"},
    "div": {"class"},
    "code": {"class"},
    "pre": {"class"},
    "th": {"colspan", "rowspan"},
    "td": {"colspan", "rowspan"},
}


def sanitize_html(value: str | None) -> str | None:
    """Strip disallowed tags/attributes/URL schemes from authored HTML.

    Passes ``None`` and empty strings through unchanged. nh3 drops ``<script>``
    and its content, event-handler attributes (``onerror`` etc.), and unsafe URL
    schemes (``javascript:``), and forces ``rel="noopener noreferrer"`` on links.
    """
    if not value:
        return value
    return nh3.clean(
        value,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer",
    )
