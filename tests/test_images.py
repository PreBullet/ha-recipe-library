"""Tests for the photo checks and the photo file store."""

import base64
import os
import time

import pytest

from custom_components.recipe_library import images
from custom_components.recipe_library.images import (
    ImageStore,
    ImageTooLargeError,
    decode_upload,
    detect_image_type,
)
from custom_components.recipe_library.library import InvalidDataError

JPEG = b"\xff\xd8\xff\xe0" + b"jpeg-data" * 10
PNG = b"\x89PNG\r\n\x1a\n" + b"png-data" * 10
WEBP = b"RIFF\x24\x00\x00\x00WEBPVP8 " + b"webp-data" * 10


def b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (JPEG, "jpg"),
        (PNG, "png"),
        (WEBP, "webp"),
        (b"GIF89a....", None),
        (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", None),
        (b"<html><script>alert(1)</script>", None),
        (b"RIFF\x00\x00\x00\x00WAVEfmt ", None),
        (b"", None),
    ],
)
def test_detect_image_type(data, expected):
    assert detect_image_type(data) == expected


def test_decode_upload_accepts_supported_images():
    for data, extension in ((JPEG, "jpg"), (PNG, "png"), (WEBP, "webp")):
        assert decode_upload(b64(data)) == (data, extension)


@pytest.mark.parametrize("encoded", ["not base64!!", "abc", "####"])
def test_decode_upload_rejects_broken_base64(encoded):
    with pytest.raises(InvalidDataError):
        decode_upload(encoded)


def test_decode_upload_rejects_unsupported_formats():
    with pytest.raises(InvalidDataError):
        decode_upload(b64(b"<svg></svg>"))


def test_decode_upload_rejects_too_large(monkeypatch):
    monkeypatch.setattr(images, "MAX_IMAGE_BYTES", 100)
    with pytest.raises(ImageTooLargeError) as err:
        decode_upload(b64(JPEG + b"x" * 200))
    assert err.value.code == "image_too_large"
    # Rejected from the length alone, before decoding.
    with pytest.raises(ImageTooLargeError):
        decode_upload("A" * 10_000)


def test_store_save_exists_delete(tmp_path):
    store = ImageStore(tmp_path / "photos")
    name = store.save(JPEG, "jpg")
    assert name.endswith(".jpg") and len(name) == 36
    assert store.exists(name)
    assert store.path(name).read_bytes() == JPEG
    # No temporary file is left behind.
    assert [p.name for p in (tmp_path / "photos").iterdir()] == [name]
    store.delete(name)
    assert not store.exists(name)
    store.delete(name)  # deleting twice is fine


def test_store_rejects_unsupported_extension(tmp_path):
    with pytest.raises(InvalidDataError):
        ImageStore(tmp_path).save(JPEG, "svg")


@pytest.mark.parametrize(
    "name",
    [
        "../secret.jpg",
        "..%2fsecret.jpg",
        "a/b.jpg",
        "/etc/passwd",
        "short.jpg",
        "0" * 32,
        "0" * 32 + ".svg",
        "0" * 32 + ".JPG",
        "G" * 32 + ".jpg",
        "",
        None,
    ],
)
def test_store_never_accepts_unsafe_names(tmp_path, name):
    store = ImageStore(tmp_path)
    assert store.path(name) is None
    assert not store.exists(name)
    store.delete(name)  # must not raise or touch anything


def test_cleanup_deletes_old_unused_files_only(tmp_path):
    store = ImageStore(tmp_path)
    used = store.save(JPEG, "jpg")
    old_unused = store.save(PNG, "png")
    new_unused = store.save(WEBP, "webp")
    stale_temp = tmp_path / f".tmp-{'1' * 32}.jpg"
    stale_temp.write_bytes(b"x")
    foreign = tmp_path / "notes.txt"
    foreign.write_text("keep me")
    old = time.time() - 3 * 86400
    for path in (tmp_path / used, tmp_path / old_unused, stale_temp, foreign):
        os.utime(path, (old, old))

    assert store.cleanup({used}, min_age=86400) == 2

    assert store.exists(used)  # in use
    assert not store.exists(old_unused)  # old and unused
    assert store.exists(new_unused)  # unused but just uploaded
    assert not stale_temp.exists()
    assert foreign.exists()  # not ours, never touched


def test_cleanup_without_directory(tmp_path):
    assert ImageStore(tmp_path / "missing").cleanup(set(), 0) == 0
