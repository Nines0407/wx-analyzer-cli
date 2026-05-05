import os
import platform
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv


def _setup_env_file() -> None:
    project_root = Path(__file__).resolve().parent.parent
    env_path = project_root / ".env"
    if not env_path.exists():
        example_path = project_root / ".env.example"
        if example_path.exists():
            env_path.write_text(example_path.read_text(encoding="utf-8"), encoding="utf-8")
    if env_path.exists():
        load_dotenv(env_path)


_setup_env_file()


def _default_playwright_args() -> List[str]:
    if platform.system() == "Linux":
        return [
            "--no-sandbox",
            "--disable-gpu",
            "--disable-dev-shm-usage",
            "--disable-setuid-sandbox",
        ]
    return []


DEFAULT_SUMMARY_PROMPT = (
    "你是一个专业的技术文章摘要助手。请用中文对以下微信公众号文章进行摘要，"
    "突出核心技术要点、关键信息与结论。控制在 300 字以内，以段落形式输出。"
)

DEFAULT_IMAGE_ANALYSIS_PROMPT = (
    "请结合提供的上下文分析此图片的内容与技术含义。"
    "用中文简要描述图片中的关键信息，并说明其与上下文的关系。"
)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/16.0 Mobile/15E148 Safari/604.1"
)


def _getenv(key: str, fallback: str = "") -> str:
    return os.getenv(key, fallback)


def _getenv_float(key: str, fallback: float) -> float:
    val = os.getenv(key)
    if val is not None:
        try:
            return float(val)
        except ValueError:
            pass
    return fallback


def _getenv_int(key: str, fallback: int) -> int:
    val = os.getenv(key)
    if val is not None:
        try:
            return int(val)
        except ValueError:
            pass
    return fallback


@dataclass
class Config:
    # ── API 配置 ──
    api_key: str = ""
    api_base: str = "https://api.deepseek.com/v1"
    text_model: str = "deepseek-v4-flash"
    vision_model: str = "deepseek-vl2"

    # ── 请求配置 ──
    max_retries: int = 3
    request_timeout: float = 60.0

    # ── Prompt 配置 ──
    summary_prompt: str = DEFAULT_SUMMARY_PROMPT
    image_analysis_prompt: str = DEFAULT_IMAGE_ANALYSIS_PROMPT

    # ── 浏览器配置 ──
    user_agent: str = DEFAULT_USER_AGENT
    playwright_launch_args: List[str] = field(default_factory=_default_playwright_args)


def load_config() -> Config:
    return Config(
        api_key=_getenv("API_KEY") or _getenv("DEEPSEEK_API_KEY"),
        api_base=_getenv("API_BASE") or _getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"),
        text_model=_getenv("TEXT_MODEL") or _getenv("DEEPSEEK_TEXT_MODEL", "deepseek-v4-flash"),
        vision_model=_getenv("VISION_MODEL") or _getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl2"),
        max_retries=_getenv_int("MAX_RETRIES", 3),
        request_timeout=_getenv_float("REQUEST_TIMEOUT", 60.0),
        summary_prompt=_getenv("SUMMARY_PROMPT") or DEFAULT_SUMMARY_PROMPT,
        image_analysis_prompt=_getenv("IMAGE_ANALYSIS_PROMPT") or DEFAULT_IMAGE_ANALYSIS_PROMPT,
        user_agent=_getenv("USER_AGENT") or DEFAULT_USER_AGENT,
    )
