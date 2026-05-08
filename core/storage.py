import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx

from core.processor import IMAGE_EXTENSIONS

METADATA_TEMPLATE = """> **源链接:** {source_url}
> **作者:** {author}
> **发布日期:** {publish_date}
> **分析时间:** {analyzed_at}
"""

MIME_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/bmp": ".bmp",
    "image/svg+xml": ".svg",
}


def _sanitize_dirname(name: str) -> str:
    safe = re.sub(r'[<>:"/\\|?*\n\r\t]', "_", name)
    safe = safe.strip().strip(".").strip()
    return safe[:60] or "article"


def _guess_extension(content_type: str, url: str) -> str:
    ct_lower = content_type.lower()
    for mime, ext in MIME_TO_EXT.items():
        if mime in ct_lower:
            return ext
    parsed = urlparse(url)
    path = parsed.path.lower()
    for ext in IMAGE_EXTENSIONS:
        if path.endswith(ext):
            return ext
    return ".jpg"


class Storage:

    def __init__(self, output_dir: Path):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._http = httpx.AsyncClient(timeout=30.0, follow_redirects=True)

    async def save(
        self,
        url: str,
        *,
        title: str = "",
        summary: str = "",
        content: str = "",
        metadata: Optional[Dict[str, str]] = None,
        image_anchors: Optional[List[Tuple[str, str]]] = None,
        video_urls: Optional[List[str]] = None,
    ) -> Path:
        short_hash = hashlib.md5(url.encode("utf-8")).hexdigest()[:8]
        safe_title = _sanitize_dirname(title)
        article_dir = self._output_dir / f"{safe_title}_{short_hash}"
        article_dir.mkdir(parents=True, exist_ok=True)

        image_anchors = image_anchors or []
        if image_anchors:
            image_dir = article_dir / "images"
            image_dir.mkdir(exist_ok=True)
            for anchor_id, img_url in image_anchors:
                local_path = await self._download_image(img_url, image_dir, anchor_id)
                if local_path:
                    rel_path = f"images/{local_path.name}"
                    content = re.sub(
                        rf"!\[{re.escape(anchor_id)}\]\([^)]+\)",
                        f"![{anchor_id}]({rel_path})",
                        content,
                        count=1,
                    )

        video_urls = video_urls or []
        if video_urls:
            content += "\n\n---\n\n## 视频\n\n"
            for i, vurl in enumerate(video_urls, 1):
                content += f"- [视频 {i}]({vurl})\n"

        meta = metadata or {}
        meta_str = METADATA_TEMPLATE.format(
            source_url=meta.get("source_url", url),
            author=meta.get("author", "N/A"),
            publish_date=meta.get("publish_date", "N/A"),
            analyzed_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        )

        file_content = (
            f"# {title}\n\n"
            f"---\n\n"
            f"## AI 摘要\n\n{summary}\n\n"
            f"---\n\n"
            f"## 原文内容\n\n{content}\n\n"
            f"---\n\n"
            f"## 元数据\n\n{meta_str}\n"
        )
        filepath = article_dir / "index.md"
        filepath.write_text(file_content, encoding="utf-8")
        return filepath

    async def _download_image(
        self, url: str, dest_dir: Path, anchor_id: str
    ) -> Optional[Path]:
        headers = {"Referer": "https://mp.weixin.qq.com/"}
        try:
            resp = await self._http.get(url, headers=headers)
            resp.raise_for_status()
            ext = _guess_extension(resp.headers.get("content-type", ""), url)
            filename = f"{anchor_id}{ext}"
            filepath = dest_dir / filename
            filepath.write_bytes(resp.content)
            return filepath
        except Exception:
            return None

    async def close(self):
        await self._http.aclose()
