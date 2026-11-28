"""Tests for importing a recipe from a web page over the WebSocket API."""

import asyncio
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from aiohttp import web
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.recipe_library import fetch as fetch_module
from custom_components.recipe_library import web_import
from custom_components.recipe_library.const import DOMAIN

from .test_integration import call, setup_integration, subscribe

JPEG = b"\xff\xd8\xff\xe0" + b"web-photo" * 30


def recipe_json(image: str | None = "/img/pasta.jpg") -> dict[str, Any]:
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Recipe",
        "name": "Tomato pasta",
        "description": "Quick and simple.",
        "totalTime": "PT30M",
        "recipeYield": "4",
        "recipeIngredient": ["200 g pasta", "1 can tomatoes"],
        "recipeInstructions": [
            {"@type": "HowToStep", "text": "Boil the pasta."},
            {"@type": "HowToStep", "text": "Add the sauce."},
        ],
    }
    if image is not None:
        data["image"] = image
    return data


def recipe_page(
    image: str | None = "/img/pasta.jpg", head: str = ""
) -> Callable[..., Any]:
    async def handler(request: web.Request) -> web.Response:
        body = (
            f"<html><head>{head}<script type='application/ld+json'>"
            f"{json.dumps(recipe_json(image))}</script></head><body>Hi</body></html>"
        )
        return web.Response(text=body, content_type="text/html")

    return handler


async def not_found(request: web.Request) -> web.Response:
    return web.Response(status=404)


def picture(data: bytes = JPEG, content_type: str = "image/jpeg") -> Callable[..., Any]:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(body=data, content_type=content_type)

    return handler


async def import_url(client, url: str) -> dict:
    return await call(client, "import/url", url=url)


def image_files(image_dir: Path) -> list[str]:
    return sorted(p.name for p in image_dir.glob("*")) if image_dir.is_dir() else []


# -- a successful import


