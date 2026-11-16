#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按月切分「心情追踪日志」总台账，生成月度分卷 Markdown。
真源：data/心情追踪日志.md（只读）
产出：data/monthly/心情追踪日志_YYYY-MM.md
"""
import os
import re
import sys
from datetime import datetime

SRC = r"C:/Users/Administrator/.workbuddy/skills/dushe__skillhub/data/心情追踪日志.md"
OUT_DIR = r"C:/Users/Administrator/.workbuddy/skills/dushe__skillhub/data/monthly"

MOOD_ORDER = ["🟢", "🟡", "🟠", "🔴"]
MOOD_NAME = {"🟢": "正面", "🟡": "轻度负面", "🟠": "重度负面", "🔴": "危机"}

ROW = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\s*\|")


def main():
    if not os.path.exists(SRC):
        print("ERROR: 台账不存在 " + SRC)
        return 1

    lines = open(SRC, encoding="utf-8").read().splitlines()
    groups = {}
    for raw in lines:
        line = raw.strip()
        m = ROW.match(line)
        if not m:
            continue
        ym = m.group(1) + "-" + m.group(2)
        groups.setdefault(ym, []).append(line)

    if not groups:
        print("ERROR: 台账中没有可识别的记录行")
        return 1

    os.makedirs(OUT_DIR, exist_ok=True)
    made = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    for ym, items in sorted(groups.items()):
        year, month = ym.split("-")
        mood_cnt = {}
        tag_cnt = {}
        for it in items:
            parts = [p.strip() for p in it.split("|")]
            if len(parts) >= 2:
                mood_cnt[parts[1]] = mood_cnt.get(parts[1], 0) + 1
            if len(parts) >= 3:
                for t in parts[2].split("/"):
                    t = t.strip()
                    if t:
                        tag_cnt[t] = tag_cnt.get(t, 0) + 1

        mood_line = " ｜ ".join(
            "%s %s %d 天" % (k, MOOD_NAME.get(k, ""), mood_cnt[k])
            for k in MOOD_ORDER
            if k in mood_cnt
        ) or "—"

        tag_line = "、".join(
            "%s ×%d" % (k, v)
            for k, v in sorted(tag_cnt.items(), key=lambda x: (-x[1], x[0]))
        ) or "—"

        body = []
        body.append("# 心情追踪日志 · %s年%s月" % (year, int(month)))
        body.append("")
        body.append("> 毒舌熨心每日心情记录 · 月度分卷")
        body.append("> 记录条数：%d 条 ｜ 最后同步：%s" % (len(items), now))
        body.append("> 心情分布：%s" % mood_line)
        body.append("")
        body.append("## 逐日记录")
        body.append("")
        for it in items:
            body.append(it)
        body.append("")
        body.append("## 本月心路标签")
        body.append("")
        body.append(tag_line)
        body.append("")
        body.append("---")
        body.append("*由总台账自动切分生成，每次同步整份覆盖本条目*")
        body.append("")

        out = os.path.join(OUT_DIR, "心情追踪日志_%s.md" % ym)
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(body))
        made.append((ym, len(items), out))

    for ym, n, p in made:
        print("%s | %d 条 | %d 字节 | %s" % (ym, n, os.path.getsize(p), p))
    return 0


if __name__ == "__main__":
    sys.exit(main())
