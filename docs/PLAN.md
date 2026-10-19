# lecture-to-obsidian — 实施方案

> 目标：把「视频学习平台上的一节课」变成「Obsidian 知识库里能复习、能自测的一份东西」。
> 覆盖采集 → 笔记 → AI 讲解 → 课后考题 → 质量门全链路，平台可插拔。
>
> 状态：P0 骨架落地中。端到端试跑对象 = 心理与精神健康 L08。

---

## 0. 结论摘要

| 问题 | 结论 |
|---|---|
| 一个 skill 还是拆开？ | **一个**。五层共享同一份 `manifest.json` 与同一份知识库画像，拆开必然出现「上游改字段、下游静默错」。用 `SKILL.md`（路由 + 铁律 + 契约）+ `references/`（按层按需加载）拿到渐进披露的全部好处。 |
| 拆分判据 | 采集需覆盖**第二所学校**，或出现**第三个平台**时，把 `adapters/` 整体抽成 `sjtu-capture`。 |
| 与现有 skill 的关系 | Canvas 采集**调用** `better-awesome-sjtu-canvas-ppt`，不复制其 11 个脚本；超星采集内置于本 skill。 |
| 讲解的默认形态 | **Obsidian md 是唯一真源**，单文件 HTML 按需派生。 |
| 考题的默认形态 | 三份同源：对话 `dsh-ui` 卷子 / md 折叠答案 / 题库 JSON v1（可直接拖进既有刷题工具）。 |

---

## 1. 目标与非目标

**目标**

1. 一条命令能跑通「某平台某节课 → 知识库里的 L## / P## 笔记」。
2. 讲解与考题从同一份素材派生，**md 与 HTML 与题库三处内容不漂移**。
3. 换一门课、换一个库、换一个平台，只换配置与 adapter，**下游零改动**。
4. 每个结论可回溯到素材：页图 ↔ 解码时间码 ↔ 页码两路读数 ↔ 转写分段。

**非目标**

- 不做通用视频下载器（只支持已登录会话下的目标平台）。
- 不做 Obsidian 插件。
- 不替用户判断「这节课讲了什么」之外的课程政策。
- 不产出诊断、医疗或成绩预测类内容。

---

## 2. 四个来源的贡献与缺口

| 来源 | 已经有的 | 缺口（本 skill 要补） |
|---|---|---|
| `better-awesome-sjtu-canvas-ppt`（SKILL.md + 12 脚本） | Canvas 双路径采集；Whisper 分段转写；WavLM 说话人；`check_vault_links.py` / `check_note_structure.py` | README 指向的 `docs/OBSIDIAN-NOTES.md` 与 `templates/` **本机不存在**（实测目录只有 `SKILL.md` + `scripts/`）；无超星；无讲解/考题 |
| 有机化学 `AGENTS.md` | 超星链路（courseid/clazzid → knowledgeid → cards → ananas/status → 直链 + Referer）；只读安全边界；76 视频 / 21 PDF 实战规模 | 平台无字幕 → 必须本地 Whisper；无 PPT 轨 |
| 有机化学 `讲解格式.md` + `_scripts/NOTE_SPEC.md` | 讲解三分工；五类证据标记；matplotlib 字形与 `$` 落单坑；配图优先级 PPT帧 > RDKit > 自绘；章级 HTML 范式 | 551 行且高度化学专属（RDKit、结构式、纽曼投影），必须抽象掉学科内容 |
| 心理与精神健康 `AGENTS.md` + `_scripts/讲解HTML/SPEC — 课次智能体作业规范.md` | 对话讲解输出规则；随堂测验出题规则；单文件 HTML 精确规范（base64 内嵌 / 吸附目录 / 灯箱 / 暗色 / 打印 / 原生判分） | 单课 2–3 MB，体积需管 |
| 细胞生物学和组织学 `AGENTS.md` + 只读侦察 | 多学生共享库的 Git 流程；**媒体政策：不保存录音/视频/转写**；PDF → 页图 的第四条素材路线；**已沉淀的题库 JSON v1 规范 + 刷题工具** | 无 `V##`；作业目录 gitignored |

---

## 3. 平台对照：为什么采集必须做成两个 adapter

| 维度 | Canvas 回放 | 超星学习通 |
|---|---|---|
| 入口 | 课程页 → LTI `external_tool` → `play-center`；`teclId` → `subject_vod_list_new` → 每节 `courseId` | 课程页 → 章节 iframe → `studentcourse` → 解析 `toOld()` 的 `knowledgeid` → cards iframe |
| 鉴权 | 页面内 cookie；API 必须在页面内 `fetch`，外部调用报 token 缺失 | 页面内 cookie；**视频直链下载需 `Referer: https://mooc1.chaoxing.com/`** |
| 节次结构 | 一节课拆 **2 个节次**（如第 9/10 节），2 路机位 `record2`(≈850 MB) / `record5`(≈440 MB)，收音相同 | 19 章 79 节，一节一视频，可能另挂 PDF |
| 课件轨 | **有，但不是干净原图**：`pptShow=1` 时 `course/ai/ppt` 返回**屏幕快照轨**。实测 L08 两节共 131 条快照 vs 35 个 PDF 阅读页；最早几条是教师桌面，188 秒起是 **PowerPoint 编辑窗口（含功能区）**；`showFlag` 全为 `true`，**不能用来判断"是否放映"**。`pptShow=0` 时走场景抽取 | **没有**。只能从视频抽帧（关键帧 + aHash 去重，或解码场景检测） |
| 平台字幕 | 有 `ai/translate`（逐句 ASR + 时间码）与 `ai/textSummary`（导图 + 概要），作**交叉校验** | 接口存在（`richvideo/allsubtitle`）但本课**实测返回空** → 必须本地 Whisper |
| 时间码 | 部分录播容器有**重复 DTS**，`ffmpeg -ss` 会取到邻页（实测偏约 1 分钟） | 未见同类报告，但同样以**解码时间码**为默认 |
| 学习记录风险 | 只读 GET，不播放即可 | **额外**：每节带 `jobid` 任务点，绝不能触发心跳上报；只做串行只读 GET（200–300 ms 间隔） |

