"""wx-analyzer-cli: 微信公众号文章分析工具

使用方法:
    wx-analyzer <url>                    # 单篇分析
    wx-analyzer --file urls.txt -w 3     # 批量分析，3 篇并行
"""

import asyncio
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

import typer
from rich.console import Console
from rich.panel import Panel

from core.ai_engine import AIEngine
from core.config import Config, load_config
from core.processor import ContentProcessor
from core.scraper import WechatScraper
from core.storage import Storage

app = typer.Typer(help="微信公众号文章分析工具 🛠️")
console = Console()

DEFAULT_OUTPUT_DIR = Path.cwd() / "output"
AVAILABLE_MODES = {"auto", "base", "deep"}


def _read_urls(filepath: Path) -> list[str]:
    urls: list[str] = []
    for line in filepath.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)
    return urls


async def _process_one(
    url: str,
    mode: str,
    output_dir: Path,
    image_concurrency: int,
    config: Config,
    index: int,
    total: int,
) -> None:
    label = f"[{index}/{total}]" if total > 1 else ""
    semaphore = asyncio.Semaphore(image_concurrency)
    engine = AIEngine(config=config, semaphore=semaphore)
    scraper = WechatScraper(config=config)
    processor = ContentProcessor()
    storage = Storage(output_dir=output_dir)

    try:
        with console.status(f"[bold green]{label} 抓取: {url[:60]}..."):
            html = await scraper.scrape(url)
            title = await scraper.get_title()
        console.print(f"✅ {label} [bold]{title}[/bold]")

        effective_mode = mode
        video_urls: list[str] = []
        if mode == "auto":
            has_media = processor.detect_media_from_html(html)
            effective_mode = "deep" if has_media else "base"
            tag = "深度" if has_media else "基础"
            console.print(f"🔍 {label} 自动检测 → [bold]{tag}分析[/bold]")
        if effective_mode == "deep":
            video_urls = processor.extract_video_urls(html)

        cleaned_html = processor.clean(html)
        markdown, image_anchors = processor.html_to_markdown(cleaned_html)
        markdown = processor.remove_noise(markdown)

        summary = ""
        do_deep = effective_mode == "deep" and image_anchors
        if do_deep:
            vision_key = config.vision_api_key or config.api_key
            if not vision_key or not config.vision_model:
                console.print(f"[yellow]⚠️  {label} 未配置视觉模型，回退为基础摘要[/yellow]")
                do_deep = False

        if do_deep:
            console.print(f"🖼️  {label} 检测到 [bold]{len(image_anchors)}[/bold] 张图片，深度分析...")
            image_items = processor.extract_images_with_context(markdown, image_anchors)
            analyses = await engine.analyze_images(image_items)
            markdown = processor.embed_analysis(markdown, analyses)
            console.print(f"📝 {label} 图片分析完成，生成摘要...")
            summary = await engine.summarize(markdown)
        else:
            console.print(f"📝 {label} 生成摘要...")
            summary = await engine.summarize(markdown)

        metadata = {
            "source_url": url,
            "author": await scraper.get_author(),
            "publish_date": await scraper.get_publish_date(),
        }
        article_dir = await storage.save(
            url,
            title=title,
            summary=summary,
            content=markdown,
            metadata=metadata,
            image_anchors=image_anchors,
            video_urls=video_urls,
        )
        console.print(f"💾 {label} [bold cyan]{article_dir / 'summary.md'}[/bold cyan]")

    except Exception as exc:
        console.print(f"[red]❌ {label} 失败: {exc}[/red]")
    finally:
        for closer in (engine.close, scraper.close, storage.close):
            try:
                await closer()
            except Exception:
                pass


@app.command()
def analyze(
    url: str | None = typer.Argument(None, help="微信公众号文章 URL"),
    file: Path | None = typer.Option(
        None, "--file", "-f", help="包含 URL 列表的文件（每行一个，# 开头跳过）"
    ),
    mode: str = typer.Option(
        "auto",
        "--mode",
        "-m",
        help="分析模式: auto | base | deep",
    ),
    output_dir: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="输出目录，默认 ./output/",
    ),
    concurrency: int = typer.Option(
        5,
        "--concurrency",
        "-c",
        min=1,
        max=20,
        help="单篇文章内图片并发数 (默认 5)",
    ),
    workers: int = typer.Option(
        1,
        "--workers",
        "-w",
        min=1,
        max=10,
        help="并行处理的文章数 (默认 1)",
    ),
):
    """分析微信公众号文章，生成结构化 Markdown 报告"""
    if not url and not file:
        console.print("[red]错误: 请提供 URL 或使用 --file 指定 URL 列表文件[/red]")
        raise typer.Exit(code=1)
    if url and file:
        console.print("[red]错误: URL 和 --file 不能同时使用[/red]")
        raise typer.Exit(code=1)
    if mode not in AVAILABLE_MODES:
        console.print(f"[red]错误: mode 必须为 'auto'、'base' 或 'deep'，当前值: '{mode}'[/red]")
        raise typer.Exit(code=1)

    config = load_config()
    text_key = config.text_api_key or config.api_key
    if not text_key:
        console.print("[red]错误: 未设置文本模型 API 密钥[/red]")
        raise typer.Exit(code=1)
    if not config.text_model:
        console.print("[red]错误: 未设置文本模型名称[/red]")
        raise typer.Exit(code=1)

    out = output_dir.resolve() if output_dir else DEFAULT_OUTPUT_DIR.resolve()

    urls = [url] if url else _read_urls(file)
    if not urls:
        console.print("[red]错误: 文件中没有可处理的 URL[/red]")
        raise typer.Exit(code=1)

    console.print(f"📋 共 {len(urls)} 篇文章，并行数: {workers}")

    async def _run():
        sem = asyncio.Semaphore(workers)

        async def _worker(u: str, idx: int):
            async with sem:
                await _process_one(u, mode, out, concurrency, config, idx, len(urls))

        tasks = [_worker(u, i + 1) for i, u in enumerate(urls)]
        await asyncio.gather(*tasks)

    asyncio.run(_run())


if __name__ == "__main__":
    app()
