"""wx-analyzer-cli: 微信公众号文章分析工具

使用方法:
    wx-analyzer <url>                # 自动检测模式（默认）
    wx-analyzer <url> --mode deep    # 强制深度模式
    wx-analyzer <url> --mode base    # 强制基础模式
"""

import asyncio
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel

from core.ai_engine import AIEngine
from core.config import load_config
from core.processor import ContentProcessor
from core.scraper import WechatScraper
from core.storage import Storage

app = typer.Typer(help="微信公众号文章分析工具 🛠️")
console = Console()

DEFAULT_OUTPUT_DIR = Path.cwd() / "output"
AVAILABLE_MODES = {"auto", "base", "deep"}


@app.command()
def analyze(
    url: str = typer.Argument(..., help="微信公众号文章 URL"),
    mode: str = typer.Option(
        "auto",
        "--mode",
        "-m",
        help="分析模式: auto (自动检测) | base (基础摘要) | deep (深度多模态分析)",
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
        help="Deep 模式下图片并发分析数 (默认 5)",
    ),
):
    """分析微信公众号文章，生成结构化 Markdown 报告"""
    if mode not in AVAILABLE_MODES:
        console.print(
            f"[red]错误: mode 必须为 'auto'、'base' 或 'deep'，当前值: '{mode}'[/red]"
        )
        raise typer.Exit(code=1)

    config = load_config()

    # ── 文本模型验证（所有模式必需）──
    text_key = config.text_api_key or config.api_key
    if not text_key:
        console.print(
            "[red]错误: 未设置文本模型 API 密钥[/red]\n"
            "[dim]请设置 TEXT_API_KEY 或 API_KEY 或 DEEPSEEK_API_KEY[/dim]"
        )
        raise typer.Exit(code=1)

    if not config.text_model:
        console.print(
            "[red]错误: 未设置文本模型名称[/red]\n"
            "[dim]请设置: export TEXT_MODEL=model-name[/dim]"
        )
        raise typer.Exit(code=1)

    out = output_dir.resolve() if output_dir else DEFAULT_OUTPUT_DIR.resolve()
    semaphore = asyncio.Semaphore(concurrency)
    engine = AIEngine(
        config=config,
        semaphore=semaphore,
    )
    scraper = WechatScraper(config=config)
    processor = ContentProcessor()
    storage = Storage(output_dir=out)

    async def _run():
        try:
            # Step 1: Scrape
            with console.status("[bold green]正在抓取文章..."):
                html = await scraper.scrape(url)
                title = await scraper.get_title()
            console.print(f"✅ 文章抓取完成: [bold]{title}[/bold]")

            # Step 2: Auto-detect mode & extract video info
            effective_mode = mode
            video_urls: list[str] = []
            if mode == "auto":
                has_media = processor.detect_media_from_html(html)
                effective_mode = "deep" if has_media else "base"
                mode_label = "深度分析 (检测到多媒体)" if has_media else "基础摘要 (未检测到多媒体)"
                console.print(f"🔍 自动检测模式 → [bold]{mode_label}[/bold]")
            if effective_mode == "deep":
                video_urls = processor.extract_video_urls(html)

            # Step 3: Clean & convert
            with console.status("[bold green]清洗与格式转换中..."):
                cleaned_html = processor.clean(html)
                markdown, image_anchors = processor.html_to_markdown(cleaned_html)
                markdown = processor.remove_noise(markdown)

            # Step 4: AI Analysis
            summary = ""
            do_deep = effective_mode == "deep" and image_anchors
            if do_deep:
                vision_key = config.vision_api_key or config.api_key
                if not vision_key or not config.vision_model:
                    console.print(
                        "[yellow]⚠️  未配置视觉模型，回退为基础摘要模式[/yellow]"
                    )
                    do_deep = False

            if do_deep:
                console.print(
                    f"🖼️  检测到 [bold]{len(image_anchors)}[/bold] 张图片，启动深度分析..."
                )
                image_items = processor.extract_images_with_context(
                    markdown, image_anchors
                )
                analyses = await engine.analyze_images(image_items)
                markdown = processor.embed_analysis(markdown, analyses)
                console.print("📝 图片分析完成，生成全局摘要...")
                summary = await engine.summarize(markdown)
            else:
                if effective_mode == "deep" and not image_anchors:
                    console.print("[dim]未检测到图片，回退为基础摘要模式[/dim]")
                console.print("📝 生成全局摘要...")
                summary = await engine.summarize(markdown)

            # Step 5: Save
            metadata = {
                "source_url": url,
                "author": await scraper.get_author(),
                "publish_date": await scraper.get_publish_date(),
            }
            console.print("💾 下载媒体资源并保存...")
            filepath = await storage.save(
                url,
                title=title,
                summary=summary,
                content=markdown,
                metadata=metadata,
                image_anchors=image_anchors,
                video_urls=video_urls,
            )

            console.print(
                f"💾 文章已保存至: [bold cyan]{filepath}[/bold cyan]"
            )
            console.print(
                Panel(summary or "(无摘要)", title="[bold]AI 摘要[/bold]", border_style="green")
            )

        finally:
            for closer in (engine.close, scraper.close, storage.close):
                try:
                    await closer()
                except Exception:
                    pass

    asyncio.run(_run())


if __name__ == "__main__":
    app()
