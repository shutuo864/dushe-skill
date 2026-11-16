#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
毒舌熨心 · 卡片配色与心情色标 · 公共模块（v2.8.0）
============================================================

这是所有卡片脚本（generate_card.py / generate_overview.py）的**唯一配色真源**。
此前的版本里，两个脚本各自维护了一份 PALETTES / MOOD_PALETTE / resolve_palette，
字段不一致（速览卡缺 rule/couplet/dark，resolve 签名也不同），属于典型的"漂移"。

本模块把配色、心情联动、心情色标全部收口到这里，脚本只负责排版与输出：

    from card_common import (
        PALETTES, MOOD_PALETTE,
        MOOD_COLORS, DEFAULT_MOOD_COLOR,
        MOOD_COLORS_DARK, DEFAULT_MOOD_COLOR_DARK,
        MOOD_DOT, resolve_palette,
    )

调色板字段约定（每套必须整组定义，否则深底配深字会糊）：
    bg_top/bg_bottom 渐变底色；couplet 对联；text 正文；sub 副文/警句；
    faint 淡字/作者；source 出处；tag 顶部标签；footer 落款；
    line 边框竖线；rule 分隔横线；accent 强调色（速览卡 top bar）；
    dark 是否深色底（用于决定心情色标提亮）
"""

# ==================== 配色方案 ====================
# 注意：accent 与 tag 同色，供速览卡 top bar 使用，避免重复定义两套色值。
PALETTES = {
    "xuan": {  # 宣纸（默认，暖米色）
        "name": "宣纸", "dark": False,
        "bg_top": "#FFF8EC", "bg_bottom": "#F5E6D3",
        "couplet": "#5C3D2E", "text": "#6B4F3A", "sub": "#9C8368",
        "faint": "#B09A7E", "source": "#A0845C", "tag": "#8B6F47",
        "footer": "#B8A088", "line": "#C4A882", "rule": "#D4C4A8",
        "accent": "#8B6F47",
    },
    "yuebai": {  # 月白（清冷灰白）
        "name": "月白", "dark": False,
        "bg_top": "#FBFCFD", "bg_bottom": "#E9EEF3",
        "couplet": "#2F3A45", "text": "#3D4A57", "sub": "#6B7A88",
        "faint": "#8B98A5", "source": "#7A8896", "tag": "#5A6875",
        "footer": "#96A3AF", "line": "#B6C2CC", "rule": "#C8D2DA",
        "accent": "#5A6875",
    },
    "qingci": {  # 青瓷（淡青绿）
        "name": "青瓷", "dark": False,
        "bg_top": "#F3F8F6", "bg_bottom": "#DCE9E3",
        "couplet": "#22483C", "text": "#31544A", "sub": "#5D8074",
        "faint": "#7C9A8E", "source": "#6B8C7F", "tag": "#3E6659",
        "footer": "#8AA79B", "line": "#A3BEB1", "rule": "#B8CFC4",
        "accent": "#3E6659",
    },
    "zhujian": {  # 朱笺（暖粉笺，节庆/喜事）
        "name": "朱笺", "dark": False,
        "bg_top": "#FFF5F1", "bg_bottom": "#F8DED5",
        "couplet": "#7A2E28", "text": "#8A4038", "sub": "#A97066",
        "faint": "#BE8B80", "source": "#B07F73", "tag": "#96544A",
        "footer": "#C49A8E", "line": "#D9AEA2", "rule": "#E5C3B8",
        "accent": "#96544A",
    },
    "sumo": {  # 素墨（深墨，夜色庄重）
        "name": "素墨", "dark": True,
        "bg_top": "#2C2C2E", "bg_bottom": "#17171A",
        "couplet": "#F0E4D0", "text": "#E2D7C6", "sub": "#B2A791",
        "faint": "#948A76", "source": "#A2977F", "tag": "#C8BCA4",
        "footer": "#7E7461", "line": "#5C564A", "rule": "#4A453C",
        "accent": "#C8BCA4",
    },
    "qiutan": {  # 秋檀（深棕暖调）
        "name": "秋檀", "dark": True,
        "bg_top": "#3B2A20", "bg_bottom": "#221813",
        "couplet": "#F5E7D3", "text": "#E8D9C2", "sub": "#BFA88C",
        "faint": "#A08A6E", "source": "#B1997C", "tag": "#D2BFA4",
        "footer": "#8E7A5F", "line": "#7A6248", "rule": "#654F3A",
        "accent": "#D2BFA4",
    },
}

# 心情类型 → 建议配色（--palette auto 时使用）
MOOD_PALETTE = {
    "green": "qingci", "🟢": "qingci",
    "yellow": "xuan", "🟡": "xuan",
    "orange": "qiutan", "🟠": "qiutan",
    "red": "zhujian", "🔴": "zhujian",
}

# 金句卡用的心情色标（正常底）
MOOD_COLORS = {
    "green": "#4C8C6B", "🟢": "#4C8C6B",
    "yellow": "#C9A227", "🟡": "#C9A227",
    "orange": "#C1663C", "🟠": "#C1663C",
    "red": "#8C4A4A", "🔴": "#8C4A4A",
}
DEFAULT_MOOD_COLOR = "#8B6F47"

# 深色底专用：心情色标需提亮，否则在深背景上看不见
MOOD_COLORS_DARK = {
    "green": "#7FCBA0", "🟢": "#7FCBA0",
    "yellow": "#E8C86A", "🟡": "#E8C86A",
    "orange": "#E59A6B", "🟠": "#E59A6B",
    "red": "#D98A8A", "🔴": "#D98A8A",
}
DEFAULT_MOOD_COLOR_DARK = "#C9B79A"

# 速览卡用的心情圆点色（偏亮，独立语义，不与 MOOD_COLORS 混用）
MOOD_DOT = {
    "🟢": "#4CAF85", "🟡": "#D9A441", "🟠": "#C0743A", "🔴": "#C0392B",
}


def resolve_palette(name=None, mood_type="", bg_top=None, bg_bottom=None):
    """解析配色：自定义色 > 指定方案 > 心情联动（auto 默认）> 宣纸兜底

    auto 时按 --mood-type 映射：🟢青瓷 🟡宣纸 🟠秋檀 🔴朱笺；
    心情类型缺失或无法识别 → 回退宣纸（浅底，最稳）。

    返回 dict（含 name 字段），调用方自行取 pal["name"] 作为配色名。
    """
    key = (name or "").strip()
    if key == "auto":
        mt = (mood_type or "").strip()
        key = (MOOD_PALETTE.get(mt)
               or (MOOD_PALETTE.get(mt[0]) if mt else None)
               or "xuan")
    p = dict(PALETTES.get(key, PALETTES["xuan"]))
    if bg_top:
        p["bg_top"] = bg_top
    if bg_bottom:
        p["bg_bottom"] = bg_bottom
    return p


def list_palettes():
    """打印配色清单（供 --list-palettes 调试用）"""
    print(f"{'别名':<12}{'配色':<8}{'深/浅':<8}底色渐变")
    print("-" * 62)
    for k, v in PALETTES.items():
        print(f"{k:<12}{v['name']:<8}{'深色' if v['dark'] else '浅色':<8}"
              f"{v['bg_top']} → {v['bg_bottom']}")
    print("\n心情联动：🟢青瓷 🟡宣纸 🟠秋檀 🔴朱笺（--palette auto 默认）")


if __name__ == "__main__":
    list_palettes()
