# 05 · L5 质量门

> 任一红即未交付。四个本 skill 的校验器 + **复用** `better-awesome-sjtu-canvas-ppt`
> 的两个既有校验器，全部**只读**：不写、不改、不创建任何文件。

```bash
SKILL="$HOME/.dsh/skills/lecture-to-obsidian"
python "$SKILL/scripts/check_all.py" --vault "<vault root>" --work "<work dir>"
```

---

## 0. 为什么质量门要单独一层

上游四层（采集 / 素材 / 笔记 / 讲解 / 考题）各自都有「看起来对」的失败模式：

| 失败模式 | 症状 | 谁抓 |
|---|---|---|
| 构建占位符没替换 | 页面显示字面量 `{{IMG:…}}` | `check_html_assets.py` |
| 内嵌图数与声明不符 | hero 写 20 张、实际 18 张 | `check_html_assets.py` |
| 题目的判分下标与解析矛盾 | 点对了却判错 | `check_html_assets.py` |
| 时间码口径混淆（毫秒当秒） | 时间码整体偏 1000 倍 | `check_manifest.py` |
| 页码两路读数不一致却写 verified | 页码错位，笔记指向错页 | `check_manifest.py` |
| 画像目录猜错 | 笔记写到错误目录（最贵） | `check_vault_profile.py` |
| 内链指向不存在的文件 | Obsidian 里是死链 | 复用的 `check_vault_links.py` |
| 笔记缺 frontmatter / 回忆题 | 结构不完整 | 复用的 `check_note_structure.py` |

**这些都不是「内容对不对」的问题，而是「形状对不对」的问题。** 内容对不对只能人工判断。

---

## 0.1 ⚠️ 通用纪律：文档提到的路径必须真实存在

> **文档里提到的每个脚本 / 模板 / 引用路径，都必须在交付物里真实存在。**
> 引用前先 `test -f`；写完后用一次全量清单核对「文档提到的路径 ⊂ 实际文件」。

**为什么单列一条**：本 skill 的存在理由之一，就是
`better-awesome-sjtu-canvas-ppt` 的 README 指向了**不存在**、**未交付**的
`docs/OBSIDIAN-NOTES.md` 与 `templates/` —— 文档承诺了没交付的东西。

这类失配比普通笔误**更坏**：接手者会以为某道防护已经生效，于是不再手工核对，
**结果比没有防护更差**。本 skill 自己也犯过一次（文档引用了
`check_builder_alignment.py`，但该文件当时只存在于临时目录、**未落地**），
所以这条纪律是踩过之后写下来的。

**自检命令**（本 skill 自己的工具，覆盖全部文档）：

```bash
python "$SKILL/scripts/check_doc_paths.py" [--skill-root DIR] [--quiet]
```

它扫描 `SKILL.md` + `references/*.md` + `docs/PLAN.md`，把形如
「受管目录名 + 斜杠 + 文件名」的引用抽出来逐个 `test -e`；
退出码 `0` = 无缺失，`1` = 有引用了但不存在的路径。

**否定语境**（「不存在 / 未交付 / 未落地 …」同行出现）里的提及不算承诺，会被跳过 ——
所以本节提到别人缺的那两个路径不会误报。**写这类示例时必须带上否定词**，
否则审计会把它当成真实引用（写本节时实测踩过一次）。

> **写示例时的坑**：连**占位符**也别写成可被正则抽取的样子 ——
> 受管目录名 + 斜杠 + 文件名 的形态会被抓成真引用，即使它只是说明用的例子。
> 本节第一版就因此报了 2 处假缺失。举例请用文字描述该形态，不要写出字面路径。

任何一行 `MISSING` 都必须先修文档或补文件，再谈交付。

---

## 0.2 ⚠️ 通用纪律：入口脚本任何分支都不许抛未捕获异常

> **`check_all.py` 是质量门总入口。它在任何分支下都必须正常退出（0 或 1），
> 不许抛 `Traceback`。**
>
> **任何「通过」的结论，必须在脚本正常退出之后才打印。**

**为什么单列一条**：入口脚本崩溃意味着**整套验收无法执行**。更坏的是——
崩溃前最后一行可能已经打印了「0 个问题」，读者会以为通过了。
**这比明确报错更危险**：报错至少让人知道要修。

**踩过的实例**：F 重构把 `demoted` 条目从三元组加宽成**四元组**，
只改了生产侧、漏改消费侧，于是**只有走到「有降级项」分支时才崩**；
无降级那条路径把问题掩盖了。所以：

- 这类 bug **必须双向自测**：让「有 X」与「无 X」两条路径都跑一遍。
  只测一条会漏 —— 这次就是。
- 从容器里取字段**用结构化元素，不要用字符串匹配去猜语义**。
  同一次修里，`fm_n` 原先是 `why == "frontmatter 字段名"` 猜出来的，
  改成直接用第 4 个元素 `cat == "frontmatter"`。字符串推断是踩过的坑
  （`assets.skipped` 那次也是）。

**自检**（两个方向 + SKIP 路径都要跑）：

```bash
# 方向 1：有降级项（心理库 + 含 structure 的画像）
python "$SKILL/scripts/check_all.py" --vault "<心理库>" --profile "<画像>"
# 方向 2：无降级项（最小沙箱 + 画像白名单置空）
# 方向 3：裸跑（大量 SKIP 分支）
python "$SKILL/scripts/check_all.py" --vault "<心理库>" --quiet
```

