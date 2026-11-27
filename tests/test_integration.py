"""Tests for the integration: setup, WebSocket API, storage and card delivery."""

import base64
import os
import time
from datetime import timedelta
from pathlib import Path

import pytest
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
from custom_components.recipe_library.images import MAX_IMAGE_BYTES


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


# -- photos ----------------------------------------------------------------

JPEG = b"\xff\xd8\xff\xe0" + b"photo-data" * 20
PNG = b"\x89PNG\r\n\x1a\n" + b"more-photo-data" * 20


def encoded(data: bytes) -> str:
    """Return photo bytes as the card sends them."""
    return base64.b64encode(data).decode()


async def upload(client, data: bytes = JPEG) -> str:
    """Upload a photo and return its file name."""
    response = await call(client, "image/upload", data=encoded(data))
    assert response["success"], response
    return response["result"]["image"]


async def test_photo_upload_save_and_serve(
    hass: HomeAssistant, hass_ws_client, hass_client_no_auth, image_dir: Path
) -> None:
    """A photo can be uploaded, attached to a recipe and shown by the browser."""
    await setup_integration(hass)
    client = await hass_ws_client(hass)
    name = await upload(client)
    assert name.endswith(".jpg")
    assert (image_dir / name).read_bytes() == JPEG

    response = await call(client, "recipe/save", title="Mit Foto", image=name)
    assert response["success"]
    assert response["result"]["image"] == name

    # The <img> tag of the browser cannot send a login, so no authentication.
    http = await hass_client_no_auth()
    served = await http.get(f"/api/recipe_library/image/{name}")
    assert served.status == 200
    assert served.headers["Content-Type"] == "image/jpeg"
    assert "immutable" in served.headers["Cache-Control"]
    assert served.headers["X-Content-Type-Options"] == "nosniff"
    assert "sandbox" in served.headers["Content-Security-Policy"]
    assert await served.read() == JPEG


@pytest.mark.parametrize(
    "name",
    [
        "0" * 32 + ".jpg",  # valid format, but no such photo
        "..%2F..%2Fsecrets.yaml",
        "%2e%2e%2f%2e%2e%2fconfiguration.yaml",
        "abc.jpg",
        "0" * 32 + ".svg",
        "0" * 32 + ".jpg.txt",
    ],
)
async def test_photo_view_rejects_unknown_and_invalid_names(
    hass: HomeAssistant, hass_client_no_auth, image_dir: Path, name: str
) -> None:
    """Only existing photos with a valid name are served."""
    await setup_integration(hass)
    http = await hass_client_no_auth()
    response = await http.get(f"/api/recipe_library/image/{name}")
    # Home Assistant itself answers 400 for encoded path traversal; both refuse.
    assert response.status in (400, 404)


async def test_png_is_served_as_png(
    hass: HomeAssistant, hass_ws_client, hass_client_no_auth, image_dir: Path
) -> None:
    """The content type follows the detected format."""
    await setup_integration(hass)
    client = await hass_ws_client(hass)
    name = await upload(client, PNG)
    assert name.endswith(".png")
    http = await hass_client_no_auth()
    assert (await http.get(f"/api/recipe_library/image/{name}")).headers[
        "Content-Type"
    ] == "image/png"


@pytest.mark.parametrize(
    ("data", "code"),
    [
        (encoded(b"just some text"), "invalid_format"),
        ("%%% not base64 %%%", "invalid_format"),
        (encoded(b"<svg onload=alert(1)></svg>"), "invalid_format"),
        (encoded(JPEG + b"x" * MAX_IMAGE_BYTES), "image_too_large"),
    ],
)
async def test_photo_upload_rejects_bad_data(
    hass: HomeAssistant, hass_ws_client, image_dir: Path, data: str, code: str
) -> None:
    """Broken, unsupported and oversized uploads are refused and not stored."""
    await setup_integration(hass)
    client = await hass_ws_client(hass)
    response = await call(client, "image/upload", data=data)
    assert response["error"]["code"] == code
    assert not image_dir.exists() or not list(image_dir.iterdir())


async def test_photo_upload_is_available_to_non_admin_users(
    hass: HomeAssistant,
    hass_ws_client,
    hass_read_only_access_token: str,
    image_dir: Path,
) -> None:
    """Every Home Assistant user can add photos."""
    await setup_integration(hass)
    client = await hass_ws_client(hass, hass_read_only_access_token)
    assert (await upload(client)).endswith(".jpg")


