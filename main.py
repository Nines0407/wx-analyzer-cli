"""wx-analyzer-cli: 微信公众号文章分析工具

使用方法:
    wx-analyzer analyze <url>                # 基础模式（仅摘要）
    wx-analyzer analyze <url> --mode deep    # 深度模式（摘要 + 图片分析）
"""

import asyncio
import sys
from pathlib import Path

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
AVAILABLE_MODES = {"base", "deep"}


@app.command()
def analyze(
    url: str = typer.Argument(..., help="微信公众号文章 URL"),
    mode: str = typer.Option(
        "base",
        "--mode",
        "-m",
        help="分析模式: base (基础摘要) | deep (深度多模态分析)",
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
    no_progress: bool = typer.Option(
        False,
        "--no-progress",
        help="关闭 Rich 进度条输出",
    ),
):
    """分析微信公众号文章，生成结构化 Markdown 报告"""
    if mode not in AVAILABLE_MODES:
        console.print(
            f"[red]错误: mode 必须为 'base' 或 'deep'，当前值: '{mode}'[/red]"
        )
        raise typer.Exit(code=1)

    config = load_config()
    if not config.api_key:
        console.print(
            "[red]错误: 未设置 DEEPSEEK_API_KEY 环境变量[/red]\n"
            "[dim]请设置: export DEEPSEEK_API_KEY=your-key[/dim]"
        )
        raise typer.Exit(code=1)

    out = output_dir.resolve() if output_dir else DEFAULT_OUTPUT_DIR.resolve()
    semaphore = asyncio.Semaphore(concurrency)
    engine = AIEngine(
        api_key=config.api_key,
        api_base=config.api_base,
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

            # Step 2: Clean & convert
            with console.status("[bold green]清洗与格式转换中..."):
                cleaned_html = processor.clean(html)
                markdown, image_anchors = processor.html_to_markdown(cleaned_html)
                markdown = processor.remove_noise(markdown)

            # Step 3: AI Analysis
            summary = ""
            if mode == "deep" and image_anchors:
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
                if mode == "deep" and not image_anchors:
                    console.print("[dim]未检测到图片，回退为基础摘要模式[/dim]")
                console.print("📝 生成全局摘要...")
                summary = await engine.summarize(markdown)

            # Step 4: Save
            metadata = {
                "source_url": url,
                "author": await scraper.get_author(),
                "publish_date": await scraper.get_publish_date(),
            }
            filepath = storage.save(
                url, title=title, summary=summary, content=markdown, metadata=metadata
            )

            console.print(
                f"💾 文章已保存至: [bold cyan]{filepath}[/bold cyan]"
            )
            console.print(
                Panel(summary or "(无摘要)", title="[bold]AI 摘要[/bold]", border_style="green")
            )

        finally:
            await engine.close()
            await scraper.close()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        console.print("\n[dim]用户中断[/dim]")
        raise typer.Exit(0)
