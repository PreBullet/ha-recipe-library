"""Photo files of recipes.

Pure Python without Home Assistant imports. The card shrinks the photo in the
browser (which also removes EXIF data such as the location) and uploads it;
this module checks and stores it.
"""

from __future__ import annotations

import base64
import binascii
import os
import time
from pathlib import Path
from uuid import uuid4

from .library import IMAGE_NAME_RE, InvalidDataError, LibraryError

# Decoded size limit. The card sends far less (about 100 to 300 KB), the limit
# only protects against misuse. The WebSocket message limit is 4 MB.
MAX_IMAGE_BYTES = 2 * 1024 * 1024

CONTENT_TYPES = {"jpg": "image/jpeg", "png": "image/png", "webp": "image/webp"}

_TMP_PREFIX = ".tmp-"


class ImageTooLargeError(LibraryError):
    """The uploaded photo is larger than the limit."""

    code = "image_too_large"


def detect_image_type(data: bytes) -> str | None:
    """Return the file extension for a supported image format, else None."""
    if data.startswith(b"\xff\xd8\xff"):
        return "jpg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp"
    return None


def decode_upload(encoded: str) -> tuple[bytes, str]:
    """Decode a base64 upload and return ``(bytes, extension)``.

    Raises InvalidDataError for broken or unsupported data and
    ImageTooLargeError above the size limit.
    """
    if len(encoded) > MAX_IMAGE_BYTES * 4 // 3 + 16:
        raise ImageTooLargeError("image is too large")
    try:
        data = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as err:
        raise InvalidDataError("image data is not valid") from err
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageTooLargeError("image is too large")
    extension = detect_image_type(data)
    if extension is None:
        raise InvalidDataError("image format is not supported (use JPEG, PNG or WebP)")
    return data, extension


class ImageStore:
    """Photo files in one directory, named by random id."""

    def __init__(self, directory: Path) -> None:
        """Use ``directory``; it is created when the first photo is saved."""
        self._dir = directory

    def path(self, name: str) -> Path | None:
        """Return the file path for a valid name, otherwise None (never escapes)."""
        if not isinstance(name, str) or not IMAGE_NAME_RE.match(name):
            return None
        return self._dir / name

    def exists(self, name: str) -> bool:
        """Return whether the photo exists."""
        path = self.path(name)
        return path is not None and path.is_file()

    def save(self, data: bytes, extension: str) -> str:
        """Store a photo and return its file name."""
        if extension not in CONTENT_TYPES:
            raise InvalidDataError("image format is not supported")
        self._dir.mkdir(parents=True, exist_ok=True)
        name = f"{uuid4().hex}.{extension}"
        target = self._dir / name
        temp = self._dir / f"{_TMP_PREFIX}{name}"
        temp.write_bytes(data)
        os.replace(temp, target)
        return name

    def delete(self, name: str) -> None:
        """Delete a photo, if it exists."""
        path = self.path(name)
        if path is not None:
            path.unlink(missing_ok=True)

    def cleanup(self, keep: set[str], min_age: float) -> int:
        """Delete photos that are not in ``keep`` and older than ``min_age`` seconds.

        The age limit protects photos that were just uploaded but whose recipe
        is not saved yet. Returns the number of deleted files.
        """
        if not self._dir.is_dir():
            return 0
        limit = time.time() - min_age
        deleted = 0
        for entry in self._dir.iterdir():
            is_photo = IMAGE_NAME_RE.match(entry.name) and entry.name not in keep
            is_stale_temp = entry.name.startswith(_TMP_PREFIX)
            if not (is_photo or is_stale_temp) or not entry.is_file():
                continue
            if entry.stat().st_mtime < limit:
                entry.unlink(missing_ok=True)
                deleted += 1
        return deleted
