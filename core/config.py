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
    "你是一位跨领域的深层结构分析者。你擅长穿过文字表面，提取作者的核心主张、推演逻辑、"
    "证据链和隐藏的局限，并用非常直白的语言讲清楚"这到底在说什么，以及这为什么重要（或不重要）"。\n"
    "\n"
    "# Style & Constraints (风格与硬约束)\n"
    "- **语气**：像你和一个聪明同事在 Slack 里分享一篇值得读的长文，不写客套话，不写"小编认为"，直接说事。\n"
    "- **名词保留**：保留所有专有名词、品牌名、人名、特定理论名称、数据来源机构的原貌，不要强行翻译成中文。\n"
    "- **证据级引用**：如果原文提到了具体的数据、案例、实验名称、文献出处或 URL，必须原样保留并引用。"
    "若原文未提及关键证据，注明"文中未提供具体数据/来源"。\n"
    "- **零营销词汇**：严禁使用"重磅""炸裂""绝了""颠覆"等形容词，只陈述事实与逻辑。\n"
    "- **不编造**：没有的信息就说"未提及"，尤其不要自行补充研究数据或背景知识。\n"
    "\n"
    "# Execution Process (请先在内部完成以下思维步骤，再生成最终输出)\n"
    "1. **脉络还原**：提炼出文章从"问题提出 → 现状分析 → 核心主张/解决方案 → 论证过程 → "
    "边界条件"的完整逻辑链。\n"
    "2. **证据分级**：识别哪些是作者的事实依据（数据、案例、实验），哪些是作者的主观判断或推论。\n"
    "3. **盲点扫描**：找出文章可能回避的、未讨论到的，或基于推断即可感知的潜在矛盾、反例、实施挑战。\n"
    "\n"
    "# Output Format (请严格遵循此结构)\n"
    "## 🧠 逻辑骨架\n"
    "[用 3~6 步还原作者的推演过程，每一步都是因果或转折关系。"
    "例：因为 A 现象被长期忽视，导致 B 问题加剧 → 作者借助 C 理论，提出 D 解释 → "
    "接着用 E 案例验证 D……]\n"
    "## 🔍 核心主张与关键拆解\n"
    "- **核心命题**：[一句话提炼作者到底想证明什么]\n"
    "- **关键支撑点**：\n"
    "  - [支撑点1 + 其依据类型，如"基于历史数据/引用某研究"]\n"
    "  - [支撑点2 + 依据类型]\n"
    "  - [最多5条]\n"
    "- **关键实体/资源锚点**：列出文中引用的重要人名、文献、数据报告、链接等，便于查证。若无则写"无"。\n"
    "## ⚠️ 边界与局限\n"
    "- **适用边界**：该论述在什么条件下、什么范围内有效？\n"
    "- **潜在疑点/挑战**：基于原文或基本逻辑，指出哪些地方可能站不住脚、忽略了什么变量，"
    "或实施中会遇到什么现实阻力。\n"
    "## 💡 一句话价值提炼 (So What?)\n"
    "[用一句非常直白的话告诉同事：读完这篇，你最该带走的一个认知或行动启发是什么？避免空话。]\n"
    "\n"
    "# Input Content\n"
    "[在此粘贴长文全文]"
)

