#!/usr/bin/env python3
"""
毒舌熨心 · 楹联心情卡片生成器
生成 1080×1440（3:4 竖版）转发卡片，用于无日历图片时的朋友圈分享
"""

import argparse
import json
import os
import sys
import subprocess


def _ensure_pillow():
    """
    自动检测 Pillow；缺失时通过国内镜像一键安装后再导入。
    目标：首次运行自动补齐依赖（秒级~分钟级，仅一次），
    之后每次直接命中已装版本，避免无谓的 venv 搭建与反复重试。
    """
    try:
        from PIL import Image, ImageDraw, ImageFont  # noqa: F401
        return Image, ImageDraw, ImageFont
    except ImportError:
        pass

    print("⏳ 未检测到 Pillow，正在通过国内镜像自动安装…", flush=True)
    mirrors = [
        "https://pypi.tuna.tsinghua.edu.cn/simple",
        "https://mirrors.aliyun.com/pypi/simple",
        "https://pypi.org/simple",
    ]
    last_err = None
    for idx, mirror in enumerate(mirrors, 1):
        try:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "--quiet",
                 "--disable-pip-version-check", "Pillow", "-i", mirror],
                timeout=300,
            )
            print(f"  · 镜像 {idx} 安装成功 ({mirror})", flush=True)
            from PIL import Image, ImageDraw, ImageFont  # noqa: F401
            return Image, ImageDraw, ImageFont
        except Exception as e:  # noqa: BLE001
            last_err = e
            print(f"  · 镜像 {idx} 失败: {e}", flush=True)

    sys.exit(
        f"❌ Pillow 自动安装失败（最后错误：{last_err}）。"
        f"请手动运行：{sys.executable} -m pip install Pillow"
    )


# 模块加载即确保 Pillow 可用（已装则秒过，缺失则自动装一次）
Image, ImageDraw, ImageFont = _ensure_pillow()


# ---- 跨平台中文字体探测 ----
# 解决原脚本在 Windows / 无特定字体环境下因硬编码 Linux 字体路径
# 导致 OSError 崩溃、或降级到英文点阵字体出现方块的问题。
def _find_cjk_font(preferred):
    """
    按平台精确探测中文字体文件，避免 glob 扫到非 CJK 字体导致方块。
    preferred: 当前场景偏好的字体文件名列表（越前越优先）。
    返回首个存在的绝对路径；找不到返回 None。
    """
    fallback_names = [
        "NotoSansSC-VF.ttf", "NotoSansSC-Bold.ttf", "NotoSansSC-Regular.ttf",
        "NotoSerifSC-VF.ttf", "NotoSerifSC-Bold.ttf", "NotoSerifSC-Regular.ttf",
        "NotoSerifCJK-Bold.ttc", "NotoSansCJK-Regular.ttc",
        "msyh.ttc", "msyhbd.ttc", "simhei.ttf", "simsun.ttc",
        "STHeiti Light.ttc", "STHeiti Medium.ttc",
        "PingFang.ttc", "Hiragino Sans GB.ttc",
    ]
    # 去重并保持顺序：偏好 > 兜底
    all_names = list(dict.fromkeys(preferred + fallback_names))

    if sys.platform.startswith("win"):
        bases = ["C:/Windows/Fonts"]
    elif sys.platform.startswith("linux"):
        bases = [
            "/usr/local/share/fonts/custom",
            "/usr/share/fonts/opentype/noto",
            "/usr/share/fonts/truetype/noto",
            "/usr/share/fonts",
        ]
    elif sys.platform == "darwin":
        bases = [
            "/System/Library/Fonts",
            "/Library/Fonts",
            os.path.expanduser("~/Library/Fonts"),
        ]
    else:
        bases = []

    for base in bases:
        for name in all_names:
            path = os.path.join(base, name)
            if os.path.exists(path):
                return path
    return None


