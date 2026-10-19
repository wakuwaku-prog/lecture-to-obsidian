# lecture-to-obsidian

把已经整理好的**课堂素材**变成能学的东西：**AI 讲解**（Obsidian md 为唯一真源，单文件 HTML 按需派生）+ **课后考题**（对话即时判分 / md 折叠答案 / 可导入题库的 JSON，**三形态同源**）+ **跨层质量门**。

这是流水线的**后半程**。前半程——从平台取课件页图 / 音轨 / 字幕，并生成 `L##` 课堂笔记、`P##` 课件逐页索引、`V##` 时间线、`Concept` 概念页——在同机的 skill **`better-awesome-sjtu-canvas-ppt`**。

```
better-awesome-sjtu-canvas-ppt                    本 skill
──────────────────────────────                    ─────────────────────────
平台回放 → 采集 → raw/
          ├ build_manifest.py ──► manifest.json ───┐（契约）
          ├ build_vault_profile.py ► vault-profile.json ─┤（契约）
          └ gen_notes.py ──► L## / P## / Concept      │
                                                      ▼
                            讲解 md 真源 ──► build_explainer_html.py ──► 单文件 HTML
                            题源         ──► gen_quiz_bank.py ────────► JSON / 围栏 / md
                                                      │
                                        check_all.py ◄┘  6 行汇总
```

**分工的理由**：采集要按平台写适配器、笔记要按知识库画像落地，这两件事的证据全在平台和库里；
讲解与考题是**产物生成**，证据全在契约文件上。混在一个 skill 里，改采集总会碰到讲解的测试基线。

## 设计要点

| 层 | 做什么 | 归属 | reference |
|---|---|---|---|
| **L0–L1** 采集 / 素材 | 平台适配器 → 抽帧 / OCR / 页码两路校验 / 分段转写 → manifest + 归档 + 来源登记 | better | 见 better 的文档 |
| **L2** 笔记 | `L##` / `P##` / `V##`（按需）/ `Concept`；索引、双链、来源登记同步 | better | 见 better 的文档 |
| **L3** 讲解 | md 真源（证据标记 + 配图）→ 按需派生单文件 HTML | **本 skill** | [`references/03-explainer.md`](references/03-explainer.md) |
| **L4** 考题 | 对话卷子（`dsh-ui`）/ md 折叠答案 / 题库 JSON v1 —— **三形态同源** | **本 skill** | [`references/04-quiz.md`](references/04-quiz.md) |
| **L5** 质量门 | 汇总两边的产物：链接、结构、必填、出题规则、HTML 资产、manifest 一致性 | **本 skill** | [`references/05-quality-gates.md`](references/05-quality-gates.md) |

层间只通过**两份冻结契约**传递（`manifest.json`、`vault-profile.json`），schema 在 better 里。
本 skill 只认契约，**不解析平台响应，也不重算时间码和页码**。

## 三条铁律

1. **不产生学习记录。** 平台侧只做**只读 GET**，不播放视频、不触发心跳上报、不点「任务点」；超星每节带 `jobid`，播放即留下**不可逆**的完成记录。本 skill 不碰平台，但引用课堂内容时同样不能为了「核实」去播放视频。
2. **先读目标库自己的 `AGENTS.md`，再动手。** 各库的目录、frontmatter、媒体政策、证据标记都能不同。冲突时**以目标库 AGENTS.md 为准**。
3. **不猜。** 页码读不出来标「待核实」；**课件存在 ≠ 课堂讲过**；**只读转写 ≠ 听过音频**——前者只能写「按转写核对」。

## 安装

两个 skill 并排放在 DSH 的 skills 目录下（本机为 `~/.dsh/skills/<name>/`）：

```bash
git clone <this repo> ~/.dsh/skills/lecture-to-obsidian
git clone <better repo> ~/.dsh/skills/better-awesome-sjtu-canvas-ppt
```

本 skill 默认从这个路径找前半程；装在别处时给 `check_all.py --canvas-ppt-skill <dir>`。

依赖：Python 3（标准库 + 可选 `jsonschema`，缺了会打印「已降级」并走内置最小校验）。

## 怎么用

### ① 先让 DSH 自己路由（推荐）

直接说需求，skill 会按 description 自动命中：

> 讲解这节课 / 逐节讲解 L08 / 把这条笔记做成讲解 HTML
> 出随堂题 / 出课后题 / 生成题库 / 跑一下质量门

### ② 手动跑后半程

