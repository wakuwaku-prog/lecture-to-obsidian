# 02 · L2 笔记层（L## / P## / V## / Concept）

本层把 **manifest**（采集层唯一出口）变成**知识库里能复习的东西**，并按目标库画像落盘。

```
manifest.json + vault-profile.json
        │
        ├── build_vault_profile.py  →  vault-profile.json      （第 ① 步，永远第一步）
        └── gen_notes.py            →  L## / P## / V## / Concept
                                       + 索引更新片段
                                       + Source Register 待插入行
```

层间**只通过契约文件传递**：本层不解析平台原始响应，也不读 `raw/`。

---

## 1. 三条硬规则（机械执行，不靠自觉）

### 1.1 图片块必须**展开**

折叠 callout（减号）会让图**默认不可见**。

> **实测证据（有机化学库 2026-10-12）**：`02 课堂笔记` 的 509 处嵌入 **100%** 写在
> `> [!example]-` 折叠 callout 内（438 个块）。Obsidian 默认收起，**72/72 篇 L 笔记打开时
> 可见图片数为 0**。修复为 `[!example]+` 后，72/72 篇默认可见 509 张课件图，
> 残留 `[!example]-` = 0。

两条**等价可见**的写法，按画像 `callouts.slideBlock` 选：

| 库 | 画像 `callouts.slideBlock` | 实测计数 |
|---|---|---|
| 有机化学 | `[!example]+` | 439 处 `example+`，残留 1 处折叠 |
| 心理与精神健康 | `[!example]` | 105 处裸 `example`，残留 12 处折叠 |
| 细胞生物学和组织学 | **未找到**（该库无 example 约定） | 0 处；模板用 `[!example]+`，已报 warning |

`gen_notes.py` 的 `_force_expanded()` 会把 `[!example]-` 强制改写成 `[!example]+`，
`audit_output()` 在写盘前再扫一遍产物，**发现折叠的图片块就报错退出（退出码 3）**。

### 1.2 表格内嵌图片必须**转义竖线** `\|`

`![[路径|宽度]]` 写在表格单元格里时，`|` 会被 Markdown 当成新的列分隔符，整行错位。
表格内一律写 `![[路径\|宽度]]`。

画像 `images.escapePipeInTables` **恒为 true**（契约硬规则，不可关闭）。
`audit_output()` 逐行检查表格里的嵌入，未转义即报错。

### 1.3 默认**内嵌页图**，不用 `#page=`

> **实测证据**：心理库 P08 曾按 AGENTS.md §6.4「优先 `#page=` 链接、避免整套派生图片」
> 改成只内嵌纯图页、其余 24 页用 `[[…第8次课.pdf#page=N|…]]` 链接。
> **学习者反馈该链接点击无效**（具体现象未确认），2026-10-16 全部恢复为内嵌页图。

画像 `images.preferEmbeddedPageImage` **恒为 true**。`gen_notes.py` 产出
`![[09 参考资料/附件/…/PDF pNN.jpg|宽度]]`；`audit_output()` 检测到图片嵌入里出现
`#page=` 就报错。

> ⚠️ **不在此列**：`#page=` 作为**表格里的文本链接**（如 P04 的页码对照表）是既有约定，
> 三库实测共 96 / 11 / 390 处。本 skill 不动它们，但若学习者反馈同样点击无效，需一并处理。
> 画像生成时会把这条计数写进 `warnings`。

---

## 2. 第 ① 步：画像（`build_vault_profile.py`）

```bash
python "$SKILL/scripts/build_vault_profile.py" "<vault root>" \
       [-o <out.json>] [--print] [--with-meta] [--validate]
```

- **先读 `<vault>/AGENTS.md`，再扫目录实况。** AGENTS.md 是唯一权威。
- **冲突时以 AGENTS.md 为准**，冲突写进 `warnings`（不静默选一边）。
- 产出恒为 `reviewedByHuman: false`。**人工复核前只允许只读操作**——
  `gen_notes.py --apply` 会拒绝执行（自动降级为 dry-run）。
- `--validate` 用 `schemas/vault-profile.schema.json` 校验（优先 jsonschema，
  没有就退回内置最小校验器）。
- `--with-meta` 额外输出 `_scan` / `_evidence` / `_unresolved` / `_warnings` 台账，
  供人工复核；**这些下划线字段不属于 schema**，`--validate` 只校验正式字段。

