# 00 · 流水线总览

五层之间**只通过契约文件传递**。任何一层都不解析上一层的原始响应。

```
① 画像     build_vault_profile.py  →  vault-profile.json
② 发现     adapters/<platform>.py  →  sessions.json（可选，人工确认节次）
③ 采集     adapters/<platform>.py  →  raw/（页图、音轨、平台文本）
④ 素材     build_manifest.py       →  manifest.json   ← 唯一出口
⑤ 归档     （由 gen_notes.py 执行） →  附件目录 + Source Register 行
⑥ 笔记     gen_notes.py            →  L## / P## / V## / Concept —
⑦ 讲解     （对话 + md）→ build_explainer_html.py → 单文件 HTML
⑧ 考题     gen_quiz_bank.py        →  题库 JSON v1（+ dsh-ui 围栏 + md 折叠答案）
⑨ 质量门   check_all.py            →  全绿才算交付
```

## ① 画像（永远第一步）

```bash
python "$SKILL/scripts/build_vault_profile.py" "<vault root>" -o "<vault root>/_scripts/vault-profile.json"
```

- 输入：目标库根目录。
- 先读 `<vault>/AGENTS.md`，再扫目录实况。**AGENTS.md 与目录冲突时以 AGENTS.md 为准**，冲突写进 `warnings`。
- 产出 `reviewedByHuman: false`。**人工复核前只允许只读操作**——画像猜错目录会导致写到错误位置。
- 失败即停。不要"先试试看"。

## ② 发现节次

```bash
python "$SKILL/adapters/canvas.py"   --list --course <COURSE_ID>
python "$SKILL/adapters/chaoxing.py" --list --course <courseid> --clazz <clazzid>
```

- 一节课常拆成 **2 个节次**（Canvas：第 9/10 节）。**分别采集、分别登记，不合并成一份材料。**
- **不要把平台节次号当课程 L 编号**。`session.lectureId` 只有在学习者确认或与课表核对后才填，否则留 `null`。
- 发现结果先给人看，确认后再采集。

## ③ 采集

```bash
python "$SKILL/adapters/canvas.py"   --course <ID> --session "<节次标签>" --out "<work>"
python "$SKILL/adapters/chaoxing.py" --course <courseid> --clazz <clazzid> --chapter <knowledgeid> --out "<work>"
python "$SKILL/adapters/pdf.py"      --pdf "<课件.pdf>" --out "<work>"
```

- 产物全部落 `raw/`，**不直接进知识库**。
- 三条只读纪律（违反即停）：不播放、不触发心跳/任务点、不并发轰炸（串行 + 200–300 ms 间隔）。
- 签名 URL 只存在于本次运行内存与临时文件，**不写入任何归档文件**。
- 大文件**前台下载**（本环境后台 `curl` 会卡在 0 字节）。

### 选路：先探测平台有没有课件轨

| 平台 | 探测 | 有轨 | 无轨 |
|---|---|---|---|
| Canvas | `course/ai/getAiFunctionShow` 的 `pptShow` | 路径 A：平台 PPT 轨（S3 原图 + 毫秒时间码） | 路径 B：解码场景抽取 + OCR + 去重 |
| 超星 | 无此接口 | — | 视频关键帧抽取 + aHash 去重 |
| PDF | — | — | PDF 渲染页图 |

**每节课都要重新探测**——同一门课不同节次可能不一样（实测某课 9/15 两节有轨、9/17 两节没有）。

## ④ 素材

```bash
python "$SKILL/scripts/build_manifest.py" "<work>"
```

- 汇总：页图 + **解码时间码** + 页码两路读数 + 转写分段 + 说话人 + PDF 文本。
- 产出必须通过 `schemas/manifest.schema.json` 校验，`warnings` 逐条列出「需要人工判断」的事实。
- 三条硬规则：
  1. **时间码一律用解码时间码**，不用容器时间戳（重复 DTS 会让 `ffmpeg -ss` 落到邻页，实测偏约 1 分钟）。
  2. **页码两路一致才 `verified`**（整帧 OCR + 页脚裁切放大）；不一致 → `mismatch`；缺页脚 → `missing`；页脚重复 → `duplicate`。
  3. **转写必须分段**（如 `--chunk 600`）；整段一次性解码会让 Whisper 漂移成重复文本或错误语言。说话人标签恒为推断。

