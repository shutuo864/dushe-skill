#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
毒舌熨心 · Agnes 生图版金句卡（v2.9.0 / 2026-11-13 固化）
============================================================
链路：当天心情 + 当天金句 → 动态提示词 → Agnes 零文字底图 → 本地 Pillow 叠真字 → 像素级体检

规则真源：references/agnes-jinju-prompt.md
  · 每日同步出，不需用户追加指令
  · 提示词 6 个槽位逐日重拼，禁止套昨天模板
  · 每天只调一次 Agnes；返工只做本地重绘，不二次扣费
  · 中文一律本地叠（AI 画中文必出伪汉字），底图零字符
  · 密钥仅内部载入并注入子进程，全程不打印、不入库

用法（AI 每日模式调用）：
  python agnes_jinju.py --date 2026-11-13 --mood 🟠 --tag "🌊 时代焦虑" \
    --event "长途归来、腿疼服老" \
    --jinju "十年河东十年河西|切莫放年华虚度" \
    --sub "周期转不转不由你我说了算，坑刨不刨是自己的事|别把还没到的三十年，先算进今晚的账里" \
    --source "广州光孝寺" --calendar "农历十月初五 · 丙午马年" \
    --ref-note "日历引文：《吴军来信 2》第 146 封" --workdir <工作区>

  --prompt-only  只生成提示词 + 变量回执，不调 Agnes、不扣费（用于自检 / diff）
  --bg <底图>    跳过 Agnes，直接用已有底图叠字（用于本地返工，不二次扣费）
