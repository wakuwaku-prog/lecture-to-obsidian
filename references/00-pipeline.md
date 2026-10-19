# 00 · 跨两个 skill 的流水线

五层之间**只通过契约文件传递**。任何一层都不解析上一层的原始响应。
本文件是**总图**；采集与笔记的实现细节归 `better-awesome-sjtu-canvas-ppt`，
讲解与考题的细节归本 skill 的 `references/03-explainer.md` / `references/04-quiz.md`。

## 1. 层与归属

| # | 层 | 归属 | 入口 | 产物 |
|---|---|---|---|---|
| ① | 画像 | **better** | `build_vault_profile.py` | `vault-profile.json` ← 契约 |
| ② | 发现节次 | **better** | `canvas.py` / `chaoxing.py` / `pdf.py` | `sessions.json`（人工确认） |
| ③ | 采集 | **better** | 同上 | `raw/`（页图、音轨、平台文本） |
| ④ | 素材 | **better** | `build_manifest.py` | `manifest.json` ← 契约，**唯一出口** |
| ⑤ | 归档登记 | **better** | 由 `gen_notes.py` 执行 | 附件目录 + Source Register 行 |
| ⑥ | 笔记 | **better** | `gen_notes.py` | L## / P## / V## / Concept — |
| ⑦ | 讲解 | **本 skill** | `build_explainer_html.py` | md 真源 → 单文件 HTML |
| ⑧ | 考题 | **本 skill** | `gen_quiz_bank.py` | 题库 JSON v1（+ `dsh-ui` 围栏 + md 折叠答案） |
| ⑨ | 质量门 | **本 skill** | `check_all.py` | 6 行汇总，全绿才算交付 |

**顺序硬约束**：① → ④ → ⑥ → ⑦ → ⑧ → ⑨。跳过画像直接采集，或跳过 manifest 直接写笔记，
都会让下游拿到猜出来的字段。

## 2. 前半程（①②③④⑤⑥）— 在 better skill 里

这一半的**命令、契约字段、平台差异、踩坑**全在 `better-awesome-sjtu-canvas-ppt`，
本 skill 不复制它的文档（复制必然两处漂移）。要读的是它的 SKILL.md 与两份长文档：
笔记规范（`OBSIDIAN-NOTES.md`）和采集契约（`ACQUISITION.md`）。

本 skill 只需要知道三件事：

1. **`manifest.json` 是素材层的唯一出口**，schema 在 better 的 `manifest.schema.json`。
   里面是：页图 + **解码时间码** + 页码两路读数 + 转写分段 + 说话人 + PDF 文本。
   讲课时引用的每个时间码和页码都来自它，**不从转写文本里另算**。
2. **`vault-profile.json` 是库差异的唯一出口**，schema 在 better 的 `vault-profile.schema.json`。
   讲解与题库的落点、Git 严格度、证据标记都从这里读。
3. **画像 `explainer.mode` 是本 skill 的总闸**：为 `none` / `markdown-only` 时
   `build_explainer_html.py` 直接退出码 4，不做派生。

> 两个契约都恒为 `reviewedByHuman: false` 直到人工复核。**未复核时只跑 dry-run。**

## 3. 后半程（⑦ 讲解）

```bash
python "$SKILL/scripts/build_explainer_html.py" \
       --src "<src.html>" --out "<out.html>" \
       --vault "<vault root>" [--profile <画像>] [--mode single-file-html|chapter-html]
```

- **md 是唯一真源**。对话讲解与单文件 HTML 都是它的呈现形态，内容不得漂移。
- 正文不出现只影响版面的观察（页脚读数异常、镜像文字、被裁切残边）——那类下沉到 P 索引的待核实项。
- 影响结论的证据边界必须留（数值只有课件在说、嵌入媒体未导出、类比被当成实验证据）。
- 配图优先级：**平台课件页图 > 可结构化渲染的图 > 自绘图**。自绘图只在课件与结构化渲染都覆盖不到时用。
- 六项自检任一 FAIL → 退出码 3，**不写出文件**。

## 4. 后半程（⑧ 考题）

```bash
python "$SKILL/scripts/gen_quiz_bank.py" --src "<题源>" --out "<题库目录>" \
       [--manifest <manifest.json>] [--lang zh|en|both]
python "$SKILL/scripts/check_quiz_rules.py" "<bank>.json"
```

- 三份同源：对话 `dsh-ui` 卷子 / md 折叠答案 / 题库 JSON v1。
- 出题规则不可关闭：正确项非最长（逐题数字符数）、下标打散、干扰项真实、去掉措辞暗示、
  同卷不自相矛盾、解析指回来源。
- **导入器不执行这些规则**，所以 `check_quiz_rules.py` 是唯一执行点。

## 5. 后半程（⑨ 质量门）

```bash
python "$SKILL/scripts/check_all.py" --vault "<vault root>" \
       [--manifest <manifest.json>] [--profile <画像>] [--html <...>] [--work <work>]
```

任一红即未交付。6 行里 **4 行查的是 better 的产物**，脚本从 better 目录读取（默认
`~/.dsh/skills/better-awesome-sjtu-canvas-ppt`，可用 `--canvas-ppt-skill` 改）。
详见 `references/05-quality-gates.md`。

---

## 幂等与断点续跑

- 每一层只读上一层的契约文件，**重跑同一层不改变下游输入**（除非契约变了）。
- 采集层最贵：`raw/` 里已存在的文件跳过；`--force` 才重下。（better）
- 素材层可反复重跑（纯计算）。（better）
- 笔记层**不覆盖已有笔记**：默认写 `<name>.new.md` 供比对，`--apply` 才写入；写入前跑 Git 门。（better）
- 讲解层**可反复重跑**：HTML 是纯派生，重跑只覆盖 HTML，不动 md。
- 题库层**可反复重跑**：三形态都由题源算出，题源不变则产物不变。
- 契约变更时：**先改 schema（在 better），再改各层**，并在 `docs/PLAN.md` 记一笔。

## 失败处理

| 症状 | 归属 | 处理 |
|---|---|---|
| 平台接口 401 / token 缺失 | better | 让学习者在浏览器完成登录；**不要试图导出 cookie** |
| 探测到 WAF / 验证码 | better | 停下，请学习者人工完成，再复查 |
| 画像与目录不符 | better | 停；人工修画像后再跑 |
| 页码两路不一致 | better | 标 `mismatch`，写进待核实，**不猜** |
| 转写语言异常 / 重复文本 | better | 检查是否整段解码；改分段重跑 |
| 平台无字幕接口 | better | 本地 Whisper；在 manifest 的 `platformSubtitles` 记 `none` |
| 讲解自检 FAIL（退出码 3） | 本 skill | 按报错改 src；**不要加 `--force` 绕过** |
| 讲解被画像总闸关掉（退出码 4） | 本 skill | 改画像 `explainer.mode`，或只交 md |
| 题库规则 ERROR | 本 skill | 重写该题；不能靠改判据放过 |
| 质量门某行 SKIP | 本 skill | 补上缺的参数再跑；**SKIP 不算通过** |
