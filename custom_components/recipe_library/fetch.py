"""Download web pages and pictures for the import, safely.

The Home Assistant server loads the addresses that users type in. Without care
that would let every user reach devices in the home network or services that
only listen on the server itself (server-side request forgery). So:

* only ``http`` and ``https`` on the standard ports, no login in the address,
* only public IP addresses: checked for addresses written as numbers, and for
  host names when the name is resolved, which is also the address that is
  connected to (so a name that changes its answer cannot get around it),
* redirects are followed by hand and every target is checked again,
* the answer is limited in size and time, and nothing but the recipe data that
  was read from it is handed on.

No Home Assistant imports, so this can be tested on its own.
"""

from __future__ import annotations

import codecs
import ipaddress
import re
import socket
from dataclasses import dataclass

import aiohttp
from aiohttp.abc import AbstractResolver, ResolveResult
from yarl import URL

from .images import MAX_IMAGE_BYTES, detect_image_type
from .library import MAX_SOURCE, LibraryError

ALLOWED_SCHEMES = ("http", "https")
ALLOWED_PORTS = (80, 443)
MAX_REDIRECTS = 5
TIMEOUT = 15  # seconds for one download, including redirects
MAX_PAGE_BYTES = 4 * 1024 * 1024
USER_AGENT = (
    "Mozilla/5.0 (compatible; HomeAssistant-RecipeLibrary; "
    "+https://github.com/PreBullet/ha-recipe-library)"
)
HTML_ACCEPT = "text/html,application/xhtml+xml;q=0.9,*/*;q=0.1"
IMAGE_ACCEPT = "image/jpeg,image/png,image/webp;q=0.9,*/*;q=0.1"

_HTML_TYPES = ("text/html", "application/xhtml+xml")
_REDIRECTS = (301, 302, 303, 307, 308)
_CHUNK = 64 * 1024
_NAT64 = ipaddress.ip_network("64:ff9b::/96")
_LANGUAGE_RE = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})?$")
_META_CHARSET_RE = re.compile(
    rb"<meta[^>]+charset\s*=\s*[\"']?\s*([A-Za-z0-9_.:-]+)", re.I
)


class InvalidUrlError(LibraryError):
    """The text is not a usable web address."""

    code = "invalid_url"


class BlockedUrlError(LibraryError):
    """The address does not lead to a public web server."""

    code = "blocked_url"


class FetchError(LibraryError):
    """The page could not be loaded."""

    code = "fetch_failed"


class PageTooLargeError(LibraryError):
    """The answer is larger than the limit."""

    code = "page_too_large"


class NotHtmlError(LibraryError):
    """The address does not lead to a web page."""

    code = "not_html"


@dataclass(frozen=True)
class Fetched:
    """A downloaded answer."""

    url: str  # final address, after redirects
    mime: str  # content type without parameters, lower case
    charset: str | None
    body: bytes


# -- which addresses are allowed


def is_public_address(address: str) -> bool:
    """Return whether an IP address belongs to the public internet."""
    try:
        ip = ipaddress.ip_address(address.split("%", 1)[0])
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address):
        # An IPv4 address inside an IPv6 one has to pass the IPv4 rules.
        if ip.ipv4_mapped is not None:
            ip = ip.ipv4_mapped
        elif ip in _NAT64:
            ip = ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    if getattr(ip, "is_site_local", False):
        return False
    return ip.is_global and not ip.is_multicast


def check_url(value: str) -> URL:
    """Return the address as a URL, or raise if it must not be loaded."""
    text = value.strip() if isinstance(value, str) else ""
    if not text or len(text) > MAX_SOURCE or re.search(r"\s", text):
        raise InvalidUrlError("not a valid web address")
    if "://" not in text:
        text = f"https://{text}"
    try:
        url = URL(text)
    except ValueError as err:
        raise InvalidUrlError("not a valid web address") from err
    if url.scheme not in ALLOWED_SCHEMES or not url.host:
        raise InvalidUrlError("not a valid web address")
    if url.user or url.password:
        raise InvalidUrlError("a web address with a login is not accepted")
    if url.explicit_port is not None and url.explicit_port not in ALLOWED_PORTS:
        raise BlockedUrlError("this port is not allowed")
    # Addresses written as numbers are not resolved, so they are checked here.
    if _is_ip_literal(url.host) and not is_public_address(url.host):
        raise BlockedUrlError("not a public address")
    return url


def _origin(address: str | None) -> str | None:
    """Return ``https://host/`` for a web address, as a browser sends it.

    Some picture servers only answer requests that come from a page of the
    same site. Only the origin is sent, never the path or the query.
    """
    if not address:
        return None
    try:
        url = URL(address)
    except ValueError:
        return None
    if url.scheme not in ALLOWED_SCHEMES or not url.raw_host:
        return None
    # Like a browser: the port only if it is not the usual one.
    default = 443 if url.scheme == "https" else 80
    port = f":{url.port}" if url.port not in (None, default) else ""
    return f"{url.scheme}://{url.raw_host}{port}/"


