"""The images a sender puts into a bulk email: checked, scaled, and stored.

An email links to each image by its absolute URL rather than carrying it, so a send
to hundreds of people stays small.  :func:`store` checks an upload's type by its
content and its size, scales it to fit an email, and keeps it under ``MEDIA_ROOT``
in ``bulk-email/``, which the web server serves to anybody, signed in or not: a
mail program fetching the image carries no session.  :func:`image_url` is the
address every copy uses.
"""

from __future__ import annotations

import io
import logging
import warnings
from dataclasses import dataclass
from urllib.parse import urljoin

from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps, ImageSequence, UnidentifiedImageError

from apps.accounts.models import User
from apps.bulk_email.models import BulkEmailImage

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class ImageFormat:
    """One image format a bulk email accepts: its file extension and save options."""

    extension: str
    save_options: dict[str, object]


#: The formats an upload may be, by Pillow's name for each, read from the content.
FORMATS: dict[str, ImageFormat] = {
    "PNG": ImageFormat("png", {"optimize": True}),
    "JPEG": ImageFormat("jpg", {"quality": 85, "optimize": True}),
    "GIF": ImageFormat("gif", {}),
    "WEBP": ImageFormat("webp", {"quality": 85}),
}

#: The most pixels an upload may hold across all its frames, whatever its file
#: size: a small file can unpack into an enormous picture, or into hundreds of
#: frames on a large canvas, and scaling one would exhaust the server.
MAX_PIXELS = 40_000_000

#: The most frames an animated upload may hold.
MAX_FRAMES = 200

#: What a saved image may not carry from the upload: a comment, the camera's EXIF
#: block (a photo's location among it), XMP, and an embedded color profile.
METADATA_KEYS = ("comment", "exif", "xmp", "icc_profile")

#: Why an upload that is not an accepted image is refused.
WRONG_TYPE_MESSAGE = "Choose a PNG, JPEG, GIF, or WebP image."

#: Why an upload with too many pixels or frames is refused.
TOO_MANY_PIXELS_MESSAGE = "This image is too big to use in an email. Choose a smaller one."

#: The JPEG modes saved as they are; any other mode, such as CMYK, is saved as RGB.
_JPEG_MODES = frozenset({"RGB", "L"})


class ImageRefusedError(Exception):
    """An upload :func:`store` will not keep; the message says why, for the sender."""


def too_large_message(max_bytes: int) -> str:
    """Return why a file over ``max_bytes`` is refused, naming the limit in MB."""
    megabytes = max_bytes / (1024 * 1024)
    return f"This image is larger than {megabytes:g} MB. Choose a smaller one."


def store(upload: UploadedFile[bytes], *, actor: User) -> BulkEmailImage:
    """Check, scale, and keep one uploaded image; return the stored row.

    The upload must be at most ``BULK_EMAIL_IMAGE_MAX_BYTES`` long and be a PNG,
    JPEG, GIF, or WebP image by its content, whatever its name says, holding at most
    :data:`MAX_FRAMES` frames and :data:`MAX_PIXELS` pixels across all of them (the
    canvas times the frame count), checked before any pixel is decoded; anything
    else raises :class:`ImageRefusedError` with the reason in words.  An image wider
    than ``BULK_EMAIL_IMAGE_MAX_WIDTH`` is scaled down to that width, keeping its
    proportions; an animated one keeps every frame.  A photo is turned upright by
    its orientation tag.  Every image is saved afresh in its own format without its
    comment, EXIF, XMP, or color profile (:data:`METADATA_KEYS`; a photo's location
    among them), as ``bulk-email/<uuid>.<ext>`` under ``MEDIA_ROOT``.  ``actor`` is
    recorded as the uploader.
    """
    max_bytes = settings.BULK_EMAIL_IMAGE_MAX_BYTES
    if upload.size is None or upload.size > max_bytes:
        raise ImageRefusedError(too_large_message(max_bytes))
    data, image_format, width, height = _processed(upload.read())
    image = BulkEmailImage(uploaded_by=actor, width=width, height=height)
    image.file.save(f"image.{image_format.extension}", ContentFile(data), save=False)
    image.save()
    log.info("Stored bulk email image %s (%dx%d)", image.pk, width, height)
    return image


