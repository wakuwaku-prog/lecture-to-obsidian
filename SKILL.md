---
name: lecture-to-obsidian
description: >
  把视频学习平台上的课堂材料整理进 Obsidian 知识库：采集课件页图 / 音轨 / 字幕，
  生成 L##（课堂笔记）、P##（课件逐页索引）、Concept（概念页），
  产出 AI 讲解（Obsidian md 为唯一真源，单文件 HTML 按需派生），
  并出课后考题（对话即时判分 + 可导入题库的 JSON）。
  采集层按平台走适配器：SJTU Canvas 课堂回放（oc.sjtu.edu.cn / v.sjtu.edu.cn，
  复用 better-awesome-sjtu-canvas-ppt 的脚本）、超星学习通（chaoxing.com）、
  只有教师 PDF 时走 PDF 渲染页图。
  当用户提到"整理课堂回放""把回放做成笔记""导出课件""课堂转写""课堂实录整理"
  "讲解这节课""逐节讲解""出随堂题""出课后题""生成题库""整理到 Obsidian"，
  或给出 oc.sjtu.edu.cn / v.sjtu.edu.cn / chaoxing.com / mooc1.chaoxing.com
  链接时使用。使用前提醒用户：1) 提前在浏览器登录对应平台；
  2) Canvas 采集需要 opencli doctor 全绿。
---

# lecture-to-obsidian — 课堂回放 / 视频课程 → Obsidian

从「平台上的一节课」到「知识库里能复习、能自测的一份东西」。**五层流水线，平台无关的下游，按平台换的采集。**

方案全文与证据台账见 [`docs/PLAN.md`](docs/PLAN.md)。

## 0. 三条铁律（先读，违反即停）

1. **不产生学习记录。** 平台侧只做**只读 GET**，不播放视频、不触发心跳上报、不点「任务点」。超星每节带 `jobid` 任务点，播放即留下完成记录——这是不可逆的。
2. **先读目标库自己的 `AGENTS.md`，再动手。** 每个知识库的目录、frontmatter、媒体政策、Git 流程都可能不同（有的库**连转写都不入库**）。冲突时**以目标库 AGENTS.md 为准**，本 skill 的默认值只是兜底。
3. **不猜。** 页码读不出来标「待核实」，页脚重复标 `dup`，页脚缺失标 `pNA`，转写可疑标「待核实（转写修正）」。**课件存在 ≠ 课堂讲过**——没有回放证据的页不能写成「已讲授」。**只读转写 ≠ 听过音频**：前者只能写「按转写核对」，只有真的播放/听取过音频才能写「已听/已核对音频」（见 §6 安全与来源纪律）。

## 1. 第一步永远是：生成知识库画像

```bash
python "$SKILL/scripts/build_vault_profile.py" "<vault root>" -o "<vault root>/_scripts/vault-profile.json"
```

产出符合 [`schemas/vault-profile.schema.json`](schemas/vault-profile.schema.json) 的画像：目录映射、命名规则、frontmatter 必填字段、**媒体政策**、图片宽度与嵌入语法、callout 约定、Git 约束、讲解与考题产物的落点。

**画像没生成成功就不要往下走。** 下游所有写文件动作都要查画像。

## 2. 流水线

| 层 | 做什么 | 读哪份 reference |
|---|---|---|
| **L0 采集** | 平台适配器：发现课程/节次 → 取课件页图 → 取视频/音轨 → 平台文本 | [`references/01-acquisition.md`](references/01-acquisition.md) |
| **L1 素材** | 抽帧 / OCR / 页码两路校验 / 分段转写 / 说话人分离 → 统一 manifest + 归档 + Source Register 登记 | [`references/01-acquisition.md`](references/01-acquisition.md) |
| **L2 笔记** | L## / P## / V##（按需）/ Concept —；索引、双链、来源登记同步 | [`references/02-notes.md`](references/02-notes.md) |
| **L3 讲解** | md 真源（证据标记 + 配图）→ 按需派生单文件 HTML | [`references/03-explainer.md`](references/03-explainer.md) |
| **L4 考题** | 对话卷子（`dsh-ui`）/ md 折叠答案 / 题库 JSON v1 | [`references/04-quiz.md`](references/04-quiz.md) |
| **L5 质量门** | 链接、结构、出题规则、HTML 资产、manifest 一致性、Git 安全 | [`references/05-quality-gates.md`](references/05-quality-gates.md) |

