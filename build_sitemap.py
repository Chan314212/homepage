#!/usr/bin/env python3
"""生成 sitemap.xml（每次改完内容跑一次，或用 build_all.sh）。

收录：首页、三个列表页、以及全部折腾笔记 / 读书笔记文章页。
文章页 lastmod 取 frontmatter 里的 date，比文件 mtime 更接近真实内容时间。
"""
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

from build_notes import parse_frontmatter, slugify
from site_meta import SITE, STATIC_PAGES

ROOT = Path(__file__).resolve().parent
SECTIONS = [
    ("notes", ROOT / "notes" / "posts"),
    ("reading", ROOT / "reading" / "posts"),
]


def collect_articles():
    """返回 [(url路径, lastmod)]。"""
    items = []
    for prefix, posts_dir in SECTIONS:
        for md in sorted(posts_dir.glob("*.md")):
            meta, _ = parse_frontmatter(md.read_text(encoding="utf-8"))
            title = meta.get("title", md.stem)
            date = meta.get("date", "")
            try:
                datetime.strptime(date, "%Y-%m-%d")
            except ValueError:
                date = datetime.fromtimestamp(md.stat().st_mtime).strftime("%Y-%m-%d")
            items.append((f"/{prefix}/{slugify(title)}.html", date))
    return items


def build_xml():
    today = datetime.now().strftime("%Y-%m-%d")
    rows = []
    for path, priority, freq in STATIC_PAGES:
        rows.append(
            f"  <url>\n"
            f"    <loc>{escape(SITE + path)}</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"    <changefreq>{freq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            f"  </url>"
        )
    for path, lastmod in collect_articles():
        rows.append(
            f"  <url>\n"
            f"    <loc>{escape(SITE + path)}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>yearly</changefreq>\n"
            f"    <priority>0.6</priority>\n"
            f"  </url>"
        )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows) + "\n</urlset>\n")


def main():
    xml = build_xml()
    (ROOT / "sitemap.xml").write_text(xml, encoding="utf-8")
    n = xml.count("<url>")
    print(f"  ✓ sitemap.xml  ({n} 条 URL)")


if __name__ == "__main__":
    main()