判据不是「退出码好看」，而是**输出里没有 `Traceback`**。

---

## 1. 五个校验器

> 前四个是通用的；**`check_note_frontmatter.py` 是画像驱动的**，
> 用来替代复用校验器硬编码字段名的误报（见 §2）。

### 1.1 `check_manifest.py` — 素材清单自洽

```bash
python "$SKILL/scripts/check_manifest.py" "<work>/manifest.json" \
       [--schema "$SKILL/schemas/manifest.schema.json"] [--quiet] [--json]
```

退出码 `0` = 无 ERROR，`1` = 有 ERROR。

核心检查（**都是查「状态声明与读数是否自洽」**）：

| 检查 | 规则 |
|---|---|
| 顶层 | `schemaVersion=1`；`source.sessions` 与 `pdf` 不能同时为空 |
| 作废字段 | 顶层 `media`/`transcript`、`source.session`、`slides[].isSlide`/`startSec`/`sessionIndex` 出现即 ERROR |
| sessions | `label` 非空；同一 `lectureId` 下 `partOfSplit` 不重复；有 media/transcript 却无 `durationSec` → WARN |
| media | `archived=true` 必须有 `videoPath` 或 `audioPath` |
| transcript | 内联了 `segments` 才比对 `segmentCount`（`segmentCount` 也可指外部文件段数）；`endSec ≥ startSec`；`speakerLabelsAreInferred` 必须 `true` |
| slides | `index` 从 1 连续；`source` 合法；**`platform-ppt-track` 不得残留 `contentType: "desktop"`**（路径 A 的关键断言） |
| projections | `sessionIndex` 落在 sessions 范围内；`startSec` 必填；有 `startMmss` 必须能换算一致；`timecodeSource` 必填；单位口径自洽（`createSec` 是毫秒、`imageSeekTime` 是秒） |
| 单调性 | **按 `sessionIndex` 分组**查组内 `startSec` 递增；组内 `isReplay: true` 允许回退 |
| 页码 | 见 §2 |
| pdf | `isSelection: true` 必须在 `warnings` / `unarchivedMaterials` / `pdf.note` 里留痕 |
| 留痕 | `unarchivedMaterials[].what` 与 `.evidence` 都非空；`usedDeck` 应在 `unarchivedMaterials` 或 Source Register 里有对应条目 |
| warnings | 逐条打印（WARN，不影响退出码） |

### 1.2 `check_html_assets.py` — 单文件讲解 HTML

```bash
python "$SKILL/scripts/check_html_assets.py" <a.html> [more.html ...] \
       [--assets-dir DIR] [--declared-list FILE] [--declared-images N] \
       [--quiet] [--json]
```

| # | 检查 | 说明 |
|---|---|---|
| 1 | `{{IMG:` 残留 = 0 | 构建占位符必须全部替换 |
| 2 | `data:image/` 计数 = 声明图数 | 声明来自页面「内嵌 N 张」或 `--declared-images` |
| 3 | assets **双向差集为空** | 引用了不存在的文件 = 破图；目录里有没被引用的 = 多带文件 |
| 4 | 每题 `data-a`/`data-answer` 与解析「答案 X」一致 | 解析没写字母时**跳过**（不制造假红） |
| 5 | hero 徽章题数 = 实际题数 | 「共 N 题」/「做 N 道选择」/「N 道选择题」 |
| 6 | `<img>` 上没有写死 px 宽度 | 应用 `max-width:min(Npx,100%)`，否则窄屏顶破卡片 |

另查：答案下标越界、radio `value` 序列不是 `0..n-1`、同题 radio `name` 不统一、
容器 `data-groups` 与各题 `data-group` 不自洽。

#### assets 口径优先级（与 `build_explainer_html.py` **逐字对齐**）

> 参数名与构建器一致，便于调用方复用同一组参数：
> `--assets-dir`（构建器 `--assets-dir`）、`--declared-list`（构建器 `--assets-list`）。

```
--assets-dir  >  --declared-list  >  自动探测（被校验 HTML 同级有 assets/ → 目录口径）
              >  HTML 内 <!--ASSETS:-->  >  SKIP
```

**每次运行都打印用了哪个口径**（含 SKIP），**不许无声降级**：

```
[assets.scope] assets 口径：assets/ 目录（自动探测：被校验 HTML 同级有 assets/）（…）
[assets.scope] assets 口径：声明清单（--declared-list）（…）
[assets.scope] assets 口径：未声明（SKIP）
```

两种口径的差集语义：

| 口径 | 正向（破图） | 反向（多带） |
|---|---|---|
| `dir` | 正文引用了但 `assets/` 里没有 | `assets/` 里有但没被正文引用 |
| `list` | 正文引用了但清单里没有（仅引用） | 清单里有但没被正文引用（仅声明） |

> **路径基准**：正文里的 `assets/xxx` 是相对 **HTML 所在目录**的。
> 目录口径下必须把引用换算到 assets 目录基准，否则两边都会报（实测踩过）。

#### ⚠️ SKIP ≠ PASS（本节最容易被忽略的一条）

走到 SKIP 时**不能显示成通过**——质量门里最危险的就是「没查却显示通过」：