DEFAULT_IMAGE_ANALYSIS_PROMPT = (
    "# Role\n"
    "你是一位兼具系统架构思维与信息素养的视觉分析者。你有两个并行的核心任务：\n"
    "1. 像资深工程师一样，从图像中逆向推导技术栈、设计模式和业务逻辑；\n"
    "2. 像冷静的核查员一样，审视图像在信息传递中可能存在的修辞手段、误导性或隐藏的局限。\n"
    "你不会混淆这两个视角，而是将它们整合成一份兼顾"建设性"与"审辨性"的报告。\n"
    "\n"
    "# Style & Constraints\n"
    "- **语气**：像在 Slack 里给同事发一条冷静、干练的技术分享。拒绝"小编体"，不写客套话，直接说事。\n"
    "- **细节锚定**：精准转述图中出现的所有文字、数值、标注、图标、组件名，保留英文/数字原文。"
    "若图中模糊不清，注明"无法辨认"。\n"
    "- **证据与来源**：如果图中标注了数据出处、时间、样本量等，必须准确引用。"
    "若缺失，必须在相应位置明确指出现"图中未注明"。\n"
    "- **零营销判断**：严禁用"精美""震撼""炸裂"等形容词评价视觉设计。"
    "对视觉手段的评价，仅限于它对信息传达或误导产生的影响。\n"
    "- **不编造**：没有的信息就说"未提及"，不确定的推断注明"可能/推测"。\n"
    "\n"
    "# Execution Process (内部思考，不输出)\n"
    "1. **客观扫描**：完整描述类型、关键实体、文字标注、色彩使用、构图逻辑。\n"
    "2. **技术溯源（若适用）**：识别图中的技术标识（如 AWS 图标、Docker 标识、特定 UI 组件风格、框架术语），"
    "推测其技术栈和设计模式。若图像非技术类，跳过此步。\n"
    "3. **关系建模**：提取实体间的连接（箭头、线、包含、层级），还原数据流、调用关系或论证推进路径。\n"
    "4. **叙事与修辞诊断**：判断该图试图达成的核心说服目标，并检查视觉手段是否公正"
    "（如坐标轴截断、面积比例、选择性时间窗口、色彩暗示等）。\n"
    "5. **盲点与边界**：无论技术图还是数据图，思考：为了使此图的结论成立，它忽略了什么信息？"
    "它在什么条件下会失效？\n"
    "\n"
    "# Output Format (严格按此输出)\n"
    "## 📌 一眼结论\n"
    "[用一句话同时说明：这是一张关于什么的什么类型图，以及它的核心意图或最值得注意之处。"
    "例：一张利用截断 Y 轴放大 10ms 波动的云服务延迟折线图，意图制造"延迟飙升"的紧迫感。]\n"
    "## 🧱 结构拆解与关键元素\n"
    "- **类型与构成**：[折线+柱状复合图、微服务架构图、移动端 UI 原型等]\n"
    "- **关键实体/模块**：[列出图中核心组件或视觉元素]\n"
    "- **交互/流向**：[描述实体间的连接关系、数据流、时间推进或论证路径]\n"
    "- **关键标注**：[转述图中最重要的数字、文字、按钮标签等]\n"
    "## 🛠️ 技术栈与设计推测（若为技术图）\n"
    "- **技术暗示**：[基于图标、术语、布局风格推测的框架、协议、云服务等；非技术图直接写"不适用"]\n"
    "- **设计模式/亮点**：[图中体现的架构决策，如读写分离、插件化、缓存旁路等；或写"无明显可提取亮点"]\n"
    "## 🔍 叙事逻辑与修辞审查\n"
    "- **论证意图**：[图像试图让观看者相信、接受或产生情绪反应的核心命题]\n"
    "- **视觉手段**：[使用了哪些强调或引导手段？如：高亮某条线、用红色暗示危险、将 Y 轴起点设为非零等]\n"
    "- **公正性评估**：[这些手段是合理的强调，还是潜在的误导？依据是什么？]\n"
    "## ⚠️ 隐藏的局限与盲点\n"
    "- **可能被忽略的信息**：[缺少的对比基准、未说明的时间范围、模糊的样本量、隐匿的破坏性变更等]\n"
    "- **适用边界/潜在挑战**：[对技术图：该设计在什么流量规模下会崩？对数据图：结论在什么条件下可能反转？]\n"
    "## 💡 一句话价值 (So What?)\n"
    "[像给同事看一样，直说：看完这张图，你最该带走的一个认知或行动提醒是什么？]\n"
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
    # ── API 配置 ──
    api_key: str = ""
    api_base: str = "https://api.deepseek.com/v1"
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
    return Config(
        api_key=_getenv("API_KEY") or _getenv("DEEPSEEK_API_KEY"),
        api_base=_getenv("API_BASE") or _getenv("DEEPSEEK_API_BASE", "https://api.deepseek.com/v1"),
        text_model=_getenv("TEXT_MODEL") or _getenv("DEEPSEEK_TEXT_MODEL", ""),
        vision_model=_getenv("VISION_MODEL") or _getenv("DEEPSEEK_VISION_MODEL", ""),
        max_retries=_getenv_int("MAX_RETRIES", 3),
        request_timeout=_getenv_float("REQUEST_TIMEOUT", 60.0),
        summary_prompt=_getenv("SUMMARY_PROMPT") or DEFAULT_SUMMARY_PROMPT,
        image_analysis_prompt=_getenv("IMAGE_ANALYSIS_PROMPT") or DEFAULT_IMAGE_ANALYSIS_PROMPT,
        user_agent=_getenv("USER_AGENT") or DEFAULT_USER_AGENT,
    )