### 2.1 三库实测差异（画像必须能表达的全部维度）

| 维度 | 心理与精神健康 | 细胞生物学和组织学 | 有机化学 |
|---|---|---|---|
| frontmatter 键 | `type` | **`note_type`** | `type` |
| `required`（交集） | 3 个 | 6 个（来自 AGENTS.md） | 3 个 |
| `requiredIsInferred` | **true** | false（AGENTS.md 逐字列出） | **true** |
| 课程代码 | HLT3202G | HLT3206G | **未找到**（课程系列，非单一课程码） |
| L 笔记页图宽度 | `540` | `760` | **不写宽度**（`![[路径]]`） |
| P 页面页图宽度 | `760` | `760` | **不写宽度**（用 `#page=` 文本链接） |
| 页图块 callout | `[!example]` | **未找到** | `[!example]+` |
| V## 默认创建 | 否 | 否 | **未找到** |
| 视频归档 | false | false（`.gitignore` 硬拦所有音视频扩展名） | false |
| 音频归档 | false | false | false |
| 转写归档 | **true** | **true** | **true** |
| 讲解产物落点 | `10 讲解 HTML` | **无** | `05 讲解稿` |
| 题库落点 | **未找到** | `刷题工具` | **未找到** |
| Git 严格度 | status + fetch + pull | status + fetch + pull | **未找到**（AGENTS.md 无 Git 条款） |
| 排除目录 | 无 | `07 课程任务/` | 无 |
| 共享仓库 | false | **true** | false |

### 2.2 frontmatter 必填：**分类型**推断（不是全局并集）

> **这是一个真缺陷的修复记录。** 旧策略用「出现频次前 12 项」当全局必填集，
> 心理库推出来是 12 个字段：
> `type, course_code, tags, status, source, date, title, lecture, concept, lecture_id, lecture_date, source_location`。
> 但 `title` / `lecture` / `concept` / `lecture_date` / `source_location` 是**分类型**字段——
> Concept 页有 `concept` 却没有 `lecture_id`，P 页有 `deck` 却没有 `lecture_date`。
> **没有任何单篇笔记能同时满足这 12 个**，于是 14 篇笔记报 23 个 ERROR，
> **全是假红灯**。假红灯长期存在就会被忽略，整套质量门随之失效。

新策略四个字段各司其职：

| 字段 | 语义 |
|---|---|
| `frontmatter.required` | **各类型必填集的交集**（每篇都有的字段）。心理库只剩 3 个 |
| `frontmatter.requiredPerNoteType` | **按类型的必填字段**——这才是「必填」的正确粒度 |
| `frontmatter.requiredIsInferred` | `required` 是推断的（AGENTS.md 未逐字列出）→ `true` |
| `frontmatter.perNoteType` | 类型 → **额外**字段（不在 `requiredPerNoteType` 里的），语义未变 |

推断规则：

- 某字段在**该类型**的笔记里出现率 **≥ 90%** 才算该类必填。
- 样本 **< 3 篇**的类型**不推断**（留空数组）——只有 1 篇笔记的类型，
  它的字段集就是那一篇的偶然写法，据此宣布必填是造红灯。写进 `warnings`。
- **字段名一律取自该库实际笔记，绝不规范化、绝不套用别的库的名字。**
  心理库的 L 笔记实际用 `lecture`（不是 `lecture_id`）、P 笔记用 `deck`（不是 `deck_id`）、
  Concept 用 `concept`。写「规范名」会让每篇 L 笔记都被报「缺 `lecture_id`」——又是一批假红灯。

### 2.2.1 三库实测（字段名 = 该库实际键名）

| 库 | `required`（交集） | 非空 `requiredPerNoteType`（节选） |
|---|---|---|
| 心理与精神健康 | `course_code, tags, type`（3） | `concept-note`(10篇) `concept` `course_code` `date` `source` `status` `tags` `title` `type`；`concept`(4) 含 **`term`**；`ppt-overview`(4) 含 **`lecture`**；`lecture-note`(9) 只剩 4 个 |
| 细胞生物学和组织学 | `note_type, course_code, status, source, date, tags`（6，来自 AGENTS.md，非推断） | `lecture`(5) 含 **`lecture`**；`concept`(18) / `method`(7) 用 `note_type` |
| 有机化学 | `course_code, tags, type`（3） | `lecture-note`(72) 含 **`lecture_id`** `module` `source_file` `source_location`；`deck-analysis`(21) 含 `deck_file` `ppt_id`；`chat-lesson`(12)；`study-guide`(32) |

