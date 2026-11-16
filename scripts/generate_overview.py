#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
毒舌熨心 · 心情速览卡生成器（v2.8.1）
------------------------------------------------------------
产出一张每日心情速览 PNG 图片（默认 1360×860，2x 高清），
作为毒舌熨心每日模式的稳定收尾视觉（板块六）。

与 generate_card.py 共用同一套调色板语义（card_common 单一真源）：
  --palette auto 时按 --mood-type 联动：🟢青瓷 🟡宣纸 🟠秋檀 🔴朱笺

渲染用 Pillow；字体探测 / 文本清洗复用 generate_card.py，
避免中文字体缺失导致的豆腐块。

用法：
  python generate_overview.py \
    --date "11月3日 · 星期二 · 农历九月廿五" \
    --mood-type "🟢" \
    --mood-label "正面 · 自我和解 / 健康焦虑" \
    --main "身体准备度87，早睡半小时换来一整天电量" \
    --side "拖了半年的一件事今天收尾，心里空出一块" \
    --seasoning "旧账清掉，比新开一摊更要紧" \
    --jinju-up "得失随缘莫强求" \
    --jinju-down "聚散随心少烦忧" \
    --mood-note "把旧账清干净，才算真正翻篇" \
    --output "dushe_overview.png"

输出：PNG 图片文件（--output 指定；默认 dushe_overview_YYYY-MM-DD.png）
"""

import argparse
import datetime as _dt
import os as _os
import sys as _sys

_sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))

# 配色单一真源
from card_common import MOOD_DOT, resolve_palette
# 字体 / 绘图工具复用 generate_card（同一套 CJK 探测，避免重复与豆腐块）
from generate_card import (
    Image, ImageDraw, ImageFont,
    _find_cjk_font, _safe_font, sanitize_text,
    create_gradient_bg, FONT_BOLD, FONT_REGULAR,
)

# 高清倍率（位图需 2x 保证文字清晰）
S = 2
W, H = 680 * S, 430 * S  # 1360 x 860

# 中文字体：标题加粗、正文常规（与金句卡同探测逻辑）
_FONT_TITLE = _find_cjk_font(
    ["msyh.ttc", "simhei.ttf", "NotoSansSC-Bold.ttf",
     "NotoSerifSC-Bold.ttf", "simsun.ttc"])
_FONT_BODY = _find_cjk_font(
    ["msyh.ttc", "simhei.ttf", "NotoSansSC-Regular.ttf", "simsun.ttc"])


def _fit_font(draw, text, max_w, base, min_sz, *paths):
    """在 [min_sz, base] 区间内选最大字号，使 text 宽度不超 max_w（避免横向溢出）。"""
    sz = base
    while sz >= min_sz:
        f = _safe_font(paths[0], sz, *paths[1:])
        if draw.textlength(text, font=f) <= max_w:
            return f
        sz -= 2
    return _safe_font(paths[0], min_sz, *paths[1:])


def build_image(args, pal):
    dot = MOOD_DOT.get((args.mood_type or "").strip(), "#4CAF85")
    img = create_gradient_bg(W, H, pal["bg_top"], pal["bg_bottom"])
    d = ImageDraw.Draw(img)

    def P(x, y):
        return (x * S, y * S)

    # 顶部强调条
    d.rectangle([0, 0, W, 6 * S], fill=pal["accent"])

    # 日期（标题字重）
    date_font = _safe_font(_FONT_TITLE, 26 * S, FONT_BOLD, FONT_REGULAR)
    d.text(P(40, 62), sanitize_text(args.date), font=date_font,
           fill=pal["text"], anchor="ls")

    # 心情徽章：色圆 + 标签
    cx, cy, r = 58 * S, 108 * S, 14 * S
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=dot)
    label_font = _safe_font(_FONT_BODY, 18 * S, FONT_BOLD, FONT_REGULAR)
    d.text(P(82, 114), sanitize_text(args.mood_label), font=label_font,
           fill=pal["text"], anchor="ls")

    # 分隔线
    d.line([P(40, 140), P(640, 140)], fill=pal["rule"], width=max(1, S))

    # 今日菜单三行（行首色点 + 标签 + 内容；超宽自动缩字号）
    menu = [
        ("主菜", args.main),
        ("配菜", args.side),
        ("调料", args.seasoning),
    ]
    y = 176
    for tag, val in menu:
        row = f"{tag}　{val}" if val else tag
        row = sanitize_text(row)
        f = _fit_font(d, row, (W - 40 * S - 40 * S), 16 * S, 11 * S,
                      _FONT_BODY, FONT_REGULAR)
        # 行首小色点（落在左留白内，不与文字重叠；垂直对齐文字视觉中心）
        dot_r = 5 * S
        cy_dot = y * S - 13
        d.ellipse([28 * S - dot_r, cy_dot - dot_r,
                   28 * S + dot_r, cy_dot + dot_r], fill=pal["accent"])
        d.text(P(40, y), row, font=f, fill=pal["text"], anchor="ls")
        y += 32

    # 分隔线
    d.line([P(40, 268), P(640, 268)], fill=pal["faint"], width=max(1, S))

    # 今日金句标签（字间距，逐字绘制）
    label_font = _safe_font(_FONT_BODY, 15 * S, FONT_REGULAR)
    spaced = "今　日　金　句"
    x = 40 * S
    for ch in spaced:
        d.text((x, 304 * S), ch, font=label_font, fill=pal["faint"], anchor="ls")
        x += label_font.getlength(ch) + 6 * S

    # 金句两行（标题字重）
    jf = _safe_font(_FONT_TITLE, 24 * S, FONT_BOLD, FONT_REGULAR)
    if args.jinju_up:
        d.text(P(40, 344), sanitize_text(args.jinju_up), font=jf,
               fill=pal["text"], anchor="ls")
    if args.jinju_down:
        d.text(P(40, 384), sanitize_text(args.jinju_down), font=jf,
               fill=pal["text"], anchor="ls")

    # 副文案
    if args.mood_note:
        nf = _safe_font(_FONT_BODY, 13 * S, FONT_REGULAR)
        d.text(P(40, 414), sanitize_text(args.mood_note), font=nf,
               fill=pal["faint"], anchor="ls")

    return img


def main():
    p = argparse.ArgumentParser(description="毒舌熨心心情速览卡生成器（PNG）")
    p.add_argument("--date", default="")
    p.add_argument("--mood-type", dest="mood_type", default="🟢",
                   help="心情类型 🟢🟡🟠🔴")
    p.add_argument("--mood-label", dest="mood_label", default="")
    p.add_argument("--main", default="")
    p.add_argument("--side", default="")
    p.add_argument("--seasoning", default="")
    p.add_argument("--jinju-up", dest="jinju_up", default="")
    p.add_argument("--jinju-down", dest="jinju_down", default="")
    p.add_argument("--mood-note", dest="mood_note", default="")
    p.add_argument("--palette", default="auto",
                   help="auto（按心情联动）/ xuan / yuebai / qingci / zhujian / sumo / qiutan")
    p.add_argument("--output", default="", help="输出 PNG 路径")
    args = p.parse_args()

    if not args.date:
        t = _dt.date.today()
        args.date = f"{t.year}年{t.month}月{t.day}日"

    pal = resolve_palette(args.palette, args.mood_type)
    pal_name = pal["name"]
    img = build_image(args, pal)

    out = args.output or f"dushe_overview_{_dt.date.today().isoformat()}.png"
    img.save(out, "PNG")

    if (args.palette or "").strip().lower() == "auto":
        note = f"配色：{pal_name}（心情 {args.mood_type or '未标记'} → auto 联动）"
    else:
        note = f"配色：{pal_name}"
    print(f"✅ 心情速览卡已生成: {out}　{note}（{W}x{H} PNG）")


if __name__ == "__main__":
    main()