| 情形 | 结论 |
|---|---|
| 有 assets 引用，但无任何口径信息 | `RESULT: INCOMPLETE` —— **明确写「这不是 PASS」**，退出码 **1** |
| 无 assets 引用（单文件 base64 形态） | 没有需要校验的差集 → 空操作，不影响结论（`[assets.notApplicable]`） |
| `--assets-dir` 指向**不存在**的目录 | **FAIL**（显式给了口径就必须能查），不是 SKIP |
| `--declared-list` 文件不存在 | **FAIL**，不是 SKIP |

`check_all.py` 把 `INCOMPLETE` 记为 **WARN + `incomplete=yes`**，**不计入 PASS**。
它**不再用文本去猜 SKIP**，而是直接用校验器自己的 `RESULT: INCOMPLETE` 判定
（用文本猜会把「无引用的单文件形态」误判，实测踩过）。

#### 与构建器的对齐保证

**已逐字对齐**，并由脚本持续验证，不靠人工记忆：

```bash
python "$SKILL/scripts/check_builder_alignment.py" [--scripts DIR]
```

读两份**源码**、用 AST 取出常量再比对（所以能真抓到漂移），退出码 `0`/`1`。

| 对齐项 | 说明 |
|---|---|
| `IMAGE_EXT` | `.jpg .jpeg .png .webp .gif .bmp .tif .tiff .svg`（9 项） |
| 兜底候选 | `assets.txt`、`图片清单.txt`（**顺序也一致**） |
| `norm_rel` / `parse_assets` / `list_image_files` | 路径归一、清单解析、目录列举 —— **函数名也一致** |

**唯一有意差异**：自动探测基准 —— 构建器用 `--out` 旁的 `assets/`，
校验器用**被校验 HTML 同级**的 `assets/`。校验器没有输出路径，只能以被校验文件为基准。
（构建器的兜底候选以 `--src` 所在目录为基准，校验器对应以被校验 HTML 所在目录为基准。）

> **漂移防护**：改动构建器的 `IMAGE_EXT` 或兜底候选后，必须同步校验器，
> 并跑上面的脚本确认两边常量集完全一致。helper **改名**同样会被它抓出来
> （实测：`parse_declared_list` 与构建器的 `parse_assets` 不同名 → 脚本判 FAIL，
> 已统一命名）。


### 1.3 `check_vault_profile.py` — 知识库画像

```bash
python "$SKILL/scripts/check_vault_profile.py" "<vault>/_scripts/vault-profile.json" \
       [--vault DIR] [--lenient-dirs] [--quiet] [--json]
```

- 结构：`schemaVersion=1`、`vault.root`/`name`、`dirs.lecture`+`dirs.attachments`、
  `mediaPolicy` 三个布尔；`dirs.excluded` 是**字符串数组**（不是字符串）。
- **画像声明的每个目录 / 模板 / Source Register 文件必须在库里真实存在**（缺失 = ERROR）。
- `vault.agentsMd` 指向的文件必须存在；没记 `agentsMd` → WARN（本 skill 的第一读就是它）。
- **`reviewedByHuman=false` → 明确 WARN**：画像未经人工复核时**只允许只读操作**，
  写笔记前必须人工确认目录映射。
- `explainer.imageWidthAttr` 不得写死 px；`quiz.*` 三条硬规则必须为 `true`。

### 1.4 `check_all.py` — 总入口

```bash
python "$SKILL/scripts/check_all.py" --vault "<vault root>" [--work DIR] \
       [--profile FILE] [--manifest FILE] [--html FILE ...] [--assets DIR] \
       [--canvas-ppt-skill DIR] [--min-recall N] \
       [--skip canvas-ppt,links,structure,frontmatter,profile,manifest,html] \
       [--quiet] [--json]
```

打印汇总表（每行：CHECK / STATUS / COUNTS / DETAIL），**任一 FAIL 即退出 1**。
STATUS 取值 `OK` / `WARN` / `FAIL` / `SKIP`；`WARN` 不导致退出 1。

`--skip canvas-ppt` 一次性跳过复用的两个校验器（`vault-links`、`note-structure`
与画像驱动的 `note-frontmatter`）。

### 1.5 `check_note_frontmatter.py` — 画像驱动的必填字段 + 结构

```bash
python "$SKILL/scripts/check_note_frontmatter.py" --profile "<vault-profile.json>" \
       [--vault DIR] [--quiet] [--json]
```

**字段名、必填清单、结构阈值全部来自画像**，**不写死** —— 这是与复用校验器的
关键差别，也是修复「复用启发式与本库约定不匹配」的那一层。

**① 读画像 `frontmatter`**

| 检查 | 规则 |
|---|---|
| frontmatter 块 | 必须有 `---` 开头的 YAML 块 |
| `requiredPerNoteType[<note_type>]` | 按类型的必填集，**恒为 ERROR** |
| `required` | 见下方「推断出来的要求不是要求」——可能是 WARN |
| `perNoteType[<note_type>]` | **不是必填清单，不参与判定**（见下） |
| 类型分布 | 打印实际 `note_type` 取值分布，便于核对画像两个 perNoteType 键是否过时 |

`note_type` 的字段名按 `note_type` → `type` 依次尝试；两者都没有 → WARN。

#### ⚠️ `perNoteType` 不是必填清单（并集 ≠ 必填）

画像里有**两个名字很像的键**，语义完全不同：

| 键 | 语义 | 校验器怎么用 |
|---|---|---|
| `requiredPerNoteType` | 该类型的**必填**字段（≥90% 推断，粒度正确） | **报 ERROR** |
| `perNoteType` | **信息性**：该类型**出现过**的可选字段**并集** | **只列出，不判定** |

