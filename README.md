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

## 安装

```bash
# 1. 克隆仓库
git clone <repo-url> && cd wx-analyzer-cli

# 2. 安装依赖和项目本身
pip install -e .

# 3. 安装 Playwright 浏览器
playwright install chromium
```

## 配置

设置 DeepSeek API 密钥：

```bash
export DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx
```

可选环境变量（均有合理默认值）：

| 变量 | 默认值 | 说明 |
|:---|:---|:---|
| `DEEPSEEK_API_BASE` | `https://api.deepseek.com/v1` | API 基础 URL |
| `DEEPSEEK_TEXT_MODEL` | `deepseekv4flash` | 文本模型 ID |
| `DEEPSEEK_VISION_MODEL` | `deepseek-vl2` | 视觉模型 ID |

## 使用方法

### 基础模式（仅生成全文摘要）

```bash
wx-analyzer analyze "https://mp.weixin.qq.com/s/xxxx"
```

### 深度模式（摘要 + 图片分析）

```bash
wx-analyzer analyze "https://mp.weixin.qq.com/s/xxxx" --mode deep
```

### 自定义参数

```bash
wx-analyzer analyze "https://mp.weixin.qq.com/s/xxxx" \
    --mode deep \
    --output ./my_analysis/ \
    --concurrency 10
```

| 参数 | 简写 | 默认值 | 说明 |
|:---|:---|:---|:---|
| `--mode` | `-m` | `base` | 分析模式：`base` / `deep` |
| `--output` | `-o` | `./output/` | 输出目录 |
| `--concurrency` | `-c` | `5` | Deep 模式图片并发数 (1-20) |
| `--no-progress` | — | `false` | 关闭 Rich 进度条 |

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
│   ├── config.py         # 配置管理（环境变量 → Config dataclass）
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
  ├── 启动无头 Chromium（iPhone User-Agent）
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

## License

MIT
