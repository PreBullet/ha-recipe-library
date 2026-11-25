"""Tests for the integration: setup, WebSocket API, storage and card delivery."""

from datetime import timedelta

from homeassistant.components import frontend
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.recipe_library.const import (
    CARD_URL,
    DOMAIN,
    SAVE_DELAY,
    STORAGE_KEY,
)


async def setup_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Set up the integration with a config entry."""
    entry = MockConfigEntry(domain=DOMAIN, unique_id=DOMAIN, data={})
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    return entry


async def subscribe(client) -> dict:
    """Subscribe to changes and return the first snapshot."""
    await client.send_json_auto_id({"type": f"{DOMAIN}/subscribe"})
    result = await client.receive_json()
    assert result["success"]
    event = await client.receive_json()
    assert event["type"] == "event"
    return event["event"]


async def call(client, command: str, **data) -> dict:
    """Send a command and return the response.

    A change is announced to subscribers before the answer is sent, so the
    snapshots that arrive first are kept in ``client.events`` (oldest first).
    """
    await client.send_json_auto_id({"type": f"{DOMAIN}/{command}", **data})
    client.events = []
    while (message := await client.receive_json())["type"] == "event":
        client.events.append(message["event"])
    return message


async def test_config_flow_creates_single_entry(hass: HomeAssistant) -> None:
    """The setup form has no fields and only one library is possible."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    await hass.async_block_till_done()

    again = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert again["type"] == "abort"


async def test_recipe_and_tag_flow(hass: HomeAssistant, hass_ws_client) -> None:
    """Create, edit, rename and delete, with live updates for the subscriber."""
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    assert await subscribe(client) == {"tags": [], "recipes": []}

    # Create a tag, then a recipe that uses it.
    response = await call(client, "tag/create", name="Pasta")
    assert response["success"]
    tag = response["result"]
    assert client.events == [{"tags": [tag], "recipes": []}]

    response = await call(
        client,
        "recipe/save",
        title="Carbonara",
        time="25 Min.",
        servings="2",
        tags=[tag["id"]],
        ingredients=["200 g Spaghetti", "2 Eier"],
        steps=["Kochen.", "Mischen."],
    )
    assert response["success"]
    recipe = response["result"]
    assert recipe["title"] == "Carbonara"
    # The snapshot is already there when the answer arrives.
    assert client.events[-1]["recipes"] == [recipe]

    # Edit: any user may change any recipe at any time. Omitted fields are
    # cleared because the card always sends the whole form.
    response = await call(
        client, "recipe/save", recipe_id=recipe["id"], title="Carbonara (neu)"
    )
    assert response["success"]
    assert response["result"]["id"] == recipe["id"]
    assert response["result"]["tags"] == []

    # Re-attach the tag, then rename it: the recipe still references the id.
    await call(
        client, "recipe/save", recipe_id=recipe["id"], title="C", tags=[tag["id"]]
    )
    response = await call(client, "tag/rename", tag_id=tag["id"], name="Nudeln")
    assert response["result"] == {"id": tag["id"], "name": "Nudeln"}
    snapshot = client.events[-1]
    assert snapshot["tags"] == [{"id": tag["id"], "name": "Nudeln"}]
    assert snapshot["recipes"][0]["tags"] == [tag["id"]]

    # Deleting the tag keeps the recipe.
    response = await call(client, "tag/delete", tag_id=tag["id"])
    assert response["result"] == {"affected": 1}
    snapshot = client.events[-1]
    assert snapshot["tags"] == []
    assert snapshot["recipes"][0]["tags"] == []

    # Delete the recipe.
    response = await call(client, "recipe/delete", recipe_id=recipe["id"])
    assert response["success"]
    assert client.events[-1]["recipes"] == []


async def test_error_codes(hass: HomeAssistant, hass_ws_client) -> None:
    """Invalid requests are answered with an error code and change nothing."""
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await call(client, "recipe/save", title="   ")
    assert response["error"]["code"] == "invalid_format"

    response = await call(client, "recipe/save", title="A", tags=["unknown"])
    assert response["error"]["code"] == "invalid_format"

    response = await call(client, "recipe/save", recipe_id="nope", title="A")
    assert response["error"]["code"] == "not_found"

    response = await call(client, "recipe/delete", recipe_id="nope")
    assert response["error"]["code"] == "not_found"

    await call(client, "tag/create", name="Pasta")
    other = (await call(client, "tag/create", name="Suppen"))["result"]
    response = await call(client, "tag/rename", tag_id=other["id"], name="pasta")
    assert response["error"]["code"] == "name_exists"

    response = await call(client, "tag/rename", tag_id="nope", name="x")
    assert response["error"]["code"] == "not_found"

    # A wrong type is rejected by the schema before reaching the library.
    response = await call(client, "recipe/save", title="A", ingredients="text")
    assert response["error"]["code"] == "invalid_format"


