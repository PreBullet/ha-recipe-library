"""Persistence of the recipe library."""

from __future__ import annotations

from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import Store

from .const import SAVE_DELAY, SIGNAL_CHANGED, STORAGE_KEY, STORAGE_VERSION
from .library import RecipeLibrary


class RecipeStore:
    """Holds the library in memory and keeps it in Home Assistant storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Create an empty store; call ``async_load`` before use."""
        self._hass = hass
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, STORAGE_KEY, atomic_writes=True
        )
        self.library = RecipeLibrary()

    async def async_load(self) -> None:
        """Load the library from storage."""
        self.library = RecipeLibrary(await self._store.async_load())

    @callback
    def async_changed(self) -> None:
        """Persist shortly and tell all subscribed cards about the change."""
        self._store.async_delay_save(self.library.as_dict, SAVE_DELAY)
        async_dispatcher_send(self._hass, SIGNAL_CHANGED)

    async def async_flush(self) -> None:
        """Write the current state immediately (used when unloading)."""
        await self._store.async_save(self.library.as_dict())