> **实测撞车一次**：`perNoteType[lecture-note]` 是 **12 个字段的并集**
> （`date` / `deck` / `lecture` / `lecture_id` / `module` / `title` … 两种写法混在一起），
> 而 `requiredPerNoteType[lecture-note]` 只有 **4 个**。
> 把并集当必填 → **9 篇 L 笔记各被报缺 7–9 个字段，每篇都满足不了**。
> 这与前面「把推断值当硬要求」是**同一个错误换了一层**。

校验器只把 `perNoteType` 作为 INFO 列出，并写明**信息性，不代表必填**。

#### ⚠️ 推断出来的要求不是要求

> **当 `frontmatter.requiredIsInferred == true` 且 `vault.reviewedByHuman == false`
> 时，缺 `required` 里的字段只报 `WARN`，不报 `ERROR`。**

输出里写明：

```
[WARN] frontmatter.requiredInferred — 画像 frontmatter.required 是从目录频次**推断**的
       （requiredIsInferred=true）且未经人工复核（reviewedByHuman=False）；
       以下缺字段按 **WARN** 处理，**复核画像后才应视为硬要求**。
       按类型的 requiredPerNoteType 不受影响，仍报 ERROR。
```

**为什么**：`required` 可能是画像生成器从目录频次取 top-N **推断**出来的，
那些是**分类型**的字段（`title` / `lecture` / `concept` / `lecture_date` /
`source_location` …），并成全局必填后**任何单篇都满足不了** → 全库假红灯。
实测心理库因此一次报出十几条 ERROR，**全部来自一个未复核的推断值** ——
那不是笔记的问题，是画像的问题，不该由笔记承担 ERROR。
长期存在的假红灯会被忽略，整套质量门随之失效（见 §0 的动机）。

**严重度对照**：

| 字段来源 | 未复核 + 推断 | 已复核 或 非推断 |
|---|---|---|
| `frontmatter.required` | **WARN**（`frontmatter.requiredInferred`） | **ERROR**（`frontmatter.required`） |
| `frontmatter.requiredPerNoteType` | **ERROR**（不受复核状态影响） | **ERROR** |

`requiredPerNoteType` 是**按类型、粒度正确**的必填集（L 笔记要 `lecture_id`、
P 笔记要 `deck`），所以它不参与「软化」—— L 笔记缺 `lecture_id` 就是真问题。

> **实测对照**（同一份画像，只改两个开关；`requiredPerNoteType` 里用的是本库
> 真实字段名 `lecture_id` / `source_file`）：
> 未复核+推断 → `ERROR 7, WARN 15`；已复核 → `ERROR 21, WARN 0`。
> **14 条**全局缺字段从 ERROR 变 WARN，**其余照旧** —— 说明只是按复核状态区分，
> **没有把检查放空**。剩下的 7 条全部来自 `requiredPerNoteType`
> （L02/L04–L08 缺 `lecture_id`、缺 `source_file`），是**真问题**。

**② 读画像 `structure`**（阈值按**笔记类型**给；键是编号前缀 `L`/`P`/`V` 或 `Concept`）

| 画像键 | 作用 |
|---|---|
| `summarySectionAliases` | 总结小节的**别名** |
| `summaryDetection` | 总结小节**怎么认**：`heading-alias`（标题命中别名）/ `any-numbered-heading`（存在编号标题 `## 一、…` 即算）/ `not-required` |
| `recallQuestions` | 该类型主动回忆题的**最低道数**（**P## 应为 0** —— 它是逐页索引，本来就没有回忆题） |
| `requireToVerifyList` | 该类型是否必须有「待核实」清单 |
| `requireUncheckedToVerifyItem` | 「待核实」里是否必须有未勾选 `- [ ]` 项 |
| `demoteReusedFindings` | 复用校验器的**哪些类**发现允许按画像复核后降级：`summary` / `recall` / `to-verify` / `frontmatter` / `other` |

> 画像缺 `structure` 段时用内置兜底，并 **WARN 提示**用的是兜底阈值。
> 未列入 `demoteReusedFindings` 的类**一律不降级**（保守：宁可多报，不可漏报）。

`summaryDetection` **必须按库实况配，不能想当然**：

| 库 | 配置 | 说明 |
|---|---|---|
| 细胞生物学和组织学 | `any-numbered-heading` | 正文用 `## 1 …` 编号小节组织 |
| 心理与精神健康 | **`heading-alias`** | 该库模板要求「中文总结与英文关键词」这类**具名**小节 |

> **更正（我曾报错）**：我早先按手写画像说「两个真实库都配 `any-numbered-heading`」——
> **对心理库不成立**。用 `any-numbered-heading` 会让**任何**编号标题都算总结小节，
> 于是**掩盖 L02 / L08 缺总结小节这两个真问题**。
> 核实原文：L02 的二级标题是「主动回忆 / 学习行动 / 待核实 / 相关链接」，
> L08 是「主动回忆 / 待核实与开放问题 / 课堂事务 / 相关链接」——**两篇都没有总结小节**。
> 真实画像现在配 `heading-alias`（12 条别名），L02/L08 照常报 ERROR，**不要放宽**。

YAML 用 `yaml.safe_load` 解析；没有 PyYAML 时退化为「键存在性 + 空值」正则解析
（不因缺依赖而假装通过）。

#### 判据实现上踩过的两个坑（已修）

