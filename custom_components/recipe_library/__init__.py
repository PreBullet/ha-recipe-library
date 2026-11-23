"""The Recipe Library integration.

A simple recipe library for Home Assistant: import recipes from websites,
videos and social media (AI-assisted) or create them manually, organise them
with tags and browse them in a dashboard card.

This is the scaffold: the integration sets itself up and does nothing else yet.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Recipe Library from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Planned, in this order (see README roadmap):
    #   1. Recipe storage (Home Assistant Store) incl. tags and tag renaming
    #   2. WebSocket API for the card: list, get, create, update, delete,
    #      plus tag management
    #   3. Serve and register the dashboard card from ./frontend
    #   4. Import services: website, YouTube, TikTok/Instagram, text/image
    _LOGGER.debug("Recipe Library set up")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data.pop(DOMAIN, None)
    return True
