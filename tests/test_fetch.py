"""Tests for the safe download of web pages and pictures."""

import asyncio
import socket
from collections.abc import Callable
from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from custom_components.recipe_library import fetch as fetch_module
from custom_components.recipe_library.fetch import (
    BlockedUrlError,
    FetchError,
    InvalidUrlError,
    NotHtmlError,
    PageTooLargeError,
    SafeResolver,
    _origin,
    check_url,
    decode_html,
    fetch_image,
    fetch_page,
    is_public_address,
)
from custom_components.recipe_library.library import MAX_SOURCE

HTTP_EQUIV = '<meta http-equiv="Content-Type" content="text/html; charset=ISO-8859-1">'
JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-data" * 10
PAGE = "<html><head><title>Hi</title></head><body>Hello</body></html>"


# -- which addresses are allowed


@pytest.mark.parametrize(
    "address",
    [
        "8.8.8.8",
        "93.184.216.34",
        "1.1.1.1",
        "2606:4700:4700::1111",
        "2001:4860:4860::8888",
        "::ffff:8.8.8.8",
    ],
)
def test_public_addresses_are_allowed(address: str) -> None:
    assert is_public_address(address)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "127.1.2.3",
        "0.0.0.0",
        "10.0.0.5",
        "172.16.0.1",
        "172.31.255.255",
        "192.168.1.1",
        "169.254.169.254",  # cloud metadata
        "100.64.0.1",  # carrier grade NAT
        "192.0.0.1",
        "198.18.0.1",
        "224.0.0.1",  # multicast
        "255.255.255.255",
        "240.0.0.1",
        "::1",
        "::",
        "fe80::1",
        "fe80::1%eth0",
        "fc00::1",
        "fd12:3456:789a::1",
        "fec0::1",
        "ff02::1",
        "::ffff:10.0.0.1",  # IPv4 inside IPv6
        "::ffff:127.0.0.1",
        "64:ff9b::a00:1",  # NAT64 to 10.0.0.1
        "64:ff9b::7f00:1",  # NAT64 to 127.0.0.1
        "not an address",
        "",
    ],
)
def test_other_addresses_are_refused(address: str) -> None:
    assert not is_public_address(address)


# -- which web addresses are accepted


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("https://recipes.example/a/b?x=1#top", "https://recipes.example/a/b?x=1#top"),
        ("http://recipes.example", "http://recipes.example"),
        ("  https://recipes.example/a  ", "https://recipes.example/a"),
        ("recipes.example/a", "https://recipes.example/a"),
        ("HTTPS://Recipes.Example/a", "https://recipes.example/a"),
        ("https://recipes.example:443/a", "https://recipes.example/a"),
        ("http://recipes.example:80/a", "http://recipes.example/a"),
        ("https://8.8.8.8/a", "https://8.8.8.8/a"),
        ("https://[2606:4700:4700::1111]/a", "https://[2606:4700:4700::1111]/a"),
        ("https://rezepte.example/käse", "https://rezepte.example/k%C3%A4se"),
    ],
)
def test_accepts_public_web_addresses(text: str, expected: str) -> None:
    assert str(check_url(text)) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "ftp://recipes.example/a",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "data:text/html,hi",
        "gopher://recipes.example",
        "https://",
        "https:///a",
        "https://user:secret@recipes.example/a",
        "https://user@recipes.example/a",
        "https://recipes example/a",
        "https://recipes.example/a b",
        "https://recipes.example/\nHost: evil",
        "https://recipes.example:abc/",
        "https://" + "a" * MAX_SOURCE,
        None,
        123,
    ],
)
def test_rejects_addresses_that_are_not_usable(text: Any) -> None:
    with pytest.raises(InvalidUrlError) as error:
        check_url(text)
    assert error.value.code == "invalid_url"


@pytest.mark.parametrize(
    "text",
    [
        "http://127.0.0.1/",
        "http://127.0.0.1:8123/api",
        "http://10.0.0.5/",
        "http://192.168.1.1/admin",
        "http://172.16.0.1/",
        "http://169.254.169.254/latest/meta-data/",
        "http://0.0.0.0/",
        "http://100.64.0.1/",
        "http://[::1]/",
        "http://[fe80::1]/",
        "http://[fd00::1]/",
        "http://[::ffff:10.0.0.1]/",
        "http://[::ffff:7f00:1]/",
        "http://[64:ff9b::a00:1]/",
        "https://recipes.example:8123/",
        "https://recipes.example:22/",
        "http://recipes.example:8080/",
        "https://8.8.8.8:6379/",
    ],
)
def test_refuses_addresses_inside_the_network_and_odd_ports(text: str) -> None:
    with pytest.raises(BlockedUrlError) as error:
        check_url(text)
    assert error.value.code == "blocked_url"


# -- host names are checked when they are resolved


