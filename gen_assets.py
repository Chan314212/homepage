#!/usr/bin/env python3
"""生成站点图标与社交分享图。

产物（全部写进 assets/ 和站点根目录）：
  favicon.svg                     矢量图标（浏览器标签页优先用）
  favicon.ico                     16/32/48 多尺寸（旧浏览器与根路径探测）
  assets/favicon-32.png           32×32
  assets/favicon-192.png          192×192（Android 主屏）
  assets/apple-touch-icon.png     180×180（iOS 主屏，用头像方图）
  assets/og-image.png             1200×630 微信/QQ/X/Telegram 分享预览图

用法: python3 gen_assets.py
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"

BG = (13, 17, 23)
BG_SOFT = (22, 27, 34)
TEXT = (230, 237, 243)
MUTED = (139, 148, 158)
ACCENT = (126, 224, 163)
ACCENT2 = (88, 166, 255)

CN_FONT = "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf"
LATIN_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
LATIN_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def is_cjk(ch: str) -> bool:
    o = ord(ch)
    return (0x3000 <= o <= 0x9FFF) or (0xFF00 <= o <= 0xFFEF) or (0x20000 <= o <= 0x2FFFF)


def mixed_font(latin_path: str, cn_size: int, latin_size: int | None = None):
    """中英混排：数字/拉丁走 DejaVu，汉字走 Droid，避免缺字形变方框。"""
    latin_size = latin_size or cn_size
    cn = ImageFont.truetype(CN_FONT, cn_size)
    la = ImageFont.truetype(latin_path, latin_size)
    return cn, la


def text_width(draw, text, cn, la):
    return sum(draw.textlength(ch, font=(cn if is_cjk(ch) else la)) for ch in text)


def draw_text(draw, pos, text, cn, la, fill):
    """逐字选择字体绘制（不用 anchor，需自己居中）。返回绘制结束的 x。"""
    x, y = pos
    for ch in text:
        f = cn if is_cjk(ch) else la
        draw.text((x, y), ch, font=f, fill=fill)
        x += draw.textlength(ch, font=f)
    return x


def draw_text_center(draw, cx, y, text, cn, la, fill):
    w = text_width(draw, text, cn, la)
    draw_text(draw, (cx - w / 2, y), text, cn, la, fill)


def measure(draw, text, cn, la):
    bbox = None
    for ch in text:
        f = cn if is_cjk(ch) else la
        b = draw.textbbox((0, 0), ch, font=f)
        bbox = b if bbox is None else (min(bbox[0], b[0]), min(bbox[1], b[1]),
                                       max(bbox[2], b[2]), max(bbox[3], b[3]))
    return bbox


# --------------------------------------------------------------------------
# favicon：深底圆角 + 绿色 H（几何绘制，32px 下依然锐利；中文在 16px 会糊）
# --------------------------------------------------------------------------
def h_icon(size: int, bg=BG_SOFT, fg=ACCENT) -> Image.Image:
    scale = 8  # 超采样后缩小，边缘平滑
    s = size * scale
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, s - 1, s - 1], radius=int(s * 0.22), fill=bg)

    # H：两根竖条 + 一横，按 32 网格比例取值
    u = s / 32.0
    bar = 3.4 * u
    stroke = 3.4 * u
    d.rectangle([9.0 * u, 8.0 * u, 9.0 * u + bar, 24.0 * u], fill=fg)
    d.rectangle([19.6 * u, 8.0 * u, 19.6 * u + bar, 24.0 * u], fill=fg)
    d.rectangle([9.0 * u, 14.3 * u, 19.6 * u + bar, 14.3 * u + stroke], fill=fg)
    return img.resize((size, size), Image.LANCZOS)


def favicon_svg() -> str:
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">
  <rect width="32" height="32" rx="7" fill="#161b22"/>
  <g fill="#7ee0a3">
    <rect x="9" y="8" width="3.4" height="16"/>
    <rect x="19.6" y="8" width="3.4" height="16"/>
    <rect x="9" y="14.3" width="14" height="3.4"/>
  </g>
</svg>
"""