def _safe_font(primary, size, *fallbacks):
    """优先用探测到的字体，依次降级，最后才用 PIL 默认（英文点阵）。"""
    for path in (primary, *fallbacks):
        if path and os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


# ==================== 可下载字体管理 ====================
# 三层优先级：显式路径 > 内置别名（自动缓存）> 系统探测字体
# 字体清单见 assets/fonts.json（全部为 OFL / 免费商用授权）

_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONT_CONFIG_PATH = os.path.join(_SKILL_DIR, "assets", "fonts.json")


def _load_font_config():
    try:
        with open(FONT_CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"fonts": [], "default": {}, "cache_dir": "~/.cache/dushe/fonts"}


FONT_CONFIG = _load_font_config()


def font_cache_dir():
    """字体缓存目录：环境变量 DUSHE_FONT_DIR 优先，其次配置，最后 ~/.cache/dushe/fonts"""
    env = os.environ.get("DUSHE_FONT_DIR")
    if env:
        return os.path.expanduser(env)
    return os.path.expanduser(FONT_CONFIG.get("cache_dir", "~/.cache/dushe/fonts"))


def _download(url, dest):
    """下载字体。优先 urllib，失败则回退 PowerShell（本机代理环境下 urllib 常失败）。"""
    tmp = dest + ".part"
    try:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
    except Exception:
        pass
    try:
        import urllib.request
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=120) as r, open(tmp, "wb") as f:
            f.write(r.read())
        if os.path.getsize(tmp) > 1024:
            os.replace(tmp, dest)
            return True
    except Exception:
        pass
    if sys.platform.startswith("win"):
        try:
            subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "$ProgressPreference='SilentlyContinue';"
                 "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12;"
                 f"Invoke-WebRequest -Uri '{url}' -OutFile '{tmp}' -TimeoutSec 300"],
                check=True, timeout=360,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if os.path.exists(tmp) and os.path.getsize(tmp) > 1024:
                os.replace(tmp, dest)
                return True
        except Exception:
            pass
    try:
        if os.path.exists(tmp):
            os.remove(tmp)
    except Exception:
        pass
    return False


def ensure_font(alias, auto_download=True):
    """按别名取字体路径。已缓存直接返回；未缓存且 auto_download=True 才下载。"""
    for f in FONT_CONFIG.get("fonts", []):
        if f.get("alias") == alias:
            path = os.path.join(font_cache_dir(), f["file"])
            if os.path.exists(path) and os.path.getsize(path) > 1024:
                return path
            if not auto_download:
                return None
            print(f"⬇️  首次使用「{f['name']}」，下载中…（约 {f.get('size_hint_mb', '?')}MB，仅此一次）", flush=True)
            if _download(f["url"], path):
                print(f"  ✅ 已缓存：{path}", flush=True)
                return path
            print("  ⚠️ 下载失败，本次回退系统字体", flush=True)
            return None
    return None


def list_fonts():
    """列出内置字体清单与本地缓存状态"""
    d = font_cache_dir()
    print(f"字体缓存目录：{d}\n")
    print(f"{'别名':<16}{'字体':<12}{'状态':<10}用途")
    print("-" * 78)
    for f in FONT_CONFIG.get("fonts", []):
        p = os.path.join(d, f["file"])
        status = "已缓存" if os.path.exists(p) and os.path.getsize(p) > 1024 else "未下载"
        print(f"{f['alias']:<16}{f['name']:<12}{status:<10}{f['use']}（{f['license']}）")
    cur = FONT_CONFIG.get("default", {})
    print(f"\n当前默认：对联={cur.get('couplet', '系统字体')}　正文={cur.get('body', '系统字体')}")


def set_default(pairs):
    """写入默认字体：--set-default couplet=mashan,body=zcool-xiaowei"""
    cur = dict(FONT_CONFIG.get("default", {}))
    for kv in pairs.split(","):
        if "=" in kv:
            k, v = kv.split("=", 1)
            cur[k.strip()] = v.strip()
    FONT_CONFIG["default"] = cur
    with open(FONT_CONFIG_PATH, "w", encoding="utf-8", newline="") as f:
        json.dump(FONT_CONFIG, f, ensure_ascii=False, indent=2)
    print(f"✅ 默认字体已写入 {FONT_CONFIG_PATH}：{cur}")


