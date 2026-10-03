"""Images in a bulk email: ``POST /bulk-email/images`` and ``apps.bulk_email.images``.

An upload is checked for its type by content and for its size, scaled to fit an
email, stored as ``bulk-email/<uuid>.<ext>`` under ``MEDIA_ROOT``, and answered with
the absolute URL every copy links to.  Only CalDART management may upload.
"""

from __future__ import annotations

import io
import re
import struct
import time
from typing import TYPE_CHECKING

import pytest
from django.conf import settings as django_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image, ImageSequence
from pytest_django import Settings
from rest_framework.test import APIClient

from apps.accounts.roles import MANAGEMENT, SYSTEM_ADMIN
from apps.bulk_email import images
from apps.bulk_email.images import MAX_FRAMES, TOO_MANY_PIXELS_MESSAGE, WRONG_TYPE_MESSAGE
from apps.bulk_email.models import BulkEmailImage
from tests.conftest import role_matrix

if TYPE_CHECKING:
    from apps.accounts.models import User

pytestmark = pytest.mark.django_db

IMAGES_URL = "/api/v1/bulk-email/images"

#: The EXIF tag that says which way up a photo was taken.
EXIF_ORIENTATION = 0x0112

#: The orientation value for a photo the camera held turned a quarter clockwise.
ROTATED_QUARTER = 6

#: Where a stored image lives, under ``MEDIA_ROOT``.
STORED_NAME = re.compile(r"bulk-email/[0-9a-f]{32}\.(png|jpg|gif|webp)")


def picture(image_format: str = "PNG", size: tuple[int, int] = (300, 200), **save: object) -> bytes:
    """Return a solid-colored image of ``size`` encoded as ``image_format``."""
    mode = "RGB" if image_format == "JPEG" else "RGBA"
    buffer = io.BytesIO()
    Image.new(mode, size, (30, 90, 160, 255)[: len(mode)]).save(buffer, format=image_format, **save)
    return buffer.getvalue()


def animated_gif(size: tuple[int, int], frames: int = 3) -> bytes:
    """Return an animated GIF of ``frames`` frames of ``size``, each another color."""
    pictures = [Image.new("RGB", size, (60 * n, 40, 200)) for n in range(frames)]
    buffer = io.BytesIO()
    pictures[0].save(
        buffer, format="GIF", save_all=True, append_images=pictures[1:], duration=200, loop=0
    )
    return buffer.getvalue()


def tiny_frame_gif(canvas: tuple[int, int], frames: int) -> bytes:
    """Return a GIF built by hand: a ``canvas`` and ``frames`` frames of one pixel each.

    The file stays a few kilobytes however large the canvas, which is what makes it
    dangerous: every frame Pillow decodes is the whole canvas.
    """
    width, height = canvas
    header = b"GIF89a" + struct.pack("<HHBBB", width, height, 0x80, 0, 0)
    palette = b"\x00\x00\x00\xff\xff\xff"
    frame = (
        b"\x21\xf9\x04\x00\x0a\x00\x00\x00"  # graphic control: 0.1 s
        + b"\x2c"
        + struct.pack("<HHHHB", 0, 0, 1, 1, 0)  # one pixel at the top left
        + b"\x02\x02\x44\x01\x00"  # its LZW data
    )
    return header + palette + frame * frames + b"\x3b"


def upload(content: bytes, name: str = "photo.png") -> SimpleUploadedFile:
    """Return ``content`` as an uploaded file called ``name``."""
    return SimpleUploadedFile(name, content, content_type="application/octet-stream")


def stored(image: BulkEmailImage) -> Image.Image:
    """Return the stored file of ``image``, opened."""
    with image.file.open("rb") as handle:
        opened = Image.open(io.BytesIO(handle.read()))
        opened.load()
        return opened


@pytest.fixture
def management_client(api_client: APIClient, management: User) -> APIClient:
    """A DRF client signed in as CalDART management."""
    api_client.force_login(management)
    return api_client


@pytest.fixture
def site(settings: Settings) -> None:
    """Serve the site from ``https://caldart.example.org`` with no URL prefix."""
    settings.SITE_URL = "https://caldart.example.org"
    settings.MEDIA_URL = "/media/"


# --------------------------------------------------------------------------
# Who may upload
# --------------------------------------------------------------------------
@pytest.mark.parametrize(("role", "allowed"), role_matrix(MANAGEMENT, SYSTEM_ADMIN))
def test_only_management_uploads_images(
    api_client: APIClient, all_role_users: dict[str, User], role: str, allowed: bool
) -> None:
    """``POST /bulk-email/images`` is for CalDART management and system administrators."""
    api_client.force_login(all_role_users[role])
    response = api_client.post(IMAGES_URL, {"image": upload(picture())}, format="multipart")
    assert response.status_code == (201 if allowed else 403)


