import asyncio
from pathlib import Path

import markdown
from playwright.async_api import async_playwright

from app.utils.logging import get_logger


logger = get_logger(__name__)


def markdown_to_html(md: str, title: str) -> str:
    body = markdown.markdown(md)
    return f"""
    <!doctype html>
    <html>
      <head>
        <meta charset='utf-8' />
        <title>{title}</title>
        <style>
          body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 36px; color: #1e293b; }}
          h1 {{ font-size: 28px; margin-bottom: 8px; }}
          h2 {{ font-size: 18px; margin-top: 22px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }}
          li {{ margin: 8px 0; line-height: 1.45; }}
          p {{ line-height: 1.45; }}
        </style>
      </head>
      <body>{body}</body>
    </html>
    """


async def _generate_pdf_async(markdown_text: str, output_path: Path, title: str) -> None:
    html = markdown_to_html(markdown_text, title)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page()
        await page.set_content(html, wait_until="networkidle")
        await page.pdf(path=str(output_path), format="A4", print_background=True, margin={"top": "18mm", "right": "12mm", "bottom": "18mm", "left": "12mm"})
        await browser.close()


def generate_pdf(markdown_text: str, run_id: str, competitor_name: str) -> str | None:
    output_dir = Path("generated_pdfs")
    output_dir.mkdir(parents=True, exist_ok=True)
    safe_name = "".join(c for c in competitor_name if c.isalnum() or c in ["-", "_"]).strip() or "battlecard"
    output_path = output_dir / f"{safe_name}_{run_id}.pdf"

    try:
        asyncio.run(_generate_pdf_async(markdown_text, output_path, competitor_name))
        # return absolute, normalized path so callers can reliably serve the file
        return str(output_path.resolve())
    except Exception as exc:
        logger.warning("pdf generation failed run_id=%s error=%s", run_id, exc)
        return None