def make_apple_touch(avatar: Image.Image) -> Image.Image:
    """iOS 主屏图标：不能用透明，用深底 + 头像圆形裁切 + 绿描边（4x 超采样）。"""
    size = 180
    ss = 4
    S = size * ss
    canvas = Image.new("RGB", (S, S), BG)
    d = ImageDraw.Draw(canvas)
    # 细密同心圆装饰，避免大面积纯色
    for i in range(6, 0, -1):
        r = int(S * 0.34 + i * S * 0.09)
        d.ellipse([S // 2 - r, S // 2 - r, S // 2 + r, S // 2 + r],
                  outline=(30, 38, 46), width=ss)

    a = avatar.convert("RGB")
    side = min(a.size)
    a = a.crop(((a.width - side) // 2, (a.height - side) // 2,
                (a.width + side) // 2, (a.height + side) // 2))
    inner = int(S * 0.74)
    a = a.resize((inner, inner), Image.LANCZOS)
    mask = Image.new("L", (inner, inner), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, inner - 1, inner - 1], fill=255)
    off = (S - inner) // 2
    canvas.paste(a, (off, off), mask)
    ImageDraw.Draw(canvas).ellipse(
        [off - 2 * ss, off - 2 * ss, off + inner + 2 * ss - 1, off + inner + 2 * ss - 1],
        outline=ACCENT, width=3 * ss)
    return canvas.resize((size, size), Image.LANCZOS)


# --------------------------------------------------------------------------
# OG 分享图 1200×630（微信/QQ/X/Telegram 通用比例 1.91:1）
# --------------------------------------------------------------------------
def make_og(avatar: Image.Image) -> Image.Image:
    W, H = 1200, 630
    canvas = Image.new("RGB", (W, H), BG)

    # 柔光：两张模糊圆叠加，模拟首页 hero 的径向渐变
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse([W - 260, -240, W + 240, 260], fill=(126, 224, 163, 78))
    gd.ellipse([-220, H - 300, 260, H + 200], fill=(88, 166, 255, 70))
    glow = glow.filter(ImageFilter.GaussianBlur(90))
    canvas = Image.alpha_composite(canvas.convert("RGBA"), glow).convert("RGB")

    d = ImageDraw.Draw(canvas)

    # 头像
    av = avatar.convert("RGB")
    side = min(av.size)
    av = av.crop(((av.width - side) // 2, (av.height - side) // 2,
                  (av.width + side) // 2, (av.height + side) // 2))
    av_size = 176
    av = av.resize((av_size, av_size), Image.LANCZOS)
    mask = Image.new("L", (av_size, av_size), 0)
    ImageDraw.Draw(mask).ellipse([0, 0, av_size - 1, av_size - 1], fill=255)
    ax, ay = (W - av_size) // 2, 100
    canvas.paste(av, (ax, ay), mask)
    d.ellipse([ax - 5, ay - 5, ax + av_size + 4, ay + av_size + 4], outline=ACCENT, width=4)

    # 姓名
    cn_n, la_n = mixed_font(LATIN_BOLD, 76)
    draw_text_center(d, W / 2, 312, "陈鸿晖", cn_n, la_n, TEXT)

    # 定位说明
    cn_t, la_t = mixed_font(LATIN_FONT, 32)
    tagline = "物理学出身 · 半导体方案工程师 · 数码折腾党"
    draw_text_center(d, W / 2, 428, tagline, cn_t, la_t, ACCENT)

    # 分隔细线
    d.rectangle([W / 2 - 40, 496, W / 2 + 40, 498], fill=(45, 51, 59))

    # 网址
    cn_u, la_u = mixed_font(LATIN_FONT, 26)
    draw_text_center(d, W / 2, 528, "huey314.online", cn_u, la_u, MUTED)

    return canvas


def main():
    ASSETS.mkdir(exist_ok=True)

    avatar_path = ASSETS / "avatar.png"
    if not avatar_path.exists():
        raise SystemExit(f"缺少头像文件：{avatar_path}")
    avatar = Image.open(avatar_path)

    # favicon.svg
    (ROOT / "favicon.svg").write_text(favicon_svg(), encoding="utf-8")

    # favicon-32 / 192
    h_icon(32).save(ASSETS / "favicon-32.png")
    h_icon(192).save(ASSETS / "favicon-192.png")

    # favicon.ico（多尺寸）
    ico = h_icon(48)
    ico.save(ROOT / "favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])

    # apple-touch-icon
    make_apple_touch(avatar).save(ASSETS / "apple-touch-icon.png")

    # og-image
    og = make_og(avatar)
    og.save(ASSETS / "og-image.png", optimize=True)

    for f in ["favicon.ico", "favicon.svg", "assets/favicon-32.png",
              "assets/favicon-192.png", "assets/apple-touch-icon.png",
              "assets/og-image.png"]:
        p = ROOT / f
        print(f"  ✓ {f}  ({p.stat().st_size / 1024:.1f} KB)")


if __name__ == "__main__":
    main()