"""

import argparse
import glob
import json
import math
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from card_common import resolve_palette                      # noqa: E402
from generate_card import font_supports_text, _find_cjk_font  # noqa: E402
from PIL import Image, ImageDraw, ImageFont                  # noqa: E402


# ============ ① 心情 → 配色 / 时段 / 亮度判据（与 card_common.py 同源） ============
MOOD_SCENE = {
    "🟢": dict(name="青瓷", period="清晨、晴光斜射", light="柔和晨光", mood_word="舒展、干净",
               whole_l="[72%,92%]", text_l="[78%,92%]", word="深"),
    "🟡": dict(name="宣纸", period="午后、薄云漫射", light="均匀漫射光", mood_word="平缓、不使劲",
               whole_l="[72%,92%]", text_l="[78%,92%]", word="深"),
    "🟠": dict(name="秋檀", period="秋日傍晚、暮色低垂", light="柔和侧逆光", mood_word="沉静克制",
               whole_l="[18%,38%]", text_l="[20%,35%]", word="浅"),
    "🔴": dict(name="朱笺", period="夜灯初上、光不刺眼", light="暖灯柔光", mood_word="先接住、留出气口",
               whole_l="[72%,92%]", text_l="[78%,92%]", word="深"),
}
MOOD_ALIAS = {"green": "🟢", "yellow": "🟡", "orange": "🟠", "red": "🔴",
              "正面": "🟢", "轻度": "🟡", "重度": "🟠", "崩溃": "🔴"}

# ============ ② 心路标签 → 器物族 ============
TAG_SCENE = [
    ("健康焦虑", "窗边一盏温茶、空药盏、软毯一角"),
    ("职场困境", "旧木桌、合上的卷宗与一支笔"),
    ("时代焦虑", "靠窗旧木桌一角，窗外远山与低垂暮色，一本合上的旧书"),
    ("家庭牵绊", "两把空椅、一盏暖灯、半掩的门"),
    ("自我和解", "空书封、一株新芽、静水杯"),
    ("终身学习", "摊开的空白本、笔、台灯"),
    ("创业运营", "空白账页、木尺、素陶杯"),
]
DEFAULT_TAG_SCENE = "一张素色桌面靠窗一角，窗外是安静的远景"

# ============ ④ 金句 → 主体物象（按顺序取首个命中） ============
MOTIF_RULES = [
    (("十年", "河东", "河西", "周期", "低谷", "虚度", "年华", "翻不了身", "三十年"),
     "刚栽下的一株花苗",
     "一只素陶小花盆，盆里是一株刚栽下不久的花苗，两片嫩叶、一茎，旁边斜放一把小泥铲；花苗只有一株、两片叶",
     "#6B7A55 ~ #8C9A6B", "低饱和暖绿",
     "⛔不多株、不盛开、不藤蔓缠绕、不出现花瓣散落；只允许一茎两叶"),
    (("放下", "清净", "平和", "半分", "不争", "安然", "随缘"),
     "一只空杯与静水面",
     "一只素陶空杯，杯旁一小片静水面，无倒影人像",
     "#B8CFC4 ~ #DCE9E3", "月白淡青",
     "⛔不出现人脸倒影、不冒浓热气、不叠加第二只杯"),
    (("退一步", "天高地阔", "放宽", "顺其自然", "无灯", "山门"),
     "远山与素石",
     "远景是柔和的远山轮廓，近处一块素石，画面大面积留白",
     "#A3BEB1 ~ #B8CFC4", "淡青",
     "⛔不出现碑刻、路标、亭子、文字牌"),
    (("回头", "倒坐", "执念", "放不下", "不肯"),
     "一把空椅",
     "一把空木椅斜对一扇半开的窗，椅面空着",
     "#C4A882 ~ #D4C4A8", "暖灰",
     "⛔不出现人物、剪影、衣帽搭在椅背上"),
    (("无常", "浮沉", "变故", "风雨", "江山", "世事"),
     "水面一片叶",
     "静水面上浮着一片叶，窗外有一层云影",
     "#B6C2CC ~ #C8D2DA", "冷灰",
     "⛔不出现船、伞、人物、波纹大字"),
    (("三心", "因果", "畏果", "专注", "手头", "日日", "改过"),
     "灯下空白纸与一支笔",
     "一盏灯下摊开一张完全空白的纸，旁边一支笔",
     "#D4C4A8 ~ #F5E6D3", "暖米",
     "⛔纸面完全空白，禁止任何小字、抬头、表格线、签名栏"),
]
FALLBACK_MOTIF = ("未命名物象", "一件与金句核心名词对应的素色实物（当天现场指定）",
                  "#C4A882 ~ #D4C4A8", "当日 accent 色", "⛔禁止沿用昨天的主体物象")

# ============ ⑤ 副文案 → 构图 ============
HOLD_WORDS = ("别", "不", "慢", "停", "先", "今晚", "算了", "莫", "勿")
GO_WORDS = ("继续", "走", "撑", "练", "攒", "再", "日日", "向前")


def split_lines(text, max_lines=2):
    """主金句 / 副文案断行：优先 |，其次中文逗号。"""
    if not text:
        return []
    parts = [p.strip() for p in text.replace("｜", "|").split("|") if p.strip()]
    if not parts:
        parts = [p.strip() for p in text.replace("，", ",").split(",") if p.strip()]
    return parts[:max_lines] if parts else [text.strip()]


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _pixels(im, box):
    """取区域 RGB 像素；用 tobytes 手动分组，规避 Pillow 14 移除 getdata 的风险。"""
    raw = im.crop(box).convert("RGB").tobytes()
    return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]


def rgb_lum(rgb):
    return 0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]


def pick_scene(tag):
    for k, v in TAG_SCENE:
        if k in (tag or ""):
            return v
    return DEFAULT_TAG_SCENE


def motif_label(text):
    """从物象描述里抽一个短标签（首个短句，≤16 字），用于回执值与点缀色标注。

    v2.9.1 修复：原 --motif 分支与未命中回退分支把标签写死为「现场指定物象」「现场生成」，
    导致两日 vars 比对时「金句物象」字面相同 → 误报「必变项未满足」。标签必须记录物象实值。
    """
    s = (text or "").strip()
    head = re.split(r"[，,；;。:：、]", s)[0].strip()
    return (head or s)[:16]


def pick_motif(jinju, override=None):
    if override:
        return (motif_label(override), override, "#C4A882 ~ #D4C4A8", "当日 accent 色",
                "⛔按现场物象逐元素补写数量/状态/位置禁例")
    for keys, name, desc, accent, accent_name, bans in MOTIF_RULES:
        if any(k in jinju for k in keys):
            return (name, desc, accent, accent_name, bans)
    return (motif_label(FALLBACK_MOTIF[1]), *FALLBACK_MOTIF[1:])


def pick_composition(sub):
    """两类语气词可能同时出现（如「先放下，继续往前走」），按命中数多者判，平手偏向行动。"""
    s = sub or ""
    hold = sum(s.count(w) for w in HOLD_WORDS)
    go = sum(s.count(w) for w in GO_WORDS)
    if hold > go:
        return ("严格位于画面下三分之一、偏右",
                "上方三分之一：平整柔和的虚化面，作为后期叠字区，不放任何物件、不放任何高对比纹理",
                f"收束语气占优（收{hold}/进{go}）→ 上方大面积留白，主体下沉")
    if go > 0:
        return ("居中略下、不顶满",
                "上方三分之一：平整柔和的虚化面，留一条向前延伸的柔和光带，不放任何物件",
                f"行动语气占优（进{go}/收{hold}）→ 留一条向前的线")
    return ("画面下三分之一", "上方三分之一：平整柔和的虚化面，作为后期叠字区，不放任何物件",
            "默认 → 上方留白、主体下沉")


def build_prompt(a, pal):
    mood = a.mood
    sc = MOOD_SCENE[mood]
    tag_scene = a.scene or pick_scene(a.tag)
    motif_name, motif_desc, accent_hex, accent_name, motif_bans = pick_motif(a.jinju, a.motif)
    pos, upper, comp_note = pick_composition(a.sub)
    bg_top, bg_bottom = pal["bg_top"], pal["bg_bottom"]
    src, tag_c = pal["source"], pal["tag"]
    detail = a.event.strip() if a.event else "当日生活节奏"

    p = f"""---