**注意最后一行**：有机化学库确实用 `lecture_id`——因为**那是它的实际键名**，
不是我们套上去的规范名。同一件事在三个库里叫三个名字，这正是画像要表达的东西。

> **⚠ 心理库 `lecture-note` 的键名分裂（实测，需要人工决策）**
> 该类型 9 篇（含 1 篇 `Lecture Note Template.md`，也算在内）：
> - `L01–L03` 用 **`lecture_id`** + `module` + `source_location`（3 篇）
> - `L04–L08` 用 **`lecture`** + `date` + `deck`（5 篇）
>
> `lecture` = 5/9 = **56%**，`lecture_id` = 4/9 = **44%**——**两者都 < 90%**，
> 所以 `lecture-note` 的必填集里**没有定位键**，只剩
> `course_code / status / tags / type`。
>
> 这是**该库真实的不一致**，不是推断失败。若强行把 `lecture` 定为必填，
> `L01–L03` 会立刻被报「缺 `lecture`」——又是假红灯。
> **需要学习者/维护者先统一键名**，再回来收紧必填集；本 skill 不替它决定。

### 2.2.2 `requiredIsInferred=true` 时的降级要求

`required` 是**推断值，不是要求**。当
`frontmatter.requiredIsInferred == true` **且** `vault.reviewedByHuman == false` 时：

- **校验器不得据此报 ERROR**，只能报 WARN/INFO，并写明「画像未经人工复核」。
- `build_vault_profile.py` 在 stdout 明确打印该提示（含字段数与「按类型必填请读
  `requiredPerNoteType`」）；`gen_notes.py` 也会打印同样的提示。
- 人工把 `reviewedByHuman` 置 `true` 后，同一批发现才升为 ERROR。

### 2.2.3 `structure` 块：复用校验器的硬编码启发式会误报

> **实测**：心理库 14 篇笔记被复用校验器报 22 个问题，多数是因为它只认固定小节名，
> 且**对 P 页面（课件逐页索引）也要求主动回忆题**——P 页面本来就没有回忆题。

| 字段 | 推断方式 |
|---|---|
| `summarySectionAliases` | 实际出现过的「中文总结」类小节标题（去掉编号前缀）；**过长（>28 字）或不含总结类关键词的不收**——`## 四、一张总结图（怎么问）` 是内容标题，不是小节名 |
| `summaryDetection` | 有总结的笔记全用编号标题 → `any-numbered-heading`；否则 `heading-alias`；一篇都没有 → `not-required` |
| `recallQuestions` | 按类型取**最小值**（下界），不是最大值——否则会把某篇的写法变成对全类型的硬要求。**P 页面实测为 0** |
| `requireToVerifyList` | 该类型 ≥80% 的笔记有「待核实」小节才算要求 |
| `requireUncheckedToVerifyItem` | 同上，针对「至少一条未勾选 `- [ ]`」 |
| `demoteReusedFindings` | 只列有明确映射的类别：`summary` / `recall` / `to-verify` / `frontmatter`。**不设 `other`**——一个接受值却不产生效果的配置项会让人以为它生效了 |

分组键优先用 **frontmatter 类型值**（`lecture-note` / `ppt-note` / `concept`）。
编号前缀（L/P/V/T）只作为补充键，且**只在「该前缀下确实有 `<前缀>##` 形式的笔记」时才加**：
心理库的 `02 课堂笔记/README — Lecture Notes.md` 不以 `L` + 数字开头，
若把它算进 `L` 组，`L` 的最小值会被拉成 0，与 `lecture-note: 3` 自相矛盾。

### 2.3 「未找到」的字段（**不猜**）

画像把读不出来的字段记进 `_unresolved[]`（字段名 + 原因），并汇总成一条 `warnings`。
实测各库的未找到项：

- **三库共有**：`frontmatter.statusEnum`（AGENTS.md 没列 status 取值）、
  `explainer.imageMaxEdgePx`、`explainer.maxBytes`、`quiz.questionsPerSet`
