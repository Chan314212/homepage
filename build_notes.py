#!/usr/bin/env python3
"""
个人主页 · 折腾笔记构建脚本
用法: python3 build_notes.py
  notes/posts/*.md  →  notes/<slug>.html (文章页)
                    →  notes/index.html   (列表页，按日期倒序)

markdown frontmatter 格式（每篇笔记开头）:
---
title: 笔记标题
date: 2026-08-19
tags: [nas, 折腾]
summary: 一句话摘要（列表页显示）
---
"""
import re
import html
from pathlib import Path
from datetime import datetime

import markdown

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "notes" / "posts"
OUT_DIR = ROOT / "notes"

# ---------- 主题样式（与主页 index.html 一致的深色 GitHub 风） ----------
BASE_CSS = """
:root {
  --bg: #0d1117; --bg-soft: #161b22; --card: #1a2029;
  --text: #e6edf3; --muted: #8b949e;
  --accent: #7ee0a3; --accent-2: #58a6ff; --border: #2d333b;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif;
  background: var(--bg); color: var(--text); line-height: 1.8;
}
.container { max-width: 760px; margin: 0 auto; padding: 0 24px; }
.topbar { padding: 28px 0 8px; }
.topbar a {
  color: var(--accent-2); text-decoration: none; font-size: .9rem;
}
.topbar a:hover { text-decoration: underline; }
header {
  padding: 48px 0 8px;
  position: relative;
  overflow: hidden;
}
header::before {
  content: ''; position: absolute; top: -80%; right: -20%;
  width: 500px; height: 500px;
  background: radial-gradient(circle, rgba(126,224,163,.10), transparent 60%);
  pointer-events: none;
}
header h1 { font-size: clamp(1.8rem, 5vw, 2.6rem); letter-spacing: .04em; }
header .meta { color: var(--muted); font-size: .88rem; margin-top: 10px; }
header .tags { margin-top: 14px; display: flex; flex-wrap: wrap; gap: 8px; }
.tag {
  font-size: .78rem; color: var(--muted);
  border: 1px solid var(--border); padding: 2px 10px; border-radius: 999px;
}
article {
  padding: 32px 0 64px;
  color: var(--text);
  font-size: 1rem;
}
article h2 { font-size: 1.35rem; margin: 32px 0 12px; padding-bottom: 8px; border-bottom: 1px solid var(--border); }
article h3 { font-size: 1.15rem; margin: 26px 0 10px; }
article h4 { font-size: 1.02rem; margin: 22px 0 8px; }
article p { margin: 12px 0; }
article a { color: var(--accent-2); text-decoration: none; }
article a:hover { text-decoration: underline; }
article ul, article ol { margin: 12px 0; padding-left: 26px; }
article li { margin: 6px 0; }
article blockquote {
  margin: 16px 0; padding: 10px 18px;
  border-left: 3px solid var(--accent);
  background: var(--bg-soft); border-radius: 0 8px 8px 0;
  color: var(--muted);
}
article code {
  background: var(--bg-soft); border: 1px solid var(--border);
  padding: 2px 6px; border-radius: 5px; font-size: .88em;
}
article pre {
  background: var(--bg-soft); border: 1px solid var(--border);
  padding: 16px 18px; border-radius: 10px; overflow-x: auto;
  margin: 16px 0;
}
article pre code { background: none; border: none; padding: 0; font-size: .86em; line-height: 1.6; }
article img { max-width: 100%; border-radius: 10px; border: 1px solid var(--border); margin: 12px 0; }
article table { border-collapse: collapse; margin: 16px 0; width: 100%; font-size: .92rem; }
article th, article td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; }
article th { background: var(--bg-soft); }
article hr { border: none; border-top: 1px solid var(--border); margin: 32px 0; }
footer {
  border-top: 1px solid var(--border);
  padding: 28px 0 56px; text-align: center;
  color: var(--muted); font-size: .85rem;
}
.filing { margin-top: 6px; }
.filing-link {
  color: var(--accent-2) !important; text-decoration: none;
  display: inline-flex; align-items: center; vertical-align: middle;
}
.filing-link:hover { color: var(--accent-2) !important; text-decoration: underline; }
"""

# 列表页卡片样式
LIST_CSS = """
.list-title { padding: 40px 0 8px; font-size: clamp(1.8rem, 5vw, 2.4rem); }
.list-sub { color: var(--muted); font-size: .92rem; margin: 10px 0 28px; }
.note-card {
  display: block; text-decoration: none;
  background: var(--card); border: 1px solid var(--border);
  border-radius: 12px; padding: 20px 24px; margin-bottom: 16px;
  transition: border-color .2s, transform .2s;
}
.note-card:hover { border-color: var(--accent); transform: translateY(-2px); }
.note-card h3 { color: var(--text); font-size: 1.08rem; }
.note-card .meta { color: var(--muted); font-size: .82rem; margin-top: 6px; }
.note-card .summary { color: var(--muted); font-size: .9rem; margin-top: 8px; }
.note-card .tags { margin-top: 10px; display: flex; gap: 8px; }
.empty { color: var(--muted); padding: 40px 0; }
"""