## ⑤ 归档与登记

- 长期附件进 `dirs.attachments`；**媒体是否入库由画像 `mediaPolicy` 决定**（有的库连转写都不存）。
- 每个长期来源在 Source Register 登记：ID / 类型 / 原始文件 / 日期 / 状态 / 备注。
- 页脚异常、页码缺失、纯图页、文本顺序错乱等**都要登记**，不能静默。
- 文件名**不使用方括号 `[ ]`**——会破坏 Obsidian 的 wikilink 与嵌入语法。

## ⑥ 笔记

```bash
python "$SKILL/scripts/gen_notes.py" --manifest "<work>/manifest.json" --vault "<vault root>"
```

- L 按概念与课堂逻辑组织，**不逐页机械抄写**；P 让每个 PDF 阅读页都能定位。
- **课件存在 ≠ 课堂讲过**。只有回放/口述证据才写「已讲授」，否则标「课件版」或「未见对应讲解」。
- 图片块用**展开** callout；表格内嵌图片转义竖线；默认内嵌页图（不用 `#page=`）。
- 同步 Home / 索引 / 概念索引 / Source Register / 回链。

## ⑦ 讲解

- **md 是唯一真源**。对话讲解与单文件 HTML 都是它的呈现形态，内容不得漂移。
- 正文不出现只影响版面的观察（页脚读数异常、镜像文字、被裁切残边）——那类下沉到 P 索引的待核实项。
- 影响结论的证据边界必须留（数值只有课件在说、嵌入媒体未导出、类比被当成实验证据）。
- 配图优先级：**平台课件页图 > 可结构化渲染的图 > 自绘图**。自绘图只在课件与结构化渲染都覆盖不到时用。

## ⑧ 考题

```bash
python "$SKILL/scripts/gen_quiz_bank.py" --manifest "<work>/manifest.json" --out "<vault>/<quizBank>"
python "$SKILL/scripts/check_quiz_rules.py" "<bank>.json"
```

- 三份同源：对话 `dsh-ui` 卷子 / md 折叠答案 / 题库 JSON v1。
- 出题规则不可关闭：正确项非最长（逐题数字符数）、下标打散、干扰项真实、去掉措辞暗示、同卷不自相矛盾、解析指回来源。

## ⑨ 质量门

```bash
python "$SKILL/scripts/check_all.py" --vault "<vault root>" --work "<work>"
```

任一红即未交付。详见 `references/05-quality-gates.md`。

---

## 幂等与断点续跑

- 每一层只读上一层的契约文件，**重跑同一层不改变下游输入**（除非契约变了）。
- 采集层最贵：`raw/` 里已存在的文件跳过；`--force` 才重下。
- 素材层可反复重跑（纯计算）。
- 笔记层**不覆盖已有笔记**：默认写 `<name>.new.md` 供比对，`--apply` 才写入；写入前跑 Git 门。
- 契约变更时：**先改 schema，再改各层**，并在 `docs/PLAN.md` 的开放问题里记一笔。

## 失败处理

| 症状 | 处理 |
|---|---|
| 平台接口 401 / token 缺失 | 让学习者在浏览器完成登录；**不要试图导出 cookie** |
| 探测到 WAF / 验证码 | 停下，请学习者人工完成，再复查 |
| 画像与目录不符 | 停；人工修画像后再跑 |
| 页码两路不一致 | 标 `mismatch`，写进待核实，**不猜** |
| 转写语言异常 / 重复文本 | 检查是否整段解码；改分段重跑 |
| 平台无字幕接口 | 本地 Whisper；在 manifest 的 `platformSubtitles` 记 `none` |