- **心理库另加**：`dirs.timeline`、`dirs.method`、`dirs.quizBank`
- **细胞库另加**：`dirs.timeline`、`dirs.disorder`、`dirs.explainer`、
  `callouts.slideBlock`、`evidenceTags`
- **有机化学另加**：`dirs.timeline`、`dirs.method`、`dirs.disorder`、`dirs.quizBank`、
  `dirs.templates`、`images.lectureWidth`、`evidenceTags`、
  `git.requireStatusBeforeEdit`、`git.requireFetchBeforeEdit`、`vault.courseCode`

**不硬塞**：例如有机化学库的 L 笔记与 P 页面**都不写宽度**（509 / 344 处无宽度嵌入），
全库其它位置的宽度是 `760/700/560`。这是真实的第三种约定，
画像把 `images.lectureWidth` 记作 `null` 并说明，**不替它编一个数**。

---

## 3. 第 ⑥ 步：笔记生成（`gen_notes.py`）

```bash
# 默认 dry-run：只打印 + 写临时目录，不碰知识库
python "$SKILL/scripts/gen_notes.py" --manifest <manifest.json> --vault "<vault root>" \
       [--profile <json>] [--out-dir <tmp>] [--with-timeline] [--with-concept TERM]...

# 真正写盘（会先跑 Git 门；画像 reviewedByHuman=false 时自动降级为 dry-run）
python "$SKILL/scripts/gen_notes.py" --manifest <m.json> --vault "<vault>" --apply [--force]
```

| 参数 | 作用 |
|---|---|
| `--dry-run` | 只打印/写 `--out-dir`。**这是默认值** |
| `--apply` | 真正写盘；写前跑 Git 门 |
| `--force` | 覆盖已有笔记。**默认不覆盖**，改写 `<name>.new.md` |
| `--with-timeline` | 额外生成 V##。**默认不建**——三库都要求按需 |
| `--with-concept TERM` | 生成 Concept 骨架（可重复） |
| `--sample` | 用内置的 L08 真实素材样例 manifest 自测 |
| `--validate-manifest` | 先按 `schemas/manifest.schema.json` 校验 |
| `--allow-pull` | 工作区干净时允许 `git pull --ff-only`（默认**不**主动同步） |

退出码：`0` 成功；`2` 参数问题；`3` 产物自检/校验失败；`4` Git 门拦住。

### 3.1 「课件存在 ≠ 课堂讲过」的唯一机器可判依据

**`slides[].projections` 为空数组 = 未见对应讲解。**

这是本层最重要的一条判定。**有页图不代表讲过**。`gen_notes.py`：

- L 笔记的「课堂覆盖与证据边界」表按 projections 统计已讲授 / 未见对应讲解；
- 正文骨架**只按放映记录**（`project_rows()`）生成小节，顺序是**课堂放映顺序**，
  不是 PDF 页序；
- P 索引逐页写「课堂放映：无——`projections` 为空，**未见对应讲解**」；
- 全部无放映记录时，L 笔记状态写 **`slide-based`（课件版）**，不写「已讲授」。

**同一页可以有多条 projections，不要按页号去重**：L08 实测 p9 在第15节 49:13 与
第16节 00:01 都放映过；p29 在 41:12 放映、42:49 重放；p31 在 42:19、42:52 重放。
产物里这三页各出现两次。

### 3.2 `contentType` 不是「坏页」

| 取值 | 含义 | 笔记里怎么写 |
|---|---|---|
| `slide` | 课件页 | 正常 |
| `video` | **嵌入视频占位** | 「该页是视频，PDF 里是未导出的视频占位，**不是坏页或排版错误**；具体讲解口径待视频或转写确认」 |
| `activity` | 课堂活动/练习页 | 标出，不当课件正文 |
| `desktop` | 教师桌面/应用窗口截图 | **不是课件页**，不能当课件内容引用 |
| `unknown` | 未判定 | 保留，不猜 |

L08 p13 = `video`：第16节 12:51 播到约 15:47，片名 *The Science of Memory —
Dr. Yewande Pearse*，画面依次出现 Hippocampus、Encoding、Long-Term / Short-Term。

### 3.3 页脚是**小节编号，不是页码**

`pageNoScope` 取值 `section | page | none`；**L08 = `section`**。