def test_an_anonymous_caller_cannot_upload(api_client: APIClient) -> None:
    """A caller who is not signed in is a 401, and nothing is stored."""
    response = api_client.post(IMAGES_URL, {"image": upload(picture())}, format="multipart")
    assert response.status_code == 401


def test_a_refused_caller_stores_nothing(api_client: APIClient, member: User) -> None:
    """A 403 leaves no image behind."""
    api_client.force_login(member)
    api_client.post(IMAGES_URL, {"image": upload(picture())}, format="multipart")
    assert BulkEmailImage.objects.count() == 0


# --------------------------------------------------------------------------
# What the upload answers and stores
# --------------------------------------------------------------------------
@pytest.mark.usefixtures("site")
def test_an_upload_answers_its_id_absolute_url_and_size(management_client: APIClient) -> None:
    """201 with the stored row's id, its absolute URL on ``SITE_URL``, and its size."""
    response = management_client.post(
        IMAGES_URL, {"image": upload(picture(size=(300, 200)))}, format="multipart"
    )
    image = BulkEmailImage.objects.get()
    assert response.json() == {
        "id": image.pk,
        "url": f"https://caldart.example.org/media/{image.file.name}",
        "width": 300,
        "height": 200,
    }


def test_the_url_carries_the_url_prefix(management_client: APIClient, settings: Settings) -> None:
    """A site under a prefix answers the URL with the prefix, once."""
    settings.SITE_URL = "https://example.org/caldart"
    settings.MEDIA_URL = "/caldart/media/"
    response = management_client.post(IMAGES_URL, {"image": upload(picture())}, format="multipart")
    name = BulkEmailImage.objects.get().file.name
    assert response.json()["url"] == f"https://example.org/caldart/media/{name}"


def test_the_uploader_is_recorded(management_client: APIClient, management: User) -> None:
    """The stored row names the account that uploaded it."""
    management_client.post(IMAGES_URL, {"image": upload(picture())}, format="multipart")
    assert BulkEmailImage.objects.get().uploaded_by == management


@pytest.mark.parametrize(
    ("image_format", "extension"),
    [("PNG", "png"), ("JPEG", "jpg"), ("GIF", "gif"), ("WEBP", "webp")],
)
def test_each_accepted_type_is_stored_under_a_random_name(
    management_client: APIClient, image_format: str, extension: str
) -> None:
    """PNG, JPEG, GIF, and WebP are kept as ``bulk-email/<uuid>.<ext>``."""
    management_client.post(
        IMAGES_URL, {"image": upload(picture(image_format), "x.bin")}, format="multipart"
    )
    name = str(BulkEmailImage.objects.get().file.name)
    assert STORED_NAME.fullmatch(name) is not None
    assert name.endswith(f".{extension}")


@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "GIF", "WEBP"])
def test_each_accepted_type_keeps_its_format(
    management_client: APIClient, image_format: str
) -> None:
    """The stored file is the same kind of image as the upload."""
    management_client.post(IMAGES_URL, {"image": upload(picture(image_format))}, format="multipart")
    assert stored(BulkEmailImage.objects.get()).format == image_format


def test_two_uploads_never_share_a_name(management_client: APIClient) -> None:
    """Each upload gets a fresh name, so none replaces an image already sent."""
    for _ in range(2):
        management_client.post(IMAGES_URL, {"image": upload(picture())}, format="multipart")
    names = {image.file.name for image in BulkEmailImage.objects.all()}
    assert len(names) == 2


