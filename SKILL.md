---
name: lecture-to-obsidian
description: >
  Obsidian 知识库的**后半程**：把已经整理好的课堂素材变成能学的东西——
  ① AI 讲解（Obsidian md 为唯一真源，单文件 HTML 按需派生）；
  ② 课后考题（对话即时判分的 dsh-ui 卷子 / md 折叠答案 / 可导入的题库 JSON v1，三形态同源）；
  ③ 跨层质量门（一条命令汇总整个流水线的产物检查）。
  前半程——采集课件页图 / 音轨 / 字幕，生成 L## 课堂笔记、P## 课件逐页索引、
  V## 时间线、Concept 概念页——在同机 skill `better-awesome-sjtu-canvas-ppt`。
  当用户提到"讲解这节课""逐节讲解""做讲解 HTML""把笔记做成讲解"
  "出随堂题""出课后题""生成题库""检查讲解""质量门"时使用。
---

# lecture-to-obsidian — 讲解 · 考题 · 质量门

本 skill 是流水线的**后半程**。前半程（采集 + 笔记）在 `better-awesome-sjtu-canvas-ppt`：

```
better-awesome-sjtu-canvas-ppt                      本 skill
────────────────────────────────                    ──────────────────────────
平台回放 → adapters/ → raw/
            │
            ├─ build_manifest.py ──► manifest.json ────┐（契约）
            ├─ build_vault_profile.py ► vault-profile.json ─┤（契约）
            └─ gen_notes.py ──► L## / P## / Concept     │
                                                        ▼
                              讲解 md 真源 ──► build_explainer_html.py ──► 单文件 HTML
                              题源         ──► gen_quiz_bank.py ────────► JSON / 围栏 / md
                                                        │
                                          check_all.py ◄┘  （6 行汇总，4 项查 better 的产物）
```

**顺序**：先跑 better 出 `manifest.json` 与笔记，再跑本 skill。本 skill **不重复采集与笔记逻辑**，
只读那两份契约。

**默认从 `~/.dsh/skills/better-awesome-sjtu-canvas-ppt` 找前半程**；装在别处时给
`check_all.py --canvas-ppt-skill <dir>`（该选项同时用于定位 better 的画像/manifest/笔记校验器）。

## 0. 三条铁律（先读，违反即停）

1. **不产生学习记录。** 平台侧只做**只读 GET**，不播放视频、不触发心跳上报、不点「任务点」。
   本 skill 自己**不碰平台**——采集在 better 里；但讲解里引用课堂内容时同样不能为了「核实」
   去播放视频留下记录。
2. **先读目标库自己的 `AGENTS.md`，再动手。** 各库的目录、frontmatter、媒体政策、证据标记都能不同。
   冲突时**以目标库 AGENTS.md 为准**，本 skill 的默认值只是兜底。
3. **不猜。** 页码读不出来标「待核实」，转写可疑标「待核实（转写修正）」。
   **课件存在 ≠ 课堂讲过**；**只读转写 ≠ 听过音频**——前者只能写「按转写核对」。

## 1. 讲解（L3）：md 真源 → 单文件 HTML

**Obsidian md 是唯一真源；HTML 按需派生，不默认派生。** 画像 `explainer.mode` 是总闸
（`none` / `markdown-only` 时脚本直接退出码 4）。

```bash
python "$SKILL/scripts/build_explainer_html.py" \
       --src "<src.html>" --out "<out.html>" \
       --vault "<vault root>" [--profile <画像>] [--mode single-file-html|chapter-html]
```

- `{{IMG:相对库根的路径|caption|w=720}}` → 构建时按长边等比缩小、base64 内嵌，
  并**强制**加 `style="max-width:min(Npx,100%)"`（写死 px 会在窄屏顶破卡片）。
- 六项自检默认执行，任一 FAIL → **退出码 3，不写出文件**：占位残留 / 图数一致 /
  assets 双向差集 / 窄屏宽度 / 体积上限 / 测验答案下标。
- **DOM 契约已冻结**（骨架、类名、`data-*`、判分行为），权威定义在
  [`references/03-explainer.md`](references/03-explainer.md)。CSS/JS 逐字继承已验证产物，
  **不要重新设计**。改动顺序：先改 reference，再改 `templates/explainer.html`，最后改脚本。