class FakeResolver:
    def __init__(self, hosts: list[str]) -> None:
        self.hosts = hosts

    async def resolve(self, host: str, port: int = 0, family: int = 0) -> list[dict]:
        return [
            {
                "hostname": host,
                "host": address,
                "port": port,
                "family": socket.AF_INET,
                "proto": 0,
                "flags": 0,
            }
            for address in self.hosts
        ]

    async def close(self) -> None:
        return None


def resolver_for(*hosts: str) -> SafeResolver:
    resolver = SafeResolver()
    resolver._resolver = FakeResolver(list(hosts))
    return resolver


async def test_a_name_with_public_addresses_is_resolved() -> None:
    results = await resolver_for("93.184.216.34", "8.8.8.8").resolve(
        "recipes.example", 443
    )
    assert [r["host"] for r in results] == ["93.184.216.34", "8.8.8.8"]


@pytest.mark.parametrize(
    "hosts",
    [
        ["127.0.0.1"],
        ["10.0.0.5"],
        ["192.168.1.20"],
        ["169.254.169.254"],
        ["93.184.216.34", "10.0.0.5"],  # one private address is enough to refuse
        ["10.0.0.5", "93.184.216.34"],
        [],
    ],
)
async def test_a_name_that_leads_into_the_network_is_refused(hosts: list[str]) -> None:
    with pytest.raises(BlockedUrlError):
        await resolver_for(*hosts).resolve("rebind.example", 80)


# -- downloads against a local server


def html_page(body: str = PAGE, content_type: str = "text/html") -> Callable[..., Any]:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(text=body, content_type=content_type)

    return handler


async def test_loads_a_page(make_site: Callable[..., Any]) -> None:
    site = await make_site({"/recipe": html_page()})

    text, url = await fetch_page(site.url("/recipe"))

    assert text == PAGE
    assert url == site.url("/recipe")


async def test_sends_a_plain_request(make_site: Callable[..., Any]) -> None:
    site = await make_site({"/": html_page()})

    await fetch_page(site.url("/"), "de")

    headers = site.requests[0].headers
    assert "HomeAssistant-RecipeLibrary" in headers["User-Agent"]
    assert headers["Accept-Language"] == "de,en;q=0.7"
    assert "text/html" in headers["Accept"]
    assert "Cookie" not in headers
    assert "Authorization" not in headers


@pytest.mark.parametrize(
    "language", ["", "de\r\nX-Evil: 1", "x" * 40, "de;q=1, *", None]
)
async def test_a_strange_language_is_not_sent(
    make_site: Callable[..., Any], language: str | None
) -> None:
    site = await make_site({"/": html_page()})

    await fetch_page(site.url("/"), language)

    assert "Accept-Language" not in site.requests[0].headers


async def test_cookies_are_not_kept(make_site: Callable[..., Any]) -> None:
    async def sets_cookie(request: web.Request) -> web.Response:
        response = web.Response(text=PAGE, content_type="text/html")
        response.set_cookie("session", "secret")
        return response

    site = await make_site({"/first": sets_cookie, "/second": html_page()})
    await fetch_page(site.url("/first"))
    await fetch_page(site.url("/second"))

    assert "Cookie" not in site.requests[1].headers


async def test_follows_redirects_and_reports_the_final_address(
    make_site: Callable[..., Any],
) -> None:
    async def start(request: web.Request) -> web.Response:
        raise web.HTTPFound("/middle")

    async def middle(request: web.Request) -> web.Response:
        raise web.HTTPMovedPermanently("/final?x=1")

    site = await make_site({"/start": start, "/middle": middle, "/final": html_page()})

    _text, url = await fetch_page(site.url("/start"))

    assert url == site.url("/final?x=1")


async def test_an_endless_redirect_is_stopped(make_site: Callable[..., Any]) -> None:
    async def loop(request: web.Request) -> web.Response:
        raise web.HTTPFound("/loop")

    site = await make_site({"/loop": loop})

    with pytest.raises(FetchError):
        await fetch_page(site.url("/loop"))
    assert len(site.requests) == fetch_module.MAX_REDIRECTS + 1


@pytest.mark.parametrize(
    "target",
    [
        "http://10.0.0.5/admin",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://127.0.0.1:8123/api/",
        "https://recipes.example:8123/",
    ],
)
async def test_a_redirect_into_the_network_is_refused(
    make_site: Callable[..., Any], target: str
) -> None:
    async def redirect(request: web.Request) -> web.Response:
        raise web.HTTPFound(target)

    site = await make_site({"/go": redirect})

    with pytest.raises(BlockedUrlError):
        await fetch_page(site.url("/go"))
    assert len(site.requests) == 1


