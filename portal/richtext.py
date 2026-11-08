"""Rendu des anciens contenus HTML et des documents Quill, avec nettoyage serveur."""

import html
import json
import re
import bleach
from bleach.css_sanitizer import CSSSanitizer
from markupsafe import Markup
from .validators import valid_link

TAGS = [
    "p",
    "div",
    "span",
    "br",
    "strong",
    "b",
    "em",
    "i",
    "u",
    "s",
    "strike",
    "sub",
    "sup",
    "blockquote",
    "pre",
    "code",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "ul",
    "ol",
    "li",
    "a",
    "img",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
    "hr",
    "video",
    "source",
]
ATTRS = {
    "*": ["dir", "lang", "class", "style"],
    "a": ["href", "title", "target", "rel"],
    "img": ["src", "alt", "width", "height", "loading"],
    "video": ["src", "controls", "poster", "preload", "playsinline"],
    "source": ["src", "type"],
    "td": ["colspan", "rowspan"],
    "th": ["colspan", "rowspan", "scope"],
}
CSS = CSSSanitizer(
    allowed_css_properties=[
        "color",
        "background-color",
        "text-align",
        "direction",
        "font-size",
        "font-weight",
        "text-decoration",
    ]
)


def sanitize(value):
    value = re.sub(
        r"<(script|style|object|iframe)\b[^>]*>.*?</\1\s*>",
        "",
        str(value or ""),
        flags=re.I | re.S,
    )
    return bleach.clean(
        value,
        tags=TAGS,
        attributes=ATTRS,
        protocols=["http", "https", "mailto"],
        css_sanitizer=CSS,
        strip=True,
    )


def delta_document(value):
    for _ in range(2):
        if isinstance(value, str):
            try:
                value = json.loads(value)
            except (ValueError, TypeError):
                return None
    if (
        not isinstance(value, dict)
        or not isinstance(value.get("ops"), list)
        or len(value["ops"]) > 20000
    ):
        return None
    total = 0
    for op in value["ops"]:
        if not isinstance(op, dict) or not isinstance(op.get("insert"), (str, dict)):
            return None
        if not isinstance(op.get("attributes", {}), dict):
            return None
        total += len(str(op["insert"]))
    return value if total <= 200000 else None


def render_delta(value):
    doc = delta_document(value)
    if not doc:
        return ""
    blocks = []
    line = []
    list_kind = None

    def flush(attrs=None):
        nonlocal line, list_kind
        attrs = attrs or {}
        text = "".join(line) or "<br>"
        line = []
        kind = attrs.get("list")
        if kind:
            typ = "ol" if kind == "ordered" else "ul"
            if list_kind != typ:
                if list_kind:
                    blocks.append(f"</{list_kind}>")
                blocks.append(f"<{typ}>")
                list_kind = typ
            tag = "li"
        else:
            if list_kind:
                blocks.append(f"</{list_kind}>")
                list_kind = None
            tag = (
                f'h{attrs["header"]}'
                if attrs.get("header") in range(1, 7)
                else (
                    "blockquote"
                    if attrs.get("blockquote")
                    else ("pre" if attrs.get("code-block") else "p")
                )
            )
        extra = ""
        if attrs.get("direction") == "rtl":
            extra += ' dir="rtl"'
        if attrs.get("align") in ["center", "right", "justify"]:
            extra += f' style="text-align:{attrs["align"]}"'
        blocks.append(f"<{tag}{extra}>{text}</{tag}>")

    for op in doc["ops"][:20000]:
        if not isinstance(op, dict):
            continue
        attrs = op.get("attributes") or {}
        insert = op.get("insert", "")
        if isinstance(insert, dict):
            if line:
                flush()
            if valid_link(insert.get("image")):
                blocks.append(
                    f'<p><img src="{html.escape(insert["image"],quote=True)}" alt="" loading="lazy"></p>'
                )
            elif valid_link(insert.get("video")):
                blocks.append(
                    f'<p><a href="{html.escape(insert["video"],quote=True)}">Consulter la vidéo</a></p>'
                )
            continue
        if not isinstance(insert, str):
            continue
        chunks = insert.split("\n")
        for i, chunk in enumerate(chunks):
            if i:
                flush(attrs)
            text = html.escape(chunk)
            for key, tag in [
                ("bold", "strong"),
                ("italic", "em"),
                ("underline", "u"),
                ("strike", "s"),
                ("code", "code"),
            ]:
                if attrs.get(key):
                    text = f"<{tag}>{text}</{tag}>"
            if attrs.get("script") in ["sub", "super"]:
                tag = "sub" if attrs["script"] == "sub" else "sup"
                text = f"<{tag}>{text}</{tag}>"
            classes = []
            if attrs.get("font") in ("serif", "monospace"):
                classes.append("ql-font-" + attrs["font"])
            if attrs.get("size") in ("small", "large", "huge"):
                classes.append("ql-size-" + attrs["size"])
            if classes:
                text = '<span class="' + " ".join(classes) + '">' + text + "</span>"
            if valid_link(attrs.get("link")):
                text = f'<a href="{html.escape(attrs["link"],quote=True)}" rel="noopener noreferrer">{text}</a>'
            styles = []
            for key, css in [("color", "color"), ("background", "background-color")]:
                if re.fullmatch(
                    r"#[a-fA-F0-9]{3,8}|[a-zA-Z]{1,20}", str(attrs.get(key, ""))
                ):
                    styles.append(f"{css}:{attrs[key]}")
            if styles:
                text = f'<span style="{";".join(styles)}">{text}</span>'
            line.append(text)
    if line and "".join(line):
        flush()
    if list_kind:
        blocks.append(f"</{list_kind}>")
    return "".join(blocks)


def render_content(delta, fallback=""):
    value = render_delta(delta) if delta_document(delta) else str(fallback or "")
    if not re.search(r"<[a-zA-Z][^>]*>", value):
        value = "".join(
            "<p>" + html.escape(x).replace("\n", "<br>") + "</p>"
            for x in value.split("\n\n")
        )
    return Markup(sanitize(value))