层间只通过**契约文件**传递，不靠口头约定。总览见 [`references/00-pipeline.md`](references/00-pipeline.md)。

### 呈现形式（DOM 契约）已冻结

单文件 HTML 的骨架、类名、`data-*` 属性与测验判分行为**已经冻结**，权威定义在 [`references/03-explainer.md`](references/03-explainer.md)：

- CSS/JS **逐字继承**自已验证的产出（心理库 `10 讲解 HTML/L06`），不要重新设计。
- 测验契约：`.quiz > .q[data-group][data-answer]` + `input[name=group]` + `label.ok/.bad` + `.q.revealed .expl` + `button.grade` / `button.ghost` / `.score`。
- **`.quiz` 上的 `data-groups` 属性在原产物里 JS 并未使用**，真正生效的是每个 `.q` 上的 `data-group`。别照抄错的那个。
- 每张内嵌图必须带 `style="max-width:min(Npx,100%)"`；**写死 px 会在窄屏顶破卡片**（这是踩过的坑）。
- 改动契约的顺序：先改 `references/03-explainer.md`，再改 `templates/explainer.html` 与 `scripts/build_explainer_html.py`。

设计理由与契约演进史见 [`docs/PLAN.md`](docs/PLAN.md) §6 与 §12.5。

### ⚠️ 复用的两个校验器有假绿灯

`better-awesome-sjtu-canvas-ppt/scripts/` 下的 `check_vault_links.py` 与 `check_note_structure.py` **都永远 `exit 0`**，只能解析 stdout。已查实的三个坑：

1. **`check_vault_links.py` 对不存在的库路径静默报 OK**（`checked 0` + `OK: every wikilink…`）——路径写错就等于「全过」。`check_all.py` 必须断言库根存在、且扫描对象数 > 0，否则 **FAIL**。
2. **`check_note_structure.py` 把 frontmatter 字段名硬编码为 `type`**，而有的库用 `note_type` → 该库全部笔记被误报。必须按画像复核后降级为 INFO，并由**画像驱动**的检查做真正的必填字段校验。
3. 两者对**目录型** wikilink 与文档里的写法示例一律报断链——这类红灯**须先人工读原文**，不要照着改笔记。

发现但**不属本 skill** 的既有缺陷（如心理库 P08 里未替换的 `#page=N` 占位链接）只登记、不代改，见 [`references/05-quality-gates.md`](references/05-quality-gates.md)。

## 3. 三份契约（改契约 = 改所有层，先改 schema）

| 契约 | 文件 | 作用 |
|---|---|---|
| 素材清单 | [`schemas/manifest.schema.json`](schemas/manifest.schema.json) | 采集层的唯一出口；下游只认它 |
| 知识库画像 | [`schemas/vault-profile.schema.json`](schemas/vault-profile.schema.json) | 目标库差异的单点配置 |
| 题库 | [`schemas/quiz-bank.schema.json`](schemas/quiz-bank.schema.json) | `schemaVersion: 1`，与细胞生物学库 `刷题工具/` 的既有规范一致 |

## 4. 与 `better-awesome-sjtu-canvas-ppt` 的关系