> **实测**：p26–p31 与 p33 页脚**都是 10**（7 页共享一个小节号）、p8/p9/p11 都是 03、
> p17/p18 都是 06。**页脚重复是正常的**，不是异常。

因此：

- **不能当唯一页码用**；引用一律以 **PDF 阅读页**为准。
- `pageNoStatus` 只有五种：`verified | anomalous | mismatch | missing | not-applicable`。
- **只有 `anomalous` / `mismatch` / `missing` 进待核实清单**。
  重复**不进**清单。
- `anomalous` = 两路读数一致但**明显偏离相邻页序列**。L08 只有 **p24 = 42**
  （前后页 08/09）。按目标库 AGENTS.md「保留原读数、不静默改名」处理。
- `missing` = 无页脚数字（含底部为「数据来源」等其它内容行）。L08 = **p4、p5、p13、p14、p15**。
- P 索引的「页脚 ↔ PDF 阅读页对照表」**必须带「所属小节 / 单元」一列**，
  并说明同小节多页共享编号——否则读者会以为编号连续、唯一。

### 3.4 必须进待核实清单的事实

`collect_to_verify()` 逐条搬运 manifest 里已有的事实，**不产生结论**：

| 来源字段 | 为什么必须留痕 |
|---|---|
| `pageNoStatus` ∈ {anomalous, mismatch, missing} | 页脚读数与判断依据，保留原样 |
| `isPureImagePage` | 纯图页文本为空，必须以图像为准，不能按上下文补齐 |
| `textExtractionIssue` | 文本顺序/内容不可直接采信 |
| `contentType: video / desktop` | 不是坏页 / 不是课件页 |
| `projections` 为空的页 | 未见对应讲解 |
| `pdf.isSelection: true` | **这份 PDF 是选页**；课堂可能还放了 PDF 之外的页 |
| `session.usedDeck` ≠ 内容基准课件 | 该节次有部分内容**无法在索引中定位** |
| `session.deckCoverageNote` | 覆盖范围说明 |
| `unarchivedMaterials[]` | **未归档材料**——不记这条，复核者会以为课件完整 |
| `transcript.knownMishearings` | 这些词**不能作为逐字教师引语** |
| `transcript.qualityNote` / `speakerLabelsAreInferred` | 限制可引用范围；说话人标签是推断 |
| `platformArtifacts[]` | 平台 AI 产物**只作交叉校验、不直接引用** |
| `media.archived: false` | 只登记来源与「原始媒体未归档」状态，**不建失效链接** |
| `manifest.warnings[]` | 逐条附在清单末尾 |

L08 实例：`usedDeck: 第9次课.pptx` + `deckCoverageNote: 0:00–35:07 未使用 S84`
→ 产物写明「本次课前半段不在 S84 范围内」，否则复核者会以为课件完整。

---

## 4. 模板（`templates/`）

| 模板 | 产物 | 关键约束 |
|---|---|---|
| `L-lecture.md` | L## 课堂笔记 | 图片块展开；覆盖表；页脚异常；待核实清单 |
| `P-deck.md` | P## 课件逐页索引 | 页脚对照表**带所属小节列**；逐页放映记录；`contentType` 提示 |
| `V-timeline.md` | V## 回放复核页 | **默认不建**；时间线用 `projections`；媒体/转写表 |
| `Concept.md` | Concept — 术语 | 跨课次复用；操作化与测量是重点 |
| `T-capture.md` | T 临时课堂捕捉 | 低打扰；整合后按库规则删除 |
| `source-register-row.md` | Source Register 行 | **本 skill 不擅自编号**；三库表头不同 |

模板里的 `{{占位}}` 由 `gen_notes.py` 填；作者注写在 `{#- … -#}` 里，
**不会出现在产物中**。产物里残留任何 `{{x}}` 都会被 `audit_output()` 报错。

### 4.1 Source Register：三库表头**实测不同**

| 库 | 表头 |
|---|---|
| 细胞生物学和组织学 | `\| ID \| 类型 \| 原始文件 / 来源 \| 日期 \| 状态 \| 备注 \|` |
| 心理与精神健康 | `\| ID \| 类型 Type \| 标题 / 文件名 \| 日期 \| 状态 Status \| 备注 \|` |
| 有机化学 | 运行时读表头确认；**本 skill 不假设** |