1. **回忆题计数不能只认数字题号**。L08 的题在 `### A. 课件原题` 之下，用
   `1. 2. 3.`；另有笔记用 `A.` / `B.`。现在两种都认
   （`^\s*(?:\d+|[A-Z])[\.\、]\s+`）。
2. **小节范围必须在下一个 `## ` 处截断**，不能用所有 `#`。用 `#{1,6}` 会让
   `### A.` 子标题把回忆小节提前切断 —— L08 实测因此被数成 **0 道**（误报）。
   现在用 `^#{1,2}\s`。

### 1.6 复用校验器的发现如何按画像复核

`check_all.py` 把 `check_note_structure.py` 的发现逐条与画像比对，
**只降它判错的那部分**，并在输出里写明：

```
[INFO] structure.reclassified — 复用校验器**结构要求硬编码**（总结小节别名、
       回忆题数、待核实清单），字段名也硬编码为 `type`；以下 20 项已按画像复核后
       降级为 INFO（不当作 ERROR）
```

| 可降级类 | 复用的硬编码 | 画像给的判据 |
|---|---|---|
| frontmatter 缺字段 | 字段名写死 `type` | `frontmatter.required` 的字段名 |
| 结构类发现 | 别名 / 阈值写死 | `structure` 段（按类型） |

**关键约束**：降级是**逐条**发生的，判据是「画像驱动的检查对该笔记的**同一项**
判为通过」。若画像检查也判失败，发现**原样保留**（绝不隐藏真红灯）。
降级后还会**修正末行汇总的问题数**，避免「输出说 22 个问题、汇总说 1 个」的矛盾。
**只有画像 `demoteReusedFindings` 列出的类才允许降级**；其余类（如「看不到节次或
时间码」「图片只放链接未内嵌」）一律保留 —— 那是真发现。

> 实现上必须用 `--json` 的**结构化 `note` 字段**归属笔记，**不要解析 message 文本**
> ——文本里的文件名会被截断，导致发现被误归属到别的笔记
> （实测踩过：L04 的「待核实」发现被错算到 L08 头上）。

### 1.7 `vault-links` 行：真断链 vs 已知局限

`check_vault_links.py` 的未解析行会**逐条分类**，避免读者以为库里有 N 处坏链接：

| 分类 | 判据 |
|---|---|
| **真断链** | 路径含未替换占位符（如 `#page=N`），或目标既非文件也非目录 |
| 已知局限 · 文档写法示例 | 形如 `![[附件路径\|宽度]]` 的说明文字，不是真链接 |
| 已知局限 · 目录型 wikilink | 目标**目录真实存在**，但该脚本只建文件索引 |

汇总行分别给出 `realBroken=` 与 `knownLimitation=`。若**全部**是已知局限
（`realBroken=0`），整行降为 **WARN** 而非 FAIL。

### 1.8 汇总表有 6 行

| CHECK | 来源 | 说明 |
|---|---|---|
| `manifest` | 本 skill | 素材清单自洽 |
| `html-assets` | 本 skill | 讲解 HTML |
| `vault-profile` | 本 skill | 画像路径真实存在 |
| `note-frontmatter` | 本 skill | **画像驱动**的必填字段检查 |
| `vault-links` | **复用** | canvas-ppt 的 `check_vault_links.py` |
| `note-structure` | **复用** | canvas-ppt 的 `check_note_structure.py` |

---

## 2. ⚠️ 复用校验器：两个「永远 exit 0」的假绿灯（最容易踩）

> **这一节是接手者最容易踩的坑，务必先读。**

| 脚本 | 真实 CLI | 退出码 |
|---|---|---|
| `check_vault_links.py` | `<vault_root>`（**没有 argparse**，位置参数就是库根） | **永远 exit 0** |
| `check_note_structure.py` | `<vault_or_dir> [--min-recall N] [--quiet]` | **永远 exit 0** |

**两个脚本无论发现多少问题都返回 0。** 所以「看退出码」完全无效，
`check_all.py` 必须解析 stdout：

- 链接：`checked N links/embeds in the vault` + `UNRESOLVED (N):`
  或 `OK: every wikilink and embed resolves to a real file`
- 结构：末行 `检查 N 篇笔记，M 个问题`

### 三道防线（都必须是 FAIL，不能是 WARN）

| 情形 | 为什么危险 | `check_all.py` 的处理 |
|---|---|---|
| 库根不存在 | `check_vault_links.py` 打印 `checked 0` + `OK: every wikilink…`，**路径写错 = 全过** | 调用任何复用校验器**之前**先断言库根存在且是目录 → **FAIL** |
| 扫描对象数 = 0 | 同上，红灯被误读成绿灯 | **FAIL**（`scanned=0` / `notes=0`） |
| 找不到预期统计行 | 脚本改版、输出格式变了 | **FAIL**（记 `UNKNOWN`，绝不当作通过） |

**这三条是「假绿灯」防线：一旦红灯被忽略，整套质量门就失效了。**

### 画像复核：硬编码判据的误报不算 ERROR

`check_note_structure.py` 把**两类判据**都写死了：

1. frontmatter 必填字段名 —— 硬编码 `type`。细胞生物学库的 `AGENTS.md` 规定用
   `note_type` → 该库**全部笔记**被误报「frontmatter 缺字段: type」。