- **Canvas 采集调用它，不复制它的脚本。** 它的 **11 个脚本**（`download_ppt` / `extract_ppt_scenes` / `extract_ppt_frames` / `ocr_slides` / `read_slide_pageno` / `dedupe_slides` / `transcribe_class` / `diarize_transcript` / `scene_times` + 两个校验器）是既有资产；本 skill 的 `adapters/canvas.py` 只做编排与契约转换。
- **超星采集在本 skill 内**（`adapters/chaoxing.py`），因为它的链路与 Canvas 完全不同：没有平台 PPT 轨、没有可用字幕、且有任务点风险。
- **它自己也有整理到知识库的部分，而且写得比本 skill 更细——先读它，再读本 skill 的 L2。**
  - `docs/OBSIDIAN-NOTES.md`（182 行）：「从素材到笔记」完整流程 —— 附件命名、Source Register 登记、三件套写法、内嵌图与表格转义、页码三态、概念页与索引、11 项收尾自查、7 条常见错误。
  - `docs/WORKFLOW.md`（11 KB）：端到端操作 —— 定位课程与节次、**探测 `pptShow`**、路径 A/B、转写与说话人、§4 配合 Obsidian 知识库。
  - `templates/`：L / P / V 三份笔记骨架。
  - ⚠️ 这三者**原先本机没装**（2026-10-19 去 GitHub 核实：远端仓库有，本地只装了 `SKILL.md` + `scripts/`）。**现已补齐并逐个通过 git blob SHA 校验**（`c2c20f65` / `a2c2b712` / `29328590` / `63944126` / `16e0aa21`）。若换机器重装，记得连 `docs/` 与 `templates/` 一起装。
- **两处有意分歧，以目标库为准**：它主张 P+V+L **每课都建**（本 skill 的 V 按需，因心理库 AGENTS.md §9 明确「V## 仅在需要回放复核时建立」）；它的页图命名是 `PPT p## — Topic (第N节 MMSS).jpg`（本 skill 的 PDF 路径用 `PDF pNN.jpg`，与心理库实际文件一致）。

**何时该把 `adapters/` 拆成独立 skill**：当采集需要覆盖第二所学校，或出现第三个平台时。在那之前，一个 skill 更好——五层共享同一份契约，拆开必然出现「上游改了字段、下游静默错」。

## 5. 快速上手

```bash
SKILL="$HOME/.dsh/skills/lecture-to-obsidian"

# ① 知识库画像
python "$SKILL/scripts/build_vault_profile.py" "<vault root>"

# ② 采集（平台二选一）
python "$SKILL/adapters/canvas.py"   --course <COURSE_ID> --session "第1周 - 周四 第9节" --out "<work dir>"
python "$SKILL/adapters/chaoxing.py" --course <courseid> --clazz <clazzid> --chapter <knowledgeid> --out "<work dir>"

# ③ 素材处理（抽帧/OCR/转写/说话人）→ manifest.json
python "$SKILL/scripts/build_manifest.py" "<work dir>"

# ④ 笔记 / 讲解 / 考题
python "$SKILL/scripts/gen_notes.py"    --manifest "<work dir>/manifest.json" --vault "<vault root>"
python "$SKILL/scripts/build_explainer_html.py" --src "<src.html>" --out "<out.html>"
python "$SKILL/scripts/gen_quiz_bank.py" --manifest "<work dir>/manifest.json" --out "<vault>/题库/"

# ⑤ 质量门（全过才算交付）
python "$SKILL/scripts/check_all.py" --vault "<vault root>" --work "<work dir>"
```

## 6. 学习者的偏好与硬约束

> 以下都是**学习者本人在库 `AGENTS.md` §7 里明确写下的**，不是本 skill 的发明。与目标库 AGENTS.md 冲突时以后者为准；库没写全时按这里兜底。

**讲解节奏（最容易漏的一条）**

- **分部分推进**：一段只讲一个重点，用短句，避免长句与大段一次倾倒。
- 每部分讲完给 **2–5 道**选择/简答题，**停下来等学习者回答**，再进入下一部分。
  这是**交互节奏**，不是产物题量——产物题量见 [`references/04-quiz.md`](references/04-quiz.md)：课次 5–8 题、章级每组 6 题。