**结论**：差异封在 adapter 里，下游只认 `manifest.json`。

---

## 4. 架构

```
L0 采集适配层    adapters/{canvas,chaoxing,pdf}.py   ← 唯一按平台变化的地方
        ↓
L1 素材 manifest  schemas/manifest.schema.json       ← 契约单点
        ↓
L2 知识库画像     schemas/vault-profile.schema.json   ← 库差异单点
   + 笔记         L## / P## / V##(按需) / Concept —
        ↓
L3 讲解           md 真源（证据标记 + 配图）
        ↓
L4 派生           单文件 HTML（按需） + 考题三层
        ↓
L5 质量门         check_all.py（链接/结构/出题/HTML资产/manifest/Git）
```

---

## 5. 知识库画像（vault profile）

三库实测差异——这些**必须**由画像驱动，不能硬编码：

| 维度 | 心理与精神健康 | 细胞生物学和组织学 | 有机化学 |
|---|---|---|---|
| 采集源 | Canvas 回放 + 教师 PDF | Canvas 回放 + 教师 PDF | 超星学习通视频 |
| L 目录 | `02 课堂笔记` | `02 课堂笔记` | `02 课堂笔记` |
| P 目录 | `01 课程资料` | `01 课程资料` | `01 课程资料` |
| 讲解产物 | `10 讲解 HTML`（单文件） | 无 | `05 讲解稿`（md + 章级 HTML） |
| 考题产物 | `08 课程考核/*.html` | `刷题工具/题库/*.json` | `dsh-ui` 卷子 + md 折叠答案 |
| 配图来源 | 课件页图（base64 内嵌） | PDF 渲染页图 PNG | 抽帧 jpg / 自绘 PNG / RDKit |
| 图片宽度 | P 760 / L 520–560 / V 300 | 760 或不带 | 无统一 |
| 媒体政策 | 临时处理后清理 | **不入库（连转写都不存）** | 临时处理后清理 |
| V## | 按需建立 | **不默认创建** | 按需建立 |
| Git | 私有库，不要求 PR | 多学生共享，严格 fetch → diff → 干净才 pull | 单机库 |
| frontmatter | `type/course_code/lecture_id/...` | `note_type/course_code/status/source/date/tags` | `type/course_code/lecture_id/module/...` |

**同一件事在三库有三种写法**，画像必须能表达：

| 事项 | 心理库 | 细胞库 | 有机化学 |
|---|---|---|---|
| 图片 callout | `> [!example]+` | 直接内嵌 | `> [!example]-`（**已废弃，会让图默认不可见**） |
| 待核实 | `> [!warning] 待核实` | 正文「待核实」标记 | `> [!note] 待核实（转写修正）` |
| PDF 页引用 | `![[…pdf#page=N]]`（**学习者实测点击无效**） | 同上，仅 11 处 | 同上 |

---

## 6. 呈现形式规范

### 6.1 md 真源（唯一真源）

- frontmatter 按画像的 `frontmatter.required`；`source` / `source_location` 指回 `S##` 或页码/时间码。
- 五类证据标记分开：`[PPT原文]` / `[课堂口述]` / `[机器转写]` / `[我的推断]` / `[待核实]`。
- 图片：`![[路径|宽度]]`；**表格内嵌必须转义竖线** `![[…jpg\|300]]`。
- 课件页图块用**展开**的 callout（`[!example]+`）；折叠会让图默认不可见（有机化学库曾 72/72 篇笔记可见图数为 0）。
- 自测答案用 `> [!success]- 答案与解析` 折叠。
- 讲解正文里**不出现只影响版面的观察**（页脚读数异常、镜像文字、被裁切残边）——那类下沉到 P 索引的待核实项。

### 6.2 单文件 HTML 派生（按需）

已验证的 DOM 契约，直接继承（来自 `10 讲解 HTML/L06`）：