```bash
SKILL=~/.dsh/skills/lecture-to-obsidian
BETTER=~/.dsh/skills/better-awesome-sjtu-canvas-ppt
VAULT="<你的 Obsidian 库根>"
PROFILE="$VAULT/_scripts/vault-profile.json"      # 由 better 的 build_vault_profile.py 生成

# 前提：better 已产出 manifest.json 与 vault-profile.json
#       （画像没生成成功就不要往下走）

# 1. 讲解：先写 md 真源，再按需派生单文件 HTML
python "$SKILL/scripts/build_explainer_html.py" --src "<src.html>" --out "<out.html>" \
       --vault "$VAULT" --profile "$PROFILE"

# 2. 考题：一份题源 → 三种产物
python "$SKILL/scripts/gen_quiz_bank.py" --src "<题源.md>" \
       --manifest "<工作目录>/manifest.json" --out "<题库目录>" --print all

# 3. 质量门（6 行：5 行查 better 的产物，1 行查本 skill 的）
#    注意：题库规则不在总门里，要用 check_quiz_rules.py 单独跑
python "$SKILL/scripts/check_all.py" --vault "$VAULT" \
       --manifest "<工作目录>/manifest.json" --profile "$PROFILE" --html "<out.html>"
```

前半程的三步（画像 → 素材清单 → 笔记）见 better skill 的 README / SKILL.md。

各脚本的完整参数以 `--help` 为准；语义与踩坑见对应 `references/`。

### ③ 只看本 skill 自己的两个校验器

```bash
python "$SKILL/scripts/check_html_assets.py" <讲解.html>   # 占位残留 / 图数 / 宽度 / 体积
python "$SKILL/scripts/check_quiz_rules.py" <题库.json>    # 六条出题规则
```

## 质量门的两条纪律

这个 skill 里最贵的一课，是同一类错误以**六种面貌**出现过：**「没查」被显示成「查了没问题」**。

1. **`SKIP` ≠ `PASS`。** 未执行的检查必须显式报 `SKIP` / `N/A` / `INCOMPLETE`，**且不计入 PASS**。要区分「规则本来不适用」（`N/A`，不影响退出码）与「应执行而未执行」（`SKIP`，**必须**使结果非通过）。
2. **必须双向证明。** 每个校验器都要对**故意违规的样例报错**、对**合规样例通过**。只证明一边的校验器不可信。

还有一条推论：**如果一个要求集让同类型的每一篇都报错，那几乎一定是要求集错了，不是笔记错了**（「出现过」被当成「必须有」，这个错出现了三次）。

## 仓库内容

```
SKILL.md                     入口：路由 + 铁律 + 讲解/考题/质量门 + 学习者偏好 + 交付物地图
docs/PLAN.md                 方案全文、证据台账、架构变更史、质量门纪律
references/00-pipeline.md    跨两个 skill 的总图与失败处理
references/03-explainer.md   讲解层：DOM 契约权威、两套测验形态、踩坑表
references/04-quiz.md        考题层：四级严重度、六条出题规则、兼容性证据
references/05-quality-gates.md  质量门：CLI、假绿灯三道防线、既有缺陷清单
schemas/quiz-bank.schema.json   题库契约（严格对齐 v1）
templates/explainer.html     单文件 HTML 模板（CSS/JS 逐字继承自已验证产物）
scripts/build_explainer_html.py     讲解源片段 → 单文件 HTML
scripts/gen_quiz_bank.py            题源 → 题库 JSON + dsh-ui 围栏 + md 折叠答案
scripts/check_html_assets.py        讲解 HTML 六项校验
scripts/check_quiz_rules.py         六条出题规则（ERROR / WARN / N-A / SKIP）
scripts/check_all.py                质量门总入口（跨 two skill 的 6 行汇总）
scripts/check_builder_alignment.py  用 AST 比对构建器与校验器的常量集，防漂移
scripts/check_doc_paths.py          审计文档引用路径是否真实存在
```

**采集 adapter、知识库画像、manifest、笔记生成器、笔记模板、笔记校验器**都在
`better-awesome-sjtu-canvas-ppt`。

## 已验证 / 未验证

**已端到端验证**（真实素材，心理库 L08，2026-10-19）：画像 → 素材清单 → L/P 笔记 → 讲解 md 真源 → 单文件 HTML（1.10 MB，7 张内嵌图，6 项自检全 PASS）→ 题库 JSON（8 题，出题规则 S/R1–R6 全 PASS）→ 质量门。三份契约过 JSON + Draft7 自校验。

**未验证**：题库规则 R3/R5 的语义部分只能出 warn 请人复核；`chapter-html` 派生模式只在
`single-file-html` 上端到端跑过。采集侧的未验证项在 better skill 里。

## 隐私说明

端到端试点用的是**真实课件与课堂内容**（未公开课件），存放在 better skill 的文档目录里。
若任一仓库转为 public，请先确认有权公开这些材料。