- `.quiz` 上的 `data-groups` 属性在真实产物里 **JS 从不读取**；真正生效的是每个 `.q`
  上的 `data-group`。照抄错的那个 = 判分静默失效。

## 2. 考题（L4）：一份题源 → 三种产物

```bash
python "$SKILL/scripts/gen_quiz_bank.py" \
       --src "<题源.md 或 .quizsrc.json>" --out "<题库目录>" \
       [--manifest <manifest.json>] [--lang zh|en|both] [--print all]

# 只有 manifest、还没写题源时，先产出一份待填骨架
python "$SKILL/scripts/gen_quiz_bank.py" --manifest <manifest.json> --out "<work dir>" --emit-source-template
```

三种产物**由同一份题源生成**（同源是构造保证的，不是靠人工对齐）：

| 产物 | 用途 |
|---|---|
| 题库 JSON v1 | 可直接拖进既有刷题工具（细胞库 `刷题工具/`），严格对齐 `schemaVersion: 1` |
| `dsh-ui` 围栏 | 对话里即时判分的卷子（`validate_dsh_ui` 必过） |
| md 折叠答案 | Obsidian 里「先作答再展开」 |

出题规则见 [`references/04-quiz.md`](references/04-quiz.md)：六条（正确项非最长 / 下标打散不成周期 /
干扰项非荒谬 / 无措辞暗示 / 同卷不自相矛盾 / 解析指回来源），四级严重度
**error / warn / N-A / SKIP**（`SKIP` 表示该规则应执行而未执行 → 必须使结果非通过）。

> **导入器不执行出题规则。** 实测：一份「正确项下标成规律」的题库照样被 `validateBank`
> 接受。所以 `check_quiz_rules.py` 是 §7 六条规则的**唯一执行点**，不是锦上添花。

## 3. 质量门（L5）：一条命令

```bash
python "$SKILL/scripts/check_all.py" --vault "<vault root>" \
       [--manifest <manifest.json>] [--profile <画像>] [--html <...>] [--work <work dir>]
```

6 行汇总，其中 **5 行查的是 better 的产物**（`manifest` / `vault-profile` /
`note-frontmatter` / 复用的 `vault-links` 与 `note-structure`），本 skill 自己只出
`html-assets`。

> ⚠️ **题库规则不在总门里。** `check_all.py` 没有 `quiz` 行，`check_quiz_rules.py` 必须
> **单独跑**。这是已知缺口（见 `docs/PLAN.md` §14），别把「总门 PASS」当成「题库合规」。

**两条纪律**（本 skill 里最贵的一课）：

1. **`SKIP` ≠ `PASS`。** 未执行的检查必须显式报 `SKIP` / `N-A` / `INCOMPLETE`，**且不计入 PASS**。
2. **必须双向证明。** 每个校验器都要对**故意违规的样例报错**、对**合规样例通过**。
   只证明一边的校验器不可信。

> 实测过的四个「假绿灯」：复用的 `check_vault_links.py` 对不存在的库路径静默报 OK；
> `check_note_structure.py` 把 frontmatter 字段名硬编码为 `type`；
> 题库导入器接受规则违规的库；`check_all.py` 曾在有降级项的分支上崩溃、且崩溃前刚打印过「0 个问题」。

## 4. 学习者的偏好与硬约束

> 这些是**学习者本人在库 `AGENTS.md` 第 7 节里明确写下的**。与目标库冲突时以后者为准；
> 库没写全时按这里兜底。

**讲解节奏（最容易漏的一条）**

- **分部分推进**：一段只讲一个重点，用短句，避免长句与大段一次倾倒。
- 每部分讲完给 **2–5 道**选择/简答题，**停下来等学习者回答**再进入下一部分。
  这是**交互节奏**，不是产物题量——产物题量见 [`references/04-quiz.md`](references/04-quiz.md)。
- 学习者答「不知道」时，**换具体例子、数字或反例重讲**，不重复原句。
- **讲细、讲深、讲全**：逐页覆盖重要信息，**不跳过** Checkpoint、插入页、术语表或历史页。

**配图与图示**

- 有助于理解时**优先用可编辑的 Mermaid 流程图 / 关系图 / 比较图**；生成后检查术语、方向、标签，
  **不用装饰图替代知识结构**。
