"""Read a recipe from the structured data of a web page.

Pure Python without Home Assistant imports. Most recipe sites describe their
recipes as schema.org ``Recipe`` data in a ``<script type="application/ld+json">``
block, so no AI is needed for them. The result is a *draft*: the card shows it
in the edit form and nothing is stored until the user saves it.
"""

from __future__ import annotations

import html
import json
import re
from typing import Any
from urllib.parse import urljoin

from .library import (
    MAX_LINE,
    MAX_LINES,
    MAX_NOTES,
    MAX_SHORT,
    MAX_SOURCE,
    MAX_TITLE,
    LibraryError,
)

# Guards against absurd pages, the real ones are far below these.
_MAX_JSON_BLOCKS = 50
_MAX_NODES = 20000
_MAX_DEPTH = 12


class NoRecipeError(LibraryError):
    """The page has no structured recipe data."""

    code = "no_recipe"


_LD_JSON_RE = re.compile(
    r"<script\b[^>]*\btype\s*=\s*[\"']?application/ld\+json[^>]*>(.*?)</script\s*>",
    re.IGNORECASE | re.DOTALL,
)
_CDATA_RE = re.compile(
    r"^\s*(?:/\*\s*)?<!\[CDATA\[(?:\s*\*/)?"  # start: /*<![CDATA[*/
    r"|(?:/\*\s*)?\]\]>(?:\s*\*/)?\s*$"  # end: /*]]>*/
)
_LINE_BREAK_TAG_RE = re.compile(
    r"<\s*br\s*/?\s*>|<\s*/\s*(?:p|li|div|h[1-6])\s*>", re.I
)
_TAG_RE = re.compile(r"</?[a-zA-Z][^<>]*>")
_DURATION_RE = re.compile(
    r"^P(?:(\d+)W)?(?:(\d+)D)?(?:T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?)?$",
    re.IGNORECASE,
)


# -- text helpers


def _strip_markup(value: str) -> str:
    """Turn a text that may contain HTML into plain text with line breaks."""
    value = html.unescape(value)
    value = _LINE_BREAK_TAG_RE.sub("\n", value)
    value = _TAG_RE.sub("", value)
    return html.unescape(value)


def _one_line(value: Any) -> str:
    """Return a text as a single line with collapsed whitespace."""
    if not isinstance(value, str):
        return ""
    return " ".join(_strip_markup(value).split())


def _paragraphs(value: Any) -> list[str]:
    """Return the non-empty lines of a text, each with collapsed whitespace."""
    if not isinstance(value, str):
        return []
    lines = (" ".join(line.split()) for line in _strip_markup(value).splitlines())
    return [line for line in lines if line]


def _clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


# -- JSON-LD


def _json_blocks(page: str) -> list[Any]:
    """Return the parsed JSON-LD blocks of a page (broken blocks are skipped)."""
    blocks: list[Any] = []
    for match in _LD_JSON_RE.finditer(page):
        raw = _CDATA_RE.sub("", match.group(1)).strip()
        if not raw:
            continue
        try:
            # strict=False allows raw line breaks inside strings, which many
            # sites produce.
            blocks.append(json.loads(raw, strict=False))
        except ValueError:
            continue
        if len(blocks) >= _MAX_JSON_BLOCKS:
            break
    return blocks


def _is_recipe(node: dict[str, Any]) -> bool:
    for kind in _as_list(node.get("@type")):
        if isinstance(kind, str) and re.split(r"[/:#]", kind)[-1].lower() == "recipe":
            return True
    return False


def _recipe_nodes(blocks: list[Any]) -> list[dict[str, Any]]:
    """Find all Recipe objects anywhere in the JSON-LD blocks."""
    found: list[dict[str, Any]] = []
    budget = _MAX_NODES
    stack: list[tuple[Any, int]] = [(block, 0) for block in reversed(blocks)]
    while stack and budget > 0:
        node, depth = stack.pop()
        budget -= 1
        if depth > _MAX_DEPTH:
            continue
        if isinstance(node, dict):
            if _is_recipe(node):
                found.append(node)
            children = list(node.values())
        elif isinstance(node, list):
            children = node
        else:
            continue
        # Reversed, so that the first entry of the page is handled first.
        stack.extend((child, depth + 1) for child in reversed(children))
    return found


# -- field conversion


