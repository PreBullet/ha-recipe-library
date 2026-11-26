"""HTTP view that serves the recipe photos."""

from __future__ import annotations

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView

from .const import DOMAIN, IMAGE_URL_BASE
from .images import CONTENT_TYPES

# The file name is a random 128 bit id, so nobody can guess a URL. A browser
# cannot send the Home Assistant login with an <img> tag, which is why the
# photos are served without authentication (Home Assistant's own image upload
# works the same way). The file name never changes its content, so photos can
# be cached for good.
_HEADERS = {
    "Cache-Control": "public, max-age=31536000, immutable",
    "X-Content-Type-Options": "nosniff",
    "Content-Security-Policy": "default-src 'none'; sandbox",
}


class RecipeImageView(HomeAssistantView):
    """Serve one stored photo."""

    url = f"{IMAGE_URL_BASE}/{{filename}}"
    name = f"api:{DOMAIN}:image"
    requires_auth = False

    async def get(self, request: web.Request, filename: str) -> web.FileResponse:
        """Return the photo, or 404 for any unknown or invalid name."""
        hass = request.app[KEY_HASS]
        store = hass.data.get(DOMAIN)
        path = store.images.path(filename) if store is not None else None
        if path is None or not await hass.async_add_executor_job(path.is_file):
            raise web.HTTPNotFound
        content_type = CONTENT_TYPES[path.suffix.lstrip(".")]
        return web.FileResponse(
            path, headers={**_HEADERS, "Content-Type": content_type}
        )
