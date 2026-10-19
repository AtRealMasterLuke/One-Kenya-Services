import io

import pytest
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from requests_app.photos import MAX_UPLOAD_BYTES, process_upload

GPS_IFD = 0x8825


def jpeg_with_gps(size=(800, 600), orientation=None):
    img = Image.new("RGB", size, (200, 30, 30))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[0x0110] = "Model X"  # Model
    exif[GPS_IFD] = {1: "S", 2: (0.0, 43.0, 15.6), 3: "E", 4: (37.0, 9.0, 1.2)}  # Murang'a town
    if orientation:
        exif[0x0112] = orientation
    out = io.BytesIO()
    img.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def upload(data, name="photo.jpg", content_type="image/jpeg"):
    return SimpleUploadedFile(name, data, content_type=content_type)


def test_fixture_really_has_gps():
    with Image.open(io.BytesIO(jpeg_with_gps())) as img:
        assert img.getexif().get_ifd(GPS_IFD)


def test_gps_and_device_exif_are_removed():
    photo = process_upload(upload(jpeg_with_gps()))
    with Image.open(io.BytesIO(photo.data)) as img:
        exif = img.getexif()
        assert not exif.get_ifd(GPS_IFD)
        assert 0x010F not in exif and 0x0110 not in exif
        assert "exif" not in img.info and "icc_profile" not in img.info
    assert b"PhoneMaker" not in photo.data


def test_orientation_is_applied_before_exif_is_dropped():
    # Orientation 6 = rotate 90° clockwise; without applying it the photo would end up sideways.
    photo = process_upload(upload(jpeg_with_gps(size=(800, 600), orientation=6)))
    assert (photo.width, photo.height) == (600, 800)


def test_large_photos_are_shrunk_for_mobile_data():
    photo = process_upload(upload(jpeg_with_gps(size=(4000, 3000))))
    assert max(photo.width, photo.height) == 1600


@pytest.mark.parametrize("make", [
    lambda: (b"%PDF-1.4 not an image", "doc.jpg"),
    lambda: (b"<script>alert(1)</script>", "x.jpg"),
])
def test_non_images_are_refused(make):
    data, name = make()
    with pytest.raises(ValidationError):
        process_upload(upload(data, name))


def test_gif_is_refused():
    out = io.BytesIO()
    Image.new("RGB", (10, 10)).save(out, format="GIF")
    with pytest.raises(ValidationError, match="JPEG, PNG or WebP"):
        process_upload(upload(out.getvalue(), "x.gif", "image/gif"))


def test_too_big_is_refused():
    with pytest.raises(ValidationError, match="4 MB"):
        process_upload(upload(b"\xff" * (MAX_UPLOAD_BYTES + 1)))


def test_polyglot_payload_does_not_survive():
    """A valid JPEG with a script appended: the re-encoded file contains only pixel data."""
    data = jpeg_with_gps() + b"<?php system($_GET['c']); ?>"
    photo = process_upload(upload(data))
    assert b"<?php" not in photo.data