| 用途 | 标记 |
|---|---|
| 阅读进度 | `#progress`（宽度 = 滚动百分比） |
| 顶栏 | `header.topbar` > `.tb-inner` / `.tb-title` / `#tbSub` / `.tb-actions` > `#tocBtn`,`#topBtn` |
| 布局 | `.layout` > `aside.toc#toc` + `main#content` |
| 侧栏 | `aside.toc{position:sticky;top:64px}`；目录由 JS 从 `main` 内 `h2,h3` **运行时生成**（缺 id 补 `sec-N`）；高亮在 `onScroll()` 取 `getBoundingClientRect().top<=120` 的最后一个 |
| 正文块 | `.hero`(`h1`/`.sub`/`.meta`) / `.callout.info|success|warning|error`(+`.ct`) / `ol.steps` / `table.tbl`(JS 自动包 `.tblwrap`) / `figure.fig`+`figcaption` / `details.acc` |
| 图注编号 | `figcaption::before` 用 CSS counter 自动出「图 N · 」 |
| 灯箱 | 只绑 `main figure.fig img` → `#lightbox.show`；点 `#lightbox` 或 `Escape` 关闭（内联 SVG 不进灯箱） |
| 暗色 | `:root{--…}` + `@media (prefers-color-scheme:dark){:root{--…}}`，只换变量 |
| 打印 | `@media print` 隐藏 `.topbar, aside.toc, #toTop, #progress, .quiz button`；`figure.fig{break-inside:avoid}` |
| 内嵌图 | `data:image/jpeg;base64,…`，且每张带 `style="max-width:min(720px,100%)"` |

测验 DOM 契约：

```html
<div class="quiz" data-groups="e1,e2,e3,e4">
  <div class="q" data-group="e1" data-answer="1">
    <p class="qtext">…</p>
    <label><input type="radio" name="e1" value="0"> A. …</label>   <!-- ×4 -->
    <p class="expl">解析：…</p>
  </div>
  <div class="row"><button class="grade">交卷 · 看结果</button>
    <button class="ghost">重做</button><p class="score"></p></div>
</div>
```

- `grade()`：逐 `.q` 读 `dataset.group` / `dataset.answer` → 对→`label.ok`，错→`label.bad` 且正确项 `label.ok`，未答→正确项 `label.ok`；`.q` 加 `revealed`（`.q.revealed .expl{display:block}`）；`.score` = `得分：ok / total`。
- **已知坑**：`data-groups` 属性 JS **实际未使用**，真正生效的是每个 `.q` 的 `data-group`。移植时别照抄错的那个。
- `.qhead` / `.qtitle` / `.qprog` 在静态 HTML 里**不存在**，是 `grade()` 运行时自建的。

### 6.3 章级 HTML 范式（有机化学路线，抽象后保留）

`make_ch8_html.py` 的结构值得保留：`hero`(`.chips` > `span.chip`) → `nav.toc`（`spy()` 高亮）→ 每节正文 + 课件帧 + 内联 SVG → **每节一组 6 题小测** → 章末 20 题综合卷（`.paper` + `#paperScore` + `data-resetpaper`）→ 一页速查表。

- `quiz(qid, qs, title="")`：`qs=[(题干,[4选项],正确下标,解析),…]` → `.quiz[data-group]` > `.q[data-a]`(`.stem`>`.qno`+`.stembody`, `.opts`>`.opt`>`.k`, `.sol`>「答案 X」) + `.quizbar`(`.reset[data-reset]` + `.score[data-for]`)。
- `svg(body,cap,w,h,cls)` → `figure.fig.svgfig` > `<svg viewBox role="img">`；`img(name,cap,tag)` → `figure.fig` > `<img src="assets/…" loading="lazy">`。
- **它的空缺**：全文**无任何 assert / sys.exit**，徽章上的「38 道题 / 31 张图」是手写字符串。三项自检必须脚本化（见 §8）。

**实现时确认的两处有意偏离**（2026-10-19，Lead 裁定接受）：

| 原方案 | 改为 | 理由 |
|---|---|---|
| 章级用手写 `nav.toc` + `spy()` | 章级也用 §6.2 的 `aside.toc#toc`，目录由 JS 从 `h2/h3` 运行时生成 | 手写目录会随正文漂移；`nav.toc` / `spy()` 只在源片段自带显式目录时生效 |
| 每张图只在写了 `w=` 时才加宽度约束（既有 `embed.py` 的行为） | **每张内嵌图强制** `style="max-width:min(Npx,100%)"` | 既有实现漏加时会在窄屏顶破卡片；强制更安全 |

两套测验形态**并存且有意为之**：课次级用冻结契约 `.quiz > .q[data-group][data-answer]`（交卷后统一判分），章级用 `.q[data-a]` + `.quizbar[data-reset]`（点选即时判分）+ 章末综合卷 `#paperScore` / `data-resetpaper`。两者选择器不相交。对照表在 `references/03-explainer.md`。

---

## 7. 考题规范

### 7.1 三份同源

| 场合 | 形态 | 判分 |
|---|---|---|
| 对话讲解内 | `dsh-ui` 卷子模式：`radio` × n（唯一 `group`、`answer`、`explanation`）+ 一个 `submit`（`groups` 列全） | 本地即时，零往返 |
| md 讲解稿内 | 同一套题，答案 `> [!success]- 答案与解析（第 N 题）` | 读者自评 |
| 跨库复用 | **题库 JSON `schemaVersion: 1`**，可直接拖入 `刷题工具/开始刷题.html` | 引擎判分 + 错题间隔 |

题库 JSON 已由细胞库沉淀为规范（`刷题工具/题库格式规范.md`，含前端实际校验规则），**本 skill 直接对齐，不另起一套**：单选 `single` / 多选 `multiple` / 判断 `boolean` / 填空 `fill`；双语对象 `{en,zh}`；图片走 `data:image/<png|jpeg|webp|gif>;base64,…`（≤8 张/处，不接受 URL 或路径）；`source:{ref,pages,note}` 用于回查，**`pages` 指 PDF 阅读器页序，不混用幻灯片印刷页码**。