size: {a.size}
---

设计一张竖版 3:4 的真实摄影质感日签底图，{sc['period']}，{sc['name']}调，供后期叠加中文金句使用。这张图本身必须完全没有任何文字，且完全没有任何人物、人体部位、动物或拟人化轮廓（只有静物、自然光与空场景）。

【画面内容·逐元素定义】
- 场景：{tag_scene}；{detail}，整体{sc['mood_word']}。
- 主体（{pos}）：{motif_desc}。
- 环境另有一件与场景相配的素色器物；所有纸面、封面、杯身、器物表面完全空白。
- {upper}。
- 底部：留白，无杂物。

【颜色·可执行判据（hex）】
- 主色调限定在 {bg_bottom} ~ {bg_top}，占画面面积 55%~75%。
- 高光与器物限定在 {src} ~ {tag_c}，占 10%~25%。
- 点缀（{motif_name}）限定在 {accent_hex}（{accent_name}），占 1%~5%，⛔不出现高饱和红/蓝/紫、荧光色。
- 整幅背景平均亮度 L∈{sc['whole_l']}；⛔禁止纯黑 #000000 与纯白 #FFFFFF 大块区域。
- 上方叠字区亮度 L∈{sc['text_l']} 且局部明暗波动 σ≤8%，保证后期叠{sc['word']}色文字对比度≥4.5:1。

【强制·零字符（最重要）】
- 整幅画面零字符：不得出现任何汉字、英文字母、数字、标点、书法、印章、题字、书名、标签、logo、水印、二维码、伪汉字笔画。
- 书封面、陶盆、杯身、纸页表面必须完全空白，⛔禁止 AI 补小字、抬头、表格线、签名栏、乱码。
- ⛔禁止把提示词里的任何短语照排进画面。