_TOFU_PROBE = "\uF8FF"  # 私用区码位，任何字体都应缺字，用于比对 tofu

# 部分设计字体（如站酷小薇）对中点类字符的 cmap 映射到"带框叉"占位字形，
# 绕过 tofu 检测却渲染成 ☒。统一替换为 U+2022（•），各字体均有正常圆点字形。
_MIDDOT_MAP = str.maketrans({
    "\u00B7": "\u2022",  # · 中点
    "\u30FB": "\u2022",  # ・ 片假名中点
    "\uFF65": "\u2022",  # ･ 半角片假名中点
})


def sanitize_text(text):
    """绘制前文本清洗：中点类字符 → U+2022"""
    return text.translate(_MIDDOT_MAP) if text else text


def font_supports_text(font, text):
    """检测字体是否覆盖 text 全部字符（缺字会渲染成豆腐块，需换字集更全的字体）"""
    try:
        tofu = font.getmask(_TOFU_PROBE, mode="1")
        tb = tofu.tobytes()
    except Exception:
        return True
    if tofu.size == (0, 0):
        return True
    for ch in text:
        try:
            m = font.getmask(ch, mode="1")
        except Exception:
            return False
        if m.size == tofu.size and m.tobytes() == tb:
            return False
    return True


def resolve_font(kind, explicit=None, alias=None, auto_download=True):
    """解析字体路径：显式路径 > 别名 > 配置默认（仅用已缓存）> 系统字体"""
    if explicit and os.path.exists(explicit):
        return explicit
    a = alias or FONT_CONFIG.get("default", {}).get(kind)
    if a:
        p = ensure_font(a, auto_download=auto_download)
        if p:
            return p
    return FONT_COUPLET if kind == "couplet" else FONT_REGULAR


# 楹联主体：隶书优先（更契合对联气质），正文用黑体/雅黑/宋体
FONT_COUPLET = _find_cjk_font(
    ["LiSu.ttf", "STLiti.ttf", "simli.ttf", "NotoSerifSC-Bold.ttf",
     "NotoSerifCJK-Bold.ttc", "simsun.ttc", "msyh.ttc"])
FONT_BOLD = _find_cjk_font(
    ["msyh.ttc", "simhei.ttf", "NotoSansSC-Bold.ttf",
     "NotoSerifSC-Bold.ttf", "simsun.ttc"])
FONT_REGULAR = _find_cjk_font(
    ["msyh.ttc", "simhei.ttf", "NotoSansSC-Regular.ttf", "simsun.ttc"])

# 卡片尺寸（3:4 竖版，朋友圈信息流不被裁切）
W, H = 1080, 1440

# 配色与心情色标统一引用 card_common（单一真源，避免多脚本各维护一份导致漂移）
import os as _os
import sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
from card_common import (
    PALETTES, MOOD_PALETTE,
    MOOD_COLORS, DEFAULT_MOOD_COLOR,
    MOOD_COLORS_DARK, DEFAULT_MOOD_COLOR_DARK,
    resolve_palette,
)


def list_palettes():
    print(f"{'别名':<12}{'配色':<8}{'深/浅':<8}底色渐变")
    print("-" * 62)
    for k, v in PALETTES.items():
        print(f"{k:<12}{v['name']:<8}{'深色' if v['dark'] else '浅色':<8}"
              f"{v['bg_top']} → {v['bg_bottom']}")
    print("\n用法：--palette auto（默认，按心情类型自动配：🟢青瓷 🟡宣纸 🟠秋檀 🔴朱笺）")
    print("　　　--palette <别名>（手动指定，仅非心情记录场景用）")
    print("　　　--bg-top <色值> --bg-bottom <色值>（自定义，覆盖方案底色）")

