"""Persistence of the recipe library."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.storage import STORAGE_DIR, Store

from .const import (
    IMAGE_CLEANUP_MIN_AGE,
    IMAGES_DIRNAME,
    MAX_PARALLEL_IMPORTS,
    SAVE_DELAY,
    SIGNAL_CHANGED,
    STORAGE_KEY,
    STORAGE_VERSION,
)
from .images import ImageStore
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
        self.images = ImageStore(Path(hass.config.path(STORAGE_DIR, IMAGES_DIRNAME)))
        # At most a few web imports run at the same time.
        self.import_slots = asyncio.Semaphore(MAX_PARALLEL_IMPORTS)

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

    async def async_release_image(self, name: str) -> None:
        """Delete a photo file if no recipe uses it (any more)."""
        if name and not self.library.is_image_used(name):
            await self._hass.async_add_executor_job(self.images.delete, name)

    async def async_cleanup_images(self) -> None:
        """Delete old photo files that no recipe refers to.

        Skipped for an empty library: if the data file could not be read, an
        empty library must never lead to deleting all photos.
        """
        if not self.library.snapshot()["recipes"]:
            return
        await self._hass.async_add_executor_job(
            self.images.cleanup,
            self.library.used_images(),
            IMAGE_CLEANUP_MIN_AGE,
        )
