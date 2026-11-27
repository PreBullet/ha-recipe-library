"""Shared test fixtures."""

from collections.abc import AsyncIterator, Callable
from pathlib import Path
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer
from homeassistant.core import HomeAssistant

from custom_components.recipe_library import fetch as fetch_module

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load the integration from custom_components."""
    return


@pytest.fixture
def image_dir(hass: HomeAssistant, tmp_path: Path) -> Path:
    """Keep photo files of a test in a temporary configuration folder."""
    hass.config.config_dir = str(tmp_path)
    return tmp_path / ".storage" / "recipe_library_images"


class Site:
    """A local web server that records the requests it gets."""

    def __init__(self, server: TestServer) -> None:
        self.server = server
        self.requests: list[web.Request] = []

    def url(self, path: str = "/", host: str = "127.0.0.1") -> str:
        return f"http://{host}:{self.server.port}{path}"


@pytest.fixture
async def make_site(
    monkeypatch: pytest.MonkeyPatch, socket_enabled: None
) -> AsyncIterator[Callable[..., Any]]:
    """Start a local server; its address is let through like a public one."""
    servers: list[TestServer] = []

    async def start(routes: dict[str, Callable[..., Any]]) -> Site:
        site: Site

        def wrap(handler: Callable[..., Any]) -> Callable[..., Any]:
            async def run(request: web.Request) -> web.StreamResponse:
                site.requests.append(request)
                return await handler(request)

            return run

        app = web.Application()
        for path, handler in routes.items():
            app.router.add_get(path, wrap(handler))
        server = TestServer(app)
        await server.start_server()
        servers.append(server)
        site = Site(server)
        monkeypatch.setattr(fetch_module, "ALLOWED_PORTS", (80, 443, server.port))
        original = fetch_module.is_public_address
        monkeypatch.setattr(
            fetch_module, "is_public_address", lambda a: a == "127.0.0.1" or original(a)
        )
        return site

    yield start
    for server in servers:
        await server.close()