2. **结构要求** —— 总结小节别名（只认 `中文总结|Chinese synthesis|Synthesis|
   整体理解|小结`）、回忆题道数（一律 ≥3）、「待核实」清单要求。心理库用编号小节
   `## 一、…` 与 `本课主线/本课总结`，且 **P## 是课件逐页索引、本来就没有回忆题**
   → 同一类误报的第二个实例。

若不处理，我们对这些库永远红灯，**红灯随即被忽略，整套质量门就失效了**。

处理方式（两层）：

1. **本 skill 自己做一次画像驱动的检查**（`check_note_frontmatter.py`，汇总表里的
   `note-frontmatter` 一行）：字段名、必填清单、结构阈值全部来自画像
   （`frontmatter` + `structure`），**它才是权威结论**。
2. 复用校验器的发现由 `check_all.py` **逐条复核后降级为 INFO**（详见 §1.6），
   输出里写明原因，并修正末行汇总的问题数。

**注意方向**：降级**逐条**发生，判据是「画像驱动的检查对该笔记的同一项判为通过」。
若笔记**真的**缺了画像声明的东西，`note-frontmatter` 行会**报 ERROR**
（自测里用删字段 / 删总结小节 / 减回忆题的沙箱证明过）——**降级不是把红灯藏起来**。

---

## 3. 页码状态：最容易写错的地方

页脚**不是页码，是小节 / 版式编号**。P08 对照表实测：p26–p31 与 p33 页脚
**都是 10**，p8/p9/p11 都是 03，p17/p18 都是 06。所以：

> **页脚数值与其他页相同，是正常现象，不报错、不警告。**

| `pageNoStatus` | 含义 | 校验要求 |
|---|---|---|
| `verified` | 两路读数一致 | `pageNoNormalized(full) == pageNoNormalized(footer)`；两路都得有值 |
| `anomalous` | 两路一致但明显不符合所属小节序列（L08 p24 页脚印 42，前后页 08/09） | **合法状态**：两路必须一致 + **`pageNoNote` 非空**，**不报错** |
| `mismatch` | 两路读数不一致 | 两路必须都有值**且不相等**；相等却标 mismatch → ERROR |
| `missing` | 无页脚数字 | 两路都应为空（有值 → WARN）+ **`pageNoNote` 非空**（ERROR） |
| `not-applicable` | 该页无页码体系 | 有读数 → WARN |

`pageNoScope`：`section` / `page` / `none`（L08 = `section`）。

### 两个必须避开的误报陷阱

1. **不要拿 `pageNoExpected` 当「应印值」去卡 `verified`。**
   页脚是小节编号，`pageNoExpected` 由采集层从读数归纳而来，拿它做判据会自我循环
   （L08 基准样本里 p24 的 `pageNoExpected` 就是 `"42"`，与读数相同）。
   `verified` 只要求两路一致。
2. **`pageNoFullOcr` 可能含版式标注**（如 `"实验心理学 11"`），
   比较一律走 `pageNoNormalized`（抽最后一串数字）。

---

## 4. 已知既有缺陷（**不属本 skill，不要顺手改**）

以下都是**复用脚本与既有知识库**的问题，**本 skill 只报告、不修改**。
它们会让红灯数量虚高，所以读原文再决定是否真修。

| # | 位置 | 现象 | 影响 |
|---|---|---|---|
| 1 | `check_note_structure.py` | frontmatter 必填字段名硬编码为 `type` | 用 `note_type` 的库（细胞库）**全库误报**；已由画像复核降级为 INFO |
| 2 | `check_note_structure.py` | 「中文总结小节」只认 `中文总结\|Chinese synthesis\|Synthesis\|整体理解\|小结` | 心理库用 `## 一、…` 编号小节 → 10 篇被误报「缺少中文总结小节」 |
| 3 | `check_note_structure.py` | 要求「待核实」清单里必须有**未勾选** `- [ ]` | 全部已核实的笔记被误报「清单为空」 |
| 4 | `check_vault_links.py` | 只建**文件**索引；目录型 wikilink 一律判断链 | `[[09 参考资料/附件/L06-L07 课件 PDF/\|…]]` 目录真实存在仍报 |
| 5 | `check_vault_links.py` | 不区分「文档里的写法示例」与真链接 | `AGENTS.md` 中 `![[附件路径\|宽度]]` 被算成 2 处断链 |
| 6 | **心理库 `01 课程资料/P08 …`** | 有一条**字面占位链接** `[[…第8次课.pdf#page=N\|…]]`（`N` 未替换） | **真实断链**；已另行向学习者报告，**本 skill 不得改动** |

第 6 条是唯一一条**真实的**库内断链（其余为脚本判据问题），
它由 `vault-links` 行如实报出。

---
   `## 一、…` 编号小节，于是 10 篇笔记被报「缺少中文总结小节」。
5. `check_note_structure.py` 的 `--min-recall 3` 对 `ppt-note` 与
   `lecture-capture` 有豁免，但对 `P##` 页是否算「课件索引」取决于其 `type` 取值。

**因此：`check_all.py` 里 `note-structure` 与 `vault-links` 的红灯要先人工读一遍
原文再决定是否真修**，不要盲目照着改笔记。

---

## 5. 只读纪律

- 五个脚本只 `open(..., encoding="utf-8")` 读，**从不写文件**；不建临时文件。
- 复用的两个脚本也是只读校验器。
- **发现库里既有问题只报告，不顺手改**——那不是本 skill 的写入范围（见 §4）。
- 自测若需要「坏样本」，**复制到临时目录再改**，绝不在真实库里造错误。

