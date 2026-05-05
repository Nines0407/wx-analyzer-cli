import re
from dataclasses import dataclass
from typing import Dict, List, Tuple
from urllib.parse import urlparse

import html2text

IMAGE_MD_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
NOISE_PATTERNS = [
    re.compile(r"推荐阅读.*?(?=\n\n|\Z)", re.DOTALL),
    re.compile(r"广告.*?(?=\n\n|\Z)", re.DOTALL),
    re.compile(r"关注我们.*?(?=\n\n|\Z)", re.DOTALL),
    re.compile(r"阅读原文.*?(?=\n\n|\Z)", re.DOTALL),
    re.compile(r"分享到.*?(?=\n\n|\Z)", re.DOTALL),
]
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
VIDEO_ELEMENT_RE = re.compile(
    r"<(?:video\b|iframe\b[^>]*\bvideo|mp-common-videosnap\b)",
    re.IGNORECASE,
)
VIDEO_URL_RE = re.compile(
    r'<(?:iframe|mp-common-videosnap)\b[^>]*(?:data-src|src)="([^"]*)"',
    re.IGNORECASE,
)


@dataclass
class ImageItem:
    anchor_id: str
    url: str
    context: str


class ContentProcessor:

    def __init__(self):
        self._h = html2text.HTML2Text()
        self._h.ignore_links = False
        self._h.ignore_images = False
        self._h.body_width = 0
        self._h.images_to_alt = False
        self._h.protect_links = True

    def clean(self, html: str) -> str:
        for tag in ("script", "style", "iframe", "noscript", "svg"):
            html = re.sub(
                rf"<{tag}[^>]*>.*?</{tag}>",
                "",
                html,
                flags=re.DOTALL | re.IGNORECASE,
            )
        return html

    def html_to_markdown(self, html: str) -> Tuple[str, List[Tuple[str, str]]]:
        markdown = self._h.handle(html)

        image_anchors: List[Tuple[str, str]] = []
        seen_urls: set = set()

        def collect_anchor(match):
            anchor_id = f"img_{len(image_anchors)}"
            url = match.group(2)
            if url and url not in seen_urls and _is_image_url(url):
                seen_urls.add(url)
                image_anchors.append((anchor_id, url))
                return f"![{anchor_id}]({url})"
            return match.group(0)

        markdown = IMAGE_MD_RE.sub(collect_anchor, markdown)

        return markdown, image_anchors

    def extract_images_with_context(
        self, markdown: str, image_anchors: List[Tuple[str, str]]
    ) -> List[ImageItem]:
        items: List[ImageItem] = []
        for anchor_id, url in image_anchors:
            needle = f"![{anchor_id}]({url})"
            idx = markdown.find(needle)
            if idx == -1:
                context = ""
            else:
                start = max(0, idx - 500)
                end = min(len(markdown), idx + len(needle) + 500)
                context = markdown[start:end]
            items.append(ImageItem(anchor_id=anchor_id, url=url, context=context))
        return items

    def embed_analysis(self, markdown: str, analyses: Dict[str, str]) -> str:
        for anchor_id, analysis in analyses.items():
            pattern = re.compile(rf"!\[{re.escape(anchor_id)}\]\([^)]+\)")

            def _replacer(match, _analysis=analysis):
                return f"{match.group(0)}\n\n> **AI 图像分析:** {_analysis}\n"

            markdown = pattern.sub(_replacer, markdown, count=1)
        return markdown

    @staticmethod
    def remove_noise(text: str) -> str:
        for pattern in NOISE_PATTERNS:
            text = pattern.sub("", text)
        return text

    @staticmethod
    def detect_media_from_html(html: str) -> bool:
        if "<img" in html.lower():
            return True
        if VIDEO_ELEMENT_RE.search(html):
            return True
        return False

    @staticmethod
    def extract_video_urls(html: str) -> List[str]:
        urls: List[str] = []
        for m in VIDEO_URL_RE.finditer(html):
            url = m.group(1)
            if url not in urls:
                urls.append(url)
        return urls


def _is_image_url(url: str) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    if any(path.endswith(ext) for ext in IMAGE_EXTENSIONS):
        return True
    if "mmbiz.qpic.cn" in parsed.netloc or "mmbiz.qlogo.cn" in parsed.netloc:
        return True
    return False
