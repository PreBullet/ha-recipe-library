"""WebSocket API used by the dashboard card.

All commands are available to every authenticated Home Assistant user, there
is no separate user management. A custom ``subscribe`` command is used instead
of the generic event subscription because the latter is admin-only.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_CHANGED
from .images import decode_upload
from .library import LibraryError, NotFoundError, check_image_name
from .storage import RecipeStore

_LOGGER = logging.getLogger(__name__)


def _get_store(hass: HomeAssistant) -> RecipeStore | None:
    return hass.data.get(DOMAIN)


def _store_or_error(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> RecipeStore | None:
    """Return the store, or answer with an error if the integration is unloaded."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "Recipe Library is not set up")
    return store


def _run(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    action: Callable[[RecipeStore], Any],
) -> None:
    """Run a change on the library, persist it and answer the request."""
    if (store := _store_or_error(hass, connection, msg)) is None:
        return
    try:
        result = action(store)
    except LibraryError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    # Subscribers (including the sender's own card) get the new snapshot before
    # the answer, so when the card's request returns its data is already current.
    store.async_changed()
    connection.send_result(msg["id"], result)


@callback
def async_register_commands(hass: HomeAssistant) -> None:
    """Register all WebSocket commands."""
    for command in (
        ws_subscribe,
        ws_recipe_save,
        ws_recipe_delete,
        ws_tag_create,
        ws_tag_rename,
        ws_tag_delete,
        ws_image_upload,
        ws_image_discard,
    ):
        websocket_api.async_register_command(hass, command)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send all tags and recipes now and again after every change."""
    if _store_or_error(hass, connection, msg) is None:
        return

    @callback
    def _send_snapshot() -> None:
        current = _get_store(hass)
        if current is not None:
            connection.send_message(
                websocket_api.event_message(msg["id"], current.library.snapshot())
            )

    connection.subscriptions[msg["id"]] = async_dispatcher_connect(
        hass, SIGNAL_CHANGED, _send_snapshot
    )
    connection.send_result(msg["id"])
    _send_snapshot()


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/recipe/save",
        # Omit recipe_id to create a new recipe.
        vol.Optional("recipe_id"): cv.string,
        vol.Required("title"): cv.string,
        vol.Optional("time"): cv.string,
        vol.Optional("servings"): cv.string,
        vol.Optional("tags"): [cv.string],
        vol.Optional("ingredients"): [cv.string],
        vol.Optional("steps"): [cv.string],
        vol.Optional("notes"): cv.string,
        vol.Optional("source"): cv.string,
        # File name returned by image/upload, or empty for no photo.
        vol.Optional("image"): cv.string,
    }
)
@websocket_api.async_response
async def ws_recipe_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create a recipe or replace the editable fields of an existing one."""
    if (store := _store_or_error(hass, connection, msg)) is None:
        return
    fields = {k: v for k, v in msg.items() if k not in ("id", "type", "recipe_id")}
    recipe_id = msg.get("recipe_id")
    try:
        previous = store.library.get_recipe(recipe_id)["image"] if recipe_id else ""
        image = check_image_name(fields.get("image"))
        if (
            image
            and image != previous
            and not await hass.async_add_executor_job(store.images.exists, image)
        ):
            raise NotFoundError("image not found")
        result = store.library.save_recipe(fields, recipe_id)
    except LibraryError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    store.async_changed()
    connection.send_result(msg["id"], result)
    if previous and previous != result["image"]:
        await store.async_release_image(previous)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/recipe/delete",
        vol.Required("recipe_id"): cv.string,
    }
)
@websocket_api.async_response
async def ws_recipe_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a recipe and its photo."""
    if (store := _store_or_error(hass, connection, msg)) is None:
        return
    try:
        image = store.library.get_recipe(msg["recipe_id"])["image"]
        store.library.delete_recipe(msg["recipe_id"])
    except LibraryError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    store.async_changed()
    connection.send_result(msg["id"])
    await store.async_release_image(image)


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/tag/create", vol.Required("name"): cv.string}
)
@callback
def ws_tag_create(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create a tag (returns the existing one if the name is already taken)."""
    _run(hass, connection, msg, lambda store: store.library.create_tag(msg["name"]))


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/tag/rename",
        vol.Required("tag_id"): cv.string,
        vol.Required("name"): cv.string,
    }
)
@callback
def ws_tag_rename(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Rename a tag; recipes and filters follow because they use the tag id."""
    _run(
        hass,
        connection,
        msg,
        lambda store: store.library.rename_tag(msg["tag_id"], msg["name"]),
    )


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/tag/delete", vol.Required("tag_id"): cv.string}
)
@callback
def ws_tag_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a tag and remove it from all recipes. Recipes are kept."""

    def _delete(store: RecipeStore) -> dict[str, int]:
        return {"affected": store.library.delete_tag(msg["tag_id"])}

    _run(hass, connection, msg, _delete)


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/image/upload",
        # The photo, base64 encoded. The card shrinks it before sending.
        vol.Required("data"): cv.string,
    }
)
@websocket_api.async_response
async def ws_image_upload(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Store a photo and return its file name, to be used in recipe/save."""
    if (store := _store_or_error(hass, connection, msg)) is None:
        return
    try:
        data, extension = await hass.async_add_executor_job(decode_upload, msg["data"])
        name = await hass.async_add_executor_job(store.images.save, data, extension)
    except LibraryError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    except OSError:
        _LOGGER.exception("Could not store the uploaded photo")
        connection.send_error(msg["id"], "write_failed", "Could not store the photo")
        return
    connection.send_result(msg["id"], {"image": name})


@websocket_api.websocket_command(
    {vol.Required("type"): f"{DOMAIN}/image/discard", vol.Required("image"): cv.string}
)
@websocket_api.async_response
async def ws_image_discard(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete an uploaded photo that was not saved with a recipe.

    A photo that a recipe uses is never deleted by this command.
    """
    if (store := _store_or_error(hass, connection, msg)) is None:
        return
    try:
        name = check_image_name(msg["image"])
    except LibraryError as err:
        connection.send_error(msg["id"], err.code, str(err))
        return
    await store.async_release_image(name)
    connection.send_result(msg["id"])