async def test_a_redirect_to_another_kind_of_address_is_refused(
    make_site: Callable[..., Any],
) -> None:
    async def redirect(request: web.Request) -> web.Response:
        raise web.HTTPFound("ftp://files.example/recipe")

    site = await make_site({"/go": redirect})

    with pytest.raises(InvalidUrlError):
        await fetch_page(site.url("/go"))


async def test_a_redirect_without_target_is_an_error(
    make_site: Callable[..., Any],
) -> None:
    async def broken(request: web.Request) -> web.Response:
        return web.Response(status=302)

    site = await make_site({"/go": broken})

    with pytest.raises(FetchError):
        await fetch_page(site.url("/go"))


async def test_local_addresses_are_refused_for_real(
    monkeypatch: pytest.MonkeyPatch, socket_enabled: None
) -> None:
    """Without the test helper, the server on this machine must be unreachable.

    The refusal must not be turned into a connection error by the HTTP
    library, for numbers and for names alike, and nothing may arrive.
    """
    hits: list[str] = []

    async def handler(request: web.Request) -> web.Response:
        hits.append(request.path)
        return web.Response(text=PAGE, content_type="text/html")

    app = web.Application()
    app.router.add_get("/", handler)
    server = TestServer(app)
    await server.start_server()
    monkeypatch.setattr(fetch_module, "ALLOWED_PORTS", (80, 443, server.port))
    try:
        for host in ("127.0.0.1", "localhost"):
            with pytest.raises(BlockedUrlError):
                await fetch_page(f"http://{host}:{server.port}/")
        # Some resolvers cannot resolve a name with a trailing dot at all.
        with pytest.raises((BlockedUrlError, FetchError)):
            await fetch_page(f"http://localhost.:{server.port}/")
    finally:
        await server.close()
    assert hits == []


@pytest.mark.parametrize("status", [403, 404, 410, 500, 503])
async def test_an_error_answer_is_a_fetch_error(
    make_site: Callable[..., Any], status: int
) -> None:
    async def fail(request: web.Request) -> web.Response:
        return web.Response(status=status, text="no")

    site = await make_site({"/": fail})

    with pytest.raises(FetchError) as error:
        await fetch_page(site.url("/"))
    assert error.value.code == "fetch_failed"


async def test_a_server_that_does_not_exist_is_a_fetch_error(
    make_site: Callable[..., Any],
) -> None:
    site = await make_site({"/": html_page()})
    port = site.server.port
    await site.server.close()

    with pytest.raises(FetchError):
        await fetch_page(f"http://127.0.0.1:{port}/")