async def test_available_to_non_admin_users(
    hass: HomeAssistant, hass_ws_client, hass_read_only_access_token: str
) -> None:
    """Every Home Assistant user can read and write, not only admins."""
    await setup_integration(hass)
    client = await hass_ws_client(hass, hass_read_only_access_token)

    assert await subscribe(client) == {"tags": [], "recipes": []}
    response = await call(client, "recipe/save", title="Von einem Nutzer")
    assert response["success"]
    assert [r["title"] for r in client.events[-1]["recipes"]] == ["Von einem Nutzer"]


async def test_changes_reach_all_subscribers(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """A change made by one user is pushed to every open card."""
    await setup_integration(hass)
    first = await hass_ws_client(hass)
    second = await hass_ws_client(hass)
    await subscribe(first)
    await subscribe(second)

    await call(first, "recipe/save", title="Geteilt")
    assert [r["title"] for r in first.events[-1]["recipes"]] == ["Geteilt"]

    # The other card gets the update without having asked for it.
    event = await second.receive_json()
    assert event["type"] == "event"
    assert [r["title"] for r in event["event"]["recipes"]] == ["Geteilt"]


async def test_unsubscribe_stops_updates(hass: HomeAssistant, hass_ws_client) -> None:
    """After unsubscribing a card receives no more snapshots."""
    await setup_integration(hass)
    client = await hass_ws_client(hass)
    # The test client numbers its messages 1, 2, 3, ...: this is message 1.
    await subscribe(client)

    await client.send_json_auto_id({"type": "unsubscribe_events", "subscription": 1})
    assert (await client.receive_json())["success"]

    # The answers arrive directly, with no snapshot event in between.
    response = await call(client, "recipe/save", title="Leise")
    assert response["success"]
    assert client.events == []
    response = await call(client, "tag/create", name="Pasta")
    assert response["success"]
    assert client.events == []


async def test_data_is_persisted_and_loaded(
    hass: HomeAssistant, hass_ws_client, hass_storage
) -> None:
    """Changes are written shortly after and are available after a restart."""
    entry = await setup_integration(hass)
    client = await hass_ws_client(hass)
    await call(client, "recipe/save", title="Bleibt")

    async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=SAVE_DELAY + 1))
    await hass.async_block_till_done()
    stored = hass_storage[STORAGE_KEY]["data"]
    assert [r["title"] for r in stored["recipes"]] == ["Bleibt"]

    # Unloading writes immediately, then a new setup loads the stored data.
    await call(client, "recipe/save", title="Zweites")
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert [r["title"] for r in hass_storage[STORAGE_KEY]["data"]["recipes"]] == [
        "Bleibt",
        "Zweites",
    ]
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    client = await hass_ws_client(hass)
    snapshot = await subscribe(client)
    assert [r["title"] for r in snapshot["recipes"]] == ["Bleibt", "Zweites"]


async def test_existing_storage_is_loaded(hass: HomeAssistant, hass_storage) -> None:
    """Data written by an earlier run is available right after setup."""
    hass_storage[STORAGE_KEY] = {
        "version": 1,
        "minor_version": 1,
        "key": STORAGE_KEY,
        "data": {
            "version": 1,
            "tags": [{"id": "t1", "name": "Pasta"}],
            "recipes": [{"id": "r1", "title": "Alt", "tags": ["t1"]}],
        },
    }
    await setup_integration(hass)
    library = hass.data[DOMAIN].library
    assert [r["title"] for r in library.snapshot()["recipes"]] == ["Alt"]


async def test_card_is_served_and_registered(hass: HomeAssistant, hass_client) -> None:
    """The card is served by the integration and loaded by the frontend."""
    entry = await setup_integration(hass)

    registered = hass.data[frontend.DATA_EXTRA_MODULE_URL].urls
    assert any(url.startswith(f"{CARD_URL}?v=") for url in registered)

    client = await hass_client()
    response = await client.get(CARD_URL)
    assert response.status == 200
    assert "javascript" in response.headers["Content-Type"]

    # Unloading removes the registration; setting up again must not fail even
    # though static paths cannot be unregistered.
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert not any(
        url.startswith(f"{CARD_URL}?v=")
        for url in hass.data[frontend.DATA_EXTRA_MODULE_URL].urls
    )
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED


async def test_commands_fail_cleanly_when_not_loaded(
    hass: HomeAssistant, hass_ws_client
) -> None:
    """After unloading, the (still registered) commands answer with an error."""
    entry = await setup_integration(hass)
    client = await hass_ws_client(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)

    response = await call(client, "recipe/save", title="A")
    assert response["error"]["code"] == "not_loaded"
    await client.send_json_auto_id({"type": f"{DOMAIN}/subscribe"})
    assert (await client.receive_json())["error"]["code"] == "not_loaded"
