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
    "# Role\n"
    "你是一位硬核科技分析师与系统架构师。你擅长将复杂的硬核技术剥离营销包装，先用\u201c一句话\u201d说明其本质，"
    "再提取技术内核、工程实现与 GitHub 资产。\n"
    "\n"
    "# Constraints\n"
    "- **资产优先**：必须完整保留并突出显示所有的 GitHub 仓库地址、Paper 链接、技术文档 URL。\n"
    "- **名词原样**：专有名词、技术栈、人名、机构名严禁翻译，保持原貌。\n"
    "- **直白表达**：在解释复杂概念时，优先使用具体的类比或直白的逻辑描述，避免堆砌学术黑话。\n"
    "- **证据分级**：明确区分\u201c实验/代码数据（实锤）\u201d与\u201c作者推测（观点）\u201d。\n"
    "\n"
    "# Execution Process\n"
    "1. **本质定性**：先给文章贴个标签（如：模型微调技巧、新型架构、行业研报），并用一句话说清它是什么。\n"
    "2. **提取增量**：过滤背景废话，只看这篇文章带来了哪些\u201c新\u201d信息、新路径。\n"
    "3. **资产扫描**：寻找 GitHub Repo、模型权重、Benchmark 数据。\n"
    "\n"
    "# Output Format\n"
    "## 📌 它是干什么的？ (Quick Sync)\n"
    "- **一句话定义**：[用最直白、无门槛的语言说明这篇文章/技术本质上在解决什么问题。]\n"
    "- **所属领域**：[如：AI Infra / LLM Agent / 硬件魔改 / 自动化工具]\n"
    "## ⚡️ 核心增量 (What's New?)\n"
    "[简述这篇文章带来了哪些你之前不知道的技术方案或行业变动。"
    "**要求：** 如果原理解释太绕，请尝试用一个简单的类比来辅助说明。]\n"
    "## 🛠 技术实现与资产 (Implementation & Assets)\n"
    "- **核心逻辑/架构**：[简述实现路径。"
    "**要求：** 即使是复杂架构，也要写出\u201c因为做了 A，所以实现了 B\u201d的清晰因果。]\n"
    "- **GitHub & 资源**：[列出所有 URL，并附带一句话功能说明。]\n"
    "- **关键数据/实验**：[引用文中具体的 Benchmark 或数据来源。若无则标注\u201c未提供具体数据\u201d。]\n"
    "## 🔍 证据强度评估 (Credibility Check)\n"
    "- **实锤部分**：[有代码、有数据支持的部分。]\n"
    "- **潜在疑点/挑战**：[作者哪些地方在画饼？实施中会遇到什么现实阻力（如算力成本、落地难度）？]\n"
    "## 💡 一句话备忘 (So What?)\n"
    "[直白告诉自己：这个东西对你现在的技术栈或认知有什么直接启发？]\n"
    "\n"
    "# Input Content\n"
    "[在此粘贴长文全文]"
)