def _minutes(value: Any) -> int | None:
    """Return an ISO 8601 duration such as ``PT1H30M`` in minutes."""
    if not isinstance(value, str):
        return None
    match = _DURATION_RE.match(value.strip())
    if not match or not any(match.groups()):
        return None
    weeks, days, hours, minutes, seconds = (
        float(g) if g else 0 for g in match.groups()
    )
    total = weeks * 7 * 1440 + days * 1440 + hours * 60 + minutes + seconds / 60
    return round(total)


def _format_minutes(total: int) -> str:
    days, rest = divmod(total, 1440)
    hours, minutes = divmod(rest, 60)
    parts = [(days, "d"), (hours, "h"), (minutes, "min")]
    return " ".join(f"{amount} {unit}" for amount, unit in parts if amount)


def _time(recipe: dict[str, Any]) -> str:
    """Return the total time, or the sum of preparation and cooking time."""
    total = recipe.get("totalTime")
    minutes = _minutes(total)
    if minutes:
        return _format_minutes(minutes)
    # Not an ISO duration: keep what the site wrote (for example "30 minutes").
    if minutes is None and (text := _clip(_one_line(total), MAX_SHORT)):
        return text
    known = [
        part
        for part in (_minutes(recipe.get("prepTime")), _minutes(recipe.get("cookTime")))
        if part is not None
    ]
    return _format_minutes(sum(known)) if sum(known) else ""


def _servings(recipe: dict[str, Any]) -> str:
    for value in _as_list(recipe.get("recipeYield")):
        text = _one_line(str(value)) if isinstance(value, (str, int, float)) else ""
        if text:
            return _clip(text, MAX_SHORT)
    return ""


def _ingredients(recipe: dict[str, Any]) -> list[str]:
    raw = recipe.get("recipeIngredient", recipe.get("ingredients"))
    lines: list[str] = []
    for item in _as_list(raw):
        # An ingredient is one line; a single string may hold several.
        lines.extend(_paragraphs(item) if isinstance(item, str) else [])
    return [_clip(line, MAX_LINE) for line in lines[:MAX_LINES]]


def _steps_of(node: Any, depth: int = 0) -> list[str]:
    """Flatten ``recipeInstructions``: text, steps, or sections of steps."""
    if depth > 6:
        return []
    if isinstance(node, str):
        return _paragraphs(node)
    if isinstance(node, list):
        steps: list[str] = []
        for item in node:
            steps.extend(_steps_of(item, depth + 1))
        return steps
    if isinstance(node, dict):
        # A step has "text"; a section (HowToSection) lists its steps.
        if "itemListElement" in node:
            return _steps_of(node["itemListElement"], depth + 1)
        for key in ("text", "name"):
            if isinstance(node.get(key), str):
                return _paragraphs(node[key])
    return []


def _steps(recipe: dict[str, Any]) -> list[str]:
    return [
        _clip(line, MAX_LINE)
        for line in _steps_of(recipe.get("recipeInstructions"))[:MAX_LINES]
    ]


def _image_url(recipe: dict[str, Any], page_url: str) -> str:
    """Return the absolute URL of the first image, or an empty string."""
    candidates = [recipe.get("image"), recipe.get("thumbnailUrl")]
    for candidate in candidates:
        for item in _as_list(candidate):
            url = item.get("url") if isinstance(item, dict) else item
            if not isinstance(url, str) or not url.strip():
                continue
            absolute = urljoin(page_url, url.strip())
            if (
                absolute.lower().startswith(("http://", "https://"))
                and len(absolute) <= MAX_SOURCE
            ):
                return absolute
    return ""


def _draft(recipe: dict[str, Any], page_url: str) -> dict[str, Any] | None:
    title = _clip(_one_line(recipe.get("name")), MAX_TITLE)
    ingredients = _ingredients(recipe)
    steps = _steps(recipe)
    if not title or not (ingredients or steps):
        return None
    description = "\n".join(_paragraphs(recipe.get("description")))
    return {
        "title": title,
        "time": _time(recipe),
        "servings": _servings(recipe),
        "ingredients": ingredients,
        "steps": steps,
        "notes": _clip(description, MAX_NOTES),
        "source": page_url if len(page_url) <= MAX_SOURCE else "",
        "image_url": _image_url(recipe, page_url),
    }


def parse_recipe(page: str, page_url: str) -> dict[str, Any]:
    """Return a recipe draft from a page, or raise NoRecipeError.

    The draft has the fields of a recipe (without tags and photo) plus
    ``image_url``, the address of the picture on the page.
    """
    for recipe in _recipe_nodes(_json_blocks(page)):
        if draft := _draft(recipe, page_url):
            return draft
    raise NoRecipeError("the page has no structured recipe data")