def hex_to_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))

def create_gradient_bg(w, h, top_color, bottom_color):
    """垂直渐变背景（小图放大，替代逐像素循环，快两个数量级且不引新依赖）"""
    grad = Image.new("RGB", (1, 2))
    grad.putpixel((0, 0), hex_to_rgb(top_color))
    grad.putpixel((0, 1), hex_to_rgb(bottom_color))
    return grad.resize((w, h), Image.BICUBIC)

def wrap_text(draw, text, font, max_width):
    """按实测像素宽度逐字断行，中英混排不溢出"""
    lines, cur = [], ""
    for ch in text:
        trial = cur + ch
        if cur and draw.textlength(trial, font=font) > max_width:
            lines.append(cur)
            cur = ch
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines

def draw_vertical(draw, text, cx, top, font, fill, gap):
    """竖排单列绘制：逐字居中于列中轴"""
    for i, ch in enumerate(text):
        bbox = draw.textbbox((0, 0), ch, font=font)
        x = cx - (bbox[2] - bbox[0]) / 2 - bbox[0]
        y = top + i * gap - bbox[1]
        draw.text((x, y), ch, font=font, fill=fill)

def draw_card(couplet_up, couplet_down, mood_line, date_label, source,
              output_path, quote="", author="", mood_type="",
              font_couplet=None, font_body=None, font_alias=None,
              palette=None, bg_top=None, bg_bottom=None):
    """
    生成楹联心情卡片（3:4 竖版，对联竖排右起）

    Args:
        couplet_up: 上联（竖排居右）
        couplet_down: 下联（竖排居左）
        mood_line: 心情解读（一行）
        date_label: 日期/节气标签
        source: 楹联出处
        output_path: 输出文件路径
        quote: 日历警句（可选）
        author: 警句作者/书名（可选）
        mood_type: 心情类型 🟢🟡🟠🔴（可选，决定色标颜色）
        font_couplet: 对联字体文件路径（可选，最高优先级）
        font_body: 正文字体文件路径（可选）
        font_alias: 内置字体别名，如 "couplet=mashan,body=zcool-xiaowei"（可选）
    """
    alias_map = {}
    if font_alias:
        for kv in font_alias.split(","):
            if "=" in kv:
                k, v = kv.split("=", 1)
                alias_map[k.strip()] = v.strip()

    couplet_path = resolve_font("couplet", font_couplet, alias_map.get("couplet"))
    body_path = resolve_font("body", font_body, alias_map.get("body"))

    couplet_up, couplet_down = sanitize_text(couplet_up), sanitize_text(couplet_down)
    mood_line, quote, author, source = sanitize_text(mood_line), sanitize_text(quote), sanitize_text(author), sanitize_text(source)
    date_label = sanitize_text(date_label)

    pal = resolve_palette(palette, mood_type, bg_top, bg_bottom)

    bg = create_gradient_bg(W, H, pal["bg_top"], pal["bg_bottom"])
    draw = ImageDraw.Draw(bg)

    # ---- 左右装饰竖线 ----
    line_color = pal["line"]
    draw.line([(80, 140), (80, H - 140)], fill=line_color, width=2)
    draw.line([(W - 80, 140), (W - 80, H - 140)], fill=line_color, width=2)

    # ---- 顶部标签 ----
    tag_font = _safe_font(body_path, 28, FONT_BOLD, FONT_REGULAR)
    tag_text = sanitize_text(f"今日一联 · {date_label}")
    tag_w = draw.textbbox((0, 0), tag_text, font=tag_font)[2]
    draw.text(((W - tag_w) / 2, 80), tag_text, fill=pal["tag"], font=tag_font)

    cursor = 150

    # ---- 日历警句 + 作者（可选） ----
    if quote:
        quote_font = _safe_font(body_path, 26, FONT_REGULAR)
        for line in wrap_text(draw, quote, quote_font, W - 240):
            lw = draw.textbbox((0, 0), line, font=quote_font)[2]
            draw.text(((W - lw) / 2, cursor), line, fill=pal["sub"], font=quote_font)
            cursor += 40
        if author:
            author_font = _safe_font(body_path, 22, FONT_REGULAR)
            a_text = f"—— {author}"
            aw = draw.textbbox((0, 0), a_text, font=author_font)[2]
            draw.text(((W - aw) / 2, cursor + 6), a_text, fill=pal["faint"], font=author_font)
            cursor += 40

    # ---- 楹联主体：竖排，上联右、下联左 ----
    couplet_top = max(cursor + 90, 380)
    max_len = max(len(couplet_up), len(couplet_down))
    couplet_size = min(64, int(620 / max(max_len, 1)))
    couplet_font = _safe_font(couplet_path, couplet_size, FONT_COUPLET, FONT_BOLD, FONT_REGULAR)
    # 缺字兜底：艺术字体字集可能不全（如马善政楷体），缺字会渲染成豆腐块，
    # 此时整体换用字集最全的思源宋体 / 系统字体，避免半副联出方块。
    if not font_supports_text(couplet_font, couplet_up + couplet_down):
        fb = ensure_font("noto-serif-sc", auto_download=False) or FONT_COUPLET
        alt = _safe_font(fb, couplet_size, FONT_COUPLET, FONT_BOLD, FONT_REGULAR)
        if font_supports_text(alt, couplet_up + couplet_down):
            couplet_font = alt
            print("  ⚠️ 对联含当前字体未覆盖的字，已自动换用字集更全的字体", flush=True)
    gap = int(couplet_size * 1.35)
    col_offset = 150
    draw_vertical(draw, couplet_up, W / 2 + col_offset, couplet_top,
                  couplet_font, pal["couplet"], gap)
    draw_vertical(draw, couplet_down, W / 2 - col_offset, couplet_top,
                  couplet_font, pal["couplet"], gap)

    couplet_bottom = couplet_top + max_len * gap

    # ---- 分隔线 + 出处 ----
    sep_y = couplet_bottom + 40
    draw.line([(200, sep_y), (W - 200, sep_y)], fill=pal["rule"], width=1)
    if source:
        source_font = _safe_font(body_path, 22, FONT_REGULAR)
        s_text = f"—— {source}"
        sw = draw.textbbox((0, 0), s_text, font=source_font)[2]
        draw.text(((W - sw) / 2, sep_y + 24), s_text, fill=pal["source"], font=source_font)

    # ---- 心情色标 + 解读 ----
    if pal["dark"]:
        mood_color = MOOD_COLORS_DARK.get(mood_type, DEFAULT_MOOD_COLOR_DARK)
    else:
        mood_color = MOOD_COLORS.get(mood_type, DEFAULT_MOOD_COLOR)
    mood_font = _safe_font(body_path, 32, FONT_BOLD, FONT_REGULAR)
    mood_lines = wrap_text(draw, mood_line, mood_font, W - 240)
    mood_start = sep_y + 110
    draw.ellipse([(W / 2 - 7, mood_start - 36), (W / 2 + 7, mood_start - 22)], fill=mood_color)
    for i, line in enumerate(mood_lines):
        lw = draw.textbbox((0, 0), line, font=mood_font)[2]
        draw.text(((W - lw) / 2, mood_start + i * 46), line, fill=pal["text"], font=mood_font)

    # ---- 底部落款 ----
    footer_font = _safe_font(body_path, 22, FONT_REGULAR)
    footer_text = sanitize_text("毒舌熨心 · 每日一联")
    fw = draw.textbbox((0, 0), footer_text, font=footer_font)[2]
    draw.text(((W - fw) / 2, H - 90), footer_text, fill=pal["footer"], font=footer_font)

    bg.save(output_path, quality=95)
    pal_name = pal.get("name", "宣纸")
    if (palette or "").strip().lower() == "auto":
        pal_note = f"配色：{pal_name}（心情 {mood_type or '未标记'} → auto 联动）"
    else:
        pal_note = f"配色：{pal_name}"
    print(f"✅ 卡片已生成: {output_path}　{pal_note}")
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="毒舌熨心楹联心情卡片生成器")
    # 注：--up/--down/--mood/--date 在下方手动校验——字体管理类命令
    # （--list-fonts / --install-font / --set-default）不需要绘图参数。
    parser.add_argument("--up", help="上联")
    parser.add_argument("--down", help="下联")
    parser.add_argument("--mood", help="心情解读")
    parser.add_argument("--date", help="日期/节气标签")
    parser.add_argument("--source", default="", help="楹联出处")
    parser.add_argument("--quote", default="", help="日历警句（可选）")
    parser.add_argument("--author", default="", help="警句作者/书名（可选）")
    parser.add_argument("--mood-type", dest="mood_type", default="", help="心情类型 🟢🟡🟠🔴（可选）")
    parser.add_argument("--output", default="dushe_card.png", help="输出路径")

    # ---- 字体（全部可选，不传则用系统字体，行为与旧版一致）----
    parser.add_argument("--font-couplet", dest="font_couplet", default="",
                        help="对联字体文件路径（.ttf/.otf，最高优先级）")
    parser.add_argument("--font-body", dest="font_body", default="",
                        help="正文字体文件路径（.ttf/.otf）")
    parser.add_argument("--font-alias", dest="font_alias", default="",
                        help='内置字体别名，如 "couplet=mashan,body=zcool-xiaowei"')
    parser.add_argument("--install-font", dest="install_font", default="",
                        help="只下载并缓存指定别名的字体，不出图")
    parser.add_argument("--set-default", dest="set_default", default="",
                        help='写入默认字体，如 "couplet=mashan,body=zcool-xiaowei"')
    parser.add_argument("--list-fonts", dest="list_fonts", action="store_true",
                        help="列出内置字体清单与缓存状态")
    parser.add_argument("--font-dir", dest="font_dir", default="",
                        help="覆盖字体缓存目录（默认 ~/.cache/dushe/fonts）")

    # ---- 配色（v2.7.1：默认 auto，按当天心情类型联动）----
    parser.add_argument("--palette", default="auto",
                        help="配色方案：auto（默认，按 --mood-type 联动）/ xuan / yuebai / qingci / "
                             "zhujian / sumo / qiutan")
    parser.add_argument("--bg-top", dest="bg_top", default="", help="自定义渐变顶色（覆盖方案底色）")
    parser.add_argument("--bg-bottom", dest="bg_bottom", default="", help="自定义渐变底色（覆盖方案底色）")
    parser.add_argument("--list-palettes", dest="list_palettes", action="store_true",
                        help="列出全部配色方案")

    args = parser.parse_args()

    if args.font_dir:
        os.environ["DUSHE_FONT_DIR"] = args.font_dir

    if args.list_palettes:
        list_palettes()
        sys.exit(0)

    # 绘图参数校验（管理类命令跳过）
    if not (args.list_fonts or args.set_default or args.install_font):
        missing = [n for n, v in (("--up", args.up), ("--down", args.down),
                                  ("--mood", args.mood), ("--date", args.date)) if not v]
        if missing:
            parser.error("缺少绘图必需参数：" + ", ".join(missing))

    if args.list_fonts:
        list_fonts()
        sys.exit(0)
    if args.set_default:
        set_default(args.set_default)
        sys.exit(0)
    if args.install_font:
        p = ensure_font(args.install_font, auto_download=True)
        print(f"✅ 已就绪：{p}" if p else f"❌ 未找到别名 {args.install_font}")
        sys.exit(0 if p else 1)

    draw_card(args.up, args.down, args.mood, args.date, args.source,
              args.output, args.quote, args.author, args.mood_type,
              args.font_couplet, args.font_body, args.font_alias,
              args.palette, args.bg_top, args.bg_bottom)
