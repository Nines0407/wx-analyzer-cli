import asyncio
import base64
import random
from typing import Dict, List, Optional

import httpx
from openai import AsyncOpenAI
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
)

from core.config import Config
from core.processor import ImageItem

SYSTEM_SUMMARY_PROMPT = (
    "你是一个专业的技术文章摘要助手。请用中文对以下微信公众号文章进行摘要，"
    "突出核心技术要点、关键信息与结论。控制在 300 字以内，以段落形式输出。"
)

IMAGE_ANALYSIS_PROMPT = (
    "请结合提供的上下文分析此图片的内容与技术含义。"
    "用中文简要描述图片中的关键信息，并说明其与上下文的关系。"
)


class AIEngine:

    def __init__(
        self,
        api_key: str,
        api_base: str | None = None,
        config: Config | None = None,
        semaphore: asyncio.Semaphore | None = None,
    ):
        base = api_base or "https://api.deepseek.com/v1"
        self._config = config or Config(api_key=api_key, api_base=base)
        self._client = AsyncOpenAI(api_key=api_key, base_url=base)
        self._semaphore = semaphore or asyncio.Semaphore(5)
        self._http = httpx.AsyncClient(timeout=30.0)

    async def summarize(self, markdown_content: str) -> str:
        truncated = markdown_content[:12000]
        messages = [
            {"role": "system", "content": SYSTEM_SUMMARY_PROMPT},
            {"role": "user", "content": truncated},
        ]
        return await self._call_with_retry(messages, self._config.text_model)

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
        image_data = await self._download_image(item.url)
        if not image_data:
            return "⚠️ 图片下载失败，无法分析"

        mime = _detect_mime_type(image_data)
        b64 = base64.b64encode(image_data).decode("utf-8")
        data_url = f"data:{mime};base64,{b64}"

        prompt = f"{IMAGE_ANALYSIS_PROMPT}\n\n上下文 ({len(item.context)} 字符):\n{item.context}"

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            },
        ]
        return await self._call_with_retry(messages, self._config.vision_model)

    async def _call_with_retry(
        self, messages: list, model: str, max_retries: int | None = None
    ) -> str:
        retries = max_retries if max_retries is not None else self._config.max_retries
        for attempt in range(retries):
            try:
                response = await self._client.chat.completions.create(
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
        try:
            resp = await self._http.get(url, follow_redirects=True)
            resp.raise_for_status()
            return resp.content
        except Exception:
            return None

    async def close(self):
        await self._http.aclose()
        await self._client.close()


def _detect_mime_type(data: bytes) -> str:
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return "image/gif"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"
