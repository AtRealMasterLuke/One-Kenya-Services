"""
Upload handling for report photos.

Phone cameras embed GPS coordinates, device serial numbers and timestamps in EXIF. A photo
of a burst pipe outside someone's gate should not publish where they live to every officer
and log that touches it, so every upload is decoded and re-encoded from pixels only. That
also neutralises files that only pretend to be images (polyglots), and shrinks the photo for
staff viewing it on mobile data.
"""

import io

from django.core.exceptions import ValidationError
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import Photo

MAX_UPLOAD_BYTES = 4 * 1024 * 1024  # Vercel rejects request bodies over 4.5 MB
MAX_PIXELS = 40_000_000  # refuse decompression bombs before decoding
MAX_EDGE = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def process_upload(uploaded):
    """Validate an uploaded file and return an unsaved Photo with EXIF-free JPEG data."""
    if uploaded.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Photos must be 4 MB or smaller.")
    raw = uploaded.read()
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            fmt = probe.format
            if fmt not in ALLOWED_FORMATS:
                raise ValidationError("Upload a JPEG, PNG or WebP photo.")
            if probe.width * probe.height > MAX_PIXELS:
                raise ValidationError("That image is too large.")
            probe.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image)  # keep the photo the right way up once EXIF is gone
            image = image.convert("RGB")
            image.thumbnail((MAX_EDGE, MAX_EDGE))
            out = io.BytesIO()
            # A fresh JPEG written from pixel data: no EXIF, XMP, ICC or comment blocks.
            image.save(out, format="JPEG", quality=82, optimize=True)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValidationError("That file is not a photo we can read.") from exc
    return Photo(data=out.getvalue(), content_type="image/jpeg", width=image.width, height=image.height)
