import asyncio
import base64
import io as io_module
import logging
import random
from typing import Dict, List, Optional

import httpx
from openai import AsyncOpenAI
from PIL import Image
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from core.config import Config
from core.processor import ImageItem
from core.security import is_safe_url

logger = logging.getLogger(__name__)


class AIEngine:

    def __init__(
        self,
        config: Config,
        semaphore: asyncio.Semaphore | None = None,
    ):
        self._config = config

        text_key = config.text_api_key or config.api_key
        text_base = config.text_api_base or config.api_base or "https://api.deepseek.com/v1"
        vision_key = config.vision_api_key or config.api_key
        vision_base = config.vision_api_base or config.api_base or "https://api.deepseek.com/v1"

        self._text_client = AsyncOpenAI(api_key=text_key, base_url=text_base, max_retries=0)
        self._vision_client = AsyncOpenAI(api_key=vision_key, base_url=vision_base, max_retries=0)
        self._semaphore = semaphore or asyncio.Semaphore(5)
        self._http = httpx.AsyncClient(timeout=30.0)

    async def summarize(self, markdown_content: str) -> str:
        truncated = markdown_content[:12000]
        messages = [
            {"role": "system", "content": self._config.summary_prompt},
            {"role": "user", "content": truncated},
        ]
        try:
            return await self._call_with_retry(
                messages, self._config.text_model, client=self._text_client
            )
        except Exception:
            return "⚠️ AI 摘要生成失败"

    async def analyze_images(self, images: List[ImageItem]) -> Dict[str, str]:
        results: Dict[str, str] = {}

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task("[cyan]分析图片中...", total=len(images))

            async def analyze_one(item: ImageItem):
                async with self._semaphore:
                    analysis = await self._analyze_single_image(item)
                    results[item.anchor_id] = analysis
                    progress.advance(task)

            await asyncio.gather(*[analyze_one(img) for img in images])

        return results

    async def _analyze_single_image(self, item: ImageItem) -> str:
        try:
            return await self._do_analyze_single_image(item)
        except Exception:
            logger.warning("AI vision analysis failed for %s", item.url, exc_info=True)
            return "⚠️ AI 请求失败"

    async def _do_analyze_single_image(self, item: ImageItem) -> str:
        image_data = await self._download_image(item.url)
        if not image_data:
            return "⚠️ 图片下载失败，无法分析"

        image_data = _normalize_image(image_data)
        b64 = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:image/png;base64,{b64}"

        prompt = f"{self._config.image_analysis_prompt}\n\n上下文 ({len(item.context)} 字符):\n{item.context}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": data_url}},
                    {"type": "text", "text": prompt},
                ],
            },
        ]
        return await self._call_with_retry(
            messages, self._config.vision_model, client=self._vision_client
        )

    async def _call_with_retry(
        self,
        messages: list,
        model: str,
        max_retries: int | None = None,
        client: AsyncOpenAI | None = None,
    ) -> str:
        _client = client or self._text_client
        retries = max_retries if max_retries is not None else self._config.max_retries
        for attempt in range(retries):
            try:
                response = await _client.chat.completions.create(
                    model=model,
                    messages=messages,
                    timeout=self._config.request_timeout,
                )
                return response.choices[0].message.content or ""
            except Exception as exc:
                status_code = None
                resp = getattr(exc, "response", None)
                if resp is not None:
                    status_code = getattr(resp, "status_code", None)
                if status_code is None:
                    status_code = getattr(exc, "status_code", None)

                if status_code == 429:
                    wait = (2**attempt) + random.uniform(0, 1)
                    await asyncio.sleep(wait)
                elif attempt < retries - 1:
                    wait = 2**attempt
                    await asyncio.sleep(wait)
                else:
                    raise
        return "⚠️ AI 请求失败"

    async def _download_image(self, url: str) -> Optional[bytes]:
        if not is_safe_url(url):
            return None
        headers = {"Referer": "https://mp.weixin.qq.com/"}
        try:
            resp = await self._http.get(url, follow_redirects=True, headers=headers)
            resp.raise_for_status()
            content_type = resp.headers.get("content-type", "").lower()
            if not any(t in content_type for t in ("image/", "octet-stream")):
                return None
            content = resp.content
            if not _detect_mime_type(content):
                return None
            return content
        except httpx.HTTPError:
            return None
        except Exception:
            logger.warning("Unexpected error downloading image from %s", url, exc_info=True)
            return None

    async def close(self):
        for closer in (self._http.aclose, self._text_client.close, self._vision_client.close):
            try:
                await closer()
            except Exception:
                logger.debug("Error during %s.close()", closer.__self__.__class__.__name__, exc_info=True)


def _detect_mime_type(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return "image/webp"
    return ""


def _normalize_image(data: bytes) -> bytes:
    mime = _detect_mime_type(data)
    if mime in ("image/png", ""):
        return data
    try:
        img = Image.open(io_module.BytesIO(data))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
        else:
            img = img.convert("RGB")
        buf = io_module.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return data
