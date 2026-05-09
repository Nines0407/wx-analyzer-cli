import tempfile
from pathlib import Path
from unittest.mock import AsyncMock

from core.storage import (
    Storage,
    _sanitize_dirname,
    _guess_extension,
    METADATA_TEMPLATE,
    MIME_TO_EXT,
)


class TestSanitizeDirname:
    def test_keeps_valid_chars(self):
        assert _sanitize_dirname("Hello_World") == "Hello_World"

    def test_strips_leading_trailing_dots(self):
        assert _sanitize_dirname("...test...") == "test"

    def test_replaces_bad_chars(self):
        name = 'name<b>ad"chars:?test*end'
        result = _sanitize_dirname(name)
        for ch in '<>:"/\\|?*':
            assert ch not in result

    def test_truncates_long_names(self):
        long_name = "a" * 80
        result = _sanitize_dirname(long_name)
        assert len(result) <= 60

    def test_empty_name_returns_article(self):
        assert _sanitize_dirname("") == "article"

    def test_only_bad_chars_returns_underscores(self):
        assert _sanitize_dirname("<>?*") == "____"

    def test_newlines_and_tabs_replaced(self):
        result = _sanitize_dirname("line1\nline2\tspace")
        assert "\n" not in result
        assert "\t" not in result

    def test_emoji_preserved(self):
        result = _sanitize_dirname("hello")
        assert result == "hello"


class TestGuessExtension:
    def test_from_content_type_jpeg(self):
        assert _guess_extension("image/jpeg", "https://x.com/photo") == ".jpg"

    def test_from_content_type_png(self):
        assert _guess_extension("image/png", "https://x.com/img") == ".png"

    def test_from_content_type_webp(self):
        assert _guess_extension("image/webp", "https://x.com/img") == ".webp"

    def test_fallbacks_to_url_extension(self):
        assert _guess_extension("application/octet-stream", "https://x.com/photo.JPG") == ".jpg"

    def test_fallback_with_no_info(self):
        assert _guess_extension("text/html", "https://x.com/unknown") == ".jpg"

    def test_content_type_case_insensitive(self):
        assert _guess_extension("IMAGE/PNG", "https://x.com/x") == ".png"

    def test_svg_content_type(self):
        assert _guess_extension("image/svg+xml", "https://x.com/icon") == ".svg"


class TestMetadataTemplate:
    def test_formats_correctly(self):
        result = METADATA_TEMPLATE.format(
            source_url="https://mp.weixin.qq.com/s/test",
            author="TestAuthor",
            publish_date="2024-01-01",
            analyzed_at="2026-05-09 10:00 UTC",
        )
        assert "https://mp.weixin.qq.com/s/test" in result
        assert "TestAuthor" in result
        assert "2024-01-01" in result
        assert "2026-05-09 10:00 UTC" in result


class TestMimeToExt:
    def test_all_mappings(self):
        assert MIME_TO_EXT["image/jpeg"] == ".jpg"
        assert MIME_TO_EXT["image/png"] == ".png"
        assert MIME_TO_EXT["image/gif"] == ".gif"
        assert MIME_TO_EXT["image/webp"] == ".webp"
        assert MIME_TO_EXT["image/bmp"] == ".bmp"
        assert MIME_TO_EXT["image/svg+xml"] == ".svg"


class TestStorageInit:
    def test_creates_output_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out = Path(tmpdir) / "my_output"
            Storage(output_dir=out)
            assert out.exists()
            assert out.is_dir()

    def test_closes_http_client(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            s = Storage(output_dir=Path(tmpdir) / "out")
            import asyncio
            asyncio.run(s.close())


class TestStorageSave:
    def test_save_creates_article_directory(self):
        import asyncio

        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                out = Path(tmpdir) / "out"
                s = Storage(output_dir=out)
                article_dir = await s.save(
                    "https://mp.weixin.qq.com/s/TESTURL",
                    title="Test Article",
                    summary="AI generated summary",
                    content="# Title\n\nContent here.",
                    metadata={"source_url": "https://mp.weixin.qq.com/s/TESTURL", "author": "Author", "publish_date": "2024-01-01"},
                )
                assert article_dir.exists()
                assert (article_dir / "summary.md").exists()
                assert (article_dir / "article.md").exists()

                summary_text = (article_dir / "summary.md").read_text(encoding="utf-8")
                assert "Test Article" in summary_text
                assert "AI generated summary" in summary_text

                article_text = (article_dir / "article.md").read_text(encoding="utf-8")
                assert "# Title" in article_text
                assert "Content here" in article_text

                await s.close()

        asyncio.run(_run())

    def test_save_with_video_urls(self):
        import asyncio

        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                out = Path(tmpdir) / "out"
                s = Storage(output_dir=out)
                article_dir = await s.save(
                    "https://mp.weixin.qq.com/s/TESTVID",
                    title="Video Article",
                    content="Content",
                    video_urls=["https://example.com/video1.mp4"],
                )
                article_text = (article_dir / "article.md").read_text(encoding="utf-8")
                assert "视频" in article_text
                assert "https://example.com/video1.mp4" in article_text
                await s.close()

        asyncio.run(_run())

    def test_save_with_downloaded_images_mocked(self):
        import asyncio

        async def _run():
            with tempfile.TemporaryDirectory() as tmpdir:
                out = Path(tmpdir) / "out"
                s = Storage(output_dir=out)

                mock_download = AsyncMock(return_value=None)
                s._download_image = mock_download

                article_dir = await s.save(
                    "https://mp.weixin.qq.com/s/TESTIMG",
                    title="Image Article",
                    content="![img_0](https://mmbiz.qpic.cn/a.png)",
                    image_anchors=[("img_0", "https://mmbiz.qpic.cn/a.png")],
                )
                assert (article_dir / "images").exists()
                mock_download.assert_called_once()
                await s.close()

        asyncio.run(_run())
