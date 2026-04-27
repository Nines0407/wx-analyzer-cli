import os
from dataclasses import dataclass


@dataclass
class Config:
    api_key: str = ""
    api_base: str = "https://api.deepseek.com/v1"
    text_model: str = "deepseekv4flash"
    vision_model: str = "deepseek-vl2"
    max_retries: int = 3
    request_timeout: float = 60.0
    user_agent: str = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/16.0 Mobile/15E148 Safari/604.1"
    )


def load_config() -> Config:
    return Config(
        api_key=os.getenv("DEEPSEEK_API_KEY", ""),
        api_base=os.getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"),
        text_model=os.getenv("DEEPSEEK_TEXT_MODEL", "deepseekv4flash"),
        vision_model=os.getenv("DEEPSEEK_VISION_MODEL", "deepseek-vl2"),
    )
