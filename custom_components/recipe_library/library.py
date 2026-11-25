"""Recipe library data model and rules.

Pure Python without Home Assistant imports, so it can be unit-tested on its
own. Persistence and the WebSocket API live in ``storage.py`` and ``ws_api.py``.

Data model
----------
* A *tag* is ``{"id", "name"}``. Recipes reference tags by id, so renaming a tag
  changes one record and is reflected everywhere (recipes, filters).
* A *recipe* is ``{"id", "title", "time", "servings", "tags", "ingredients",
  "steps", "notes", "source", "created", "updated"}``. Ingredients are plain
  text lines, there is no ingredient database.
* Recipes are never locked: every recipe can be edited and deleted, regardless
  of how it was created.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

DATA_VERSION = 1

# Limits keep the stored file and the WebSocket messages at a sane size.
MAX_RECIPES = 1000
MAX_TAGS = 100
MAX_TITLE = 200
MAX_TAG_NAME = 50
MAX_SHORT = 100  # time, servings
MAX_SOURCE = 2048
MAX_NOTES = 5000
MAX_LINES = 200  # ingredient lines / steps per recipe
MAX_LINE = 3000


class LibraryError(Exception):
    """Base class; ``code`` is sent to the frontend as the error code."""

    code = "error"


class NotFoundError(LibraryError):
    """A recipe or tag does not exist."""

    code = "not_found"


class InvalidDataError(LibraryError):
    """The given data is not valid."""

    code = "invalid_format"


class NameExistsError(LibraryError):
    """Another tag already uses this name."""

    code = "name_exists"


class LimitError(LibraryError):
    """A size limit of the library is reached."""

    code = "limit_reached"


def _utcnow() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _new_id() -> str:
    return uuid.uuid4().hex


def _text(value: Any, field: str, max_len: int, *, required: bool = False) -> str:
    """Return a stripped string or raise InvalidDataError."""
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise InvalidDataError(f"{field} must be text")
    value = value.strip()
    if required and not value:
        raise InvalidDataError(f"{field} must not be empty")
    if len(value) > max_len:
        raise InvalidDataError(f"{field} is too long (max {max_len} characters)")
    return value


def _lines(value: Any, field: str) -> list[str]:
    """Return a list of non-empty, stripped strings or raise InvalidDataError."""
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        raise InvalidDataError(f"{field} must be a list")
    result = [_text(item, field, MAX_LINE) for item in value]
    result = [line for line in result if line]
    if len(result) > MAX_LINES:
        raise InvalidDataError(f"{field} has too many entries (max {MAX_LINES})")
    return result


def _tag_name(value: Any) -> str:
    """Normalise a tag name: trimmed, inner whitespace collapsed."""
    if not isinstance(value, str):
        raise InvalidDataError("name must be text")
    name = " ".join(value.split())
    if not name:
        raise InvalidDataError("name must not be empty")
    if len(name) > MAX_TAG_NAME:
        raise InvalidDataError(f"name is too long (max {MAX_TAG_NAME} characters)")
    return name


def _as_str(value: Any) -> str:
    return value if isinstance(value, str) else ""


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [item for item in value if isinstance(item, str)]


class RecipeLibrary:
    """In-memory recipes and tags with all rules for changing them."""

    def __init__(
        self,
        data: Mapping[str, Any] | None = None,
        *,
        now: Callable[[], str] = _utcnow,
    ) -> None:
        """Create the library, optionally from previously stored data."""
        self._now = now
        self._tags: dict[str, dict[str, str]] = {}
        self._recipes: dict[str, dict[str, Any]] = {}
        if data:
            self._restore(data)

    # -- persistence -------------------------------------------------------

    def _restore(self, data: Mapping[str, Any]) -> None:
        """Load stored data. Tolerant on purpose: never drop recipes on load."""
        for raw in data.get("tags") or []:
            if (
                isinstance(raw, Mapping)
                and isinstance(raw.get("id"), str)
                and isinstance(raw.get("name"), str)
            ):
                self._tags[raw["id"]] = {"id": raw["id"], "name": raw["name"]}

        for raw in data.get("recipes") or []:
            if not isinstance(raw, Mapping) or not isinstance(raw.get("id"), str):
                continue
            tags: list[str] = []
            for tag_id in _as_str_list(raw.get("tags")):
                if tag_id in self._tags and tag_id not in tags:
                    tags.append(tag_id)
            self._recipes[raw["id"]] = {
                "id": raw["id"],
                "title": _as_str(raw.get("title")).strip() or "?",
                "time": _as_str(raw.get("time")),
                "servings": _as_str(raw.get("servings")),
                "tags": tags,
                "ingredients": _as_str_list(raw.get("ingredients")),
                "steps": _as_str_list(raw.get("steps")),
                "notes": _as_str(raw.get("notes")),
                "source": _as_str(raw.get("source")),
                "created": _as_str(raw.get("created")),
                "updated": _as_str(raw.get("updated")),
            }

    def as_dict(self) -> dict[str, Any]:
        """Return the data in the form it is stored."""
        return {"version": DATA_VERSION, **self.snapshot()}

    def snapshot(self) -> dict[str, Any]:
        """Return a copy of all tags and recipes for the frontend."""
        return {
            "tags": deepcopy(list(self._tags.values())),
            "recipes": deepcopy(list(self._recipes.values())),
        }

    # -- tags --------------------------------------------------------------

    def _tag_by_name(self, name: str) -> dict[str, str] | None:
        folded = name.casefold()
        for tag in self._tags.values():
            if tag["name"].casefold() == folded:
                return tag
        return None

    def create_tag(self, name: Any) -> dict[str, str]:
        """Create a tag. If the name exists (ignoring case), return that tag."""
        name = _tag_name(name)
        if (existing := self._tag_by_name(name)) is not None:
            return dict(existing)
        if len(self._tags) >= MAX_TAGS:
            raise LimitError(f"at most {MAX_TAGS} tags are possible")
        tag = {"id": _new_id()[:12], "name": name}
        while tag["id"] in self._tags:
            tag["id"] = _new_id()[:12]
        self._tags[tag["id"]] = tag
        return dict(tag)

    def rename_tag(self, tag_id: str, name: Any) -> dict[str, str]:
        """Rename a tag. Recipes reference the id, so they follow automatically."""
        tag = self._tags.get(tag_id)
        if tag is None:
            raise NotFoundError("tag not found")
        name = _tag_name(name)
        other = self._tag_by_name(name)
        if other is not None and other["id"] != tag_id:
            raise NameExistsError("a tag with this name already exists")
        tag["name"] = name
        return dict(tag)

    def delete_tag(self, tag_id: str) -> int:
        """Delete a tag, remove it from all recipes and return how many had it."""
        if tag_id not in self._tags:
            raise NotFoundError("tag not found")
        del self._tags[tag_id]
        affected = 0
        for recipe in self._recipes.values():
            if tag_id in recipe["tags"]:
                recipe["tags"] = [t for t in recipe["tags"] if t != tag_id]
                affected += 1
        return affected

    # -- recipes -----------------------------------------------------------

    def get_recipe(self, recipe_id: str) -> dict[str, Any]:
        """Return a copy of a recipe."""
        recipe = self._recipes.get(recipe_id)
        if recipe is None:
            raise NotFoundError("recipe not found")
        return deepcopy(recipe)

    def save_recipe(
        self, fields: Mapping[str, Any], recipe_id: str | None = None
    ) -> dict[str, Any]:
        """Create a recipe, or replace all editable fields of an existing one.

        Nothing is stored if validation fails.
        """
        existing = None
        if recipe_id is not None:
            existing = self._recipes.get(recipe_id)
            if existing is None:
                raise NotFoundError("recipe not found")
        elif len(self._recipes) >= MAX_RECIPES:
            raise LimitError(f"at most {MAX_RECIPES} recipes are possible")

        tags: list[str] = []
        for tag_id in _as_str_list_strict(fields.get("tags"), "tags"):
            if tag_id not in self._tags:
                raise InvalidDataError("unknown tag")
            if tag_id not in tags:
                tags.append(tag_id)

        now = self._now()
        recipe = {
            "id": existing["id"] if existing else _new_id(),
            "title": _text(fields.get("title"), "title", MAX_TITLE, required=True),
            "time": _text(fields.get("time"), "time", MAX_SHORT),
            "servings": _text(fields.get("servings"), "servings", MAX_SHORT),
            "tags": tags,
            "ingredients": _lines(fields.get("ingredients"), "ingredients"),
            "steps": _lines(fields.get("steps"), "steps"),
            "notes": _text(fields.get("notes"), "notes", MAX_NOTES),
            "source": _text(fields.get("source"), "source", MAX_SOURCE),
            "created": existing["created"] if existing else now,
            "updated": now,
        }
        self._recipes[recipe["id"]] = recipe
        return deepcopy(recipe)

    def delete_recipe(self, recipe_id: str) -> None:
        """Delete a recipe."""
        if recipe_id not in self._recipes:
            raise NotFoundError("recipe not found")
        del self._recipes[recipe_id]


def _as_str_list_strict(value: Any, field: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, (list, tuple)) or not all(
        isinstance(item, str) for item in value
    ):
        raise InvalidDataError(f"{field} must be a list of text")
    return list(value)