def image_url(image: BulkEmailImage) -> str:
    """Return the absolute address of ``image``'s file, on ``SITE_URL``'s host.

    ``MEDIA_URL`` already carries any ``URL_PREFIX``, so the path is joined to the
    site's scheme and host alone: ``https://caldart.example.org/media/bulk-email/
    <uuid>.png``.
    """
    site_url: str = settings.SITE_URL
    return urljoin(site_url, image.file.url)


def _processed(content: bytes) -> tuple[bytes, ImageFormat, int, int]:
    """Return ``content`` as stored: the bytes, the format, and the width and height.

    Raises :class:`ImageRefusedError` for content that is not an accepted image or
    holds too many pixels or frames.
    """
    source = _opened(content)
    if source.format not in FORMATS:
        raise ImageRefusedError(WRONG_TYPE_MESSAGE)
    image_format = FORMATS[source.format]
    # Counting a GIF's frames reads their headers alone, never their pixels.
    frame_count: int = getattr(source, "n_frames", 1)
    if frame_count > MAX_FRAMES or source.width * source.height * frame_count > MAX_PIXELS:
        raise ImageRefusedError(TOO_MANY_PIXELS_MESSAGE)
    try:
        frames = _scaled_frames(source)
    except OSError as exc:
        # A truncated or corrupt file fails only once its pixels are read.
        raise ImageRefusedError(WRONG_TYPE_MESSAGE) from exc
    first = frames[0]
    buffer = io.BytesIO()
    options = dict(image_format.save_options)
    if len(frames) > 1:
        options.update(
            save_all=True,
            append_images=frames[1:],
            loop=source.info.get("loop", 0),
            duration=[frame.info.get("duration", 100) for frame in frames],
        )
    first.save(buffer, format=source.format, **options)
    return buffer.getvalue(), image_format, first.width, first.height


def _opened(content: bytes) -> Image.Image:
    """Return ``content`` opened by Pillow, its header read and no pixel decoded.

    Raises :class:`ImageRefusedError` with :data:`WRONG_TYPE_MESSAGE` for content
    Pillow cannot identify, and with :data:`TOO_MANY_PIXELS_MESSAGE` for a canvas
    Pillow itself judges a decompression bomb, whether it would only warn (over
    about 89 million pixels) or refuse (over about 179 million).  Either is far
    past :data:`MAX_PIXELS`, so the warning is raised as an error here rather than
    left to reach the log.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            return Image.open(io.BytesIO(content))
        except UnidentifiedImageError as exc:
            raise ImageRefusedError(WRONG_TYPE_MESSAGE) from exc
        except (Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
            raise ImageRefusedError(TOO_MANY_PIXELS_MESSAGE) from exc


def _scaled_frames(source: Image.Image) -> list[Image.Image]:
    """Return every frame of ``source``, upright and no wider than the limit.

    A still image is one frame.  A JPEG not in RGB or grayscale, such as a CMYK
    one, is converted to RGB, which every mail program shows.  Each frame loses
    the metadata in :data:`METADATA_KEYS`, which Pillow would otherwise write back.
    """
    max_width = settings.BULK_EMAIL_IMAGE_MAX_WIDTH
    frames: list[Image.Image] = []
    for frame in ImageSequence.Iterator(source):
        upright = ImageOps.exif_transpose(frame)
        if upright.width > max_width:
            height = max(1, round(upright.height * max_width / upright.width))
            scaled = upright.resize((max_width, height), Image.Resampling.LANCZOS)
            scaled.info = dict(frame.info)
            upright = scaled
        if source.format == "JPEG" and upright.mode not in _JPEG_MODES:
            upright = upright.convert("RGB")
        for key in METADATA_KEYS:
            upright.info.pop(key, None)
        frames.append(upright)
    return frames