### 7.2 出题硬规则（来源：心理库 `AGENTS.md` §7，两次反馈后固定）

1. **正确项不得是最长的选项。** 每道题写完必须**逐题数字符数**核对：四个选项字符数接近，且**至少一个干扰项比正确项更长**。不允许凭感觉判断——第一版与「优化版」都栽在这里。
2. **正确项位置打散**：同一份题里答案下标在 0–3 之间变化，不集中、不交替成规律。
3. **干扰项用真实易错点**，不用荒谬选项凑数；避免「只有一个选项说得通」的送分题。
4. **去掉措辞暗示**：不让正确项独占「通常 / 可能 / 一定 / 主要」等限定词。
5. 题干用了「最直接」「主要」这类限定词时，必须确保**只有一项**满足；否则换掉限定词或重写选项。
6. **同一份题内部不得自相矛盾**：某题的正确项不能在另一题的解释里被排除（H.M. 病例一题曾出现）。
7. 判分后给解释，解释里**指回课件页码或原文**。
8. 已发出的题目若被发现违反本节，**重发修订版**并说明改了哪几处，不能只在后续题目上生效。

### 7.3 题量与配比

5–8 题（对话讲解）或每组 6 题（章级 HTML）。配比：2–3 题定义/概念直接回忆（保底分）；2–3 题易错辨析（把常见误解放进错项）；1–2 题应用/推理（跨节连接）。

---

## 8. 质量门

| 脚本 | 查什么 |
|---|---|
| `check_vault_links.py`（复用） | wikilink / `![[…]]` 能否解析；**索引页预留的骨架链接与目录级链接允许未解析** |
| `check_note_structure.py`（复用） | frontmatter、来源位置、图片是否内嵌、表格竖线是否转义、中文总结、回忆题数量、待核实清单、孤岛页——**只查形状，不查对错** |
| `check_quiz_rules.py`（新） | 逐题数字符数（正确项非最长 + 至少一个干扰项更长）、答案下标分布、跨题一致性、限定词独占 |
| `check_html_assets.py`（新） | `{{IMG:` 残留 = 0；`data:image/` 数 = 声明选图数；`assets/` 与正文引用**双向差集**为空；`data-a` 与解析里「答案 X」逐题一致；**徽章题数 = 实际题数** |
| `check_manifest.py`（新） | 页图 ↔ 解码时间码一一对应；页码 `page_full_ocr` 与 `page_cut_ocr` 一致才标 verified；重复/缺失已标 `dup` / `pNA` |
| `check_vault_profile.py`（新） | 画像声明的目录、模板、Source Register 表头在库里真实存在 |

**Git 门**（按目标库画像）：`git status --short --branch` → `git fetch` → 比对远端 → 只有工作区干净才 `git pull --ff-only` → 编辑 → `git status` + `git diff --check` → **只暂存目标文件**。禁止 `reset --hard` / `checkout -- .` / `clean` / `push --force`。

### 8.1 质量门的两条可信度纪律

这一轮里同一个问题以四种面貌反复出现：**「没查」被显示成「查了没问题」**。一个说「0」或「OK」的指标，会被读者当成「已检查且通过」，这比不检查更危险。因此定两条纪律：

1. **SKIP ≠ PASS。** 任何未执行的检查必须显式报 `SKIP` / `未执行（原因）`，且**不计入 PASS**。
2. **必须双向证明。** 每个校验器都要对**故意违规的样例报错**、对**合规样例通过**，两条都在自测里贴原始输出。只证明一边的校验器不可信。

已查实的四个实例（都真实发生过，不是假想）：

| 实例 | 表现 | 真相 |
|---|---|---|
| 复用的 `check_vault_links.py` | 库路径不存在时报 `checked 0` + `OK: every wikilink…` | **假绿灯**：路径写错等于全过。`check_all.py` 已改为断言库根存在 + 扫描数 > 0，否则 FAIL |
| 复用的 `check_note_structure.py` | 把 frontmatter 字段名硬编码为 `type` | 细胞库用 `note_type` → 全库被误报。红灯一旦长期误报就会被忽略，整套质量门失效。已改为画像驱动 + 复用发现降级为 INFO |
| `canvas.py` 去重 | dry-run 报「重复帧 0」，warnings 写「已跑文本去重」 | 实测 `duplicateOf` 非空 **0 条**，而相邻对 OCR 相似度 ≥0.82 的有 **19 对**（380s 与 386s 的 OCR 完全相同，ratio = 1.0000）。「未执行」被报成了「0」 |
| 题库导入器 `validateBank` | 「答案下标成规律」的题库被 **ACCEPTED**（实测「已导入 4 道题」） | 导入器**只做结构校验、不执行出题规则**，所以 `check_quiz_rules.py` 是 §7 六条规则的**唯一防线**——不能因为「能导入」就认为题目合规 |

同一逻辑也适用于采集层的 `--no-dedupe` / `--no-ocr`：**关掉某个步骤时，输出必须写明它没跑，而不是给出该步骤的「零结果」。**

---

## 9. 目录结构

