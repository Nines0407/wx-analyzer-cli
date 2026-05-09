import io as io_module
import struct

from PIL import Image

from core.ai_engine import _detect_mime_type, _normalize_image


def _make_png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    )


def _make_jpeg_bytes() -> bytes:
    return b"\xff\xd8\xff\xe0" + b"\x00" * 100


def _make_gif_bytes() -> bytes:
    return b"GIF89a" + b"\x00" * 100


def _make_webp_header() -> bytes:
    return b"RIFF" + struct.pack("<I", 100) + b"WEBP" + b"\x00" * 100


class TestDetectMimeType:
    def test_png_from_signature(self):
        assert _detect_mime_type(_make_png_bytes()) == "image/png"

    def test_jpeg_from_signature(self):
        assert _detect_mime_type(_make_jpeg_bytes()) == "image/jpeg"

    def test_gif87a(self):
        assert _detect_mime_type(b"GIF87a" + b"\x00" * 10) == "image/gif"

    def test_gif89a(self):
        assert _detect_mime_type(b"GIF89a" + b"\x00" * 10) == "image/gif"

    def test_webp_from_signature(self):
        data = _make_webp_header()
        assert _detect_mime_type(data) == "image/webp"

    def test_unknown_returns_empty(self):
        assert _detect_mime_type(b"UNKNOWN_DATA") == ""

    def test_empty_data(self):
        assert _detect_mime_type(b"") == ""

    def test_data_too_short(self):
        assert _detect_mime_type(b"\xff") == ""


class TestNormalizeImage:
    def test_png_passes_through(self):
        data = _make_png_bytes()
        result = _normalize_image(data)
        assert result is data

    def test_jpeg_converts_to_png(self):
        buf = io_module.BytesIO()
        Image.new("RGB", (5, 5), color="green").save(buf, format="JPEG")
        data = buf.getvalue()
        result = _normalize_image(data)
        assert _detect_mime_type(result) == "image/png"

    def test_gif_converts_to_png(self):
        buf = io_module.BytesIO()
        Image.new("RGB", (5, 5), color="blue").save(buf, format="GIF")
        data = buf.getvalue()
        result = _normalize_image(data)
        assert _detect_mime_type(result) == "image/png"

    def test_webp_converts_to_png(self):
        buf = io_module.BytesIO()
        Image.new("RGB", (5, 5), color="yellow").save(buf, format="WEBP")
        data = buf.getvalue()
        result = _normalize_image(data)
        assert _detect_mime_type(result) == "image/png"

    def test_empty_data_returns_unchanged(self):
        assert _normalize_image(b"") == b""

    def test_invalid_data_returns_unchanged(self):
        data = b"not an image at all"
        result = _normalize_image(data)
        assert result == data

    def test_real_jpeg(self):
        buf = io_module.BytesIO()
        img = Image.new("RGB", (10, 10), color="red")
        img.save(buf, format="JPEG")
        jpeg_data = buf.getvalue()
        assert _detect_mime_type(jpeg_data) == "image/jpeg"
        result = _normalize_image(jpeg_data)
        assert _detect_mime_type(result) == "image/png"

    def test_real_png_unchanged(self):
        buf = io_module.BytesIO()
        img = Image.new("RGB", (10, 10), color="blue")
        img.save(buf, format="PNG")
        png_data = buf.getvalue()
        assert _detect_mime_type(png_data) == "image/png"
        result = _normalize_image(png_data)
        assert result == png_data
