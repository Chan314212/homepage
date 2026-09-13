#!/usr/bin/env python3
"""构建摘抄板块：excerpts/posts/*.md -> excerpts/index.html。

摘抄条目不是独立文章页，全部渲染在同一个列表页上（每条一张卡片）。

每条 md 的 frontmatter 格式：
---
quote: 引文正文（必填）
source: 出处，如「《士兵突击》视频的评论区」
date: 2026-09-13
note: 附记，可选，一两句自己的话
---
"""
import html
from datetime import datetime
from pathlib import Path

from build_notes import BASE_CSS, parse_frontmatter
from site_meta import head_meta

ROOT = Path(__file__).resolve().parent
POSTS_DIR = ROOT / "excerpts" / "posts"
OUT_DIR = ROOT / "excerpts"

EXCERPTS_DESC = "陈鸿晖的摘抄本：把读书、看电影，或在某个偶然的时刻遇见的好句子留下来。"

EXCERPT_CSS = """
.quote-card {
  background: var(--bg-soft); border: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  border-radius: 0 12px 12px 0; padding: 24px 26px; margin: 0 0 20px;
}
.quote-card blockquote { font-size: 1.06rem; line-height: 1.9; color: var(--text); }
.quote-card .attrib { color: var(--muted); font-size: .86rem; margin-top: 14px; }
.quote-card .attrib .date { color: var(--muted); opacity: .75; margin-left: 10px; }
.quote-card .exc-note {
  color: var(--muted); font-size: .86rem; margin-top: 10px;
  padding-top: 10px; border-top: 1px dashed var(--border);
}
"""


def load_excerpts():
    items = []
    for md_file in sorted(POSTS_DIR.glob("*.md")):
        meta, body = parse_frontmatter(md_file.read_text(encoding="utf-8"))
        quote = meta.get("quote", "").strip() or body.strip()
        if not quote:
            print(f"  ! 跳过（无 quote）: {md_file.name}")
            continue
        date_raw = meta.get("date", "").strip()
        try:
            date_display = datetime.strptime(date_raw, "%Y-%m-%d").strftime("%Y-%m-%d")
        except ValueError:
            date_display = date_raw
        items.append({
            "quote": quote,
            "source": meta.get("source", "").strip(),
            "note": meta.get("note", "").strip(),
            "date": date_raw,
            "date_display": date_display,
        })
    return sorted(items, key=lambda x: x["date"], reverse=True)


def card(item):
    attrib = ""
    if item["source"]:
        attrib = f'<div class="attrib">—— {html.escape(item["source"])}'
        if item["date_display"]:
            attrib += f'<span class="date">{html.escape(item["date_display"])}</span>'
        attrib += "</div>"
    note = f'<div class="exc-note">{html.escape(item["note"])}</div>' if item["note"] else ""
    return (f'<figure class="quote-card">\n'
            f'<blockquote>{html.escape(item["quote"])}</blockquote>\n'
            f'{attrib}{note}</figure>')


def list_page(items):
    if items:
        body = "\n".join(card(i) for i in items)
    else:
        body = ('<div class="empty" style="margin-top:44px;padding:38px 26px;text-align:center;'
                'background:var(--bg-soft);border:1px solid var(--border);border-radius:12px;color:var(--muted);">'
                '<p style="color:var(--text);font-size:1.08rem;">这里暂时空着。</p>'
                '<p>以后读书、看电影，或在某个偶然的时刻遇见值得留下的话，再慢慢填进来。</p></div>')
    meta_html = head_meta("我的摘抄 · 陈鸿晖", EXCERPTS_DESC, "/excerpts/")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>我的摘抄 · 陈鸿晖</title>
{meta_html}
<style>{BASE_CSS}{EXCERPT_CSS}</style>
</head>
<body>
<div class="container">
  <div class="topbar"><a href="/">← 返回主页</a></div>
  <h1 style="padding:40px 0 8px;font-size:clamp(1.8rem,5vw,2.4rem);">我的摘抄</h1>
  <p style="color:var(--muted);font-size:.92rem;margin:10px 0 28px;">把遇见过的好句子留下来。</p>
  {body}
</div>
<footer>
  <div class="container"><p>© {datetime.now().year} 陈鸿晖 · <a href="/" style="color:var(--accent-2);text-decoration:none;">个人主页</a></p><p class="filing"><a class="filing-link" href="https://beian.miit.gov.cn/" target="_blank" rel="noopener">苏ICP备2026058485号-1</a> · <a class="filing-link" href="https://beian.mps.gov.cn/#/query/webSearch?code=32011402012693" target="_blank" rel="noopener">苏公网安备32011402012693号</a></p></div>
</footer>
</body>
</html>"""


def main():
    POSTS_DIR.mkdir(parents=True, exist_ok=True)
    items = load_excerpts()
    (OUT_DIR / "index.html").write_text(list_page(items), encoding="utf-8")
    print(f"  ✓ excerpts/index.html  ({len(items)} 条摘抄)")


if __name__ == "__main__":
    main()