async def test_import_returns_a_draft_with_its_picture(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    site = await make_site({"/recipe": recipe_page(), "/img/pasta.jpg": picture()})
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/recipe"))

    assert response["success"], response
    draft = response["result"]
    image = draft.pop("image")
    assert draft == {
        "title": "Tomato pasta",
        "time": "30 min",
        "servings": "4",
        "ingredients": ["200 g pasta", "1 can tomatoes"],
        "steps": ["Boil the pasta.", "Add the sauce."],
        "notes": "Quick and simple.",
        "source": site.url("/recipe"),
        "image_issue": "",
    }
    assert (image_dir / image).read_bytes() == JPEG


async def test_import_does_not_save_anything(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    site = await make_site({"/recipe": recipe_page(), "/img/pasta.jpg": picture()})
    await setup_integration(hass)
    client = await hass_ws_client(hass)
    before = await subscribe(client)

    response = await import_url(client, site.url("/recipe"))

    assert response["success"]
    assert before["recipes"] == []
    assert client.events == []  # nobody is told about a change
    assert hass.data[DOMAIN].library.snapshot()["recipes"] == []


async def test_the_draft_can_be_saved_like_any_recipe(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    site = await make_site({"/recipe": recipe_page(), "/img/pasta.jpg": picture()})
    await setup_integration(hass)
    client = await hass_ws_client(hass)
    draft = (await import_url(client, site.url("/recipe")))["result"]

    fields = {k: v for k, v in draft.items() if k != "image_issue"}

    saved = await call(client, "recipe/save", tags=[], **fields)

    assert saved["success"], saved
    assert saved["result"]["title"] == "Tomato pasta"
    assert saved["result"]["image"] == draft["image"]
    assert image_files(image_dir) == [draft["image"]]


async def test_an_unused_draft_picture_can_be_discarded(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    site = await make_site({"/recipe": recipe_page(), "/img/pasta.jpg": picture()})
    await setup_integration(hass)
    client = await hass_ws_client(hass)
    draft = (await import_url(client, site.url("/recipe")))["result"]
    assert image_files(image_dir) == [draft["image"]]

    response = await call(client, "image/discard", image=draft["image"])
    await hass.async_block_till_done(wait_background_tasks=True)

    assert response["success"]
    assert image_files(image_dir) == []


async def test_the_final_address_after_a_redirect_is_the_source(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    async def moved(request: web.Request) -> web.Response:
        raise web.HTTPMovedPermanently("/new/recipe")

    site = await make_site({"/old": moved, "/new/recipe": recipe_page(None)})
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/old"))

    assert response["result"]["source"] == site.url("/new/recipe")


async def test_everybody_may_import_not_only_admins(
    hass: HomeAssistant,
    hass_ws_client,
    hass_read_only_access_token: str,
    make_site,
    image_dir: Path,
) -> None:
    site = await make_site({"/recipe": recipe_page(None)})
    await setup_integration(hass)
    client = await hass_ws_client(hass, hass_read_only_access_token)

    response = await import_url(client, site.url("/recipe"))

    assert response["success"], response


# -- the picture is optional


@pytest.mark.parametrize(
    "routes",
    [
        {},  # the picture is not there (404)
        {"/img/pasta.jpg": picture(b"<html>not a picture</html>", "image/jpeg")},
        {"/img/pasta.jpg": picture(b"GIF89a" + b"0" * 100, "image/gif")},
    ],
    ids=["missing", "not-an-image", "unsupported-format"],
)
async def test_a_recipe_without_usable_picture_is_still_imported(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path, routes: dict
) -> None:
    site = await make_site({"/recipe": recipe_page(), **routes})
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/recipe"))

    assert response["success"], response
    assert response["result"]["title"] == "Tomato pasta"
    assert response["result"]["image"] == ""
    assert response["result"]["image_issue"] == "download_failed"
    assert image_files(image_dir) == []


async def test_a_too_large_picture_is_skipped(
    hass: HomeAssistant,
    hass_ws_client,
    make_site,
    image_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = await make_site({"/recipe": recipe_page(), "/img/pasta.jpg": picture()})
    monkeypatch.setattr(fetch_module, "MAX_IMAGE_BYTES", 50)
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/recipe"))

    assert response["success"]
    assert response["result"]["image"] == ""
    assert response["result"]["image_issue"] == "too_large"
    assert image_files(image_dir) == []


@pytest.mark.parametrize(
    "target",
    [
        "http://10.0.0.5/camera.jpg",
        "http://169.254.169.254/x.jpg",
        "http://[::1]/x.jpg",
    ],
)
async def test_a_picture_inside_the_network_is_not_loaded(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path, target: str
) -> None:
    site = await make_site({"/recipe": recipe_page(target)})
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/recipe"))

    assert response["success"]
    assert response["result"]["image"] == ""
    assert response["result"]["image_issue"] == "download_failed"
    assert (
        len(site.requests) == 1
    )  # only the page, nothing was requested for the picture


async def test_a_page_without_picture_says_so(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    site = await make_site({"/recipe": recipe_page(None)})
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/recipe"))

    assert response["success"], response
    assert response["result"]["image"] == ""
    assert response["result"]["image_issue"] == "not_found"
    assert len(site.requests) == 1


# -- several pictures


async def test_the_preview_picture_of_the_page_is_the_fallback(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    head = '<meta property="og:image" content="/img/preview.jpg">'
    site = await make_site(
        {
            "/recipe": recipe_page(None, head),
            "/img/preview.jpg": picture(),
        }
    )
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/recipe"))

    assert response["success"], response
    assert response["result"]["image_issue"] == ""
    assert (image_dir / response["result"]["image"]).read_bytes() == JPEG


async def test_the_next_picture_is_tried_when_one_fails(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    head = '<meta property="og:image" content="/img/preview.jpg">'
    site = await make_site(
        {
            "/recipe": recipe_page("/img/broken.jpg", head),
            "/img/broken.jpg": picture(b"<html>no picture</html>", "image/jpeg"),
            "/img/preview.jpg": picture(),
        }
    )
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/recipe"))

    assert response["success"], response
    assert response["result"]["image_issue"] == ""
    assert (image_dir / response["result"]["image"]).read_bytes() == JPEG
    assert [r.path for r in site.requests] == [
        "/recipe",
        "/img/broken.jpg",
        "/img/preview.jpg",
    ]
    assert image_files(image_dir) == [response["result"]["image"]]


async def test_only_one_picture_is_kept(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    head = '<meta property="og:image" content="/img/preview.jpg">'
    site = await make_site(
        {
            "/recipe": recipe_page("/img/pasta.jpg", head),
            "/img/pasta.jpg": picture(),
            "/img/preview.jpg": picture(),
        }
    )
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/recipe"))

    assert response["result"]["image_issue"] == ""
    assert [r.path for r in site.requests] == ["/recipe", "/img/pasta.jpg"]
    assert len(image_files(image_dir)) == 1


async def test_the_first_problem_is_the_one_that_is_reported(
    hass: HomeAssistant,
    hass_ws_client,
    make_site,
    image_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    head = '<meta property="og:image" content="/img/missing.jpg">'
    site = await make_site(
        {
            "/recipe": recipe_page("/img/pasta.jpg", head),
            "/img/pasta.jpg": picture(),
            "/img/missing.jpg": not_found,
        }
    )
    monkeypatch.setattr(fetch_module, "MAX_IMAGE_BYTES", 50)
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/recipe"))

    assert response["result"]["image"] == ""
    assert response["result"]["image_issue"] == "too_large"  # not the later 404
    assert len(site.requests) == 3


async def test_the_time_for_pictures_is_limited(
    hass: HomeAssistant,
    hass_ws_client,
    make_site,
    image_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = await make_site({"/recipe": recipe_page(), "/img/pasta.jpg": picture()})
    monkeypatch.setattr(web_import, "PICTURE_BUDGET", 0)
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/recipe"))

    assert response["success"], response
    assert response["result"]["image"] == ""
    assert response["result"]["image_issue"] == "download_failed"
    assert len(site.requests) == 1


async def test_a_picture_is_asked_for_like_a_browser_does(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    site = await make_site(
        {"/recipe/secret-path": recipe_page(), "/img/pasta.jpg": picture()}
    )
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/recipe/secret-path?token=1"))

    assert response["result"]["image_issue"] == ""
    page_request, picture_request = site.requests
    assert "Referer" not in page_request.headers
    # Only the origin of the page, never its path or query.
    assert picture_request.headers["Referer"] == site.url("/")


# -- errors


async def test_a_page_without_recipe_data(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    async def plain(request: web.Request) -> web.Response:
        return web.Response(
            text="<html><body>Just text</body></html>", content_type="text/html"
        )

    site = await make_site({"/": plain})
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/"))

    assert not response["success"]
    assert response["error"]["code"] == "no_recipe"


@pytest.mark.parametrize(
    ("url", "code"),
    [
        ("", "invalid_url"),
        ("ftp://recipes.example/a", "invalid_url"),
        ("javascript:alert(1)", "invalid_url"),
        ("https://user:pw@recipes.example/a", "invalid_url"),
        ("http://127.0.0.1:8123/api/", "blocked_url"),
        ("http://localhost/", "blocked_url"),
        ("http://192.168.1.1/", "blocked_url"),
        ("http://169.254.169.254/latest/meta-data/", "blocked_url"),
        ("http://[::1]/", "blocked_url"),
        ("https://recipes.example:8123/", "blocked_url"),
    ],
)
async def test_addresses_that_must_not_be_loaded(
    hass: HomeAssistant, hass_ws_client, image_dir: Path, url: str, code: str
) -> None:
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, url)

    assert not response["success"]
    assert response["error"]["code"] == code


@pytest.mark.parametrize(
    ("status", "code"),
    [(404, "fetch_failed"), (403, "fetch_failed"), (500, "fetch_failed")],
)
async def test_a_page_that_cannot_be_loaded(
    hass: HomeAssistant,
    hass_ws_client,
    make_site,
    image_dir: Path,
    status: int,
    code: str,
) -> None:
    async def fail(request: web.Request) -> web.Response:
        return web.Response(status=status)

    site = await make_site({"/": fail})
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/"))

    assert response["error"]["code"] == code


async def test_something_that_is_not_a_web_page(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    site = await make_site({"/": picture()})
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/"))

    assert response["error"]["code"] == "not_html"


async def test_a_page_that_is_too_large(
    hass: HomeAssistant,
    hass_ws_client,
    make_site,
    image_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    site = await make_site({"/": recipe_page()})
    monkeypatch.setattr(fetch_module, "MAX_PAGE_BYTES", 100)
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, site.url("/"))

    assert response["error"]["code"] == "page_too_large"


async def test_the_error_does_not_reveal_details_of_the_request(
    hass: HomeAssistant, hass_ws_client, image_dir: Path
) -> None:
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await import_url(client, "http://10.1.2.3/secret-admin-page")

    assert response["error"]["code"] == "blocked_url"
    assert "secret-admin-page" not in response["error"]["message"]


async def test_the_command_needs_a_url(
    hass: HomeAssistant, hass_ws_client, image_dir: Path
) -> None:
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    response = await call(client, "import/url")

    assert not response["success"]
    assert response["error"]["code"] == "invalid_format"


async def test_import_after_the_integration_was_removed(
    hass: HomeAssistant, hass_ws_client, image_dir: Path
) -> None:
    entry = await setup_integration(hass)
    client = await hass_ws_client(hass)
    await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED

    response = await import_url(client, "https://recipes.example/a")

    assert response["error"]["code"] == "not_loaded"


# -- load limits


async def test_only_a_few_imports_run_at_the_same_time(
    hass: HomeAssistant, hass_ws_client, make_site, image_dir: Path
) -> None:
    running = 0
    most = 0

    async def slow_page(request: web.Request) -> web.Response:
        nonlocal running, most
        running += 1
        most = max(most, running)
        await asyncio.sleep(0.1)
        running -= 1
        return await recipe_page(None)(request)

    site = await make_site({"/": slow_page})
    await setup_integration(hass)
    client = await hass_ws_client(hass)

    ids = [
        await client.send_json_auto_id(
            {"type": f"{DOMAIN}/import/url", "url": site.url("/")}
        )
        for _ in range(6)
    ]
    answers = [await client.receive_json() for _ in ids]

    assert all(answer["success"] for answer in answers)
    assert most == 2
