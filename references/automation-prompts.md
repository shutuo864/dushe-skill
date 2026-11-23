# 毒舌熨心 · 周期复盘自动化 Prompt 模板（v2.5 新增）

> 由 WorkBuddy Automations 承载，在周日 / 月末 / 年末自动触发，主动执行对应周期心情复盘。
> 重建自动化时，将对应段的 prompt 整体复制进 automation 的 `prompt` 字段即可。
>
> **运行前准备（三条通用）**：
> 1. 读取 ima 接口凭证：`set -a && source $HOME/.baoyu-skills/.env && set +a`（该文件提供两个变量：ima 客户端 ID、ima 接口凭证）。**可选**——未配置时跳过持久化与历史调取，走纯对话降级模式。
> 2. 定位「心情追踪日志」笔记：**唯一真源 `doc_id=<YOUR_IMA_NOTE_ID>`，每次显式固定复用**；⛔禁止按标题 search 重定位、⛔禁止 import_doc 新建同名笔记（2026-11-13 已实际发生的分叉根因）。读取/追加失败即报错停止并标注「本次未持久化」，不造第二份。WB 侧分月文件（如《心情追踪日志_2026-11.md》）**仅为镜像副本**，不得作为独立真源写入或当作复盘数据源。
> 3. 提取区间记录：`get_doc_content`（body `{"doc_id":"<YOUR_IMA_NOTE_ID>","target_content_format":0}`），用正则切出 `[日期] | [类型] | [标签] | [事件]` 行。
> 4. 输出复盘 markdown，写入当前 cwd 并以 `present_files` 呈现。
> 5. **降级**：若 ima API 不可用，改用用户当次口述数据走空窗/精简模式，并注明「非完整历史记录」。

---

## 1. 周复盘提醒（RRULE: `FREQ=WEEKLY;BYDAY=SU`）

```
执行本周心情复盘（毒舌熨心·模式二）。
步骤：
1. set -a && source $HOME/.baoyu-skills/.env && set +a 获取 ima 凭证。
2. 调用 ima OpenAPI 读取唯一真源「心情追踪日志」笔记（显式固定 doc_id <YOUR_IMA_NOTE_ID>；⛔失效即报错停止，禁止 search_note_book 重定位 / 新建同名笔记），用 get_doc_content(target_content_format=0) 取全文。
3. 用正则切出本周一 0:00 至本周日 24:00 之间所有 "[日期] | [类型] | [标签] | [事件]" 记录行。
4. 按毒舌熨心「模式二：每周心情复盘」输出格式生成结构化周复盘：一周心情轨迹表 + emoji 心情色条（v2.2 可视化）+ 本周情绪画像（🟢/🟡/🟠/🔴 占比）+ 趋势洞察（2-3 句）+ 本周金句 + 下周提醒（1-2 条轻量建议）。
5. 将复盘 markdown 写入当前工作区（如 week-review-YYYY-MM-DD.md）并以 present_files 呈现。
6. 若本周零记录：走空窗复盘模式（提示"不记录本身就是一种信号"），不生成空表。
损友人设保持：可毒舌不冷漠，结尾轻量收尾不灌鸡汤。
```

---

## 2. 月复盘提醒（RRULE: `FREQ=MONTHLY;BYMONTHDAY=-1`）

```
执行本月心路回顾（毒舌熨心·模式三）。
步骤：
1. set -a && source $HOME/.baoyu-skills/.env && set +a 获取 ima 凭证。
2. 调用 ima OpenAPI 读取唯一真源「心情追踪日志」笔记（显式固定 doc_id <YOUR_IMA_NOTE_ID>；⛔失效即报错停止，禁止 search_note_book 重定位 / 新建同名笔记），get_doc_content(target_content_format=0) 取全文。
3. 用正则切出本月 1 日 至 月末 所有记录行，按周分组。
4. 按毒舌熨心「模式三：月度心路回顾」输出格式生成：月度心情曲线（按周 emoji 色条）+ 数据画像（累计天数 / 正面·轻度负面·重度负面·崩溃占比 / 最常心路标签 / 最稳定区间 / 本月转折点）+ 心路主题词（有温度的人话总结）+ 月度金句 + 下月提醒（1-2 条）+ 可选联动提示。
5. 将复盘 markdown 写入当前工作区（如 month-review-YYYY-MM.md）并以 present_files 呈现。
6. 若当月记录 < 5 天：走精简版，仅出数据画像 + 一句提醒。
```

---

## 3. 年复盘提醒（RRULE: `FREQ=YEARLY;BYMONTH=12;BYMONTHDAY=-1`）

```
执行年度心路年报（毒舌熨心·模式四）。
步骤：
1. set -a && source $HOME/.baoyu-skills/.env && set +a 获取 ima 凭证。
2. 调用 ima OpenAPI 读取唯一真源「心情追踪日志」笔记（显式固定 doc_id <YOUR_IMA_NOTE_ID>；⛔失效即报错停止，禁止 search_note_book 重定位 / 新建同名笔记），get_doc_content(target_content_format=0) 取全年全文。
3. 用正则切出全年 1/1 至 12/31 所有记录行，按季度分组。
4. 按毒舌熨心「模式四：年度心路年报」输出格式生成（模仿得到年度学习报告叙事风格）：数字说这一年 + 年度标签（主题+最活跃标签+最常见组合）+ 年度情绪走势（Q1-Q4 色条）+ 这一年你学会的事（从全年翻转记录提炼 2-3 条，附具体日期证据）+ 翻转弹药库（沉淀条数/最常用/最新入库）+ 年度金句 TOP3 + 给新一年的你（温暖收尾不灌鸡汤）。
5. 将年报 markdown 写入当前工作区（如 year-review-YYYY.md）并以 present_files 呈现。
6. 若全年记录 < 30 天：走精简版，重点放在"能记下来的都是什么日子"。
```
