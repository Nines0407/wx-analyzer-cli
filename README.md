# wx-analyzer-cli

微信公众号文章智能分析 CLI 工具。通过 Playwright 动态抓取文章内容，调用 DeepSeek 大模型对正文生成摘要并支持多模态图片分析，最终输出结构化 Markdown 文件。

## 功能特性

- **响应式抓取** — Playwright 模拟移动端浏览器，修复 `data-src` 懒加载图片，确保内容完整获取
- **双模式分析**
  - `base`：全文 AI 摘要（DeepSeek-V4-Flash）
  - `deep`：摘要 + 逐图视觉分析（DeepSeek-VL2），分析结果嵌入原文对应位置
- **噪音过滤** — 自动剥离 script / iframe / style 标签，正则去除「推荐阅读」「广告」等噪点文本
- **并发控制** — deep 模式下通过 `asyncio.Semaphore` 控制图片分析并发数，默认 5
- **429 指数退避** — 针对 API 频率限制实现 `2^n + jitter` 重试机制
- **Rich 终端 UI** — 进度条、状态面板、彩色输出、摘要面板
- **Linux 原生支持** — 自动检测平台，注入 Chromium headless 所需参数（`--no-sandbox`、`--disable-gpu`、`--disable-dev-shm-usage`），无需手动配置即可在服务器/容器环境运行

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
# 必填：DeepSeek API 密钥
DEEPSEEK_API_KEY=sk-your-key-here

# 以下均为可选，有默认值
# DEEPSEEK_API_BASE=https://api.deepseek.com/v1
# DEEPSEEK_TEXT_MODEL=deepseek-v4-flash
# DEEPSEEK_VISION_MODEL=deepseek-vl2
```

也可通过环境变量配置（优先级高于 `.env`）：

```bash
export DEEPSEEK_API_KEY=sk-your-key-here
```

可选环境变量（均有合理默认值）：

| 变量 | 默认值 | 说明 |
|:---|:---|:---|
| `DEEPSEEK_API_BASE` | `https://api.deepseek.com/v1` | API 基础 URL |
| `DEEPSEEK_TEXT_MODEL` | `deepseek-v4-flash` | 文本模型 ID |
| `DEEPSEEK_VISION_MODEL` | `deepseek-vl2` | 视觉模型 ID |

## 使用方法

安装后通过 `wx-analyzer` 命令使用，也可在项目根目录直接使用 `python -m main`：

### 基础模式（仅生成全文摘要）

```bash
wx-analyzer "https://mp.weixin.qq.com/s/xxxx"
```

### 深度模式（摘要 + 图片分析）

```bash
wx-analyzer "https://mp.weixin.qq.com/s/xxxx" --mode deep
```

### 自定义参数

```bash
wx-analyzer "https://mp.weixin.qq.com/s/xxxx" \
    --mode deep \
    --output ./my_analysis/ \
    --concurrency 10
```

| 参数 | 简写 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `--mode` | `-m` | `base` | 分析模式：`base` / `deep` |
| `--output` | `-o` | `./output/` | 输出目录 |
| `--concurrency` | `-c` | `5` | Deep 模式图片并发数 (1-20) |

输出文件以 `MD5(URL).md` 命名，包含三部分：
1. AI 生成的全文摘要
2. 带有 AI 图片分析注释的原文 Markdown
3. 元数据（作者、发布日期、源链接、分析时间）

## 项目结构

```
wx-analyzer-cli/
├── main.py              # Typer CLI 入口，命令路由与生命周期管理
├── pyproject.toml        # 项目元数据与依赖声明
├── core/
│   ├── config.py         # 配置管理（环境变量 → Config dataclass，含 Linux 平台检测）
│   ├── scraper.py        # Playwright 浏览器自动化与 DOM 抓取
│   ├── processor.py      # HTML 清洗、Markdown 转换、噪点去除
│   ├── ai_engine.py      # DeepSeek API 调用（文本 + 视觉）
│   └── storage.py        # 本地 Markdown 文件存储
├── .env.example          # 环境变量模板
└── .gitignore
```

## 执行流程

```
用户输入 URL
    │
    ▼
WechatScraper.scrape()
  ├── 启动无头 Chromium（iPhone User-Agent + Linux 适配 args）
  ├── 等待 networkidle + 额外 1.5s 延迟
  ├── 注入 JS 修复 data-src → src
  └── 返回完整 HTML
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
       │ mode == "deep" 且有图片？   │
       └────────────────────────────┘
         │ yes                │ no
         ▼                    ▼
  AIEngine.analyze_images()  AIEngine.summarize()
    ├── Semaphore(5) 并发
    ├── 下载图片 → base64
    ├── 提取图片上下文 (前后 500 字)
    ├── DeepSeek-VL2 分析
    └── embed_analysis()
        将分析结果回填至
        Markdown 对应锚点处
         │
         ▼
  AIEngine.summarize()
    │
    ▼
Storage.save()
  └── 写入 output/{MD5(URL)}.md
```

## Linux 适配

在 Linux 环境下，Chromium headless 模式需要额外的启动参数才能正常运行（尤其在没有桌面环境的服务器或 Docker 容器中）。项目已内置平台自动检测：

| 参数 | 说明 |
|:---|:---|
| `--no-sandbox` | 禁用沙箱，root 用户或容器环境必需 |
| `--disable-gpu` | 禁用 GPU 加速，避免无 GPU 环境下崩溃 |
| `--disable-dev-shm-usage` | 使用 `/tmp` 替代 `/dev/shm`，解决 Docker 共享内存不足问题 |
| `--disable-setuid-sandbox` | 禁用 setuid 沙箱，兼容部分 Linux 发行版 |

实现方式：
- `core/config.py` — `_default_playwright_args()` 通过 `platform.system()` 判断操作系统，Linux 下自动返回上述参数
- `core/config.py` — `Config` dataclass 新增 `playwright_launch_args` 字段
- `core/scraper.py` — `_ensure_browser()` 启动 Chromium 时传入 `args=self._config.playwright_launch_args`

在 macOS / Windows 上返回空列表，不影响原生功能。

## License

MIT
