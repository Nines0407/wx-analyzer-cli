# wx-analyzer-cli — Implementation Reference [AI Agent Edition]

> 本文件专为 AI 编码助理（Claude、AutoGPT 等）设计，采用结构化格式描述实现细节、数据流与约定。
> 阅读 `README.md` 获取面向人类用户的使用说明。

---

## 1. 项目元数据

```yaml
name: wx-analyzer-cli
runtime: Python 3.10+
entry: main.py  # typer app
package: core/  # flat namespace, no nested subpackages
deps:
  python-dotenv: .env 文件自动加载
  playwright:  动态 DOM 渲染, data-src 懒加载修复
  html2text:   HTML → Markdown 转换
  openai:      AsyncOpenAI, DeepSeek 兼容 OpenAI 协议
  rich:        终端进度条 / Panel / status spinner
  typer:       CLI 路由, 参数校验
  httpx:       Async HTTP 图片下载
```

---

## 2. 模块接口契约

### 2.1 `main.py` — 入口与编排

| 符号 | 类型 | 说明 |
|:---|:---|:---|
| `app` | `typer.Typer` | 全局 CLI 实例 |
| `@app.command()` | decorator | 唯一的子命令 `analyze` |
| `analyze(url, mode, output_dir, concurrency)` | sync fn | Typer 命令函数，内部 `asyncio.run(_run())` |

**执行顺序（不可变）**:

1. 校验 `mode ∈ {"base", "deep"}`
2. `load_config()` 从环境变量加载配置
3. 若 `DEEPSEEK_API_KEY` 为空则报错退出
4. 实例化 `AIEngine`, `WechatScraper`, `ContentProcessor`, `Storage`
5. 创建 `asyncio.Semaphore(concurrency)` 传入 AIEngine
6. 调用 `asyncio.run(_run())` 执行异步核心流程
7. `finally` 块保证 `engine.close()` + `scraper.close()` 资源释放

---

### 2.2 `core/config.py` — 配置

```python
@dataclass
class Config:
    api_key: str = ""                                    # DEEPSEEK_API_KEY
    api_base: str = "https://api.deepseek.com/v1"        # DEEPSEEK_API_BASE
    text_model: str = "deepseek-v4-flash"                # DEEPSEEK_TEXT_MODEL
    vision_model: str = "deepseek-vl2"                    # DEEPSEEK_VISION_MODEL
    max_retries: int = 3                                  # 重试次数
    request_timeout: float = 60.0                         # SDK timeout
    user_agent: str = <Mobile Safari UA>
```

| `load_config()` 从 `.env` 文件及环境变量读取:
- `DEEPSEEK_API_KEY` (required)
- `DEEPSEEK_API_BASE` (optional)
- `DEEPSEEK_TEXT_MODEL` (optional)
- `DEEPSEEK_VISION_MODEL` (optional)

---

### 2.3 `core/scraper.py` — 抓取模块

**类**: `WechatScraper(config: Config | None)`

| 方法 | 返回 | 说明 |
|:---|:---|:---|
| `_ensure_browser()` | `None` | 惰性初始化 Playwright + Chromium |
| `scrape(url)` | `str` | 返回完整 HTML，流程见下 |
| `get_title()` | `str` | 通过 JS 选择器 `#activity-name` 或 `document.title` |
| `get_author()` | `str` | 选择器 `#js_name` |
| `get_publish_date()` | `str` | 选择器 `#publish_time` |
| `close()` | `None` | 依次关闭 page → context → browser → playwright |

**scrape 流程**:
1. `page.goto(url, wait_until="networkidle", timeout=30000)`
2. `page.wait_for_timeout(1500)` — 等待异步 DOM 变化
3. `page.evaluate(LAZY_LOAD_JS)` — 注入懒加载修复脚本
4. `page.wait_for_timeout(500)` — 等待图片渲染
5. 返回 `page.content()`

**LAZY_LOAD_JS**:
```javascript
// 修复 data-src / data-original → src
imgs.forEach(img => {
    const ds = img.getAttribute('data-src') || img.getAttribute('data-original');
    if (ds && (!img.src || img.src.startsWith('data:'))) {
        img.src = ds;
        img.removeAttribute('data-src');
    }
});
// 修复 data-background / data-bg → style.backgroundImage
```

---

### 2.4 `core/processor.py` — 清洗与转换

**类**: `ContentProcessor`