```
~/.dsh/skills/lecture-to-obsidian/
├── SKILL.md                      # 路由 + 铁律 + 契约（唯一总是加载的文件）
├── docs/PLAN.md                  # 本文件
├── references/                   # 按层按需加载
│   ├── 00-pipeline.md
│   ├── 01-acquisition.md
│   ├── 02-notes.md
│   ├── 03-explainer.md
│   ├── 04-quiz.md
│   └── 05-quality-gates.md
├── schemas/                      # 三份契约
│   ├── manifest.schema.json
│   ├── vault-profile.schema.json
│   └── quiz-bank.schema.json
├── adapters/                     # 唯一按平台变化的地方
│   ├── canvas.py                 # 编排 better-awesome-sjtu-canvas-ppt
│   ├── chaoxing.py
│   └── pdf.py
├── scripts/                      # 契约构建 + 派生器 + 质量门
└── templates/                    # L / P / V / Concept md + explainer.html
```

---

## 10. 实施阶段与验收

| 阶段 | 产出 | 验收标准 |
|---|---|---|
| **P0 骨架与契约** | `SKILL.md`、三份 schema、`references/00-pipeline.md`、`docs/PLAN.md` | skill 能被加载并路由；三份 schema 通过 JSON Schema 校验；任一 reference 单独读得懂 |
| **P1 Canvas 适配** | `adapters/canvas.py`、`references/01-acquisition.md`、`scripts/build_manifest.py` | 对心理库 L08 生成合法 `manifest.json`；页图↔时间码一一对应 |
| **P2 超星适配** | `adapters/chaoxing.py` | 对有有机化学某一节跑通 discovery → 直链；**全程无播放、无心跳** |
| **P3 笔记生成** | `references/02-notes.md`、`templates/*.md`、`scripts/gen_notes.py`、`build_vault_profile.py` | L08 产出 L/P 笔记；`check_vault_links` + `check_note_structure` 全过 |
| **P4 讲解** | `references/03-explainer.md`、`templates/explainer.html`、`build_explainer_html.py` | L08 md 真源 → 单文件 HTML；`check_html_assets` 全过；430 px 视口无横向溢出 |
| **P5 考题** | `references/04-quiz.md`、`schemas/quiz-bank.schema.json`、`gen_quiz_bank.py`、`check_quiz_rules.py` | L08 题库 JSON 能被 `刷题工具/开始刷题.html` 导入且判分正确；出题规则全过 |
| **P6 质量门** | `check_all.py`、`check_manifest.py`、`check_vault_profile.py` | 一次调用跑完全部门；L08 端到端全绿 |

**端到端试跑对象**：心理与精神健康 L08（已有回放 + 转写 + 页图，适合纯下游验证）。

---

## 11. 风险与已知坑

| 风险 / 坑 | 证据 | 对策 |
|---|---|---|
| 折叠 callout 让课件图默认不可见 | 有机化学库实测 72/72 篇 L 笔记打开时可见图数为 0 | 课件图块一律 `[!example]+`；`check_note_structure.py` 查残留 `[!example]-` |
| 表格内嵌图片未转义竖线 → 表格结构坏 | `V01` 曾有 17 行表格图片未转义 | 生成器强制转义；校验器查 |
| `#page=` 链接点击无效 | 心理库 `AGENTS.md` §2 记录学习者反馈 | 默认内嵌页图，不用 `#page=`；画像可显式开启 |
| `ffmpeg -ss` 取到邻页 | 重复 DTS，实测偏约 1 分钟 | 一律用解码时间码（`extract_ppt_scenes.py` 的两遍滤镜图方案） |
| 页码误读 | 整帧 OCR 与页脚裁切不一致 | 两路一致才采信；否则 `dup` / `pNA` / 待核实 |
| EasyOCR / soundfile 在中文路径下失败 | `cv2.imread` 不支持非 ASCII；`soundfile` 相对路径报 System error | 脚本已改用 PIL→ndarray；`--wav` 传绝对路径。**移植时不要退化** |
| 后台 curl 下载卡 0 字节 | 本环境已知问题 | 大文件前台下载并给足超时 |
| 超星任务点被触发 | 每节带 `jobid` | 只读 GET、串行、200–300 ms 间隔、不播放 |
| 讲成「工作记录」而不是「讲课」 | 心理库 §7 学习者明确要求 | 版面类观察下沉到待核实；`[课堂口述]` 不单独成块 |
| 正确项最长（凭感觉对齐长度） | 心理库 §7：两版都栽过 | 脚本逐题数字符数，不靠感觉 |
| 单课 HTML 2–3 MB | 心理库实测合计 18.6 MB / 7 课 | 图缩到长边 1600 px（或 1100/1200）；单文件 < 4 MB |
| 路径 A 被当成"干净原图" | 实测 L08 平台快照轨 131 条 vs 35 页；含教师桌面与 PowerPoint 编辑窗口；`showFlag` 68/68 全 `true` | 路径 A 产出**必须**做 OCR 分类（非课件画面标 `isSlide: false`）+ 去重；不得直接当课件页用 |
| 平台时间码单位混用 | 同一平台：旧接口 `createSec` 是**毫秒**，`ai/ppt` 的 `imageSeekTime` 是**秒**（实测 max 2953/3210 对应时长 3308.6/3289.0） | `startSec` 一律换算成秒；用 `timecodeSource` + `rawTimecode` 保留原始读数 |
| 网络受限 | 本机 `web_search` 返回 401、MCP 搜索代理 `ECONNREFUSED` | 平台接口探测靠本机已登录浏览器会话，不依赖外网检索 |

