import html
import re


def hackbridge_header_handler(message):
    author = getattr(message, "author", None)
    author_name = getattr(author, "name", "") if author else ""
    display_name = getattr(author, "display_name", "") if author else ""

    normalized_name = str(author_name).lower()
    normalized_display = str(display_name).lower()

    raw_content = message.content or ""
    content_looks_hackbridge = is_hackbridge_content(raw_content)

    # Allow webhook-style/non-bot authors; rely on name match OR recognizable formatting
    if ("hackbridge" not in normalized_name and "hackbridge" not in normalized_display) and not content_looks_hackbridge:
        return None

    if not raw_content.strip():
        return None

    lines = raw_content.splitlines()
    formatted_lines = []

    for idx, line in enumerate(lines):
        if idx == 0:
            formatted_lines.append(format_hackbridge_header_line(line))
        else:
            formatted_lines.append(format_hackbridge_body_line(line))

    formatted_lines = [line for line in formatted_lines if line]
    if not formatted_lines:
        return None

    return {"text": "\n".join(formatted_lines), "disable_preview": True}


def format_hackbridge_header_line(line):
    header = line.strip()
    header = re.sub(r"^[\s\-•]*#?\s*", "", header)

    if header.startswith("➤"):
        header = header[1:].strip()

    if not header:
        return ""

    return f"➤ {hackbridge_markdown_to_html(header)}"


def format_hackbridge_body_line(line):
    text_line = line.strip()
    if not text_line:
        return ""

    pattern = r'^(?P<prefix>[\s\S]*?)\*\*\[(?P<name>[^\]]+)\]\(<(?P<link>[^>]+)>\)\*\*:\s*(?P<message>.*)$'
    pattern_no_angle = r'^(?P<prefix>[\s\S]*?)\*\*\[(?P<name>[^\]]+)\]\((?P<link>[^)]+)\)\*\*:\s*(?P<message>.*)$'
    match = re.match(pattern, text_line)
    if match:
        prefix = escape_text(match.group("prefix"))
        username = escape_text(match.group("name"))
        link = html.escape(match.group("link"), quote=True)
        message_text = escape_text(match.group("message"))
        return f"{prefix}<b><a href=\"{link}\">{username}</a></b>: {message_text}"

    match_no_angle = re.match(pattern_no_angle, text_line)
    if match_no_angle:
        prefix = escape_text(match_no_angle.group("prefix"))
        username = escape_text(match_no_angle.group("name"))
        link = html.escape(match_no_angle.group("link"), quote=True)
        message_text = escape_text(match_no_angle.group("message"))
        return f"{prefix}<b><a href=\"{link}\">{username}</a></b>: {message_text}"

    return hackbridge_markdown_to_html(text_line)


def hackbridge_markdown_to_html(text):
    if not text:
        return ""

    def replace_link(match):
        label = escape_text(match.group(1))
        url = html.escape(match.group(2), quote=True)
        return f'<a href="{url}">{label}</a>'

    formatted = re.sub(r'\[([^\]]+)\]\(<([^>]+)>\)', replace_link, text)
    formatted = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: f'<a href="{html.escape(m.group(2), quote=True)}">{escape_text(m.group(1))}</a>', formatted)
    formatted = re.sub(r'\*\*(.+?)\*\*', lambda m: f'<b>{escape_text(m.group(1))}</b>', formatted)
    formatted = re.sub(r'_(.+?)_', lambda m: f'<i>{escape_text(m.group(1))}</i>', formatted)

    parts = re.split(r'(<[^>]+>)', formatted)
    escaped_parts = [
        part if part.startswith("<") and part.endswith(">")
        else escape_text(part)
        for part in parts
    ]
    return "".join(escaped_parts)


def is_hackbridge_content(raw_content):
    if not raw_content:
        return False

    lines = raw_content.splitlines()
    if not lines:
        return False

    header_line = lines[0].strip()
    header_like = bool(re.match(r'^[\s\-•]*#?\s*➤', header_line))
    body_like = any(re.match(r'^[^\n]*\*\*\[[^\]]+\]\(<[^>]+>\)\*\*:', line.strip()) for line in lines[1:])

    return header_like or body_like


def escape_text(value: str) -> str:
    """
    Escape text for Telegram HTML while keeping '&' visible to avoid &amp; showing up.
    We still escape angle brackets to prevent HTML injection.
    """
    if value is None:
        return ""
    escaped = html.escape(value, quote=False)
    return escaped.replace("&amp;", "&")