- 学习者答「不知道」时，**换具体例子、数字或反例重讲**，不重复原句。
- **讲细、讲深、讲全**：逐页覆盖重要信息，**不跳过** Checkpoint、插入页、术语表或历史页。

**配图与图示**

- 有助于理解时**优先用可编辑的 Mermaid 流程图 / 关系图 / 比较图**；生成后检查术语、方向、标签，**不用装饰图替代知识结构**。
- 配图优先级：**课件页图 > 可结构化渲染的图 > 自绘**；自绘只在两者都覆盖不到时用。

**贴图分两种场合，规则不同**

| 场合 | 写法 |
|---|---|
| **对话（聊天正文）** | Markdown 图片走 `AssistantMarkdown → localPathMediaUrl → fileMediaUrl`，而 `fileMediaUrl` 里有 `!isAbsoluteWorkspacePath(path) → return void 0`，所以**相对路径永远不显示**。必须写**绝对路径**，且路径里的空格、括号、中文要**百分号编码**（`localPathMediaUrl` 会 `decodeURIComponent`，编码后可完整还原）。**用脚本生成，不要手写。** |
| **共享笔记（Obsidian）** | 统一 `![[附件路径\|宽度]]`，**不写本机绝对路径**。 |

已知限制：侧边对话不做 `decodeURIComponent`，百分号编码的本地图在侧边栏仍退化为 alt 文字；**不要为它改回相对路径**（相对路径在主会话同样不显示）。

**证据标记多一类**

除 `[PPT原文]` `[课堂口述]` `[机器转写]` `[我的推断]` `[待核实]` 外，补充人物或研究背景时必须标 **`[背景补充，非课件原文]`**，交代**谁、什么情境、说明什么**；要作学术论据时核对原始研究。

**安全与来源纪律（库级硬约束，不因任务紧急而放松）**

- **学习资料不得转化成自我诊断或医疗建议。** 这门课涉及临床内容——凡是临床解释，必须标出来源、适用范围与证据限制。
- **「已听」与「按转写核对」不是一回事。** 只读了 TXT/SRT/VTT 或自动转写，**只能**写「按转写核对」；**只有真的播放/听取过音频**才能写「已听/已核对音频」。自动说话人标签是**推断**，引用前需核对原始音频。
- **时间戳保留在转写或来源登记**；正式笔记只在学习者需要回放定位时才引用。
- **原始媒体（视频 / AAC / WAV）只作临时处理输入**，处理并完成必要核对后清理。Source Register 保留「原始媒体未归档」状态，**但不建立指向不存在媒体的链接**。
- **不无脑渲染整套页图。** P 索引优先让每个阅读页**可定位**（页图 / `#page=` 链接 / 明确页码范围）；只在图表、版式、OCR 缺失或学习理解确有需要时才嵌入渲染页图。
  ⚠️ 但以**目标库实际情况**为准：心理库实测 `#page=` 链接**点击无效**，该库因此改为 35 页全部内嵌——画像与学习者反馈优先于这条默认。

## 7. 禁止事项

- 不写 `http://127.0.0.1:...` 这类临时服务地址进任何笔记或图片链接。
- 不为「让图片显示」而启动预览服务；Obsidian 内嵌统一 `![[路径|宽度]]`。
- 不把签名 URL、cookie、token、个人绝对路径写进笔记、Source Register 或题库。
- 不删除原件、旧版本、课堂截图、转写或有引用的派生材料。
- 不执行 `git reset --hard`、`git checkout -- .`、`git clean`、`git push --force`。
- 不在目标库里创建游离文件；临时产物放工作目录，整合后清理。

## 8. 交付物地图

> 纪律：**本文件与 `references/` 里提到的每个路径都必须在交付物里真实存在。** 引用前先确认；改完用 `python scripts/check_doc_paths.py` 核一遍。文档承诺了不存在的路径，会让接手者以为某道防护已生效——比没有防护更危险。

