"""The Recipe Library integration.

A simple recipe library for Home Assistant: create recipes manually (imports
from websites, videos and social media follow), add a photo, organise them with
tags and browse them in a dashboard card.

The integration stores the recipes, offers a WebSocket API for the card and
serves and registers the card itself, so no separate card installation and no
manual dashboard resource are needed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.http import StaticPathConfig
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration
from homeassistant.util.hass_dict import HassKey

from .const import CARD_FILENAME, CARD_URL, DOMAIN
from .storage import RecipeStore
from .views import RecipeImageView
from .ws_api import async_register_commands

_LOGGER = logging.getLogger(__name__)

# Static paths and views cannot be unregistered, so they are registered once.
DATA_FRONTEND_REGISTERED: HassKey[bool] = HassKey(f"{DOMAIN}_frontend_registered")


async def _async_register_card(hass: HomeAssistant) -> str:
    """Serve the dashboard card and load it in the frontend. Returns its URL."""
    integration = await async_get_integration(hass, DOMAIN)
    # The version in the URL makes browsers fetch the new file after an update.
    url = f"{CARD_URL}?v={integration.version}"

    if not hass.data.get(DATA_FRONTEND_REGISTERED):
        card_file = Path(__file__).parent / "frontend" / CARD_FILENAME
        await hass.http.async_register_static_paths(
            [StaticPathConfig(CARD_URL, str(card_file))]
        )
        hass.http.register_view(RecipeImageView())
        hass.data[DATA_FRONTEND_REGISTERED] = True

    frontend.add_extra_js_url(hass, url)
    return url


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Recipe Library from a config entry."""
    store = RecipeStore(hass)
    await store.async_load()
    await store.async_cleanup_images()
    hass.data[DOMAIN] = store

    async_register_commands(hass)

    card_url = await _async_register_card(hass)
    entry.async_on_unload(lambda: frontend.remove_extra_js_url(hass, card_url))

    # Still to come, in this order (see README roadmap):
    #   import services: website, YouTube, TikTok/Instagram, text/image
    _LOGGER.debug("Recipe Library set up with %s", card_url)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    store: RecipeStore | None = hass.data.pop(DOMAIN, None)
    if store is not None:
        # Delayed saves are written at shutdown, but not when only unloading.
        await store.async_flush()
    return True
