import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

METADATA_TEMPLATE = """> **源链接:** {source_url}
> **作者:** {author}
> **发布日期:** {publish_date}
> **分析时间:** {analyzed_at}
"""


class Storage:

    def __init__(self, output_dir: Path):
        self._output_dir = Path(output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)

    def save(
        self,
        url: str,
        *,
        title: str = "",
        summary: str = "",
        content: str = "",
        metadata: Dict[str, str] | None = None,
    ) -> Path:
        url_hash = hashlib.md5(url.encode("utf-8")).hexdigest()
        filepath = self._output_dir / f"{url_hash}.md"

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
        filepath.write_text(file_content, encoding="utf-8")
        return filepath