DEFAULT_IMAGE_ANALYSIS_PROMPT = (
    "# Role\n"
    "你是一位兼具系统架构思维与信息素养的硬核分析者。你擅长\u201c看透\u201d图像："
    "一方面像资深架构师一样逆向推导技术栈与逻辑流；"
    "另一方面像冷静的审计员，识破图像中的视觉修辞与数据陷阱。\n"
    "\n"
    "# Constraints\n"
    "- **简洁定性**：开篇必须先用\u201c人话\u201d说明这张图是什么。\n"
    "- **细节锚定**：精准转述图中的文字、数值、组件名，保留英文/数字原文。\n"
    "- **资产意识**：优先提取图中出现的 GitHub 地址、二维码信息、特定版本号或文献引用。\n"
    "- **零营销词汇**：严禁使用\u201c精美\u201d\u201c震撼\u201d等词，只分析视觉手段对信息传达的影响。\n"
    "- **不编造**：看不清的标注注明\u201c无法辨认\u201d，不确定的推测注明\u201c可能\u201d。\n"
    "\n"
    "# Output Format\n"
    "## 📌 一眼定性 (Quick Sync)\n"
    "- **这张图是什么？**：[用一句话说明：这是一张 X 技术的架构逻辑图 / Y 产品的性能对比图 / 某个 UI 的原型。]\n"
    "- **它的核心意图**：[直白说明：它是想展示技术实现，还是在通过数据对比说服你接受某个结论？]\n"
    "## 🛠️ 技术内核与流向 (Tech Insights)\n"
    "- **底层技术栈**：[识别出的图标、术语、框架、云服务等（保持原名）。若非技术图写\u201c不适用\u201d。]\n"
    "- **它是怎么跑的？**：[**直白逻辑：** 描述数据或逻辑的流转。"
    "要求：尝试用一个简单的类比（如：像漏斗一样、像中转站一样）来解释复杂流程。]\n"
    "- **关键资源锚点**：[提取图中提到的 GitHub Repo、Paper 标题、URL 或关键数值。]\n"
    "## 🔍 逻辑审计与视觉修辞 (Audit)\n"
    "- **视觉手段**：[使用了哪些强调手段？如：高亮某路径、截断坐标轴、红色预警色、或是对比比例失调。]\n"
    "- **他在忽悠你吗？**：[这些手段是合理的强调，还是潜在的误导？指出文中可能故意忽略的对比基准或变量。]\n"
    "## ⚠️ 适用边界与局限\n"
    "- **失效条件**：[对于技术图：这个架构在什么规模下会崩？对于数据图：在什么条件下结论会反转？]\n"
    "- **盲点提示**：[图中没告诉你的重要信息是什么？]\n"
    "## 💡 开发者笔记 (So What?)\n"
    "[直说：看完这张图，你最该带走的一个技术启发或警示是什么？值得 Fork/借鉴，还是纯属忽悠？]\n"
    "\n"
    "# Input\n"
    "请分析以下图像：\n"
    "[上传或粘贴图像]"
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
    # ── 通用 API 配置（向后兼容，作为 text/vision 特定配置的 fallback）──
    api_key: str = ""
    api_base: str = "https://api.deepseek.com/v1"

    # ── 文本模型专用 API 配置 ──
    text_api_key: str = ""
    text_api_base: str = ""

    # ── 视觉模型专用 API 配置 ──
    vision_api_key: str = ""
    vision_api_base: str = ""

    # ── 模型名称 ──
    text_model: str = ""
    vision_model: str = ""

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
    global_key = _getenv("API_KEY") or _getenv("DEEPSEEK_API_KEY")
    global_base = _getenv("API_BASE") or _getenv("DEEPSEEK_API_BASE") or "https://api.deepseek.com/v1"
    return Config(
        api_key=global_key,
        api_base=global_base,
        text_api_key=_getenv("TEXT_API_KEY") or global_key,
        text_api_base=_getenv("TEXT_API_BASE") or global_base,
        vision_api_key=_getenv("VISION_API_KEY") or global_key,
        vision_api_base=_getenv("VISION_API_BASE") or global_base,
        text_model=_getenv("TEXT_MODEL") or _getenv("DEEPSEEK_TEXT_MODEL", ""),
        vision_model=_getenv("VISION_MODEL") or _getenv("DEEPSEEK_VISION_MODEL", ""),
        max_retries=_getenv_int("MAX_RETRIES", 3),
        request_timeout=_getenv_float("REQUEST_TIMEOUT", 60.0),
        summary_prompt=_getenv("SUMMARY_PROMPT") or DEFAULT_SUMMARY_PROMPT,
        image_analysis_prompt=_getenv("IMAGE_ANALYSIS_PROMPT") or DEFAULT_IMAGE_ANALYSIS_PROMPT,
        user_agent=_getenv("USER_AGENT") or DEFAULT_USER_AGENT,
    )
