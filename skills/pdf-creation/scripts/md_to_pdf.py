#!/usr/bin/env python3
"""Markdown → PDF (weasyprint) or HTML fallback for browser print."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def md_to_html(md: str, title: str) -> str:
    try:
        import markdown  # type: ignore

        body = markdown.markdown(
            md,
            extensions=["fenced_code", "tables", "toc"],
        )
    except ImportError:
        # Minimal escape hatch — preformatted
        escaped = (
            md.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        body = f"<pre>{escaped}</pre>"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<title>{title}</title>
<style>
  body {{ font-family: DejaVu Sans, sans-serif; margin: 1in; line-height: 1.45; }}
  code, pre {{ font-family: DejaVu Sans Mono, monospace; font-size: 0.9em; }}
  pre {{ background: #f4f4f4; padding: 0.75em; overflow-x: auto; }}
  h1, h2, h3 {{ page-break-after: avoid; }}
  table {{ border-collapse: collapse; width: 100%; }}
  th, td {{ border: 1px solid #ccc; padding: 0.35em 0.5em; }}
</style>
</head>
<body>
{body}
</body>
</html>
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("src", type=Path, help="Input .md")
    p.add_argument("out", type=Path, help="Output .pdf (or .html if PDF engine missing)")
    args = p.parse_args()

    if not args.src.is_file():
        print(f"error: missing {args.src}", file=sys.stderr)
        return 1

    md = args.src.read_text(encoding="utf-8")
    title = args.src.stem
    for line in md.splitlines():
        if line.startswith("# "):
            title = line[2:].strip()
            break

    html = md_to_html(md, title)
    args.out.parent.mkdir(parents=True, exist_ok=True)

    try:
        from weasyprint import HTML  # type: ignore

        HTML(string=html, base_url=str(args.src.parent)).write_pdf(args.out)
        print(f"wrote {args.out}")
        return 0
    except ImportError:
        html_path = args.out.with_suffix(".html")
        html_path.write_text(html, encoding="utf-8")
        print(
            f"weasyprint not installed; wrote {html_path}\n"
            "Install: pip install weasyprint markdown\n"
            "Or open the HTML and Print → Save as PDF.",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