def _is_ip_literal(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


class SafeResolver(AbstractResolver):
    """Resolve host names, but refuse names that lead to non-public addresses."""

    def __init__(self) -> None:
        """Wrap the resolver that aiohttp would use anyway."""
        self._resolver = aiohttp.DefaultResolver()

    async def resolve(
        self, host: str, port: int = 0, family: socket.AddressFamily = socket.AF_INET
    ) -> list[ResolveResult]:
        """Return the addresses of a host if all of them are public."""
        results = await self._resolver.resolve(host, port, family)
        # One private address is enough to refuse, a name must not mix them.
        if not results or not all(is_public_address(r["host"]) for r in results):
            raise BlockedUrlError("not a public address")
        return results

    async def close(self) -> None:
        """Close the wrapped resolver."""
        await self._resolver.close()


# -- download


async def fetch(
    url: str,
    *,
    accept: str,
    max_bytes: int,
    language: str | None = None,
    timeout: float | None = None,
    referer: str | None = None,
) -> Fetched:
    """Download an address and return the answer.

    Raises ``InvalidUrlError``, ``BlockedUrlError``, ``PageTooLargeError`` or
    ``FetchError`` (with codes the card can show).
    """
    current = check_url(url)
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": accept,
        "Accept-Encoding": "gzip, deflate",
    }
    if language and _LANGUAGE_RE.match(language):
        headers["Accept-Language"] = f"{language},en;q=0.7"
    if origin := _origin(referer):
        headers["Referer"] = origin
    # A session of its own: the shared one of Home Assistant cannot be given
    # the resolver that refuses non-public addresses. No cookies are kept and
    # no proxy settings of the environment are used.
    connector = aiohttp.TCPConnector(resolver=SafeResolver(), force_close=True, limit=2)
    try:
        async with aiohttp.ClientSession(
            connector=connector,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout or TIMEOUT),
            cookie_jar=aiohttp.DummyCookieJar(),
        ) as session:
            for _ in range(MAX_REDIRECTS + 1):
                async with session.get(current, allow_redirects=False) as response:
                    if response.status in _REDIRECTS:
                        location = response.headers.get("Location")
                        if not location:
                            raise FetchError("redirect without a target")
                        current = check_url(str(current.join(URL(location))))
                        continue
                    if response.status != 200:
                        raise FetchError(f"the server answered {response.status}")
                    return await _read(response, current, max_bytes)
        raise FetchError("too many redirects")
    except (aiohttp.ClientError, TimeoutError, ValueError, UnicodeError) as err:
        raise FetchError("the address could not be loaded") from err


async def _read(response: aiohttp.ClientResponse, url: URL, max_bytes: int) -> Fetched:
    """Read the body of an answer up to the size limit."""
    if response.content_length is not None and response.content_length > max_bytes:
        raise PageTooLargeError("the answer is too large")
    body = bytearray()
    async for chunk in response.content.iter_chunked(_CHUNK):
        body.extend(chunk)
        if len(body) > max_bytes:
            raise PageTooLargeError("the answer is too large")
    mime = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
    return Fetched(str(url), mime, response.charset, bytes(body))


def decode_html(body: bytes, charset: str | None) -> str:
    """Decode a page using its declared character set, UTF-8 if nothing fits."""
    candidates = [charset] if charset else []
    if meta := _META_CHARSET_RE.search(body[:4096]):
        candidates.append(meta.group(1).decode("ascii", "ignore"))
    candidates.append("utf-8")
    for name in candidates:
        try:
            codecs.lookup(name)
            return body.decode(name)
        except (LookupError, UnicodeDecodeError):
            continue
    return body.decode("utf-8", errors="replace")


async def fetch_page(url: str, language: str | None = None) -> tuple[str, str]:
    """Download a web page and return ``(text, final address)``."""
    answer = await fetch(
        url, accept=HTML_ACCEPT, max_bytes=MAX_PAGE_BYTES, language=language
    )
    if answer.mime not in _HTML_TYPES:
        raise NotHtmlError("the address does not lead to a web page")
    return decode_html(answer.body, answer.charset), answer.url


async def fetch_image(
    url: str,
    language: str | None = None,
    *,
    referer: str | None = None,
    timeout: float | None = None,
) -> tuple[bytes, str]:
    """Download a picture and return ``(bytes, extension)``.

    ``referer`` is the page the picture belongs to (only its origin is sent).
    Only JPEG, PNG and WebP are accepted, judged by the content and not by the
    type the server claims. Raises ``FetchError`` for anything else.
    """
    answer = await fetch(
        url,
        accept=IMAGE_ACCEPT,
        max_bytes=MAX_IMAGE_BYTES,
        language=language,
        timeout=timeout or TIMEOUT,
        referer=referer,
    )
    extension = detect_image_type(answer.body)
    if extension is None:
        raise FetchError("the picture format is not supported")
    return answer.body, extension