---

## 12. 证据台账

| 结论 | 证据位置 |
|---|---|
| Canvas 双路径与 11 个脚本 | `~/.dsh/skills/better-awesome-sjtu-canvas-ppt/SKILL.md`、`scripts/` |
| 该 skill 缺 `docs/` 与 `templates/` | 实测 `ls` 仅 `SKILL.md` + `scripts`（README 第 60–64 行承诺了它们） |
| 超星链路与安全边界 | `C:\这是一个文件夹\大三\有机化学\AGENTS.md` §阶段 0、§阶段 1 |
| 超星无平台字幕 | 同上：「`richvideo/allsubtitle` 抽样返回 `[]`」 |
| 讲解三分工与五类标记 | `C:\这是一个文件夹\大三\有机化学\讲解格式.md` §0、§2.3 |
| 配图优先级 PPT帧 > RDKit > 自绘 | 同上 §8.6 |
| matplotlib 字形与 `$` 落单坑 | 同上 §4.4、§8.4、§8.7 |
| 章级 HTML 范式与三项自检 | 同上 §8.8 |
| 对话讲解输出规则 / 随堂测验出题规则 | `<Obsidian 库根>\心理与精神健康\AGENTS.md` §7 |
| 折叠 callout 致图片不可见（72/72） | `C:\这是一个文件夹\大三\有机化学\AGENTS.md` §阶段 5 |
| `#page=` 链接点击无效 | 心理库 `AGENTS.md` §2（2026-10-16 记录） |
| 单文件 HTML 精确 DOM 契约 | 心理库 `10 讲解 HTML/L06 — 全课讲解 眼动追踪.html`（只读侦察） |
| `.qhead/.qtitle/.qprog` 由 JS 运行时生成 | 同上（静态 HTML 0 处） |
| `data-groups` 未被 JS 使用 | 同上 |
| `make_ch8_html.py` 无内置自检 | `C:\这是一个文件夹\大三\有机化学\_scripts\make_ch8_html.py`（无 assert / sys.exit） |
| 题库 JSON v1 规范 | `<Obsidian 库根>\细胞生物学和组织学\刷题工具\题库格式规范.md` |
| 刷题工具导入契约 | 同目录 `开始刷题.html`（`schemaVersion!==1` 抛错、10 MB 上限、localStorage 进度） |
| 细胞库不保存转写/音视频 | 该库 `AGENTS.md` §原始资料、音视频与临时文件政策；Source Register L84 |
| 细胞库不默认创建 `V##` | 该库 `AGENTS.md` L42 |
| 细胞库 `07 课程任务/` 已 gitignore | 该库 `AGENTS.md` L48；`git ls-files` 实测 0 |
| 三库 frontmatter 字段不一致 | 只读侦察：`note_type` vs `type`；`status` 实测 10 种值 |
| 平台 `ai/ppt` 是屏幕快照轨、含桌面与应用窗口 | 实测 `L08 第15节 1355 平台课件轨清单.json` 的 `data.data.docList`：68 条（第16节 63 条），而 S84 仅 35 页；最早条目 OCR 为教师桌面（回收站/东方财富证券/微信/VLC），188 秒起为「第9次课 - PowerPoint 文件 开始 插入 绘图 设计…」 |
| `showFlag` 不代表"是否放映" | 同上：68/68 与 63/63 条全为 `true`；`pptDocId`/`imageId` 也全不重复，无现成去重键 |
| `imageSeekTime` 单位是秒 | 同上：max 2953（第15节）/ 3210（第16节），对应时长 3308.6 s / 3289.0 s |
| L08 一节课 = 两个平台节次 | `Source Register.md` S88：第15节 courseId 179741、第16节 courseId 180045，时长 3308.6 s / 3289.0 s |
| L08 前 35 分钟用**未归档**的教师端 pptx | S88：「本次课的前 35 分钟使用教师端 `第9次课.pptx`，该文件尚未归档；S84 的 35 页从第15节 35:07 起才开始放映」 |
| L08 p24 页脚读数与阅读页不一致 | S84：「p24 页脚显示异常读数 42（疑为 09 笔误），按原样保留」；p4/p5/p13/p14/p15 无页脚数字 |
| L08 页图来自 PDF 渲染而非视频抽帧 | S85：`09 参考资料/附件/L08 课件 PDF/PDF p01.jpg`–`p35.jpg`，共 35 张 |

---

## 12.5 契约演进：L08 试点逼出的五处修正（2026-10-19）

**方法**：在写任何采集/生成代码之前，先用手工造的 L08 `manifest.json` 去压 schema。凡是 schema 表达不了的，就是契约错了。五处全部命中——如果等代码写完才发现，就要返工五层。

基准 fixture：`docs/pilot/L08.manifest.json`（35 页 / 2 节次 / 38 条放映记录，已通过 `manifest.schema.json` 校验；数据全部取自 P08 的放映记录表与页脚对照表）。

