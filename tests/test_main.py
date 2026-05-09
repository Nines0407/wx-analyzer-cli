import tempfile
from pathlib import Path

from main import _read_urls


class TestReadUrls:
    def test_reads_urls_from_file(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("https://mp.weixin.qq.com/s/abc\nhttps://mp.weixin.qq.com/s/def\n")
            f.flush()
            path = Path(f.name)
        try:
            urls = _read_urls(path)
            assert len(urls) == 2
            assert urls[0] == "https://mp.weixin.qq.com/s/abc"
            assert urls[1] == "https://mp.weixin.qq.com/s/def"
        finally:
            path.unlink()

    def test_skips_empty_lines(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("https://example.com/1\n\n\nhttps://example.com/2\n")
            f.flush()
            path = Path(f.name)
        try:
            urls = _read_urls(path)
            assert len(urls) == 2
        finally:
            path.unlink()

    def test_skips_comment_lines(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("# This is a comment\nhttps://example.com/1\n# Another comment\n")
            f.flush()
            path = Path(f.name)
        try:
            urls = _read_urls(path)
            assert len(urls) == 1
            assert urls[0] == "https://example.com/1"
        finally:
            path.unlink()

    def test_strips_whitespace(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("  https://example.com/1  \n")
            f.flush()
            path = Path(f.name)
        try:
            urls = _read_urls(path)
            assert urls[0] == "https://example.com/1"
        finally:
            path.unlink()

    def test_empty_file_returns_empty_list(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("")
            f.flush()
            path = Path(f.name)
        try:
            urls = _read_urls(path)
            assert urls == []
        finally:
            path.unlink()

    def test_all_comments_returns_empty(self):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        ) as f:
            f.write("# comment 1\n# comment 2\n")
            f.flush()
            path = Path(f.name)
        try:
            urls = _read_urls(path)
            assert urls == []
        finally:
            path.unlink()
