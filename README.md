# wx-analyzer-cli

微信公众号文章智能分析 CLI 工具。通过 Playwright 动态抓取文章内容，调用大模型 API 对正文生成摘要并支持多模态图片分析，最终输出结构化 Markdown 文件。

## 功能特性

- **响应式抓取** — Playwright 模拟移动端浏览器，修复 `data-src` 懒加载图片，确保内容完整获取
- **自动模式检测** — 默认 `auto` 模式，自动检测文章中是否包含图片/视频，有则启用深度多模态分析
- **双模式分析**
  - `base`：全文 AI 摘要
  - `deep`：摘要 + 逐图视觉分析，分析结果嵌入原文对应位置
- **本地资源持久化** — 自动下载文章中图片到本地，Markdown 引用改为本地相对路径，离线可读
- **视频识别** — 自动检测微信视频播放器嵌入，在输出 Markdown 末尾附视频链接列表
- **噪音过滤** — 自动剥离 script / iframe / style 标签，正则去除「推荐阅读」「广告」等噪点文本
- **并发控制** — deep 模式下通过 `asyncio.Semaphore` 控制图片分析并发数，默认 5
- **429 指数退避** — 针对 API 频率限制实现 `2^n + jitter` 重试机制
- **Rich 终端 UI** — 进度条、状态面板、彩色输出、摘要面板
- **Linux 原生支持** — 自动检测平台，注入 Chromium headless 所需参数（`--no-sandbox`、`--disable-gpu`、`--disable-dev-shm-usage`），无需手动配置即可在服务器/容器环境运行
- **完全可配置化** — API 地址、模型名称、系统提示词、重试策略、User-Agent 等全部通过环境变量/`.env` 配置

## 安装

```bash
# 1. 克隆仓库
git clone https://github.com/Nines0407/wx-analyzer-cli.git && cd wx-analyzer-cli

# 2. 安装依赖和项目本身
pip install -e .

# 3. 安装 Playwright 浏览器
playwright install chromium

# 4. [Linux] 安装系统依赖 (Chromium 运行所需的 .so 库)
playwright install-deps chromium
```

## 配置

项目**首次运行时会自动**将 `.env.example` 复制为 `.env`，编辑该文件填入 API 密钥即可：

```bash
# 编辑自动生成的 .env 文件
vim .env
# 或
nano .env
```

`.env` 文件格式：

```ini
# ── 通用 API 配置 ──
API_KEY=sk-your-key-here                     # API 密钥（作为 text/vision 的 fallback）
# API_BASE=https://api.deepseek.com/v1        # API 地址（默认 DeepSeek）

# ── 模型名称 ──
TEXT_MODEL=deepseek-v4-flash                 # 文本模型
VISION_MODEL=deepseek-vl2                    # 视觉模型

# ── 文本/视觉独立 API 配置（可选，不设置则使用通用配置）──
# TEXT_API_KEY=sk-text-key                   # 文本模型专用 API 密钥
# TEXT_API_BASE=https://text-api.example.com  # 文本模型专用 API 地址
# VISION_API_KEY=sk-vision-key               # 视觉模型专用 API 密钥
# VISION_API_BASE=https://vision-api.example.com  # 视觉模型专用 API 地址

# ── 请求配置 ──
# MAX_RETRIES=3                              # 最大重试次数
# REQUEST_TIMEOUT=60.0                       # 请求超时秒数

# ── Prompt 配置 ──
# SUMMARY_PROMPT=你是一个专业的技术文章摘要助手...
# IMAGE_ANALYSIS_PROMPT=请结合提供的上下文分析...

# ── 浏览器配置 ──
# USER_AGENT=Mozilla/5.0 ...
```

也可通过环境变量配置（优先级高于 `.env`）：

```bash
export API_KEY=sk-your-key-here
```

### 全部配置项