| # | 我原本的假设 | L08 的真实素材 | 契约改成 |
|---|---|---|---|
| 1 | 一节课 = 一个平台节次 | L08 = 第15节（courseId 179741）+ 第16节（180045），时长 3308.6 s / 3289.0 s | `source.session` → **`source.sessions[]`**；`media` / `transcript` 移入 session 内部 |
| 2 | 一页只有一个放映时间 | p9 在**两节都放映**（49:13 / 00:01）；p29 在 41:12 放映、42:49 重放；p31 在 42:19、42:52 重放 | `slides[].startSec` / `sessionIndex` → **`slides[].projections[]`**；**空数组 = 未见对应讲解**（"课件存在≠课堂讲过"的唯一机器可判依据） |
| 3 | 页脚是页码，应当等于 PDF 阅读页 | 页脚是**小节 / 版式编号**：p26–p31 与 p33 页脚**都是 10**，p8/p9/p11 都是 03，p17/p18 都是 06 | `pageNoScope: "section"`；**删掉 `duplicate-in-unit`**；枚举收敛为 `verified / anomalous / mismatch / missing / not-applicable`。只有 p24（42，前后页 08/09）是 `anomalous` |
| 4 | 平台 PPT 轨是干净原图 | 两节 **131 条快照 vs 35 页**；最早几条是教师桌面（回收站/东方财富/微信/VLC），188 秒起是 **PowerPoint 编辑窗口（含功能区）**；`showFlag` 68/68 与 63/63 **全为 true**，不能当"是否放映"用 | `isSlide` → **`contentType`**（`slide / video / activity / desktop / unknown`）；采集层**必须**做 desktop 过滤 + 去重 |
| 5 | 教师 PDF 就是课件全部 | S84 是**选页**：p35 之后课堂还放了两页（第16节 46:41 / 48:28）；第15节 **0:00–35:07 根本没用 S84**，用的是**未归档**的教师端 `第9次课.pptx` | 新增 **`pdf.isSelection`**、**`unarchivedMaterials[]`**、**`session.usedDeck` / `deckCoverageNote`** |

另外两处由真实素材确认（原本只是推测）：
- `imageSeekTime` 单位**确实是秒**（max 2953 / 3210，对应时长 3308.6 / 3289.0），而旧接口 `createSec` 是毫秒 → 保留 `timecodeSource` + `rawTimecode` 防单位混淆。
- `pageNoFullOcr` / `pageNoFooterOcr` 必须是**字符串**：p10 读作「实验心理学 11」、p12 读作「实验心理学 06」，带版式标注。

## 12.6 端到端试点结果（L08，2026-10-19）

产物落在 `docs/pilot/e2e-L08/`（可复核、可重跑）：

| 环节 | 产物 | 实测结果 |
|---|---|---|
| ① 画像 | `vault-profile.json` | `[validate] OK（jsonschema）`；`reviewedByHuman=false`、warnings=6 |
| ② 笔记 | `notes/L08 …md`（512 行）、`notes/P08 …md`（597 行） | 38 个展开的图片块 · `#page=` 0 处 · 表格转义竖线 0 处违规 |
| ③ 讲解真源 | `L08 讲解真源 — 记忆引导眼跳（第一部分）.md` | 覆盖课件 p1–p9；三条证据边界 + 五类证据标记 |
| ④ 单文件 HTML | `L08 — 全课讲解 记忆引导眼跳（第一部分）.html` | **1.10 MB** · 7 张内嵌图 · 自检 ①–⑥ 全 PASS · 窄屏无写死 px |
| ⑤ 题库（三形态同源） | `题库/psych-hlt3202g-l08-memory.{json,fence.md,quiz.md}` | 8 题 · schema PASS · **S/R1–R6 全 PASS**（error 0 / warn 0）· 围栏 `validate_dsh_ui` → **status=valid, rendered=9** |
| ⑥ 质量门 | `check_html_assets.py` / `check_quiz_rules.py` | HTML **PASS**（0 ERROR）· 题库 **PASS**（0 ERROR） |

**试点逼出的两处新缺陷**（都属「假红灯」类，都会让质量门被忽略）：

| # | 缺陷 | 表现 | 修法 |
|---|---|---|---|
| 6 | 画像的 `frontmatter.required` 用「出现频次前 N 项」推断 | 得到 **12 个全局必填字段**（含 `title`/`lecture`/`concept`/`lecture_date`/`source_location`），而 `perNoteType` 全为空数组 → **任何单篇笔记都满足不了** → 14 篇报 **23 个 ERROR**，全是假红灯 | 契约加 `requiredPerNoteType`（按类型推断必填）与 `requiredIsInferred`；全局 `required` 改为**各类型的交集**；`requiredIsInferred && !reviewedByHuman` 时校验器只能报 WARN |
| 7 | 单文件 base64 HTML 用 `--declared-list` 口径做差集 | 图片已内联，正文**不再有任何路径引用** → 必然报「引用 0 / 声明 7 / 仅声明 7」→ **假 FAIL**。构建期（内联前）这个差集是真跑且 PASS 的 | 单文件形态下声明清单差集应判 **N/A**；有意义的检查是「`data:image/` 数 = 声明图数」（该检查已 PASS） |
| 8 | `perNoteType` 被当成必填清单 | `requiredPerNoteType[lecture-note]` = 4 个字段（正确的必填集），而 `perNoteType[lecture-note]` = **12 个字段**（该类型**出现过**的可选字段并集）。检查器的文档串写着「可用 `perNoteType` 覆盖该类型的必填清单」→ 9 篇 L 笔记各报缺 7–9 个字段 | 必填检查**只读 `requiredPerNoteType`**；`perNoteType` 仅作信息展示。schema 描述已改成「**它不是必填清单，校验器不得据此报缺字段**」。13 → 2 |

