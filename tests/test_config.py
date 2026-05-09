import os
import platform
from unittest.mock import patch

from core.config import (
    Config,
    _getenv,
    _getenv_float,
    _getenv_int,
    _default_playwright_args,
    DEFAULT_SUMMARY_PROMPT,
    DEFAULT_IMAGE_ANALYSIS_PROMPT,
    DEFAULT_USER_AGENT,
)


class TestEnvHelpers:
    def test_getenv_returns_value(self):
        with patch.dict(os.environ, {"FOO": "bar"}, clear=True):
            assert _getenv("FOO") == "bar"

    def test_getenv_returns_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _getenv("MISSING", "default") == "default"

    def test_getenv_returns_empty_string_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _getenv("MISSING") == ""

    def test_getenv_int_valid(self):
        with patch.dict(os.environ, {"COUNT": "5"}, clear=True):
            assert _getenv_int("COUNT", 1) == 5

    def test_getenv_int_invalid_fallback(self):
        with patch.dict(os.environ, {"COUNT": "abc"}, clear=True):
            assert _getenv_int("COUNT", 3) == 3

    def test_getenv_int_missing_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _getenv_int("MISSING", 10) == 10

    def test_getenv_float_valid(self):
        with patch.dict(os.environ, {"TIMEOUT": "30.5"}, clear=True):
            assert _getenv_float("TIMEOUT", 60.0) == 30.5

    def test_getenv_float_invalid_fallback(self):
        with patch.dict(os.environ, {"TIMEOUT": "nope"}, clear=True):
            assert _getenv_float("TIMEOUT", 60.0) == 60.0

    def test_getenv_float_missing_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            assert _getenv_float("MISSING", 10.0) == 10.0


class TestDefaultPlaywrightArgs:
    def test_linux_returns_sandbox_args(self):
        with patch.object(platform, "system", return_value="Linux"):
            args = _default_playwright_args()
            assert "--no-sandbox" in args
            assert "--disable-gpu" in args
            assert "--disable-dev-shm-usage" in args
            assert "--disable-setuid-sandbox" in args

    def test_windows_returns_empty(self):
        with patch.object(platform, "system", return_value="Windows"):
            assert _default_playwright_args() == []

    def test_macos_returns_empty(self):
        with patch.object(platform, "system", return_value="Darwin"):
            assert _default_playwright_args() == []


class TestConfigDataclass:
    def test_default_values(self):
        c = Config()
        assert c.api_base == "https://api.deepseek.com/v1"
        assert c.max_retries == 3
        assert c.request_timeout == 60.0
        assert c.user_agent == DEFAULT_USER_AGENT
        assert c.summary_prompt == DEFAULT_SUMMARY_PROMPT
        assert c.image_analysis_prompt == DEFAULT_IMAGE_ANALYSIS_PROMPT

    def test_custom_values(self):
        c = Config(
            api_key="key1",
            text_model="gpt-4",
            max_retries=5,
        )
        assert c.api_key == "key1"
        assert c.text_model == "gpt-4"
        assert c.max_retries == 5


class TestLoadConfig:
    def test_load_config_with_env_vars(self):
        env = {
            "API_KEY": "sk-global",
            "API_BASE": "https://custom.api/v1",
            "TEXT_API_KEY": "sk-text",
            "TEXT_API_BASE": "https://text.api/v1",
            "VISION_API_KEY": "sk-vision",
            "VISION_API_BASE": "https://vision.api/v1",
            "TEXT_MODEL": "gpt-4",
            "VISION_MODEL": "gpt-4v",
            "MAX_RETRIES": "5",
            "REQUEST_TIMEOUT": "120.0",
        }
        with patch.dict(os.environ, env, clear=True):
            from core.config import load_config
            c = load_config()
            assert c.api_key == "sk-global"
            assert c.api_base == "https://custom.api/v1"
            assert c.text_api_key == "sk-text"
            assert c.text_api_base == "https://text.api/v1"
            assert c.vision_api_key == "sk-vision"
            assert c.vision_api_base == "https://vision.api/v1"
            assert c.text_model == "gpt-4"
            assert c.vision_model == "gpt-4v"
            assert c.max_retries == 5
            assert c.request_timeout == 120.0

    def test_load_config_text_falls_back_to_global(self):
        env = {
            "API_KEY": "sk-global",
            "API_BASE": "https://global.api/v1",
        }
        with patch.dict(os.environ, env, clear=True):
            from core.config import load_config
            c = load_config()
            assert c.text_api_key == "sk-global"
            assert c.text_api_base == "https://global.api/v1"
            assert c.vision_api_key == "sk-global"
            assert c.vision_api_base == "https://global.api/v1"

    def test_load_config_deepseek_compat(self):
        env = {"DEEPSEEK_API_KEY": "sk-deep", "DEEPSEEK_API_BASE": "https://ds.api/v1"}
        with patch.dict(os.environ, env, clear=True):
            from core.config import load_config
            c = load_config()
            assert c.api_key == "sk-deep"
            assert c.api_base == "https://ds.api/v1"

    def test_load_config_no_env_returns_defaults(self):
        with patch.dict(os.environ, {}, clear=True):
            from core.config import load_config
            c = load_config()
            assert c.api_key == ""
            assert c.api_base == "https://api.deepseek.com/v1"
            assert c.max_retries == 3
