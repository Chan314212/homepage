#!/usr/bin/env python3
"""构建读书笔记板块：reading/posts/*.md -> reading/*.html。"""
import html
import re
from datetime import datetime
from pathlib import Path

from build_notes import BASE_CSS, LIST_CSS, parse_frontmatter, render_article, slugify

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "reading" / "posts"
OUT_DIR = ROOT / "reading"


def load_posts():
    posts = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        meta, body = parse_frontmatter(md_file.read_text(encoding="utf-8"))
        title = meta.get("title", md_file.stem)
        date_raw = meta.get("date", "")
        try:
            date_display = datetime.strptime(date_raw, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            date_display = date_raw
        slug = slugify(title)
        posts.append({
            "title": title,
            "date": date_raw,
            "date_display": date_display,
            "tags": meta.get("tags", []),
            "summary": meta.get("summary", ""),
            "body_html": render_article(body),
            "file": f"{slug}.html",
        })
    return sorted(posts, key=lambda p: p["date"], reverse=True)


def article_page(post):
    tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in post["tags"])
    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(post["title"])} · 陈鸿晖的读书笔记</title><style>{BASE_CSS}</style></head>
<body><div class="container">
<div class="topbar"><a href="index.html">← 返回读书笔记</a></div>
<header><h1>{html.escape(post["title"])}</h1><div class="meta">{post["date_display"]}</div><div class="tags">{tags}</div></header>
<article>{post["body_html"]}</article>
</div><footer><div class="container"><p>© {datetime.now().year} 陈鸿晖 · <a href="../index.html" style="color:var(--accent-2);text-decoration:none;">个人主页</a></p></div></footer>
</body></html>'''


def list_page(posts):
    cards = []
    for p in posts:
        tags = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in p["tags"])
        cards.append(f'''<a class="note-card" href="{p["file"]}">
<h3>{html.escape(p["title"])}</h3><div class="meta">{p["date_display"]}</div>
<div class="summary">{html.escape(p["summary"])}</div><div class="tags">{tags}</div></a>''')
    cards_html = "\n".join(cards) or '<p class="empty">还没有读书笔记。</p>'
    return f'''<!DOCTYPE html>
<html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>读书笔记 · 陈鸿晖</title><style>{BASE_CSS}{LIST_CSS}</style></head>
<body><div class="container"><div class="topbar"><a href="../index.html">← 返回主页</a></div>
<h1 class="list-title">读书笔记</h1><p class="list-sub">记下读到某处时，心里被翻动的东西。</p>{cards_html}
</div><footer><div class="container"><p>© {datetime.now().year} 陈鸿晖 · <a href="../index.html" style="color:var(--accent-2);text-decoration:none;">主页</a></p></div></footer>
</body></html>'''


def main():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    posts = load_posts()
    for old in OUT_DIR.glob("*.html"):
        old.unlink()
    for post in posts:
        (OUT_DIR / post["file"]).write_text(article_page(post), encoding="utf-8")
        print(f'  ✓ {post["file"]}  ({post["title"]})')
    (OUT_DIR / "index.html").write_text(list_page(posts), encoding="utf-8")
    print(f"  ✓ reading/index.html  ({len(posts)} 篇读书笔记)")


if __name__ == "__main__":
    main()
