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


@dataclass
class Config:
    api_key: str = ""
    api_base: str = "https://api.deepseek.com/v1"
    text_model: str = "deepseek-v4-flash"
    vision_model: str = "deepseek-vl2"
    max_retries: int = 3
    request_timeout: float = 60.0
    user_agent: str = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    )
    playwright_launch_args: List[str] = field(default_factory=_default_playwright_args)


def load_config() -> Config:
    return Config(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        api_base=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"),
        text_model=os.getenv("DEEPSEEK_TEXT_MODEL", "deepseek-v4-flash"),
        vision_model=os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl2"),
    )