async def test_a_slow_server_is_given_up_on(
    make_site: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    async def slow(request: web.Request) -> web.Response:
        await asyncio.sleep(5)
        return web.Response(text=PAGE, content_type="text/html")

    site = await make_site({"/": slow})
    monkeypatch.setattr(fetch_module, "TIMEOUT", 0.2)

    with pytest.raises(FetchError):
        await fetch_page(site.url("/"))


async def test_a_large_page_is_refused_by_its_announced_size(
    make_site: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    site = await make_site({"/": html_page("x" * 5000)})
    monkeypatch.setattr(fetch_module, "MAX_PAGE_BYTES", 1000)

    with pytest.raises(PageTooLargeError) as error:
        await fetch_page(site.url("/"))
    assert error.value.code == "page_too_large"


async def test_a_large_page_without_announced_size_is_cut_off(
    make_site: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    sent = 0

    async def endless(request: web.Request) -> web.StreamResponse:
        nonlocal sent
        response = web.StreamResponse(headers={"Content-Type": "text/html"})
        await response.prepare(request)
        try:
            for _ in range(10000):
                await response.write(b"x" * 1024)
                sent += 1024
        except ConnectionResetError:
            pass
        return response

    site = await make_site({"/": endless})
    monkeypatch.setattr(fetch_module, "MAX_PAGE_BYTES", 100 * 1024)

    with pytest.raises(PageTooLargeError):
        await fetch_page(site.url("/"))
    assert sent < 10000 * 1024


@pytest.mark.parametrize(
    "content_type", ["application/json", "image/png", "text/plain", "application/pdf"]
)
async def test_something_that_is_no_web_page_is_refused(
    make_site: Callable[..., Any], content_type: str
) -> None:
    site = await make_site({"/": html_page("{}", content_type)})

    with pytest.raises(NotHtmlError) as error:
        await fetch_page(site.url("/"))
    assert error.value.code == "not_html"


async def test_xhtml_is_a_web_page(make_site: Callable[..., Any]) -> None:
    site = await make_site({"/": html_page(PAGE, "application/xhtml+xml")})
    assert (await fetch_page(site.url("/")))[0] == PAGE


async def test_compressed_pages_are_read(make_site: Callable[..., Any]) -> None:
    async def gzipped(request: web.Request) -> web.Response:
        response = web.Response(text=PAGE * 50, content_type="text/html")
        response.enable_compression()
        return response

    site = await make_site({"/": gzipped})

    text, _url = await fetch_page(site.url("/"))

    assert text == PAGE * 50
    assert "gzip" in site.requests[0].headers["Accept-Encoding"]
    assert "br" not in site.requests[0].headers["Accept-Encoding"]


# -- pictures


def image_handler(data: bytes, content_type: str = "image/jpeg") -> Callable[..., Any]:
    async def handler(request: web.Request) -> web.Response:
        return web.Response(body=data, content_type=content_type)

    return handler


async def test_loads_a_picture(make_site: Callable[..., Any]) -> None:
    site = await make_site({"/p.jpg": image_handler(JPEG)})

    data, extension = await fetch_image(site.url("/p.jpg"))

    assert (data, extension) == (JPEG, "jpg")
    assert "image/jpeg" in site.requests[0].headers["Accept"]


async def test_a_picture_is_asked_for_with_the_origin_of_its_page(
    make_site: Callable[..., Any],
) -> None:
    site = await make_site({"/p.jpg": image_handler(JPEG)})

    await fetch_image(site.url("/p.jpg"), referer=site.url("/recipes/1?token=secret"))

    assert site.requests[0].headers["Referer"] == site.url("/")


@pytest.mark.parametrize("referer", [None, "", "not a web address", "ftp://x.example/"])
async def test_no_referer_without_a_usable_page_address(
    make_site: Callable[..., Any], referer: str | None
) -> None:
    site = await make_site({"/p.jpg": image_handler(JPEG)})

    await fetch_image(site.url("/p.jpg"), referer=referer)

    assert "Referer" not in site.requests[0].headers


@pytest.mark.parametrize(
    ("address", "expected"),
    [
        ("https://www.example.com/a/b?c=1#d", "https://www.example.com/"),
        ("http://example.com:80/x", "http://example.com/"),
        ("https://example.com:443/x", "https://example.com/"),
        ("http://127.0.0.1:8123/p", "http://127.0.0.1:8123/"),
        ("https://user:secret@example.com/x", "https://example.com/"),
        ("https://b\u00fccher.example/x", "https://xn--bcher-kva.example/"),
        ("ftp://example.com/", None),
        ("javascript:alert(1)", None),
        ("/relative", None),
        ("", None),
        (None, None),
    ],
)
def test_origin_for_the_referer(address: str | None, expected: str | None) -> None:
    assert _origin(address) == expected


async def test_the_picture_type_is_judged_by_content_not_by_header(
    make_site: Callable[..., Any],
) -> None:
    html_as_image = image_handler(
        b"<html><script>alert(1)</script></html>", "image/jpeg"
    )
    site = await make_site(
        {"/fake.jpg": html_as_image, "/real": image_handler(JPEG, "text/plain")}
    )

    with pytest.raises(FetchError):
        await fetch_image(site.url("/fake.jpg"))
    assert (await fetch_image(site.url("/real")))[1] == "jpg"


async def test_pictures_of_other_formats_are_refused(
    make_site: Callable[..., Any],
) -> None:
    site = await make_site(
        {"/a.gif": image_handler(b"GIF89a" + b"0" * 50, "image/gif")}
    )
    with pytest.raises(FetchError):
        await fetch_image(site.url("/a.gif"))


async def test_a_large_picture_is_refused(
    make_site: Callable[..., Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    site = await make_site({"/big.jpg": image_handler(JPEG + b"0" * 5000)})
    monkeypatch.setattr(fetch_module, "MAX_IMAGE_BYTES", 1000)

    with pytest.raises(PageTooLargeError):
        await fetch_image(site.url("/big.jpg"))


async def test_a_picture_address_in_the_network_is_refused() -> None:
    with pytest.raises(BlockedUrlError):
        await fetch_image("http://192.168.0.10/camera.jpg")


# -- character sets


@pytest.mark.parametrize(
    ("body", "charset", "expected"),
    [
        ("Käse & Brötchen".encode(), None, "Käse & Brötchen"),
        ("Käse".encode("latin-1"), "iso-8859-1", "Käse"),
        ("Käse".encode("windows-1252"), "windows-1252", "Käse"),
        (
            b'<meta charset="iso-8859-1">K\xe4se',
            None,
            '<meta charset="iso-8859-1">Käse',
        ),
        (HTTP_EQUIV.encode() + b"K\xe4se", None, HTTP_EQUIV + "Käse"),
        ("Käse".encode(), "no-such-charset", "Käse"),
        ("Käse".encode(), "rot13", "Käse"),
        (b"K\xe4se", None, "K�se"),  # not UTF-8 and nothing declared
        (b"", None, ""),
    ],
)
def test_decode_html(body: bytes, charset: str | None, expected: str) -> None:
    assert decode_html(body, charset) == expected