async def test_recipe_rejects_unknown_or_invalid_photo(
    hass: HomeAssistant, hass_ws_client, image_dir: Path
) -> None:
    """A recipe can only use a photo that was uploaded."""
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await call(client, "recipe/save", title="A", image="0" * 32 + ".jpg")
    assert response["error"]["code"] == "not_found"
    for bad in ("../../x.jpg", "photo.jpg", "0" * 32 + ".svg"):
        response = await call(client, "recipe/save", title="A", image=bad)
        assert response["error"]["code"] == "invalid_format"


async def test_replaced_and_removed_photos_are_deleted(
    hass: HomeAssistant, hass_ws_client, image_dir: Path
) -> None:
    """A photo file is deleted as soon as no recipe uses it any more."""
    await setup_integration(hass)
    client = await hass_ws_client(hass)
    first = await upload(client)
    second = await upload(client, PNG)
    recipe = (await call(client, "recipe/save", title="A", image=first))["result"]

    # Replace the photo: the old file goes, the new one stays.
    await call(client, "recipe/save", recipe_id=recipe["id"], title="A", image=second)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not (image_dir / first).exists()
    assert (image_dir / second).exists()

    # Saving without a photo removes it.
    response = await call(client, "recipe/save", recipe_id=recipe["id"], title="A")
    assert response["result"]["image"] == ""
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not (image_dir / second).exists()


async def test_deleting_a_recipe_deletes_its_photo(
    hass: HomeAssistant, hass_ws_client, image_dir: Path
) -> None:
    """The photo goes together with its recipe."""
    await setup_integration(hass)
    client = await hass_ws_client(hass)
    name = await upload(client)
    recipe = (await call(client, "recipe/save", title="A", image=name))["result"]
    assert (await call(client, "recipe/delete", recipe_id=recipe["id"]))["success"]
    await hass.async_block_till_done(wait_background_tasks=True)
    assert not (image_dir / name).exists()


async def test_shared_photo_is_kept_while_another_recipe_uses_it(
    hass: HomeAssistant, hass_ws_client, image_dir: Path
) -> None:
    """Deleting one of two recipes with the same photo keeps the file."""
    await setup_integration(hass)
    client = await hass_ws_client(hass)
    name = await upload(client)
    first = (await call(client, "recipe/save", title="A", image=name))["result"]
    await call(client, "recipe/save", title="B", image=name)
    await call(client, "recipe/delete", recipe_id=first["id"])
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (image_dir / name).exists()


async def test_discard_removes_only_unused_photos(
    hass: HomeAssistant, hass_ws_client, image_dir: Path
) -> None:
    """Cancelling a form discards the upload, but never a photo in use."""
    await setup_integration(hass)
    client = await hass_ws_client(hass)
    unused = await upload(client)
    used = await upload(client, PNG)
    await call(client, "recipe/save", title="A", image=used)

    assert (await call(client, "image/discard", image=unused))["success"]
    assert (await call(client, "image/discard", image=used))["success"]
    assert not (image_dir / unused).exists()
    assert (image_dir / used).exists()

    response = await call(client, "image/discard", image="../../etc/passwd")
    assert response["error"]["code"] == "invalid_format"


async def test_setup_removes_old_unused_photos(
    hass: HomeAssistant, hass_ws_client, image_dir: Path
) -> None:
    """Old uploads without a recipe are cleaned up when the integration starts."""
    entry = await setup_integration(hass)
    client = await hass_ws_client(hass)
    used = await upload(client)
    old = await upload(client)
    recent = await upload(client)
    await call(client, "recipe/save", title="A", image=used)
    assert await hass.config_entries.async_unload(entry.entry_id)

    two_days_ago = time.time() - 2 * 24 * 3600
    os.utime(image_dir / old, (two_days_ago, two_days_ago))
    os.utime(image_dir / used, (two_days_ago, two_days_ago))
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)

    assert not (image_dir / old).exists()
    assert (image_dir / used).exists()  # a recipe uses it
    assert (image_dir / recent).exists()  # too new, may still be in a form


async def test_setup_keeps_all_photos_when_the_library_is_empty(
    hass: HomeAssistant, hass_ws_client, image_dir: Path
) -> None:
    """An unreadable data file must never lead to deleting every photo."""
    entry = await setup_integration(hass)
    client = await hass_ws_client(hass)
    name = await upload(client)
    assert await hass.config_entries.async_unload(entry.entry_id)
    old = time.time() - 5 * 24 * 3600
    os.utime(image_dir / name, (old, old))

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert (image_dir / name).exists()