| 变量 | 默认值 | 说明 |
|:---|:---|:---|
| `API_KEY` | - | API 密钥（通用 fallback，兼容旧名 `DEEPSEEK_API_KEY`） |
| `API_BASE` | `https://api.deepseek.com/v1` | API 基础 URL（通用 fallback） |
| `TEXT_API_KEY` | - | 文本模型专用 API 密钥（可选，不设置则使用 `API_KEY`） |
| `TEXT_API_BASE` | - | 文本模型专用 API 基础 URL（可选，不设置则使用 `API_BASE`） |
| `VISION_API_KEY` | - | 视觉模型专用 API 密钥（可选，不设置则使用 `API_KEY`） |
| `VISION_API_BASE` | - | 视觉模型专用 API 基础 URL（可选，不设置则使用 `API_BASE`） |
| `TEXT_MODEL` | 无 | 文本摘要模型 |
| `VISION_MODEL` | 无 | 视觉分析模型 |
| `MAX_RETRIES` | `3` | API 调用最大重试次数 |
| `REQUEST_TIMEOUT` | `60.0` | API 请求超时秒数 |
| `SUMMARY_PROMPT` | （内置中文提示词） | 文本摘要系统提示词 |
| `IMAGE_ANALYSIS_PROMPT` | （内置中文提示词） | 图片分析系统提示词 |
| `USER_AGENT` | iPhone Safari UA | Playwright 浏览器 User-Agent |

## 使用方法

安装后通过 `wx-analyzer` 命令使用，也可在项目根目录直接使用 `python main.py`：

### 自动模式（默认，推荐）

自动检测文章中是否包含图片/视频，有则启用深度分析，无则仅生成摘要：

```bash
wx-analyzer "https://mp.weixin.qq.com/s/xxxx"
```

### 手动指定模式

```bash
# 强制深度分析（摘要 + 图片分析）
wx-analyzer "https://mp.weixin.qq.com/s/xxxx" --mode deep

# 强制基础分析（仅摘要，跳过图片分析）
wx-analyzer "https://mp.weixin.qq.com/s/xxxx" --mode base
```

### 批量分析

从文件读取 URL 列表，并发处理多篇文章：

```bash
# urls.txt 每行一个 URL，# 开头的行为注释
wx-analyzer --file urls.txt

# 3 篇文章并行处理
wx-analyzer --file urls.txt --workers 3

# 批量 + 基础模式
wx-analyzer --file urls.txt --mode base -w 5
```

### 自定义参数

```bash
wx-analyzer "https://mp.weixin.qq.com/s/xxxx" \
    --mode auto \
    --output ./my_analysis/ \
    --concurrency 10
```

| 参数 | 简写 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `--file` | `-f` | - | URL 列表文件（每行一个，`#` 跳过） |
| `--mode` | `-m` | `auto` | 分析模式：`auto` / `base` / `deep` |
| `--output` | `-o` | `./output/` | 输出根目录 |
| `--concurrency` | `-c` | `5` | 单篇文章内图片并发分析数 (1-20) |
| `--workers` | `-w` | `1` | 并行处理的文章数 (1-10) |

## 输出结构

每篇文章在输出目录下生成一个以 **文章标题** 命名的子文件夹：

```
output/
└── 微信小程序性能优化实战_a1b2c3d4/
    ├── summary.md           # AI 摘要 + 元数据
    ├── article.md           # 原文（含 AI 图片分析嵌入）
    └── images/
        ├── img_0.jpg        # 下载的图片（本地引用）
        └── img_1.png
```

`summary.md` 包含以下部分：

1. **文章标题**
2. **AI 摘要** — 全文深度摘要
3. **元数据** — 源链接、作者、发布日期、分析时间

`article.md` 包含以下部分：

1. **文章标题**
2. **原文内容** — 带有 AI 图片分析注释的正文（图片引用已替换为本地路径）
3. **视频列表** — 若检测到视频嵌入，列出视频链接

## 项目结构

