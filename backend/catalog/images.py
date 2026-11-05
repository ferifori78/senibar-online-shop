"""Shrinking uploaded photographs to something a web page can serve.

A phone or camera photograph is routinely 15-25 MB and 6000px wide. Stored as
uploaded, every product page would push that down the wire — slow on a phone,
and expensive on an Iranian mobile connection. The roaster uploads the good
file; this makes the version the site serves.

Kept out of the serializer so the rule is in one readable place, and so the
one case that must not be touched — an image that is already small enough —
is obvious.
"""

import io
import logging

from django.conf import settings
from django.core.files.uploadedfile import InMemoryUploadedFile

logger = logging.getLogger("senobar.catalog")

# Wider than any layout uses, with room for a retina display and for cropping.
MAX_WIDTH = 2400
MAX_HEIGHT = 2400

# Visually indistinguishable from 95 at roughly half the bytes.
JPEG_QUALITY = 85


def shrink(upload):
    """Return `upload` resized and recompressed, or unchanged if it is fine.

    Never raises: a file Pillow cannot read is passed through untouched and
    validated by the serializer's ImageField as before. Refusing the upload
    here would turn "we could not optimise this" into "you cannot add a
    photograph", which is much worse.
    """
    if not getattr(settings, "IMAGE_SHRINK_ENABLED", True):
        return upload

    try:
        from PIL import Image, ImageOps
    except ImportError:  # pragma: no cover - Pillow is a hard requirement
        logger.warning("Pillow not available; storing %s as uploaded", upload.name)
        return upload

    try:
        upload.seek(0)
        image = Image.open(upload)
        image.load()
    except Exception as exc:
        logger.info("Not a readable image, storing as uploaded (%s): %s", upload.name, exc)
        upload.seek(0)
        return upload

    # A photograph carries its rotation in EXIF rather than in the pixels.
    # Dropping that tag without applying it — which saving does — would turn
    # every portrait photo on its side.
    try:
        image = ImageOps.exif_transpose(image)
    except Exception:
        pass

    keep_alpha = image.mode in ("RGBA", "LA", "P")
    fits = image.width <= MAX_WIDTH and image.height <= MAX_HEIGHT
    small = upload.size <= 1_500_000

    # Already web-sized: leave it exactly as the roaster made it. Re-encoding
    # a small file only loses quality.
    if fits and small:
        upload.seek(0)
        return upload

    if not fits:
        image.thumbnail((MAX_WIDTH, MAX_HEIGHT), Image.LANCZOS)

    # PNG for anything with transparency, JPEG otherwise: a photograph saved
    # as PNG is several times larger for no visible gain.
    if keep_alpha:
        image = image.convert("RGBA")
        fmt, params, ext, content_type = "PNG", {"optimize": True}, ".png", "image/png"
    else:
        image = image.convert("RGB")
        fmt = "JPEG"
        params = {"quality": JPEG_QUALITY, "optimize": True, "progressive": True}
        ext, content_type = ".jpg", "image/jpeg"

    buffer = io.BytesIO()
    try:
        image.save(buffer, format=fmt, **params)
    except Exception as exc:
        logger.warning("Could not re-encode %s, storing as uploaded: %s", upload.name, exc)
        upload.seek(0)
        return upload

    size = buffer.tell()

    # If the re-encode came out bigger, the original was already better.
    if size >= upload.size:
        upload.seek(0)
        return upload

    buffer.seek(0)
    stem = (upload.name or "image").rsplit(".", 1)[0][:80]
    logger.info(
        "Shrank %s: %.1fMB -> %.1fMB (%dx%d)",
        upload.name, upload.size / 1e6, size / 1e6, image.width, image.height,
    )

    return InMemoryUploadedFile(
        buffer, "ImageField", f"{stem}{ext}", content_type, size, None
    )
