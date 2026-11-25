"""WebSocket API used by the dashboard card.

All commands are available to every authenticated Home Assistant user, there
is no separate user management. A custom ``subscribe`` command is used instead
of the generic event subscription because the latter is admin-only.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DOMAIN, SIGNAL_CHANGED
from .library import LibraryError
from .storage import RecipeStore


def _get_store(hass: HomeAssistant) -> RecipeStore | None:
    return hass.data.get(DOMAIN)


def _run(
    hass: HomeAssistant,
    connection: websocket_api.ActiveConnection,
    msg: dict[str, Any],
    action: Callable[[RecipeStore], Any],
) -> None:
    """Run a change on the library, persist it and answer the request."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "Recipe Library is not set up")
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
    websocket_api.async_register_command(hass, ws_subscribe)
    websocket_api.async_register_command(hass, ws_recipe_save)
    websocket_api.async_register_command(hass, ws_recipe_delete)
    websocket_api.async_register_command(hass, ws_tag_create)
    websocket_api.async_register_command(hass, ws_tag_rename)
    websocket_api.async_register_command(hass, ws_tag_delete)


@websocket_api.websocket_command({vol.Required("type"): f"{DOMAIN}/subscribe"})
@callback
def ws_subscribe(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Send all tags and recipes now and again after every change."""
    store = _get_store(hass)
    if store is None:
        connection.send_error(msg["id"], "not_loaded", "Recipe Library is not set up")
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
    }
)
@callback
def ws_recipe_save(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Create a recipe or replace the editable fields of an existing one."""
    fields = {k: v for k, v in msg.items() if k not in ("id", "type", "recipe_id")}
    _run(
        hass,
        connection,
        msg,
        lambda store: store.library.save_recipe(fields, msg.get("recipe_id")),
    )


@websocket_api.websocket_command(
    {
        vol.Required("type"): f"{DOMAIN}/recipe/delete",
        vol.Required("recipe_id"): cv.string,
    }
)
@callback
def ws_recipe_delete(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    """Delete a recipe."""

    def _delete(store: RecipeStore) -> None:
        store.library.delete_recipe(msg["recipe_id"])

    _run(hass, connection, msg, _delete)


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