【对抗约束·逐元素枚举变形风险（铁律-027①）】
- 人物风险（最高优先级·铁律-027③）：⛔画面绝对禁止任何人体部位或拟人化轮廓——包括但不限于手指、手掌、手臂、手腕、腿、脚、肩膀、头颈、衣袖、衣物、剪影、影子中的人形、半透明人影、只露局部肢体的特写。⛔禁止把「手搭在…」「手臂垂落」「衣角」「袖口」等任何人体姿态描述转成画面元素。整张图只能有静物、自然光、空场景，不得出现任何生命体或生命体曾经使用过的痕迹（如搭着的衣物、半握的手印）。
- 主体风险：{motif_bans}。
- 器物风险：⛔器物不变形为其他器具、不叠加同类、不加多余构件、不出现标识文字；⛔茶杯/陶杯不加把手指环，⛔书不多本堆叠，⛔小泥铲不变形为农具/武器。
- 构图风险：⛔主体不居中顶满，⛔叠字区不被物件遮挡，⛔主体不贴边、不被裁切；主体{pos}；⛔触发事件转成的场景细节（鞋、杯、书、光斑等）只能作弱化的环境陪衬，不得比金句物象更显眼、不得占据画面中心、不得横贯画面中部。
- 光线风险：⛔不出现硬边光斑、镜头炫光条纹、过曝白块；只用{sc['light']}。