| 路径 | 作用 |
|---|---|
| `SKILL.md` | 本文件：路由 + 铁律 + 契约指针 + **学习者呈现与节奏偏好** + 交付物地图 |
| `docs/PLAN.md` | 方案全文、证据台账、契约演进史、质量门纪律 |
| `docs/pilot/L08.manifest.json` | **基准 fixture**：真实 L08 素材（35 页 / 2 节次 / 38 放映记录） |
| `docs/pilot/make_L08_fixture.py` | 重新生成基准 fixture（可原地重跑） |
| `references/00-pipeline.md` | 五层流水线总览与失败处理 |
| `references/01-acquisition.md` | L0/L1 采集层：两条路径、三个 adapter、上游真实签名 |
| `references/02-notes.md` | L2 笔记层：画像、模板、三库实测差异 |
| `references/03-explainer.md` | L3/L4 讲解层：**DOM 契约权威**、两套测验形态、踩坑表 |
| `references/04-quiz.md` | L4 考题层：三级严重度、六条出题规则、兼容性证据 |
| `references/05-quality-gates.md` | L5 质量门：CLI、假绿灯三道防线、既有缺陷清单 |
| `schemas/manifest.schema.json` | 素材清单契约 |
| `schemas/vault-profile.schema.json` | 知识库画像契约（含 `structure` 结构要求） |
| `schemas/quiz-bank.schema.json` | 题库契约（严格对齐 v1） |
| `adapters/_common.py` | 三个 adapter 共用：凭据护栏、契约枚举、原子写、下载器 |
| `adapters/canvas.py` | Canvas 双路径采集（过滤桌面 → 清单内去重 → 只下保留帧） |
| `adapters/chaoxing.py` | 超星学习通采集（只读白名单 + 200–300 ms 限速） |
| `adapters/pdf.py` | PDF 渲染页图 + 版式家具法判纯图页 |
| `scripts/build_vault_profile.py` | 读 AGENTS.md + 扫目录 → 知识库画像 |
| `scripts/build_manifest.py` | `raw/` → `manifest.json`（两层校验） |
| `scripts/gen_notes.py` | manifest + 画像 → L/P/V/Concept + 索引 + Source Register 行 |
| `scripts/build_explainer_html.py` | 讲解源片段 → 单文件 HTML（图片 base64 内嵌） |
| `scripts/gen_quiz_bank.py` | 题源 → 题库 JSON + `dsh-ui` 围栏 + md 折叠答案（三形态同源） |
| `scripts/check_manifest.py` | 校验 manifest 自洽性 |
| `scripts/check_html_assets.py` | 校验讲解 HTML（占位残留 / 图数 / assets 双向差集 / 答案一致 / 宽度） |
| `scripts/check_vault_profile.py` | 校验画像声明的路径真实存在 |
| `scripts/check_note_frontmatter.py` | **画像驱动**的必填字段与结构要求检查 |
| `scripts/check_quiz_rules.py` | 六条出题规则（三级严重度：ERROR / WARN / N-A） |
| `scripts/check_all.py` | 质量门总入口，6 行汇总表 |
| `scripts/check_builder_alignment.py` | 用 AST 比对构建器与校验器的常量集，防漂移 |
| `scripts/check_doc_paths.py` | 审计文档引用的路径是否真实存在（就是本节这条纪律的执行者） |
| `templates/L-lecture.md` | L## 课堂笔记骨架 |
| `templates/P-deck.md` | P## 课件逐页索引骨架 |
| `templates/V-timeline.md` | V## 回放时间线骨架（按需） |
| `templates/Concept.md` | Concept — 概念页骨架 |
| `templates/T-capture.md` | 临时课堂捕捉骨架 |
| `templates/source-register-row.md` | Source Register 登记行规范 |
| `templates/explainer.html` | 单文件 HTML 模板（CSS/JS 逐字继承自已验证产物） |