| 方法 | 输入 | 输出 | 说明 |
|:---|:---|:---|:---|
| `clean(html)` | `str` | `str` | 正则剥离 `<script>`, `<style>`, `<iframe>`, `<noscript>`, `<svg>` |
| `html_to_markdown(html)` | `str` | `(md_str, anchors)` | html2text 转换 + 图片锚点归一化 |
| `extract_images_with_context(md, anchors)` | `str, list` | `list[ImageItem]` | 每张图提取前后 500 字上下文 |
| `embed_analysis(md, analyses)` | `str, dict` | `str` | 将 VL2 分析结果插入图片锚点下方 |
| `remove_noise(text)` | `str` | `str` | 正则去除「推荐阅读」「广告」等 |

**图片锚点格式**:
```
![img_0](https://mmbiz.qpic.cn/xxx)
![img_1](https://example.com/chart.png)
```

**ImageItem**:
```python
@dataclass
class ImageItem:
    anchor_id: str    # "img_0"
    url: str          # 原始图片 URL
    context: str      # 图片前后 500 字符的上下文文本
```

**图片 URL 判定** (`_is_image_url`):
- 扩展名匹配: `.jpg`, `.jpeg`, `.png`, `.gif`, `.webp`, `.bmp`, `.svg`
- 域名匹配: `mmbiz.qpic.cn`, `mmbiz.qlogo.cn`

**噪点正则** (`NOISE_PATTERNS`):
- `推荐阅读.*?(?=\n\n|\Z)`
- `广告.*?(?=\n\n|\Z)`
- `关注我们.*?(?=\n\n|\Z)`
- `阅读原文.*?(?=\n\n|\Z)`
- `分享到.*?(?=\n\n|\Z)`

---

### 2.5 `core/ai_engine.py` — AI 引擎

**类**: `AIEngine(api_key, api_base?, config?, semaphore?)`

| 方法 | 返回 | 说明 |
|:---|:---|:---|
| `summarize(markdown)` | `str` | DeepSeek-V4-Flash 生成 300 字中文摘要 |
| `analyze_images(images)` | `dict[anchor_id → analysis]` | 并发调用 DeepSeek-VL2 分析图片 |
| `_analyze_single_image(item)` | `str` | 单张图片: 下载 → base64 → VL2 API |
| `_call_with_retry(messages, model, retries?)` | `str` | 统一 API 调用 + 指数退避重试 |
| `_download_image(url)` | `bytes | None` | HTTP 下载图片二进制 |
| `close()` | `None` | 关闭 httpx 和 openai 客户端 |

**OpenAI SDK 调用格式**:

```python
# 文本摘要
messages = [
    {"role": "system", "content": SYSTEM_SUMMARY_PROMPT},
    {"role": "user", "content": truncated_markdown[:12000]},
]
response = await client.chat.completions.create(
     model="deepseek-v4-flash",  # or DEEPSEEK_TEXT_MODEL
    messages=messages,
    timeout=60.0,
)

# 视觉分析
messages = [
    {"role": "user", "content": [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,..."}},
    ]},
]
response = await client.chat.completions.create(
    model="deepseek-vl2",  # or DEEPSEEK_VISION_MODEL
    messages=messages,
    timeout=60.0,
)
```

**速率限制与重试** (`_call_with_retry`):

```
attempt 0 → 429 → sleep(2^0 + random(0,1)) → retry
attempt 1 → 429 → sleep(2^1 + random(0,1)) → retry
attempt 2 → 429 → sleep(2^2 + random(0,1)) → 不再重试, 返回 "⚠️ AI 请求失败"
非 429   → 按 2^attempt 退避(无 jitter), 最后一次直接 raise
```

- 重试次数 = `Config.max_retries` (默认 3)，即 `range(3)` → 0, 1, 2 共 3 次尝试
- 提取 HTTP status code: 优先 `exc.response.status_code`，回退 `exc.status_code`
- 全部重试耗尽后 429 返回 fallback 字符串，非 429 则抛出异常

**并发控制**:
- `analyze_images()` 使用 `asyncio.gather` 并发启动所有图片分析
- 每个子任务内部 `async with self._semaphore` 限制同时进行的 API 调用数
- 默认 `Semaphore(5)`，即最多 5 个并发请求

**MIME 检测** (`_detect_mime_type`):
- `\xff\xd8\xff` → `image/jpeg`
- `\x89PNG\r\n\x1a\n` → `image/png`
- `GIF87a` / `GIF89a` → `image/gif`
- `RIFF....WEBP` → `image/webp`
- fallback → `image/jpeg`

---

### 2.6 `core/storage.py` — 持久化