【风格】胶片摄影质感、浅景深、颗粒细腻、沉静克制、无过度摆拍、无插画感、无 3D 渲染感、无边框、无装饰花纹。
"""
    vars_ = dict(心情=mood, 配色=sc["name"], 主色=f"{bg_bottom} ~ {bg_top}",
                 时段=sc["period"], 标签器物=tag_scene, 触发细节=detail,
                 金句物象=motif_name, 点缀色=accent_hex, 主体位置=pos,
                 构图依据=comp_note, 叠字色=sc["word"])
    return p, vars_


# ============ Agnes 通道（密钥只进子进程，不打印） ============
def _extract_key(node, parent=None, path=""):
    if isinstance(node, dict):
        blob = " ".join(str(v) for k, v in node.items()
                        if isinstance(v, str) and k.lower() in ("id", "name", "model", "provider", "slug"))
        has_agnes = "agnes" in blob.lower() or "agnes" in path.lower()
        for k in ("apiKey", "api_key", "key", "token", "credential"):
            v = node.get(k)
            if has_agnes and isinstance(v, str) and v.strip():
                return v.strip()
            # 凭据常挂在 provider 层（agnes 作为子项出现）
            if parent is not None and "agnes" in str(node.get("id", "")).lower():
                pv = parent.get(k)
                if isinstance(pv, str) and pv.strip():
                    return pv.strip()
        for k, v in node.items():
            got = _extract_key(v, node, path + "/" + str(k))
            if got:
                return got
    elif isinstance(node, list):
        for i, v in enumerate(node):
            got = _extract_key(v, parent, path + f"/{i}")
            if got:
                return got
    return None


def load_agnes_key(explicit=None):
    k = os.environ.get("AGNES_API_KEY", "").strip()
    if k:
        return k, "环境变量"
    home = os.path.expanduser("~")
    cands = []
    if explicit:
        cands.append(explicit)
    env_path = os.environ.get("AGNES_MODELS_JSON", "").strip()
    if env_path:
        cands.append(env_path)
    cands += [
        os.path.join(home, ".workbuddy", "models.json"),
        os.path.join(home, ".config", "workbuddy", "models.json"),
    ]
    for pat in (os.path.join(home, ".workbuddy", "**", "models.json"),
                os.path.join(home, "AppData", "Roaming", "**", "models.json")):
        try:
            cands += glob.glob(pat, recursive=True)
        except OSError:
            pass
    seen = set()
    for p in cands:
        if not p or p in seen or not os.path.isfile(p):
            continue
        seen.add(p)
        try:
            with open(p, "r", encoding="utf-8-sig") as f:
                data = json.load(f)
        except Exception:
            continue
        got = _extract_key(data)
        if got:
            return got, "本机模型配置（值不显示）"
    return None, "未找到"


def call_agnes(prompt_path, bg_path, size, key, gen_script):
    env = os.environ.copy()
    env["AGNES_API_KEY"] = key          # 只注入子进程，父进程不打印
    cmd = [sys.executable, gen_script, prompt_path, bg_path, "--size", size]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    # 防御：万一上游把密钥回显，脱敏后再打印
    out = out.replace(key, "***")
    print(out.strip()[-1500:])
    if r.returncode != 0 or not os.path.isfile(bg_path) or os.path.getsize(bg_path) < 1024:
        raise RuntimeError("Agnes 底图生成失败或落盘异常（见上方日志）")


# ============ 本地叠真字 + 机械体检 ============
def overlay(a, pal, bg_path, out_path):
    main_font_path = _find_cjk_font(["msyhbd.ttc", "NotoSansSC-Bold.ttf", "simhei.ttf"])
    body_font_path = _find_cjk_font(["simsun.ttc", "NotoSerifSC-Regular.ttf", "msyh.ttc"])
    if not main_font_path or not body_font_path:
        raise RuntimeError("未探测到可用中文字体，禁止出图（会出豆腐块）")

    im = Image.open(bg_path).convert("RGB").resize((1080, 1440), Image.LANCZOS)
    W, H = im.size

    # 底图叠字区平整度（叠字前测，铁律-027②）：11-13 实战争议点即左侧窗框导致 σ 超标
    bp = _pixels(im, (int(W * 0.18), int(H * 0.08), int(W * 0.88), int(H * 0.28)))
    bl = [rgb_lum(p) for p in bp]
    bm = sum(bl) / len(bl)
    bsd = math.sqrt(sum((x - bm) ** 2 for x in bl) / len(bl))
    print(f"底图叠字区(18%~88% / 8%~28%): L={bm / 255 * 100:.1f}%  σ={bsd:.1f}  (判据 σ≤8)")
    if bsd > 8:
        print("⚠️ 底图叠字区波动超标 → 收窄文字落区 / 本地渐隐重绘，勿重复调 Agnes")

    d = ImageDraw.Draw(im, "RGBA")

    f_tag = ImageFont.truetype(body_font_path, 30)
    f_main = ImageFont.truetype(main_font_path, 78)
    f_sub = ImageFont.truetype(body_font_path, 34)
    f_src = ImageFont.truetype(body_font_path, 27)
    f_foot = ImageFont.truetype(body_font_path, 24)
    f_tiny = ImageFont.truetype(body_font_path, 20)

    jinju_lines = split_lines(a.jinju)
    sub_lines = split_lines(a.sub)
    cal = a.calendar or ""
    ref = a.ref_note or ""
    all_text = ("毒舌熨心今日金句" + a.jinju.replace("|", "") + a.sub.replace("|", "")
                + a.source + cal + ref + "底图中文本地叠真字" + MOOD_LABEL.get(a.mood, ""))
    for f in (f_tag, f_main, f_sub, f_src, f_foot, f_tiny):
        if not font_supports_text(f, all_text):
            raise RuntimeError("字体缺字（豆腐块风险），禁止出图")

    # 底部渐隐到该配色的实底色：压住浅色书面/器物，保证落款对比度
    base = hex_rgb(pal["bg_bottom"])
    for y in range(1100, H):
        t = min(1.0, (y - 1100) / 150)
        d.line([(0, y), (W, y)], fill=(base[0], base[1], base[2], int(232 * t)))
    d = ImageDraw.Draw(im, "RGB")

    # 落款色自适应（铁律-027③）：底部渐隐后按净底色选同色系中对比度最高的墨色，
    # 浅底配色的 sub / faint / footer 偏淡，硬套会低于 4.5:1（2026-11-13 模拟跑实测 🟢 仅 3.49:1）。
    # 只改 Agnes 卡叠字，不动 card_common.py 配色真源。
    foot_bg_px = _pixels(im, (int(W * 0.15), 1300, int(W * 0.85), 1400))
    foot_bg_lum = sum(rgb_lum(p) for p in foot_bg_px) / len(foot_bg_px)

    def _rel(v):
        v = v / 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4

    def _contrast(text_rgb, bg_lum):
        ca, cb = _rel(rgb_lum(text_rgb)), _rel(bg_lum)
        return (max(ca, cb) + 0.05) / (min(ca, cb) + 0.05)

    ink_cands = [hex_rgb(pal["sub"]), hex_rgb(pal["text"]), hex_rgb(pal["couplet"])]
    foot_ink = max(ink_cands, key=lambda c: _contrast(c, foot_bg_lum))
    foot_cr_pred = _contrast(foot_ink, foot_bg_lum)
    print(f"落款色自适应: {pal['sub']} → #{foot_ink[0]:02X}{foot_ink[1]:02X}{foot_ink[2]:02X}"
          f"（预计对比度 {foot_cr_pred:.2f}:1）")

    def center(text, y, font, fill):
        w = d.textbbox((0, 0), text, font=font)[2]
        d.text(((W - w) / 2, y), text, font=font, fill=fill)

    center("毒 舌 熨 心 · 今 日 金 句", 92, f_tag, pal["tag"])
    d.ellipse((W / 2 - 150, 148, W / 2 - 130, 168), fill=MOOD_DOT.get(a.mood, "#C1663C"))
    d.text((W / 2 - 118, 145), MOOD_LABEL.get(a.mood, "心情记录"), font=f_foot, fill=pal["faint"])

    if len(jinju_lines) == 1:
        center(jinju_lines[0], 265, f_main, pal["couplet"])
    else:
        center(jinju_lines[0], 210, f_main, pal["couplet"])
        center(jinju_lines[1], 320, f_main, pal["couplet"])
    d.line([(330, 448), (750, 448)], fill=pal["rule"], width=2)
    for i, line in enumerate(sub_lines):
        center(line, 486 + i * 50, f_sub, pal["text"])
    center("—— " + a.source, 606, f_src, pal["source"])

    center(f"{a.date} · {cal}" if cal else a.date, 1310, f_foot, foot_ink)
    if ref:
        center(ref, 1350, f_foot, foot_ink)
    im.save(out_path, "PNG")

    # ---- 铁律-027③ 机械体检 ----
    def stat(box, text_rgb):
        px = _pixels(im, box)
        l = [rgb_lum(p) for p in px]
        m = sum(l) / len(l)
        sd = math.sqrt(sum((x - m) ** 2 for x in l) / len(l))
        def rel(v):
            v = v / 255
            return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
        a_, b_ = rel(rgb_lum(text_rgb)), rel(m)
        cr = (max(a_, b_) + 0.05) / (min(a_, b_) + 0.05)
        return m / 255 * 100, sd, cr

    main_rgb = hex_rgb(pal["couplet"])
    foot_rgb = foot_ink
    L, sd, cr = stat((int(W * 0.15), int(H * 0.06), int(W * 0.90), int(H * 0.40)), main_rgb)
    L2, sd2, cr2 = stat((int(W * 0.15), 1328, int(W * 0.85), 1344), foot_rgb)
    print(f"成品尺寸: {im.size}  字节: {os.path.getsize(out_path)}")
    print(f"文字区底色 L={L:.1f}%  σ={sd:.1f}  主金句对比度={cr:.2f}:1")
    print(f"落款区净底色 L={L2:.1f}%  σ={sd2:.1f}  落款字对比度={cr2:.2f}:1")
    print("字形自检: 通过（无豆腐块）")
    print("⚠️ 仍需目视回读：底图零文字 / 零人物 / 主体数量正确 / 构图未贴边")
    if cr < 4.5 or cr2 < 4.5:
        print("⛔ 对比度未达 4.5:1，本地重绘后仍不合格 → 不作为成品交付（退出码 3，上层走本地 Pillow 降级）")
        os.remove(out_path)
        sys.exit(3)
    print("体检结论: 全部达标，允许交付")
    return dict(L=L, sigma=sd, cr=cr, foot_cr=cr2)


MOOD_LABEL = {"🟢": "正面", "🟡": "轻度负面", "🟠": "重度负面", "🔴": "崩溃级"}
MOOD_DOT = {"🟢": "#4C8C6B", "🟡": "#C9A227", "🟠": "#E59A6B", "🔴": "#8C4A4A"}


def diff_with_yesterday(workdir, today_prompt, today_name, today_vars=None, today_vars_name=""):
    """验收「提示词必须随当天心情 + 金句同步调整」。

    判据（v2.9.0 · 2026-11-13 模拟跑修订）：
      · 必变项（每天都要重拼）：金句物象、触发细节
      · 条件项：心情变了 → hex 必变；心路标签变了 → 场景器物必变
      · ⛔ 不再无条件要求「场景/物象/hex 三处全变」：连续两天同心情时
        hex 与场景本就该与 card_common 同源，强改等于造假。
    找不到变量回执时回退到旧版纯文本三行比对（兼容历史文件）。
    """
    if today_vars:
        vf = sorted(glob.glob(os.path.join(workdir, "_agnes_vars_*.json")))
        vf = [f for f in vf if os.path.basename(f) != today_vars_name]
        if vf:
            try:
                with open(vf[-1], "r", encoding="utf-8") as f:
                    old = json.load(f)
            except Exception:
                old = {}
            if old:
                must = {"金句物象": "随主金句变", "触发细节": "随当天事件变"}
                cond = {}
                if today_vars.get("心情") != old.get("心情"):
                    cond["主色"] = "心情变了，hex 必须跟着变"
                if today_vars.get("心路标签") != old.get("心路标签"):
                    cond["标签器物"] = "标签变了，场景器物必须跟着变"
                m_ok = [k for k in must if today_vars.get(k) != old.get(k)]
                c_ok = [k for k in cond if today_vars.get(k) != old.get(k)]
                base = os.path.basename(vf[-1])
                print(f"动态校验: 与 {base} 相比 | 必变项 {len(m_ok)}/{len(must)} {m_ok}"
                      f" | 条件项 {len(c_ok)}/{len(cond)} {c_ok or '（心情/标签未变，hex/场景允许同源）'}")
                if len(m_ok) < len(must):
                    miss = "、".join(f"{k}（{v}）" for k, v in must.items() if k not in m_ok)
                    print(f"⚠️ 提示词疑似未随当天更新：必变项未满足 → {miss}")
                if len(c_ok) < len(cond):
                    miss = "、".join(f"{k}（{v}）" for k, v in cond.items() if k not in c_ok)
                    print(f"⚠️ 心情/标签已变但画面没跟上 → {miss}")
                # 辅助：纯文本三行差异，便于人工核对
                old_prompt_path = vf[-1].replace("_agnes_vars_", "_agnes_prompt_").replace(".json", ".md")
                if os.path.isfile(old_prompt_path):
                    with open(old_prompt_path, "r", encoding="utf-8") as f:
                        old_prompt = f.read()
                    keys = ["主色调限定在", "- 场景：", "- 主体（"]
                    changed = [k for k in keys if _line_with(old_prompt, k) != _line_with(today_prompt, k)]
                    print(f"  （辅助）文本槽位变化 {len(changed)}/3 {changed}")
                return

    # 回退：仅按 prompt 文本比对（历史 / 首次运行场景）
    files = sorted(glob.glob(os.path.join(workdir, "_agnes_prompt_*.md")))
    files = [f for f in files if os.path.basename(f) != today_name]
    if not files:
        print("动态校验: 未找到历史 prompt（首次运行），跳过")
        return
    with open(files[-1], "r", encoding="utf-8") as f:
        old = f.read()
    keys = ["主色调限定在", "- 场景：", "- 主体（"]
    changed = [k for k in keys if _line_with(old, k) != _line_with(today_prompt, k)]
    print(f"动态校验(文本回退): 与 {os.path.basename(files[-1])} 相比，变化槽位 {len(changed)}/3 {changed}")
    if len(changed) == 0:
        print("⚠️ 提示词与昨天完全相同，必须重拼")


def _line_with(text, key):
    for line in text.splitlines():
        if key in line:
            return line.strip()
    return ""


def main():
    ap = argparse.ArgumentParser(description="毒舌熨心 · Agnes 生图版金句卡（动态提示词）")
    ap.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--mood", default="🟡", help="🟢/🟡/🟠/🔴 或 green/yellow/orange/red")
    ap.add_argument("--tag", default="", help="心路标签（含动态扩展标签）")
    ap.add_argument("--event", default="", help="触发事件转成的 1 个具象视觉细节；⛔不要直接贴原话/公司名/人名")
    ap.add_argument("--jinju", required=True, help="主金句；用 | 分两行，否则按逗号断行")
    ap.add_argument("--sub", default="", help="副文案 / 心境解读；用 | 分行")
    ap.add_argument("--source", default="拟联·自撰", help="金句出处（须过铁律-003 核验）")
    ap.add_argument("--calendar", default="", help="日期·农历·节气（只进叠字）")
    ap.add_argument("--ref-note", default="", help="日历引文等信息（只进叠字）")
    ap.add_argument("--scene", default="", help="手动覆盖槽位③场景细节")
    ap.add_argument("--motif", default="", help="手动覆盖槽位④主体物象（未命中规则时用）")
    ap.add_argument("--workdir", default=os.getcwd())
    ap.add_argument("--out", default="")
    ap.add_argument("--bg", default="", help="已有底图：跳过 Agnes，仅本地叠字（返工不扣费）")
    ap.add_argument("--size", default="960x1280")
    ap.add_argument("--gen-script", default="")
    ap.add_argument("--models-json", default="")
    ap.add_argument("--prompt-only", action="store_true", help="只出提示词，不调 Agnes、不扣费")
    a = ap.parse_args()

    a.mood = MOOD_ALIAS.get(a.mood.strip(), a.mood.strip())
    if a.mood not in MOOD_SCENE:
        sys.exit(f"❌ 心情无法识别：{a.mood}（应为 🟢/🟡/🟠/🔴 或英文别名）")
    os.makedirs(a.workdir, exist_ok=True)

    pal = resolve_palette("auto", a.mood)
    prompt, vars_ = build_prompt(a, pal)
    mmdd = a.date[5:7] + a.date[8:10]
    prompt_path = os.path.join(a.workdir, f"_agnes_prompt_{mmdd}.md")
    with open(prompt_path, "w", encoding="utf-8") as f:
        f.write(prompt)

    print("===== 当天动态变量回执（用于核对是否真的换过）=====")
    for k, v in vars_.items():
        print(f"  {k}: {v}")
    print(f"  主金句: {a.jinju}")
    print(f"  副文案: {a.sub}")
    vars_path = os.path.join(a.workdir, f"_agnes_vars_{mmdd}.json")
    payload = dict(vars_, 日期=a.date, 心路标签=a.tag,
                   主金句=a.jinju, 副文案=a.sub)
    with open(vars_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print(f"===== 提示词已写入: {prompt_path} =====")
    print(f"===== 变量回执已落盘: {vars_path} =====")
    # 静态自检：当天色值与物象必须真的落在 prompt 里
    assert pal["bg_bottom"] in prompt and pal["bg_top"] in prompt, "心情色值未注入提示词"
    assert vars_["金句物象"] in prompt or a.motif, "金句物象未注入提示词"
    diff_with_yesterday(a.workdir, prompt, os.path.basename(prompt_path),
                        today_vars=payload, today_vars_name=os.path.basename(vars_path))

    if a.prompt_only:
        print("--prompt-only：未调用 Agnes、未扣费。")
        return

    out_path = a.out or os.path.join(a.workdir, f"dushe_jinju_{a.date}_agnes.png")
    bg_path = a.bg or os.path.join(a.workdir, f"_agnes_bg_{a.date}.png")
    if not a.bg:
        key, origin = load_agnes_key(a.models_json or None)
        if not key:
            print("⚠️ Agnes 凭据未找到，按降级链改走 scripts/generate_card.py 本地 Pillow 金句卡")
            sys.exit(3)
        gen = a.gen_script or os.path.join(os.path.expanduser("~"), ".workbuddy", "skills",
                                          "agnes-image-gen", "gen_image.py")
        if not os.path.isfile(gen):
            print(f"⚠️ Agnes 生图脚本不存在: {gen} → 走本地 Pillow 降级")
            sys.exit(3)
        print(f"密钥来源: {origin}（值不显示）｜模型: agnes-image-2.5-flash｜每日仅此一次")
        try:
            call_agnes(prompt_path, bg_path, a.size, key, gen)
        except Exception as e:
            print(f"⚠️ {e} → 走本地 Pillow 降级")
            sys.exit(3)
    else:
        print("使用已有底图（本地返工，未调用 Agnes、未扣费）")

    overlay(a, pal, bg_path, out_path)
    print(f"✅ 交付: {out_path}")


if __name__ == "__main__":
    main()