# --------------------------------------------------------------------------
# Type
# --------------------------------------------------------------------------
@pytest.mark.parametrize(
    ("content", "name"),
    [
        (b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", "logo.svg"),
        (b"%PDF-1.4 not an image", "flyer.png"),
        (b"plain text", "notes.jpg"),
        (picture("BMP"), "old.bmp"),
        (picture("TIFF"), "scan.tiff"),
    ],
    ids=["svg", "pdf-named-png", "text-named-jpg", "bmp", "tiff"],
)
def test_anything_but_png_jpeg_gif_or_webp_is_refused(
    management_client: APIClient, content: bytes, name: str
) -> None:
    """A file that is not an accepted image by its content is a 400 under ``image``."""
    response = management_client.post(
        IMAGES_URL, {"image": upload(content, name)}, format="multipart"
    )
    assert (response.status_code, response.json()) == (400, {"image": [WRONG_TYPE_MESSAGE]})


def test_a_png_named_as_text_is_accepted(management_client: APIClient) -> None:
    """The type is read from the content, not the file name."""
    response = management_client.post(
        IMAGES_URL, {"image": upload(picture(), "notes.txt")}, format="multipart"
    )
    assert response.status_code == 201


def test_a_truncated_image_is_refused(management_client: APIClient) -> None:
    """A PNG cut short fails once its pixels are read, and is refused as not an image."""
    content = picture(size=(400, 400))[:200]
    response = management_client.post(IMAGES_URL, {"image": upload(content)}, format="multipart")
    assert (response.status_code, response.json()) == (400, {"image": [WRONG_TYPE_MESSAGE]})


def test_a_missing_file_is_refused(management_client: APIClient) -> None:
    """A body with no ``image`` is DRF's own message."""
    response = management_client.post(IMAGES_URL, {}, format="multipart")
    assert (response.status_code, response.json()) == (
        400,
        {"image": ["No file was submitted."]},
    )


def test_a_json_body_is_refused(management_client: APIClient) -> None:
    """The upload takes multipart form data only."""
    response = management_client.post(IMAGES_URL, {"image": "x"}, format="json")
    assert response.status_code == 415


# --------------------------------------------------------------------------
# Size
# --------------------------------------------------------------------------
def test_a_file_over_the_limit_is_refused(management_client: APIClient, settings: Settings) -> None:
    """A file longer than ``BULK_EMAIL_IMAGE_MAX_BYTES`` is a 400 naming the limit."""
    settings.BULK_EMAIL_IMAGE_MAX_BYTES = 1024 * 1024
    content = picture("PNG", (10, 10)) + b"\0" * (1024 * 1024)
    response = management_client.post(IMAGES_URL, {"image": upload(content)}, format="multipart")
    assert (response.status_code, response.json()) == (
        400,
        {"image": ["This image is larger than 1 MB. Choose a smaller one."]},
    )


def test_a_file_at_the_limit_is_accepted(management_client: APIClient, settings: Settings) -> None:
    """A file exactly ``BULK_EMAIL_IMAGE_MAX_BYTES`` long is accepted."""
    content = picture()
    settings.BULK_EMAIL_IMAGE_MAX_BYTES = len(content)
    response = management_client.post(IMAGES_URL, {"image": upload(content)}, format="multipart")
    assert response.status_code == 201


def test_the_default_limit_is_five_megabytes() -> None:
    """Out of the box, ``BULK_EMAIL_IMAGE_MAX_BYTES`` is 5 MB."""
    assert django_settings.BULK_EMAIL_IMAGE_MAX_BYTES == 5 * 1024 * 1024


def test_the_default_limit_is_named_in_megabytes() -> None:
    """The refusal for the default limit names 5 MB."""
    assert images.too_large_message(django_settings.BULK_EMAIL_IMAGE_MAX_BYTES) == (
        "This image is larger than 5 MB. Choose a smaller one."
    )


def test_an_image_with_too_many_pixels_is_refused(
    management_client: APIClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A small file that unpacks into too many pixels is refused before it is read."""
    monkeypatch.setattr(images, "MAX_PIXELS", 300 * 200 - 1)
    response = management_client.post(
        IMAGES_URL, {"image": upload(picture(size=(300, 200)))}, format="multipart"
    )
    assert (response.status_code, response.json()) == (
        400,
        {"image": [TOO_MANY_PIXELS_MESSAGE]},
    )


# --------------------------------------------------------------------------
# Scaling
# --------------------------------------------------------------------------
@pytest.mark.parametrize("image_format", ["PNG", "JPEG", "WEBP"])
def test_a_wide_image_is_scaled_to_the_limit(
    management_client: APIClient, image_format: str
) -> None:
    """An image wider than 1200 pixels is stored 1200 wide, its proportions kept."""
    response = management_client.post(
        IMAGES_URL, {"image": upload(picture(image_format, (2400, 600)))}, format="multipart"
    )
    image = BulkEmailImage.objects.get()
    assert (response.json()["width"], response.json()["height"]) == (1200, 300)
    assert stored(image).size == (1200, 300)


def test_the_width_limit_is_a_setting(management_client: APIClient, settings: Settings) -> None:
    """``BULK_EMAIL_IMAGE_MAX_WIDTH`` sets the widest image stored."""
    settings.BULK_EMAIL_IMAGE_MAX_WIDTH = 600
    management_client.post(
        IMAGES_URL, {"image": upload(picture(size=(900, 300)))}, format="multipart"
    )
    assert stored(BulkEmailImage.objects.get()).size == (600, 200)


def test_an_image_within_the_limit_keeps_its_size(management_client: APIClient) -> None:
    """An image 1200 pixels wide or narrower is stored at its own size."""
    management_client.post(
        IMAGES_URL, {"image": upload(picture(size=(1200, 50)))}, format="multipart"
    )
    assert stored(BulkEmailImage.objects.get()).size == (1200, 50)


def test_an_animated_gif_keeps_every_frame_when_scaled(management_client: APIClient) -> None:
    """A wide animated GIF is scaled frame by frame, and still animates."""
    management_client.post(
        IMAGES_URL, {"image": upload(animated_gif((1600, 400)), "wave.gif")}, format="multipart"
    )
    image = stored(BulkEmailImage.objects.get())
    frames = sum(1 for _ in ImageSequence.Iterator(image))
    assert (image.size, frames) == ((1200, 300), 3)


def test_a_sideways_photo_is_turned_upright(management_client: APIClient) -> None:
    """A JPEG whose orientation tag says it was turned is stored upright, tag dropped."""
    exif = Image.Exif()
    exif[EXIF_ORIENTATION] = ROTATED_QUARTER
    content = picture("JPEG", (400, 200), exif=exif.tobytes())
    management_client.post(IMAGES_URL, {"image": upload(content)}, format="multipart")
    image = stored(BulkEmailImage.objects.get())
    assert (image.size, image.getexif().get(EXIF_ORIENTATION)) == ((200, 400), None)


def test_a_cmyk_jpeg_is_stored_as_rgb(management_client: APIClient) -> None:
    """A CMYK JPEG, which some mail programs cannot show, is stored as RGB."""
    buffer = io.BytesIO()
    Image.new("CMYK", (100, 100), (0, 50, 100, 0)).save(buffer, format="JPEG")
    management_client.post(IMAGES_URL, {"image": upload(buffer.getvalue())}, format="multipart")
    assert stored(BulkEmailImage.objects.get()).mode == "RGB"


@pytest.mark.parametrize(
    ("canvas", "frames"),
    [((6000, 6000), 200), ((2000, 2000), 11), ((10, 10), MAX_FRAMES + 1)],
    ids=["large-canvas-many-frames", "frames-times-canvas-over-the-cap", "too-many-frames"],
)
def test_an_animation_with_too_many_pixels_or_frames_is_refused_before_decoding(
    management_client: APIClient, canvas: tuple[int, int], frames: int
) -> None:
    """A small GIF of many tiny frames on a large canvas is refused, at once."""
    content = tiny_frame_gif(canvas, frames)
    started = time.monotonic()
    response = management_client.post(
        IMAGES_URL, {"image": upload(content, "spin.gif")}, format="multipart"
    )
    assert (response.status_code, response.json()) == (
        400,
        {"image": [TOO_MANY_PIXELS_MESSAGE]},
    )
    assert time.monotonic() - started < 5


def test_an_animation_within_the_caps_is_accepted(management_client: APIClient) -> None:
    """The hand-built GIF itself is a valid image when its canvas and frames are small."""
    response = management_client.post(
        IMAGES_URL, {"image": upload(tiny_frame_gif((100, 100), 5), "spin.gif")}, format="multipart"
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    "canvas",
    [(10_000, 10_000), (20_000, 20_000)],
    ids=["pillow-would-warn", "pillow-refuses"],
)
def test_a_canvas_pillow_calls_a_bomb_is_too_big(
    management_client: APIClient, canvas: tuple[int, int]
) -> None:
    """Past Pillow's own decompression-bomb limits, the refusal is the "too big" one."""
    response = management_client.post(
        IMAGES_URL, {"image": upload(tiny_frame_gif(canvas, 1), "huge.gif")}, format="multipart"
    )
    assert (response.status_code, response.json()) == (
        400,
        {"image": [TOO_MANY_PIXELS_MESSAGE]},
    )


@pytest.mark.parametrize("image_format", ["JPEG", "GIF"])
def test_a_comment_does_not_survive(management_client: APIClient, image_format: str) -> None:
    """The comment an image carries is not written back into the stored file."""
    content = picture(image_format, comment=b"taken at 37.7N 122.4W")
    management_client.post(IMAGES_URL, {"image": upload(content)}, format="multipart")
    assert "comment" not in stored(BulkEmailImage.objects.get()).info


def test_the_exif_block_does_not_survive(management_client: APIClient) -> None:
    """A photo's EXIF block, where a camera writes the location, is not stored."""
    exif = Image.Exif()
    exif[0x010F] = "Cessna camera"  # Make
    management_client.post(
        IMAGES_URL, {"image": upload(picture("JPEG", exif=exif.tobytes()))}, format="multipart"
    )
    assert "exif" not in stored(BulkEmailImage.objects.get()).info
