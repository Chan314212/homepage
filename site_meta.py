#!/usr/bin/env python3
"""站点级元信息（SEO / 社交分享）统一生成。

所有页面模板都从这里取 head_meta()，保证四类页面（主页、折腾笔记、读书笔记、
摘抄）的 OG / Twitter Card / canonical / favicon 引用完全一致；改一处即全站生效。
"""
import html
from urllib.parse import quote

SITE = "https://huey314.online"
SITE_NAME = "陈鸿晖"
OG_IMAGE = f"{SITE}/assets/og-image.png"
OG_IMAGE_W, OG_IMAGE_H = 1200, 630
THEME_COLOR = "#0d1117"

HOME_DESC = ("陈鸿晖的个人主页：物理学出身，在南京做半导体 FIB 切片方案工程师。"
             "这里记录折腾笔记、读书笔记与摘抄——刷机、黑苹果、NAS 自托管、骑行与阅读。")


def _e(s: str) -> str:
    return html.escape(s, quote=True)


def head_meta(title: str, description: str, path: str,
              og_type: str = "website", published: str | None = None,
              tags: list[str] | None = None) -> str:
    """返回 head 内的元信息标签块。

    title       页面标题（与 <title> 保持一致）
    description 页面描述，用于搜索结果与分享摘要
    path        以 / 开头的站内路径，如 "/"、"/notes/"、"/notes/xxx.html"
    og_type     "website"（列表/首页）或 "article"（文章页）
    published   文章页发布日期 YYYY-MM-DD
    tags        文章页标签（作为 article:tag）
    """
    # 中文文件名必须百分号编码：EdgeOne 只认编码后的路径，未编码的中文 URL 直接 404，
    # 而爬虫（百度/搜狗）按 sitemap 里的原始中文 URL 抓取会全部落空。
    url = f"{SITE}{quote(path, safe='/-._~')}"
    lines = [
        f'<meta name="description" content="{_e(description)}">',
        f'<link rel="canonical" href="{url}">',
        f'<meta name="theme-color" content="{THEME_COLOR}">',
        '<link rel="icon" href="/favicon.ico" sizes="any">',
        '<link rel="icon" type="image/svg+xml" href="/favicon.svg">',
        '<link rel="icon" type="image/png" sizes="32x32" href="/assets/favicon-32.png">',
        '<link rel="apple-touch-icon" href="/assets/apple-touch-icon.png">',
        f'<meta property="og:site_name" content="{_e(SITE_NAME)}">',
        f'<meta property="og:type" content="{og_type}">',
        f'<meta property="og:locale" content="zh_CN">',
        f'<meta property="og:title" content="{_e(title)}">',
        f'<meta property="og:description" content="{_e(description)}">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:image" content="{OG_IMAGE}">',
        f'<meta property="og:image:width" content="{OG_IMAGE_W}">',
        f'<meta property="og:image:height" content="{OG_IMAGE_H}">',
        f'<meta property="og:image:alt" content="{_e(SITE_NAME)} · 个人主页">',
        # 老派社交爬虫兼容：微信 / QQ 的部分版本不读 og:image，只认这两个
        f'<link rel="image_src" href="{OG_IMAGE}">',
        f'<meta itemprop="image" content="{OG_IMAGE}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{_e(title)}">',
        f'<meta name="twitter:description" content="{_e(description)}">',
        f'<meta name="twitter:image" content="{OG_IMAGE}">',
    ]
    if og_type == "article" and published:
        lines.append(f'<meta property="article:published_time" content="{published}">')
        for t in (tags or []):
            lines.append(f'<meta property="article:tag" content="{_e(t)}">')
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 站点地图
# ---------------------------------------------------------------------------
# 每个条目：(路径, 优先级, 变更频率)。文章页由 build_sitemap.py 自动追加。
STATIC_PAGES = [
    ("/", "1.0", "weekly"),
    ("/notes/", "0.8", "weekly"),
    ("/reading/", "0.7", "monthly"),
    ("/excerpts/", "0.5", "monthly"),
    ("/home/", "0.6", "monthly"),
]
