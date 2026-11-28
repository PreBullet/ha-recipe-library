"""Import a recipe draft from a web page (structured data, no AI)."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.core import HomeAssistant

from .fetch import PageTooLargeError, fetch_image, fetch_page
from .importer import parse_recipe
from .library import LibraryError
from .storage import RecipeStore

_LOGGER = logging.getLogger(__name__)

# What the card is told when the draft has no picture. An empty string means
# that the picture was imported.
ISSUE_NOT_FOUND = "not_found"  # the page names no picture
ISSUE_TOO_LARGE = "too_large"  # the picture is larger than the limit
ISSUE_FAILED = "download_failed"  # the picture could not be loaded or used

PICTURE_BUDGET = 20  # seconds for all picture attempts together


async def async_import_url(
    hass: HomeAssistant, store: RecipeStore, url: str
) -> dict[str, Any]:
    """Return a recipe draft for a web page.

    The draft has the fields of a recipe (without tags) plus ``image_issue``,
    which says why there is no picture (see the constants above). The picture
    is stored like an upload that is not saved yet: the card either saves it
    with the recipe or discards it, and a leftover is removed after 24 hours.
    Raises ``LibraryError`` with a code the card can show.
    """
    language = hass.config.language
    text, page_url = await fetch_page(url, language)
    draft = await hass.async_add_executor_job(parse_recipe, text, page_url)
    image_urls = draft.pop("image_urls")
    draft["image"], draft["image_issue"] = await _async_store_picture(
        hass, store, image_urls, page_url, language
    )
    return draft


async def _async_store_picture(
    hass: HomeAssistant,
    store: RecipeStore,
    urls: list[str],
    page_url: str,
    language: str,
) -> tuple[str, str]:
    """Download the picture of a recipe: ``(file name, issue)``.

    The addresses are tried one after the other until one works. A recipe
    without picture is fine, so nothing here raises.
    """
    if not urls:
        return "", ISSUE_NOT_FOUND
    loop = asyncio.get_running_loop()
    deadline = loop.time() + PICTURE_BUDGET
    issue = ""
    for url in urls:
        remaining = deadline - loop.time()
        if remaining < 1:
            issue = issue or ISSUE_FAILED
            break
        try:
            data, extension = await fetch_image(
                url, language, referer=page_url, timeout=remaining
            )
            name = await hass.async_add_executor_job(store.images.save, data, extension)
        except (LibraryError, OSError) as err:
            _LOGGER.debug("Recipe picture %s was not imported: %s", url, err)
            # The first problem is the one that is reported.
            issue = issue or (
                ISSUE_TOO_LARGE if isinstance(err, PageTooLargeError) else ISSUE_FAILED
            )
            continue
        return name, ""
    return "", issue