```
wx-analyzer-cli/
├── main.py              # Typer CLI 入口，单篇/批量分析调度与并发控制
├── pyproject.toml        # 项目元数据与依赖声明
├── core/
│   ├── config.py         # 配置管理（环境变量 → Config dataclass，含 Linux 平台检测）
│   ├── scraper.py        # Playwright 浏览器自动化与 DOM 抓取
│   ├── processor.py      # HTML 清洗、Markdown 转换、噪点去除、多媒体检测
│   ├── ai_engine.py      # 大模型 API 调用（文本摘要 + 视觉分析）
│   └── storage.py        # 本地文件存储与图片下载
├── .env.example          # 环境变量配置模板
└── .gitignore
```

## 执行流程

```
用户输入 URL / --file 批量URL
    │
    ▼
WechatScraper.scrape()
  ├── 启动无头 Chromium（可配置 User-Agent + Linux 适配 args）
  ├── 等待 domcontentloaded + 延迟缓冲
  ├── 注入 JS 修复 data-src → src
  └── 返回完整 HTML
    │
    ▼
自动模式检测（detect_media_from_html）
  ├── 检测 <img> 标签、<video> 标签、视频 iframe
  └── 有媒体 → deep 模式，无媒体 → base 模式
    │
    ▼
ContentProcessor.clean()
  └── 正则剥离 script / style / iframe / noscript / svg
    │
    ▼
ContentProcessor.html_to_markdown()
  ├── html2text 转换 HTML → Markdown
  ├── 识别图片 URL，替换为 ![img_N](url) 锚点
  └── remove_noise() 去除噪点文本
    │
    ▼  ┌────────────────────────────┐
       │ effective_mode == "deep"    │
       │ 且有图片？                  │
       └────────────────────────────┘
         │ yes                │ no
         ▼                    ▼
  AIEngine.analyze_images()  AIEngine.summarize()
    ├── Semaphore(N) 并发
    ├── 下载图片 → base64
    ├── 提取图片上下文 (前后 500 字)
    ├── 视觉模型分析
    └── embed_analysis()
        将分析结果回填至
        Markdown 对应锚点处
         │
         ▼
  AIEngine.summarize()
    │
    ▼
Storage.save()
  ├── 创建 output/{标题}_{hash}/ 子目录
  ├── 下载图片至 images/ 子目录
  ├── 替换 Markdown 中图片引用为本地路径
  ├── 追加视频链接列表
  └── 写入 summary.md + article.md
```

## 自定义模型示例

### 使用 OpenAI

```bash
export API_KEY=sk-openai-xxx
export API_BASE=https://api.openai.com/v1
export TEXT_MODEL=gpt-4o-mini
wx-analyzer "https://mp.weixin.qq.com/s/xxxx"
```

### 使用本地模型（如 Ollama + Open WebUI）

```bash
export API_KEY=ollama
export API_BASE=http://localhost:11434/v1
export TEXT_MODEL=qwen2.5:7b
wx-analyzer "https://mp.weixin.qq.com/s/xxxx"
```

### 自定义分析提示词

```bash
export SUMMARY_PROMPT="你是专业财经分析师，请用中文总结以下文章的核心观点与投资建议，200 字以内。"
wx-analyzer "https://mp.weixin.qq.com/s/xxxx"
```

## Linux 适配

在 Linux 环境下，Chromium headless 模式需要额外的启动参数才能正常运行（尤其在没有桌面环境的服务器或 Docker 容器中）。项目已内置平台自动检测：

| 参数 | 说明 |
|:---|:---|
| `--no-sandbox` | 禁用沙箱，root 用户或容器环境必需 |
| `--disable-gpu` | 禁用 GPU 加速，避免无 GPU 环境下崩溃 |
| `--disable-dev-shm-usage` | 使用 `/tmp` 替代 `/dev/shm`，解决 Docker 共享内存不足问题 |
| `--disable-setuid-sandbox` | 禁用 setuid 沙箱，兼容部分 Linux 发行版 |

在 macOS / Windows 上不注入额外参数，不影响原生功能。

## License

MIT