---

## 6. 实测结果（2026-10-19）

### 心理与精神健康（带画像）

```
manifest          WARN    errors=0 warns=1        warnings 非空（5 条，清单要求列出）
html-assets       OK      errors=0 warns=0        页面没声明内嵌图数；data:image/ 实际 20
vault-profile     OK      errors=0 warns=0
note-frontmatter  FAIL    errors=1 warns=0        L04 缺「待核实」
vault-links       FAIL    errors=4 realBroken=1 knownLimitation=3 scanned=1164  真断链 1 条
note-structure    FAIL    demoted=21 errors=1 notes=14
                          14 篇笔记 / 1 个问题；另有 21 项硬编码判据的发现已按画像复核
```

`note-structure` 从 **22 个问题降到 1 个**，且与 `note-frontmatter` 行
**完全一致**（同一批真问题，两条路径互相印证）：

| 真问题 | 说明 |
|---|---|
| **L04 缺「待核实」清单** | 该笔记正文确实没有「待核实」小节（其余 7 篇 L 笔记都有） |

> 画像用 `summaryDetection: any-numbered-heading`（两个真实库都用编号小节）。
> 曾有一处**我自己的**误报也在这里修掉：L08 的回忆题在 `### A.` 之下，
> 我的计数器一开始在 `###` 处截断小节 → 数成 0 道。修完 L08 回忆题 = 11 道
> （详见 §1.5 的两个坑）。

### 画像驱动结构（F）正反例

沙箱 = 心理库副本（复制到临时目录后改，原库未写入）：

| 样例 | 期望 | 实测 |
|---|---|---|
| L01 回忆题砍到 2 道 | ERROR | `structure.recallQuestions …2 道，画像要求 L 类 ≥3 道` |
| **P01 加 5 道回忆题** | **不报错**（P 阈值 0） | 无 finding（证明 P 类不被过度要求） |
| L03 删掉全部总结小节 | 仍通过 | 该笔记有编号标题，`any-numbered-heading` 下算有总结（**模式行为正确**） |
| L05 未改动 | 无 finding | 无 finding |
| 原库已有的 L04 真问题 | 保留 | 仍在 ERROR 清单里 |

> 注意：上表用的是**我手写的沙箱画像**（`any-numbered-heading`）。
> **真实画像对心理库用 `heading-alias`** —— 所以真实画像下 L02/L08 缺总结小节
> 会照常报 ERROR（那是真问题，见 §1.5 的更正）。

### 真实画像的端到端实测（`docs/pilot/e2e-L08/vault-profile.json`）

```
检查项 61 条；ERROR 2，WARN 1，INFO 26
  [structure.summarySection] L02 — 研究方法与行为学习 … 缺总结小节（heading-alias）
  [structure.summarySection] L08 — 记忆引导眼跳与知识表征 … 缺总结小节（heading-alias）
RESULT: FAIL（2 个 ERROR）
```

**13 → 2**：`perNoteType` 当必填造成的 11 条假红灯全部消失，
剩下 **2 条都是真问题**（L02 / L08 缺总结小节）。

> 关于 L04 缺「待核实」：真实画像里 `requireToVerifyList[lecture-note] = false`，
> 所以**不报**——这是画像驱动的正常结果，不是漏检。

### `vault-links` 分类（心理库 4 条未解析）

| # | 条目 | 分类 |
|---|---|---|
| 1–2 | `AGENTS.md` → `![[附件路径\|宽度]]`（第 87、97 行） | 已知局限 · **文档写法示例** |
| 3 | `08 课程考核/L06 复习…` → `[[09 参考资料/附件/L06-L07 课件 PDF/\|…]]` | 已知局限 · **目录型 wikilink**（该目录真实存在） |
| 4 | `01 课程资料/P08 …` → `[[…第8次课.pdf#page=N\|…]]` | **真断链**（`N` 未替换） |

→ `realBroken=1 knownLimitation=3`。**只有第 4 条是真断链**，
已另行向学习者报告；本 skill **不得改动**它（见 §4 第 6 条）。

### 细胞生物学和组织学（带画像）

```
vault-profile     WARN    errors=0 warns=1        画像未人工复核
note-frontmatter  OK      errors=0 warns=0        必填：note_type, course_code, status, tags
vault-links       OK      errors=0 scanned=536    扫描 536 个链接/嵌入
note-structure    FAIL    demoted=17 errors=4 notes=8
                          8 篇笔记 / 4 个问题；另有 17 项硬编码判据的发现已按画像复核
```

`note_type` 不再产生 ERROR，结构阈值也按画像走。剩余 **4 个真发现**
（**不属 `demoteReusedFindings` 允许降级的类，因此一律保留**）：

| 真发现 | 条数 | 说明 |
|---|---|---|
| 看不到节次或时间码（来源位置） | 3 | 该笔记没有节次/时间码/「第」字样的来源定位 |
| 有 10 处图片只放链接未内嵌（应写成 `![[...]]`） | 1 | 确实用了 `[[...]]` 而非 `![[...]]` |

这两类都不在画像 `demoteReusedFindings` 里 —— **保守不降级**，
需要人工判断是否真要改笔记。

### 假绿灯防线（B）正反例