> **同一错误的三种面貌**：⑥ 全局并集当必填、⑧ 类型内并集当必填——都是**把「出现过」当成「必须有」**。这类错误的共同特征是：**没有任何一篇能同时满足**。识别方法：如果一个要求集让**同类型的每一篇**都报错，那几乎一定是要求集错了，不是笔记错了。

### 12.7 定稿验收（2026-10-19）

```
manifest          WARN    errors=0 warns=1     warnings 非空（5 条，清单本就要求列出）
html-assets       OK      errors=0 warns=0
vault-profile     WARN    errors=0 warns=1     reviewedByHuman=false（画像未复核，未写入知识库）
note-frontmatter  FAIL    errors=2 warns=1     L02/L08 缺总结小节（真阳性）
vault-links       FAIL    errors=4 knownLimitation=3 realBroken=1 scanned=1164
note-structure    FAIL    demoted=20 errors=2  与 note-frontmatter 指向同 2 个问题
OK 1 | WARN 2 | FAIL 3 | SKIP 0
```

**两条独立路径（`note-frontmatter` 与 `note-structure`）得出完全相同的 2 个真问题**——这是交叉印证，不是两个校验器各说各话。剩下的 1 条真断链是库里既有的 P08 `#page=N` 占位符。

其余全绿：三份 schema 过 JSON + Draft7 · 文档 176 处路径引用 0 缺失 · 构建器/校验器常量集一致 · 全部 Python 编译通过 · 知识库**零写入**（独立 mtime 复核）。

### 12.8 偏好审计（2026-10-19，学习者追问后补做）

学习者问「我的个人偏好有没有写进去」。逐条拿两个库 `AGENTS.md` §4–§9 的**具体偏好条目**去 skill 里 grep，结果：

**初版已覆盖**（7 条）：短句 / 一段只讲一个重点 · 先作答再展开 · 已发题目违规要重发修订版 · `[课堂口述]` 不单独成块 · 不写临时服务地址进笔记 · 出题六规则 · 说话人标签是推断。

**初版漏掉**（12 条，已全部补进 `SKILL.md` §6 与 `references/03-explainer.md` §1）：

| 漏项 | 出处 | 为什么值得单列 |
|---|---|---|
| **学习资料不得转化成自我诊断或医疗建议；临床解释须标来源/适用范围/证据限制** | §4 安全 | **安全类**。这门课涉及临床内容，这条最不该漏 |
| 「已听/已核对音频」vs「按转写核对」的用词区分 | §4 证据 | 只读转写却写「已听」＝把推断伪装成事实 |
| 时间戳保留在转写或来源登记，笔记只在需要回放定位时引用 | §8 | — |
| 原始媒体只作临时输入、核对后清理；登记「未归档」但不建死链 | §5 | — |
| 不无脑渲染整套页图，P 索引优先「可定位」 | §6.4 | 成本偏好（心理库因 `#page=` 无效而例外） |
| **每部分后给 2–5 道题、停下等回答**（交互节奏 ≠ 产物题量） | §7 | 最初需求里的「呈现形式」正是这块 |
| 答「不知道」时换具体例子/数字/反例重讲，不重复原句 | §7 | 同上 |
| **优先用可编辑 Mermaid** 流程图/关系图/比较图 | §7 | 全库原本 0 处提及 |
| `[背景补充，非课件原文]` 标记 | §7 | 证据标记少了一类 |
| 讲细、讲深、讲全，不跳过 Checkpoint/插入页/术语表/历史页 | §7 | 同上 |
| **对话贴图须绝对路径 + 百分号编码**（笔记才用 `![[…\|宽度]]`） | §7 | 从 `app.asar` 源码查实的结论，最值钱却漏了 |
| 不为预览启动临时服务 | §7 | 部分覆盖（原先只禁了写地址） |

> **教训：库级偏好最容易漏，而且漏的往往是「怎么讲、怎么呈现」这类软约束**——因为它们不在 schema 里、不参与任何自动校验，写代码时不会被「报错」提醒。
> 处置：`SKILL.md` 新增 **§6「学习者的偏好与硬约束」** 作为**跨层偏好的唯一汇总处**；以后往任何库里加偏好，先补这一节。
> 这也暴露一个方法论缺口：**契约能压住数据形状，压不住呈现与节奏。** 那部分只能靠一份显式清单 + 人工核对，没有自动兜底。

## 13. 开放问题

1. 超星 adapter 是否要支持「一个课程多学期」的节次去重？（有机化学当前是 19 章 79 节单学期）
2. 题库 JSON 是否需要扩展 `schemaVersion: 2`（如加入「易错点标签」与「间隔复习优先级」）？当前先严格对齐 v1，不擅自加字段——规范明确「额外未知字段不执行且不保留」。
3. 章级 HTML 与课次 HTML 两种范式是否需要统一成一套模板？当前先保留两套，由画像选择。
