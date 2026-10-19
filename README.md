# lecture-to-obsidian

把**视频学习平台上的课堂材料**整理进 **Obsidian 知识库**：采集课件页图 / 音轨 / 字幕，生成 `L##`（课堂笔记）、`P##`（课件逐页索引）、`Concept`（概念页），产出 **AI 讲解**（Obsidian md 为唯一真源，单文件 HTML 按需派生），并出**课后考题**（对话即时判分 + 可导入题库的 JSON）。

这是 [better-awesome-sjtu-canvas-ppt](https://github.com/wakuwaku-prog/better-awesome-sjtu-canvas-ppt) 的下游：那个 skill 负责**从平台把素材取下来**，这个 skill 负责**把它变成能复习、能自测的知识库内容**。

## 设计要点

**五层流水线，层间只通过契约文件传递，不靠口头约定。**

| 层 | 做什么 | reference |
|---|---|---|
| **L0 采集** | 平台适配器：发现课程/节次 → 取课件页图 → 取视频/音轨 → 平台文本 | `references/01-acquisition.md` |
| **L1 素材** | 抽帧 / OCR / 页码两路校验 / 分段转写 / 说话人分离 → 统一 manifest + 归档 + 来源登记 | `references/01-acquisition.md` |
| **L2 笔记** | `L##` / `P##` / `V##`（按需）/ `Concept`；索引、双链、来源登记同步 | `references/02-notes.md` |
| **L3 讲解** | md 真源（证据标记 + 配图）→ 按需派生单文件 HTML | `references/03-explainer.md` |
| **L4 考题** | 对话卷子（`dsh-ui`）/ md 折叠答案 / 题库 JSON v1 —— **三形态同源** | `references/04-quiz.md` |
| **L5 质量门** | 链接、结构、出题规则、HTML 资产、manifest 一致性、Git 安全 | `references/05-quality-gates.md` |

采集层按平台换适配器，**下游平台无关**：SJTU Canvas 课堂回放、超星学习通、只有教师 PDF 时走 PDF 渲染页图。

## 三条铁律

1. **不产生学习记录。** 平台侧只做**只读 GET**，不播放视频、不触发心跳上报、不点「任务点」。超星每节带 `jobid` 任务点，播放即留下完成记录——**不可逆**。
2. **先读目标库自己的 `AGENTS.md`，再动手。** 每个知识库的目录、frontmatter、媒体政策、Git 流程都可能不同（有的库连转写都不入库）。冲突时**以目标库 AGENTS.md 为准**。
3. **不猜。** 页码读不出来标「待核实」，页脚重复标 `dup`，转写可疑标「待核实（转写修正）」。**课件存在 ≠ 课堂讲过**——没有回放证据的页不能写成「已讲授」。

## 安装

skill 放在 DSH 的 skills 目录下即可被自动发现（本机为 `~/.dsh/skills/<name>/`，含 `SKILL.md`）：

```bash
git clone <this repo> ~/.dsh/skills/lecture-to-obsidian
```

依赖：Python 3（标准库 + `jsonschema`，可选；缺了会打印「已降级」并走内置最小校验）。Canvas 采集另需 `opencli doctor` 全绿。

## 怎么用

### ① 先让 DSH 自己路由（推荐）

直接说需求，skill 会按 description 自动命中：

> 把这个回放整理到 Obsidian：`https://oc.sjtu.edu.cn/...`
> 讲解这节课 / 逐节讲解 L08 / 出课后题 / 生成题库

使用前请先**在浏览器登录对应平台**（Canvas 还需要 `opencli doctor` 全绿）。

### ② 或者手动跑流水线

```bash
SKILL=~/.dsh/skills/lecture-to-obsidian
VAULT="<你的 Obsidian 库根>"

# 1. 生成知识库画像（必须先做；没成功就不要往下走）
python "$SKILL/scripts/build_vault_profile.py" "$VAULT" \
       -o "$VAULT/_scripts/vault-profile.json" --validate

# 2. 采集 → 素材清单
python "$SKILL/adapters/canvas.py" --ppt-json "<平台课件轨清单.json>" \
       --session "<节次标签>" --drop-desktop --dedupe-thresh 0.82 --dry-run --out "<工作目录>"
python "$SKILL/scripts/build_manifest.py" "<工作目录>"

# 3. 笔记（默认 dry-run，确认形状后再 --apply）
python "$SKILL/scripts/gen_notes.py" --manifest "<工作目录>/manifest.json" \
       --vault "$VAULT" --profile "$VAULT/_scripts/vault-profile.json" --out-dir "<工作目录>/notes"

# 4. 讲解：先写 md 真源，再按需派生单文件 HTML
python "$SKILL/scripts/build_explainer_html.py" --src "<src.html>" --out "<out.html>" \
       --vault "$VAULT" --profile "$VAULT/_scripts/vault-profile.json"

# 5. 考题：一份题源 → 三种产物
python "$SKILL/scripts/gen_quiz_bank.py" --src "<题源.md>" \
       --manifest "<工作目录>/manifest.json" --out "<题库目录>" --print all

# 6. 质量门
python "$SKILL/scripts/check_all.py" --vault "$VAULT" \
       --manifest "<工作目录>/manifest.json" --profile "$VAULT/_scripts/vault-profile.json"
```

各脚本的完整参数以 `--help` 为准；语义与踩坑见对应 `references/`。

### ③ 只看质量门

```bash
python "$SKILL/scripts/check_manifest.py" <manifest.json>          # 素材清单自洽
python "$SKILL/scripts/check_quiz_rules.py" <题库.json>            # 六条出题规则
python "$SKILL/scripts/check_html_assets.py" <讲解.html>           # 占位残留 / 图数 / 宽度
python "$SKILL/scripts/check_note_frontmatter.py" --profile <画像> --vault "$VAULT"
python "$SKILL/scripts/check_vault_profile.py" <画像.json>
python "$SKILL/scripts/check_all.py" --vault "$VAULT"              # 总入口，6 行汇总
```

## 质量门的两条纪律

这个 skill 里最贵的一课，是同一类错误以**六种面貌**出现过：**「没查」被显示成「查了没问题」**。

1. **`SKIP` ≠ `PASS`。** 未执行的检查必须显式报 `SKIP` / `N/A` / `INCOMPLETE`，**且不计入 PASS**。区分「规则本来不适用」（`N/A`，不影响退出码）与「应执行而未执行」（`SKIP`，**必须**使结果非通过）。
2. **必须双向证明。** 每个校验器都要对**故意违规的样例报错**、对**合规样例通过**。只证明一边的校验器不可信。

还有一条推论：**如果一个要求集让同类型的每一篇都报错，那几乎一定是要求集错了，不是笔记错了**（「出现过」被当成「必须有」，出现了三次）。

## 仓库内容

```
SKILL.md                    入口：路由 + 三条铁律 + 契约指针 + 交付物地图
docs/PLAN.md                方案全文、证据台账、契约演进史、质量门纪律
docs/pilot/                 基准 fixture + 端到端试点产物（见下方隐私说明）
references/00-pipeline.md   五层总览与失败处理
references/01-acquisition.md  L0/L1 采集层：两条路径、三个 adapter、上游真实签名
references/02-notes.md      L2 笔记层：画像、模板、三库实测差异
references/03-explainer.md  L3/L4 讲解层：DOM 契约权威、两套测验形态、踩坑表
references/04-quiz.md       L4 考题层：三级严重度、六条出题规则、兼容性证据
references/05-quality-gates.md  L5 质量门：CLI、假绿灯三道防线、既有缺陷清单
schemas/                    3 份冻结契约（manifest / vault-profile / quiz-bank）
adapters/                   平台适配器（canvas / chaoxing / pdf）+ 共用模块
scripts/                    画像、清单、笔记、讲解、题库生成器 + 6 个校验器 + 2 个防漂移/审计工具
templates/                  L/P/V/Concept/T 笔记骨架 + 单文件 HTML 模板
```

### 基准 fixture

`docs/pilot/L08.manifest.json` 是一份**真实素材**的清单（35 页 / 2 节次 / 38 条放映记录），由 `docs/pilot/make_L08_fixture.py` 可重跑生成。它是这个 skill 的设计基础：**先用手工 fixture 反压契约、再写代码**，这一步推翻了 5 处原本的假设（一节课其实是两个平台节次、一页可以有多次放映、页脚是小节号不是页码、平台课件轨是屏幕快照轨、教师 PDF 是选页）。

## 已验证 / 未验证

**已端到端验证**（真实素材，2026-10-19）：画像 → 素材清单 → L/P 笔记 → 讲解 md 真源 → 单文件 HTML（1.10 MB，7 张内嵌图，6 项自检全 PASS）→ 题库 JSON（8 题，出题规则 S/R1–R6 全 PASS）→ 质量门。三份契约过 JSON + Draft7 自校验。

**未验证**（缺已登录会话或真实音轨）：超星 `--live` 平台响应解析、Canvas `--list` 的 opencli eval、路径 A 真实联网下载、路径 B 的抽帧 / OCR / 转写 / 说话人分离。逐条列在 `references/01-acquisition.md` 的未验证清单里。题库规则 R3/R5 的语义部分只能出 warn 请人复核。

## 隐私说明

`docs/pilot/` 里含**真实的课件页图与课堂内容**（未公开课件）。若本仓库转为 public，请先确认你有权公开这些材料；只想要代码与文档的话，可以只保留 `SKILL.md` / `references/` / `schemas/` / `adapters/` / `scripts/` / `templates/`。

文档里的本机路径已参数化为 `<Obsidian 库根>` / `~/.dsh`，不含用户名。