| 输入 | 期望 | 实测 |
|---|---|---|
| `--vault C:/nonexistent/vault-xyz` | FAIL | `ERROR: 库根不存在…` → `EXIT=1`，且**未调用**复用校验器 |
| 存在但为空的目录 | FAIL | `vault-links FAIL scanned=0`；`note-structure FAIL notes=UNKNOWN` → `EXIT=1` |
| 真实库 | 正常扫描 | `scanned=1164` / `scanned=536` → 正常判定 |

空目录那一行是重点：`note-structure` 找不到统计行时记 **UNKNOWN 并 FAIL**，
不当作通过。

### 画像驱动 frontmatter（A）正反例

| 输入 | 期望 | 实测 |
|---|---|---|
| 细胞库（用 `note_type`） | PASS | `note-frontmatter OK errors=0`；8 项 `type` 发现降级 INFO |
| 沙箱：删掉 L01 的 `status` 整行 | ERROR | `[frontmatter.required] …缺必填字段 status` |
| 沙箱：L02 的 `tags:` 置空 | ERROR | `[frontmatter.empty] …必填字段为空：tags` |
| 沙箱：L03 删掉整个 frontmatter 块 | ERROR | `[frontmatter.missing] …缺 YAML frontmatter 块` |
| 沙箱：L04 未改动 | 通过 | 无 finding（证明不是一律报错） |

沙箱是**真实库的副本**（复制到临时目录后改），原库未被写入。

### assets 口径（E）五例

| # | 输入 | 期望 | 实测 |
|---|---|---|---|
| E1 | 单文件 base64 + `--declared-list`（正例） | PASS | `RESULT: PASS`，`口径=list；引用 1 / 声明 1 / 仅引用 0 / 仅声明 0`，EXIT=0 |
| E2 | 同上，清单多一条 | FAIL | `assets.unreferenced …仅声明 1：['assets/extra.png']`，EXIT=1 |
| E3 | 有引用但无任何口径信息 | **SKIP ≠ PASS** | `RESULT: INCOMPLETE（…**这不是 PASS**）`，EXIT=**1** |
| E4 | `--assets-dir` 指向不存在目录 | FAIL | `assets.dirMissing`，EXIT=1 |
| E5 | 章级形态（`assets/` 与 HTML 同级） | 自动探测 → 目录口径 PASS | `口径=assets/ 目录（自动探测：被校验 HTML 同级有 assets/）`，EXIT=0 |

真实 7 份产物（单文件 base64，无 assets 引用）：**全部 PASS**，EXIT=0
（`[assets.notApplicable]` 空操作，不影响结论）。

`check_all.py` 的三种情形：

| 情形 | html-assets 行 |
|---|---|
| 真实库 7 份（无引用） | **OK** |
| 有引用但无口径 | **WARN + `incomplete=yes`**（不计入 PASS） |
| 给了 `--declared-list` 的正例 | **OK** |

### 讲解 HTML（7 份真实产物）

L02 / L03 / L04 / L05 / L06 / L07 / L08 **全部 PASS**（ERROR 0）。
L03 与 L07 各 1 条 WARN：页面没写「内嵌 N 张」声明，无法核对图数
（可用 `--declared-images` 补）。

### 基准样本 `docs/pilot/L08.manifest.json`

```
检查项 537 条；ERROR 0，WARN 1，INFO 15
  slide.footerRepeat  页脚编号重复 6 组（section 作用域下正常，不报错）：
                      02 → [2,7,22]; 03 → [3,8,9,11]; 06 → [12,17,18];
                      07 → [19,20,21]; 10 → [26..31,33]; 11 → [10,32]
  projection.monotonic session 1：9 条；session 2：29 条，组内单调性已查
RESULT: PASS（无 ERROR）
```

35 页全通过：29 `verified`、5 `missing`（均有 note）、1 `anomalous`（有 note）；
38 条放映记录；`projections` 空数组 0 条。
唯一 WARN 是 `warnings` 非空（5 条），那是清单**要求**列出的待人工判断项。

### 构造样例（双向证明）

**必须报错的**：

| 样例 | 实测 |
|---|---|
| 读数改 99 但状态仍 `verified`（声明与读数不自洽） | `ERROR 1`：`slide.pageNoVerified` |
| 违规 manifest（16 类问题） | `ERROR 26, WARN 7` |
| 违规 HTML（8 类问题） | `ERROR 8, WARN 1` |
| 违规画像 | `ERROR 4, WARN 1` |
| 沙箱缺/空/无 frontmatter 必填字段 | `ERROR 3` |

**必须通过的**（证明不误报）：

| 样例 | 实测 |
|---|---|
| 页脚 10 出现在 p26–p31/p33（7 页，section 作用域） | `ERROR 0, WARN 0` |
| p24 式 `anomalous`（两路 42 + note） | `ERROR 0, WARN 0` |
| 两路不一致且已标 `mismatch` + note | `ERROR 0, WARN 0` |
| 合规 HTML（`site/page.html` + `site/assets/`，双向差集为空） | `ERROR 0, WARN 0` |
| 合规画像（真实心理库路径） | `ERROR 0, WARN 1`（未人工复核） |
| 细胞库用 `note_type` 的画像驱动 frontmatter | `ERROR 0` |

> 构造样例时注意：assets 双向差集要求 HTML 与 `assets/` 是**兄弟关系**
> （`site/page.html` ↔ `site/assets/`）。若把 HTML 放别处再指 `--assets` 到另一个
> 目录，两边都会报——那是**基准不一致**，不是产物有问题。