- 配图优先级：**课件页图 > 可结构化渲染的图 > 自绘**；自绘只在两者都覆盖不到时用。

**贴图分两种场合，规则不同**

| 场合 | 写法 |
|---|---|
| **对话（聊天正文）** | Markdown 图片走 `localPathMediaUrl → fileMediaUrl`，而 `fileMediaUrl` 里有 `!isAbsoluteWorkspacePath(path) → return void 0`，所以**相对路径永远不显示**。必须写**绝对路径**，且空格、括号、中文要**百分号编码**。**用脚本生成，不要手写。** |
| **共享笔记（Obsidian）** | 统一 `![[附件路径\|宽度]]`，**不写本机绝对路径**。 |

**安全与来源纪律**

- **学习资料不得转化成自我诊断或医疗建议。** 临床解释必须标出来源、适用范围与证据限制。
- **「已听」≠「按转写核对」。** 只读了 TXT/SRT/VTT 或自动转写只能写「按转写核对」；
  **只有真的播放/听取过音频**才能写「已听/已核对音频」。自动说话人标签是**推断**。
- 证据标记多一类：补人物或研究背景时标 **`[背景补充，非课件原文]`**，交代谁、什么情境、说明什么。

## 5. 禁止事项

- 不写 `http://127.0.0.1:...` 这类临时服务地址进任何笔记或图片链接；不为「让图片显示」启动预览服务。
- 不把签名 URL、cookie、token、个人绝对路径写进笔记、Source Register 或题库。
- 不重新设计已冻结的 DOM 契约（类名 / `data-*` / 判分行为）。
- 不删除原件、旧版本、课堂截图、转写或有引用的派生材料。
- 不执行 `git reset --hard`、`git checkout -- .`、`git clean`、`git push --force`。
- 不在目标库里创建游离文件；临时产物放工作目录，整合后清理。

## 6. 交付物地图

> 纪律：**本文件与 `references/` 里提到的每个路径都必须在交付物里真实存在。** 引用前先确认；
> 改完用 `python scripts/check_doc_paths.py` 核一遍。文档承诺了不存在的路径，会让接手者
> 以为某道防护已生效——比没有防护更危险。

| 路径 | 作用 |
|---|---|
| `SKILL.md` | 本文件：路由 + 铁律 + 偏好 + 契约指针 |
| `docs/PLAN.md` | 方案全文、证据台账、架构变更史、质量门纪律 |
| `references/00-pipeline.md` | **跨两个 skill 的**总流水线与层间契约 |
| `references/03-explainer.md` | 讲解层：**DOM 契约权威**、两套测验形态、踩坑表 |
| `references/04-quiz.md` | 考题层：四级严重度、六条出题规则、兼容性证据 |
| `references/05-quality-gates.md` | 质量门：CLI、假绿灯三道防线、既有缺陷清单 |
| `schemas/quiz-bank.schema.json` | 题库契约（严格对齐 v1） |
| `scripts/build_explainer_html.py` | 讲解源片段 → 单文件 HTML（图片 base64 内嵌） |
| `scripts/gen_quiz_bank.py` | 题源 → 题库 JSON + `dsh-ui` 围栏 + md 折叠答案（三形态同源） |
| `scripts/check_html_assets.py` | 校验讲解 HTML（占位残留 / 图数 / assets 双向差集 / 答案一致 / 宽度 / 体积） |
| `scripts/check_quiz_rules.py` | 六条出题规则（四级严重度：ERROR / WARN / N-A / SKIP） |
| `scripts/check_all.py` | 质量门总入口，6 行汇总表 |
| `scripts/check_builder_alignment.py` | 用 AST 比对构建器与校验器的常量集，防漂移 |
| `scripts/check_doc_paths.py` | 审计文档引用的路径是否真实存在 |
| `templates/explainer.html` | 单文件 HTML 模板（CSS/JS 逐字继承自已验证产物） |

**前半程的交付物**（采集 adapter、画像、manifest、笔记生成脚本、笔记模板、笔记校验器，
以及笔记规范与采集契约两份长文档）在 `~/.dsh/skills/better-awesome-sjtu-canvas-ppt`。