def parse_frontmatter(text: str):
    """解析 --- 包裹的 frontmatter，返回 (meta_dict, body)"""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if k == "tags":
                meta[k] = [t.strip() for t in v.strip("[]").split(",") if t.strip()]
            else:
                meta[k] = v
    return meta, m.group(2)


def slugify(title: str) -> str:
    """从标题生成文件名安全 slug（保留中文）"""
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", title).strip("-")
    return s or "note"


def render_article(md_text: str) -> str:
    return markdown.markdown(
        md_text,
        extensions=["fenced_code", "tables", "codehilite", "sane_lists", "nl2br"],
        extension_configs={"codehilite": {"guess_lang": False, "noclasses": True}},
    )


def build_list_page(posts):
    cards = []
    for p in posts:
        tag_html = "".join(f'<span class="tag">{html.escape(t)}</span>' for t in p["tags"])
        cards.append(f"""<a class="note-card" href="{p['file']}">
  <h3>{html.escape(p['title'])}</h3>
  <div class="meta">{p['date_display']}</div>
  <div class="summary">{html.escape(p['summary'])}</div>
  <div class="tags">{tag_html}</div>
</a>""")
    cards_html = "\n".join(cards) if cards else '<p class="empty">还没有笔记，第一篇在路上。</p>'
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>折腾笔记 · 陈鸿晖</title>
<style>{BASE_CSS}{LIST_CSS}</style>
</head>
<body>
<div class="container">
  <div class="topbar"><a href="../index.html">← 返回主页</a></div>
  <h1 class="list-title">折腾笔记</h1>
  <p class="list-sub">数码折腾、黑苹果、Linux、NAS 自托管……把搞明白的东西写下来，对抗遗忘。</p>
  {cards_html}
</div>
<footer>
  <div class="container"><p>© {datetime.now().year} 陈鸿晖 · <a href="../index.html" style="color:var(--accent-2);text-decoration:none;">主页</a></p><p class="filing"><a class="filing-link" href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">苏ICP备2026058485号-1</a> · <a class="filing-link" href="https://beian.mps.gov.cn/#/query/webSearch?code=32011402012693" target="_blank" rel="noopener">苏公网安备32011402012693号</a></p></div>
</footer>
</body>
</html>"""


def build_post_page(post):
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(post['title'])} · 陈鸿晖的折腾笔记</title>
<style>{BASE_CSS}</style>
</head>
<body>
<div class="container">
  <div class="topbar"><a href="index.html">← 返回笔记</a></div>
  <header>
    <h1>{html.escape(post['title'])}</h1>
    <div class="meta">{post['date_display']}</div>
    <div class="tags">{''.join(f'<span class="tag">{html.escape(t)}</span>' for t in post['tags'])}</div>
  </header>
  <article>
{post['body_html']}
  </article>
</div>
<footer>
  <div class="container"><p>© {datetime.now().year} 陈鸿晖 · <a href="index.html" style="color:var(--accent-2);text-decoration:none;">折腾笔记</a></p><p class="filing"><a class="filing-link" href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">苏ICP备2026058485号-1</a> · <a class="filing-link" href="https://beian.mps.gov.cn/#/query/webSearch?code=32011402012693" target="_blank" rel="noopener">苏公网安备32011402012693号</a></p></div>
</footer>
</body>
</html>"""


def main():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    posts = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        meta, body = parse_frontmatter(md_file.read_text(encoding="utf-8"))
        title = meta.get("title", md_file.stem)
        date_raw = meta.get("date", "")
        tags = meta.get("tags", [])
        summary = meta.get("summary", body.strip().replace("\n", " ")[:80])
        try:
            date_display = datetime.strptime(date_raw, "%Y-%m-%d").strftime("%Y-%m-%d")
            date_sort = date_raw
        except ValueError:
            date_display = date_raw
            date_sort = "0000-00-00"

        slug = slugify(title)
        # 避免重名覆盖：加序号
        n, candidate = 1, slug
        while any(p["slug"] == candidate for p in posts):
            n += 1
            candidate = f"{slug}-{n}"

        posts.append({
            "slug": candidate,
            "title": title,
            "date_sort": date_sort,
            "date_display": date_display,
            "tags": tags,
            "summary": summary,
            "body_html": render_article(body),
            "file": f"{candidate}.html",
        })

    # 按日期倒序
    posts.sort(key=lambda p: p["date_sort"], reverse=True)

    # 写文章页
    for p in posts:
        (OUT_DIR / p["file"]).write_text(build_post_page(p), encoding="utf-8")
        print(f"  ✓ {p['file']}  ({p['title']})")

    # 写列表页
    (OUT_DIR / "index.html").write_text(build_list_page(posts), encoding="utf-8")
    print(f"  ✓ index.html  ({len(posts)} 篇笔记)")


if __name__ == "__main__":
    main()