**类**: `Storage(output_dir: Path)`

| 方法 | 返回 | 说明 |
|:---|:---|:---|
| `save(url, *, title, summary, content, metadata)` | `Path` | 写入 Markdown 文件，返回文件路径 |

**文件命名**: `MD5(URL).md`

**输出文件结构**:
```markdown
# {title}

---

## AI 摘要

{summary}

---

## 原文内容

{markdown_with_embedded_analysis}

---

## 元数据
> **源链接:** {url}
> **作者:** {author}
> **发布日期:** {publish_date}
> **分析时间:** {UTC timestamp}
```

---

## 3. 完整数据流

```
┌─────────────────────────────────────────────────────┐
│                    analyze(url)                      │
└─────────────────────────────────────────────────────┘
                        │
           ┌────────────┴────────────┐
           │  load_config()          │
           │  DEEPSEEK_API_KEY 检查   │
           └────────────┬────────────┘
                        │
           ┌────────────┴────────────┐
           │  实例化 4 个核心对象      │
           │  scraper, processor,     │
           │  engine, storage          │
           └────────────┬────────────┘
                        │
           ┌────────────┴────────────┐
           │  scraper.scrape(url)     │
           │  → raw HTML              │
           └────────────┬────────────┘
                        │
           ┌────────────┴────────────┐
           │  processor.clean(html)   │
           │  → script/iframe 剥离    │
           └────────────┬────────────┘
                        │
           ┌────────────┴────────────┐
           │  processor.html_to_md()  │
           │  → (md, image_anchors)   │
           │  processor.remove_noise  │
           └────────────┬────────────┘
                        │
              ┌─────────┴─────────┐
              │ mode == "deep"     │
              │ && image_anchors?  │
              └─────────┬─────────┘
           yes          │          no
           │            │           │
  ┌────────┴───────┐    │    ┌──────┴────────┐
  │ extract_images │    │    │ engine.        │
  │ _with_context  │    │    │ summarize(md)  │
  │   → ImageItem[]│    │    └──────┬────────┘
  └────────┬───────┘    │           │
           │            │           │
  ┌────────┴───────┐    │           │
  │ engine.        │    │           │
  │ analyze_images │    │           │
  │  → dict        │    │           │
  └────────┬───────┘    │           │
           │            │           │
  ┌────────┴───────┐    │           │
  │ processor.     │    │           │
  │ embed_analysis │    │           │
  └────────┬───────┘    │           │
           │            │           │
  ┌────────┴───────┐    │           │
  │ engine.        │    │           │
  │ summarize(md)  │    │           │
  └────────┬───────┘    │           │
           │            │           │
           └────────────┴───────────┘
                        │
           ┌────────────┴────────────┐
           │  storage.save(url, ...)  │
           │  → output/{md5}.md      │
           └────────────┬────────────┘
                        │
           ┌────────────┴────────────┐
           │  finally:               │
           │    engine.close()       │
           │    scraper.close()      │
           └─────────────────────────┘
```

---

## 4. 关键设计决策

### 4.1 安全与隐私

- **发送前剥离 script/iframe/noscript/svg/style**: `processor.clean()` 在 `html_to_markdown()` 之前执行，确保敏感标签不进入 AI 上下文
- **API Key 仅通过环境变量注入**: 不硬编码，不暴露在命令行参数中

### 4.2 线程安全

- 所有 Playwright 操作和 OpenAI API 调用均为 `async/await`，无 `threading` 依赖
- `asyncio.Semaphore` 而非 `threading.Semaphore` 控制并发
- `asyncio.gather` 管理并发任务生命周期

### 4.3 错误处理策略

- **图片下载失败** → 返回 `"⚠️ 图片下载失败，无法分析"`，不中断整体流程
- **AI API 失败** → 经 3 次重试后返回 `"⚠️ AI 请求失败"`，不抛出异常
- **Playwright 异常** → 向上传播，由 `finally` 块保证资源释放
- **KeyboardInterrupt** → 优雅退出（Typer Exit(0)）

### 4.4 性能考量

- Playwright 浏览器实例复用：`_ensure_browser()` 惰性初始化，多次调用共享同一浏览器实例
- httpx.AsyncClient 复用：AIEngine 内部持有一个共享的 `httpx.AsyncClient`
- Markdown 截断：`summarize()` 取前 12000 字符发送，避免超长内容导致 token 溢出
- Output 目录惰性创建：`Storage.__init__` 中 `mkdir(parents=True, exist_ok=True)`