- `sourceRegisterEntries[].id` 允许为 `null`——**`S##` 由目标库分配**。
  L08 pilot manifest 自带 S84/S85/S88/S89/S90，本层原样打印，不改编号。
- **一节课拆成两段时分别登记**（一行一节，对应真实 `source.sessions[]`），
  这**不影响**它们合成同一篇 L 笔记。
- 已删除的媒体只登记状态，**不建失效链接**。

---

## 5. Git 安全

`gen_notes.py --apply` 写盘前跑 **Git 门**（`git_gate()`）：

```
status --short --branch  →  fetch origin  →  比对 @{u}（rev-list --left-right --count）
                         →  工作区干净才 pull --ff-only（且要 --allow-pull）
```

- **只读**：`status` / `fetch` / `rev-list` / `rev-parse`。本脚本**不做**
  `add` / `commit` / `push`——暂存由人工按 `stageOnlyTargetFiles` 执行。
- `git fetch` 失败 → **本次不写盘**（目标库 AGENTS.md 要求「无法连接时立即停止本库编辑并报告错误」）。
- 远端有本地尚未包含的提交 → **本次不写盘**，先读差异。
- 工作区有已跟踪文件的未提交修改 → **不 pull、不合并**；只新增文件。
- 未跟踪文件（`??`）不阻断——本 skill 只新增笔记。
- 禁止：`git reset --hard`、`git checkout -- .`、`git clean`、`git push --force`。

> ⚠️ **共享库（细胞生物学和组织学）**：`07 课程任务/` 已被 `.gitignore` 排除。
> 若它出现在 `git status` 的未跟踪列表里，说明忽略规则被改动——**停下核对**，
> 不要为了清空状态而删除本地文件。本层**不在该库执行任何 git 写操作**。

---

## 6. 幂等与断点续跑

- 本层只读 manifest + 画像。重跑同一层不改变下游输入（除非契约变了）。
- **不覆盖已有笔记**：默认写 `<name>.new.md` 供比对；`--force` 才覆盖。
- 画像 `reviewedByHuman: false` 时 `--apply` 自动降级为 dry-run。
- 契约变更时：**先改 schema，再改各层**，并在 `docs/PLAN.md` 的开放问题里记一笔。

---

## 7. 已知边界（未验证 / 未实现）

- **画像 `frontmatter.statusEnum` 恒为「未找到」**：三库 AGENTS.md 都没列 status 取值，
  目录实况只能给实例、不能给枚举。本层不猜。
- **`frontmatter.required` 在心理库与有机化学库是推断值**（`requiredIsInferred=true`）：
  复核前不得据此报 ERROR。**真正的必填粒度是 `requiredPerNoteType`**。
- **心理库 `lecture-note` 的定位键名不统一**（`lecture` 5 篇 / `lecture_id` 4 篇，
  都 < 90%），因此该类型的必填集里**没有定位键**。这是库的真实不一致，
  需维护者先统一键名；本层不替它决定（详见 §2.2.1）。
- **样本 < 3 篇的类型一律留空必填集**：心理库 22 个类型、细胞库 18 个、有机化学 8 个
  属此情形。宁可少报，不造红灯。
- **`images.timelineWidth` 恒为 null**：V## 是三库的按需产物，没有实测样本。
- **V## 只在心理库跑过 dry-run 的形状验证**（`--with-timeline`），
  细胞库与有机化学库未跑；`naming.timeline` 在有机化学库是「未找到」。
- **有机化学库的 `git.*` 记为 false 是「未找到」而非「不要求」**——
  编辑该库前必须人工确认。
- **有机化学库的 L/P 编号格式与 `lectureId` 不匹配**：该库实际用
  `L1.1` / `P10.1`（章节号），而 manifest 的 `session.lectureId` 形如 `L08`。
  本层按 `lectureId` 拼文件名，**没有该库的编号转换规则**，落到该库时需人工改名。
  这条是「未找到规则」，不是「格式就是这样」。
- **`#page=` 文本链接未处理**：三库分别有 96 / 11 / 390 处，用于表格内页码对照。
  契约只规定**图片嵌入**默认内嵌，这些文本链接不在改动范围内。
- **本层不生成讲解 HTML、不生成题库**（属 L3/L4）。
- **未跑过 `--apply`**：所有自测都是 dry-run 或写临时目录，
  三个真实知识库**未被修改**。
