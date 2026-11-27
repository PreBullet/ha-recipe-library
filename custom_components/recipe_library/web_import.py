"""Import a recipe draft from a web page (structured data, no AI)."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .fetch import fetch_image, fetch_page
from .importer import parse_recipe
from .library import LibraryError
from .storage import RecipeStore

_LOGGER = logging.getLogger(__name__)


async def async_import_url(
    hass: HomeAssistant, store: RecipeStore, url: str
) -> dict[str, Any]:
    """Return a recipe draft for a web page.

    The draft has the fields of a recipe (without tags). Its picture is stored
    like an upload that is not saved yet: the card either saves it with the
    recipe or discards it, and a leftover is removed after 24 hours.
    Raises ``LibraryError`` with a code the card can show.
    """
    language = hass.config.language
    text, page_url = await fetch_page(url, language)
    draft = await hass.async_add_executor_job(parse_recipe, text, page_url)
    image_url = draft.pop("image_url")
    draft["image"] = (
        await _async_store_picture(hass, store, image_url, language)
        if image_url
        else ""
    )
    return draft


async def _async_store_picture(
    hass: HomeAssistant, store: RecipeStore, url: str, language: str
) -> str:
    """Download the picture of a recipe; a recipe without picture is fine."""
    try:
        data, extension = await fetch_image(url, language)
        return await hass.async_add_executor_job(store.images.save, data, extension)
    except (LibraryError, OSError) as err:
        _LOGGER.debug("Recipe picture was not imported: %s", err)
        return ""
