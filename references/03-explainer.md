# 03 · 讲解层（L3）：md 真源 + 单文件 HTML 派生

> 上游是 L2 笔记与画像；下游是 L4 考题与 L5 质量门。流水线第 ⑦ 步，见 [`00-pipeline.md`](00-pipeline.md)。
> 脚本：[`../scripts/build_explainer_html.py`](../scripts/build_explainer_html.py) · 模板：[`../templates/explainer.html`](../templates/explainer.html)
>
> **本文件是讲解层 DOM 契约的权威定义**（SKILL.md 已指回此处）。`docs/PLAN.md` §6.2/§6.3 保留设计理由与演进史。
> 契约变更顺序：**先改本文件 → 再改模板 → 最后改脚本**。有意偏离见 §7。

## 0. 一条铁律

**md 是唯一真源。** 对话讲解（`dsh-ui` 卷子）与单文件 HTML 都只是它的呈现形态，**内容不得漂移**：
HTML 里的正文必须能在 md/对话原文里找到出处，不允许「HTML 版顺手补一段没核实的话」。

---

## 1. md 真源怎么写

| 项 | 规则 |
|---|---|
| frontmatter | 按画像 `frontmatter.required`；`source` / `source_location` 指回 `S##` 或页码/时间码 |
| 证据标记 | **六类**分开：`[PPT原文]` `[课堂口述]` `[机器转写]` `[我的推断]` **`[背景补充，非课件原文]`** `[待核实]`（以画像 `evidenceTags` 为准）。补人物/研究背景必须用 `[背景补充，非课件原文]`，交代**谁、什么情境、说明什么**；要作学术论据时核对原始研究 |
| 配图 | `![[路径\|宽度]]`；**表格内嵌必须转义竖线** `![[…jpg\|300]]` |
| 课件页图块 | 用**展开**的 callout（`[!example]+`）——折叠会让图默认不可见（有机化学库曾 72/72 篇可见图数为 0） |
| 自测答案 | `> [!success]- 答案与解析（第 N 题）` 折叠 |
| 配图优先级 | 平台课件页图 > 可结构化渲染的图 > 自绘图；自绘图只在两者都覆盖不到时用。**有助于理解时优先用可编辑的 Mermaid 流程图 / 关系图 / 比较图**（生成后检查术语、方向、标签；不用装饰图替代知识结构） |
| **讲解节奏** | **分部分推进**：一段只讲一个重点、用短句。每部分讲完给 **2–5 道**题，**停下等学习者回答**再进下一部分——这是**交互节奏**，与 [`04-quiz.md`](04-quiz.md) 的产物题量（课次 5–8 题、章级每组 6 题）不是一回事。答「不知道」时**换具体例子、数字或反例重讲**，不重复原句 |
| **覆盖度** | **讲细、讲深、讲全**：逐页覆盖重要信息，**不跳过** Checkpoint、插入页、术语表或历史页 |

**正文里不写、但必须下沉到 P 索引待核实项的东西**：页脚读数异常、镜像文字、被裁切残边、栏目条归属等
**只影响版面**的观察。

**必须留在正文的东西**：会改变「这句话能证明什么」的限制——数值只有课件在说、同一数字两处读数不一致、
嵌入媒体未导出、类比被当成实验证据。

### 章节结构

- **课次级**：`hero`（标题/副标题/元信息）→ 按概念分节的 `h2/h3` → 每节配图与 callout → 文末一组小测 → 追加追问（如有）。
- **章级**：`hero`（标题 + 徽章 `.chips`）→ sticky 目录 → 开场 → 预备/衔接 → 每节（正文 + 课件帧 + 自绘 SVG）
  → **每节末尾一组小测** → 章末 **20 题综合卷**（sticky 计分条 + 「重做全部」）→ 一页速查表（`.map` 卡片或 `table.tbl`）。
- 题量与配比见 [`04-quiz.md`](04-quiz.md)：课次 5–8 题，章级每组 6 题。

---

## 2. 单文件 HTML：什么时候派生

**按需派生，不默认派生。** 画像 `explainer.mode` 是总闸：

| mode | 行为 |
|---|---|
| `none` / `markdown-only` | **不派生**。脚本直接退出码 4；要强行构建必须显式 `--force`（源片段里的 `<!--MODE:-->` **顶不掉**画像的总闸） |
| `single-file-html` | 课次讲解单文件 |
| `chapter-html` | 章级单文件（额外支持徽章 / 综合卷 / 速查卡） |

产物落画像 `explainer.outDir`。体积上限 `explainer.maxBytes`（默认 4 MB），图片长边 `imageMaxEdgePx`（默认 1600），
默认图宽取自 `imageWidthAttr`（如 `max-width:min(720px,100%)` → 720）。

---

## 3. `build_explainer_html.py` 真实 CLI

```bash
python "$SKILL/scripts/build_explainer_html.py" \
  --src "<src.html>" --out "<out.html>" --vault "<知识库根>" \
  [--profile "<vault-profile.json>"] [--template "<explainer.html>"] \
  [--mode single-file-html|chapter-html] \
  [--max-edge 1600] [--quality 82] [--width 720] \
  [--assets-list "<清单.txt>"] [--force] [--no-check] [--dry-run]
```

| 参数 | 说明 |
|---|---|
| `--src` | **必填**。源片段 html（含 `{{IMG:…}}` 标记） |
| `--out` | 输出 html；省略时用画像 `explainer.outDir` + `TITLE` |
| `--vault` | 相对图片路径的基准；省略时依次取「画像所在库 → `--src` 所在目录」 |
| `--profile` | 画像；省略时自动找 `<vault>/_scripts/vault-profile.json` |
| `--template` | 省略时用本 skill 的 `templates/explainer.html` |
| `--mode` | 覆盖源片段与画像的 mode（**不覆盖画像的 none/markdown-only 总闸**） |
| `--max-edge` / `--quality` / `--width` | 覆盖画像；`--width` 只是**默认**图宽，标记里的 `w=` 优先 |
| `--assets-dir` | **目录口径**：与 L5 的 `check_html_assets.py --assets DIR` 完全一致（同一份 `assets/` 目录、同一条双向差集规则）。省略时自动探测：`--out` 所在目录有 `assets/` 就用目录口径 |
| `--assets-list` | **声明清单口径**：清单文件（每行一个路径），优先于源片段的 `<!--ASSETS:-->` |
| `--force` | 画像说 `none`/`markdown-only` 时仍构建 |
| `--no-check` | 跳过自检（**不推荐**；交付前必须补跑） |
| `--dry-run` | 只统计不写文件，并打印全部自检结论 |

**退出码**：`0` 成功 · `2` 缺图（stderr 列出全部缺失路径） · `3` 自检未通过（**不写出文件**） ·
`4` 参数/画像不允许 · `5` 环境或模板异常（缺 Pillow、模板占位符个数不对）。

---

## 4. 源片段格式

开头三行元信息注释（必填），随后是正文 HTML；图片用 `{{IMG:相对知识库根的路径|caption|w=720}}`。

```html
<!--TITLE: L06 — 全课讲解 眼动追踪-->
<!--SUBTITLE: Eye Tracking: Active Sampling, Measurement and Inference-->
<!--META: 讲解来源：会话 session-… （2026-10-13）· 正文 66,088 字 · 内嵌 14 张-->
<!--MODE: chapter-html-->                                   ← 可选
<!--CHIPS: 约 3 节课内容|{{NIMG}} 张页图|{{NQ}} 道题-->      ← 可选，仅章级
<!--ASSETS: 09 参考资料/附件/…/PDF p01.jpg|…/PDF p02.jpg--> ← 可选，自检③ 的比对基准
```

- `{{IMG:路径|caption|w=720}}`：`w=` 可省（省了用画像默认值）。**路径不 URL 编码**，含空格与中文直接写。
  构建时按长边等比缩小、base64 内嵌，并**强制**加 `style="max-width:min(Npx,100%)"`。
- caption 会进 `<figcaption>`（原样，可含 HTML）；`alt` 是去掉 `<>"` 的 caption。
- `{{NIMG}}` / `{{NQ}}` / `{{NQUIZ}}`：被换成**真实**张数/题数/题组数（防止徽章数字漂移，见 §8）。
- 正文里残留的 `$…$` / `$$…$$` 会被包成 `<code>`（模板不渲染数学，内容原样保留）。
- **不要**在正文或注释里写出 `{{IMG:` 的字面量（连「说明怎么写标记」都不要）——自检① 是按字面量数的。

### 测验写法

冻结契约（§6.2，课次级与章级小测都用它）：

```html
<div class="quiz" data-groups="q1,q2">
  <div class="q" data-group="q1" data-answer="1">
    <p class="qtext">1. 题干</p>
    <label><input type="radio" name="q1" value="0"> A. …</label>   <!-- ×4 -->
    <p class="expl">解析：…（指回课件页码或原文）</p>
  </div>
  <div class="row"><button class="grade">交卷 · 看结果</button>
    <button class="ghost">重做</button><p class="score"></p></div>
</div>
```

- `data-answer` 必须等于某个选项的 `value`（自检⑥ 会拦）；`name` 在同一题组内一致、**跨题组不得重复**（会串判分）。
- `.qhead` / `.qtitle` / `.qprog` **不要手写**：`grade()` 运行时自建。

章级附加形态（有机化学 `quiz()` 路线，点选项即时判分）：

```html
<div class="quiz" data-group="c1">
  <div class="q" data-a="1">
    <div class="stem"><span class="qno">1</span><span class="stembody">题干</span></div>
    <div class="opts"><button class="opt" type="button"><span class="k">A</span><span>…</span></button> <!-- ×4 --></div>
    <div class="sol"><b>答案 B</b><span class="solsep">·</span>解析…</div>
  </div>
  <div class="quizbar"><button class="reset" data-reset="c1">重做这组题</button>
    <div class="score" data-for="c1">这一组还没开始作答</div></div>
</div>
```

章末综合卷（`#paperScore` + `data-resetpaper`）：

```html
<div class="paperhead"><span class="big" id="paperScore">0 / 20</span>
  <span>点击选项立刻判分</span>
  <button class="reset" type="button" data-resetpaper="1">重做全部</button></div>
<div class="paper"> …一个 20 题的 .quiz（冻结形态）… </div>
```

两套形态**可以同页共存**：模板里两段 JS 的选择器不相交（冻结段只认 `.q[data-group]`，章级段只认 `.q[data-a]`）。

**两套形态对照表（别混用）**

| | 冻结形态（§6.2） | 章级形态（§6.3） |
|---|---|---|
| 题块 | `.q[data-group][data-answer]` | `.q[data-a]` |
| 选项 | `<label><input type="radio" name=组 value=n>` | `<button class="opt"><span class="k">A</span>` |
| 题干 | `<p class="qtext">` | `.stem` > `.qno` + `.stembody` |
| 解析 | `<p class="expl">`，`.q.revealed` 时显示 | `.sol`（含 `<b>答案 X</b>` + `.solsep`），`.q.done` 时显示 |
| 判分时机 | 点 `button.grade` 一次性交卷 | 点选项**即时**判分，且每题只有一次机会 |
| 标记 | `label.ok` / `label.bad`（`.q` 加 `revealed`） | `.opt.ok` / `.opt.bad`（`.q` 加 `done`） |
| 组内计分 | `.score`（`得分：ok / total`） | `.quizbar` > `.score[data-for=组]`（`已答 n/N　答对 k`） |
| 复位 | `button.ghost` | `[data-reset=组]` |
| 适用 | **课次级**小测；也可做章末综合卷的题块 | **章级**每节小测；综合卷的即时判分 |
| 综合卷计分 | `#paperScore` + `[data-resetpaper]`（两种题块都算得出来） | 同左 |

组名约定：`name` / `data-group` **每个题块各自唯一**（同一份题里两个 `.q` 用同一个组名会让两组 radio 互相排斥——自检⑥ 会拦）。

---

## 5. 冻结 DOM 契约（照抄，不要自己发明类名）

本节即**权威清单**（`docs/PLAN.md` §6.2 / §6.3 是设计理由与演进史）。模板已内置，**只用下面这些标签**：

`h2` `h3` `h4` `p` `ul` `ol` `li` `blockquote` `code` `pre` `svg` ·
`table.tbl`（JS 自动包 `.tblwrap`）· `details.acc` · `ol.steps` ·
`div.callout.info|success|warning|error`（+ `p.ct`）· `figure.fig`（+ `figcaption`）· `figure.fig.svgfig` ·
`.key` `.must`（+ `.calt`）· `.map`（+ `.n` `.t` `.d`）· `.hero .chips > span.chip` · `.paperhead` `.paper`

| 用途 | 标记（已冻结） |
|---|---|
| 阅读进度 | `#progress`（宽度 = 滚动百分比） |
| 顶栏 | `header.topbar` > `.tb-inner` / `.tb-title` / `#tbSub` / `.tb-actions` > `#tocBtn` `#topBtn` |
| 布局 | `.layout` > `aside.toc#toc` + `main#content` |
| 侧栏目录 | `aside.toc{position:sticky;top:64px}`；条目由 JS 从 `main` 内 `h2,h3` **运行时生成**（缺 id 补 `sec-N`），高亮取 `top<=120` 的最后一个 |
| 灯箱 | 只绑 `main figure.fig img` → `#lightbox.show`；点 `#lightbox` 或 `Escape` 关闭（**内联 SVG 不进灯箱**） |
| 暗色 | `:root{--…}` + `@media (prefers-color-scheme:dark)`，只换变量 |
| 打印 | `@media print` 隐藏 `.topbar, aside.toc, #toTop, #progress, .quiz button`，并**展开答案/解析** |
| 内嵌图 | `data:image/jpeg;base64,…`，每张带 `style="max-width:min(Npx,100%)"` |

**已知坑（别照抄错的那个）**：真实产物里 `.quiz` 上的 `data-groups` 属性 **JS 从未使用**，
真正生效的是每个 `.q` 上的 `data-group`。`data-groups` 留着无害，但**不要指望它**。

---

## 6. 自检（默认执行，任一 FAIL → 退出码 3，不写出文件）

| # | 检查 | 通过条件 |
|---|---|---|
| ① | 占位符残留 | `{{IMG:` = 0 且未替换的模板占位 = 0 |
| ② | 内嵌图数 | `src="data:image/` 次数 = 实际内嵌 = 声明图数（同时报 `grep -c "data:image/"` 行数，两者不等说明正文里字面写了 `data:image/`） |
| ③ | assets 双向差集 | **两条口径，构建器都会显式打印用了哪条，不无声降级**：<br>**目录口径**（`--assets-dir`，或自动探测到 `--out` 旁有 `assets/`）——正文引用 vs 目录内图片（递归、只看图片扩展名），与 L5 `check_html_assets.py` 同一规则，能同时抓「引用了但不存在」与「存在但没被引用」；引用落在目录之外会被标成「（不在 assets/ 内）」判 FAIL。<br>**声明清单口径**（`--assets-list` / `<!--ASSETS:-->` / `assets.txt` / `图片清单.txt`）——正文引用 vs 本文声明要内嵌的图（单文件 base64 形态没有 assets 目录，这是唯一选择）。<br>**都没有** → SKIP（行里仍打印真实引用数），正向差集仍要求文件存在 |
| ④ | 窄屏宽度 | 每个内嵌 `<img>` 都带 `max-width:min(Npx,100%)`；行内 `style` 里写死 px = 0 |
| ⑤ | 体积 | ≤ 画像 `maxBytes`（默认 4 MB） |
| ⑥ | 测验 | `data-answer` / `data-a` 都指向真实存在的选项；radio `name` 不跨题组重复 |

附加提醒（**WARN，不判失败**）：选项数 ≠ 4、某题没有解析、章级模式缺 `#hero .chip` / `#paperScore` / `data-resetpaper`。

交付前的等价 grep（与 `10 讲解 HTML/SPEC` 一致）：

```bash
F="10 讲解 HTML/<文件名>.html"
grep -c "{{IMG:" "$F"        # 0
grep -c "data:image/" "$F"   # = 你选的图数
grep -c "⚠️ 缺图" "$F"       # 0
grep -o "{{[A-Z]*}}" "$F"    # 空
```

---

## 7. 与冻结契约的偏差（有意为之，已获 Lead 裁定）

> 本层是 DOM 契约的**权威定义**（SKILL.md 已指回本文件）。契约变更顺序：**先改本文件 → 再改
> [`../templates/explainer.html`](../templates/explainer.html) → 最后改
> [`../scripts/build_explainer_html.py`](../scripts/build_explainer_html.py)**。
> 下面四条是相对 `docs/PLAN.md` §6.2/§6.3 原始描述的**有意偏离**，不是笔误。

| # | 原始描述 | 本层实现 | 理由（Lead 已裁定接受） |
|---|---|---|---|
| 1 | §6.3 章级用**手写 `nav.toc`** + `spy()` 高亮 | 章级也用 §6.2 的 `aside.toc#toc`（sticky），条目由 JS 从 `main` 内 `h2,h3` **运行时生成** | 手写目录必然漂移（有机化学库已出现徽章数字与实际题数不一致）。`nav.toc` 的 CSS 与 `spy()` 高亮**保留**，仅在源片段自带显式目录时生效 |
| 2 | §6.2 一套测验契约 | 冻结形态（`.q[data-group][data-answer]`）**与**章级形态（`.q[data-a]` + `.opt` 即时判分）**同页并存** | 课次级要「交卷式」、章级要「点选项即时判分」；两段 JS 选择器不相交，互不触发。对照表见 §4 |
| 3 | 既有实现 `embed.py` 只在写了 `w=` 时才加宽度 | **每张**内嵌图都强制 `style="max-width:min(Npx,100%)"`（`w=` 只决定 N） | §6.2 明确要求每张带该 style；写死 px 或漏写会在窄屏顶破卡片 |
| 4 | 模式由源片段 `<!--MODE:-->` 决定 | 画像 `explainer.mode` 是**总闸**：`none`/`markdown-only` 时源片段顶不掉，必须 `--force` | 画像代表库级政策，源片段只是单次输入；政策优先，`--force` 作逃生门 |

`--flag` > 画像 > 内置默认 的优先级链对 `max-edge` / `quality` / `width` / `maxBytes` / `mode` 一律适用；
**唯一例外**是 `--width` 只是默认值，标记里的 `w=` 优先于它。

---

## 8. 踩过的坑（每条都真的发生过）

1. **写死 px 宽度** → 窄屏顶破卡片。图一律 `max-width:min(Npx,100%)`；自检④ 会拦。模板 CSS 里的
   `max-width:1280px` 是布局，不算问题——所以检查只看**行内 style**。
2. **把占位符字面量写进模板注释** → 注释里那份也被替换，正文被注入两遍（本层自测时踩过一次）。
   脚本现在会先查 `{{CONTENT}}`/`{{CHIPS}}` 是否**恰好各出现一次**，否则退出码 5。
3. **正文里字面写出 `{{IMG:` 或 `data:image/`** → 自检① ② 是笨 grep，会被自己的说明文字绊倒。
   写「IMG 占位标记」「内嵌图 URI」即可。
4. **徽章数字手写** → 有机化学库曾写「36 道题」而实际 38 道。用 `{{NIMG}}`/`{{NQ}}`/`{{NQUIZ}}` 让脚本填。
5. **`data-groups` 无效** → 真实产物里 `.quiz` 上的 `data-groups` **JS 从不读取**；真正生效的是每个 `.q` 上的
   `data-group`（配合同题块的 `input[name=…]`）。照抄 `data-groups` 当分组依据 = 判分静默失效。
6. **表格里嵌图不转义竖线** → `![[…jpg|300]]` 会把 `300` 当成表格分隔。
7. **折叠 callout 装页图** → 默认不可见；课件页图块用展开的 `[!example]+`。
8. **手写目录** → 会漂移。目录由 JS 从 `h2/h3` 运行时生成；章级也用它（`nav.toc` 只在源片段自带显式目录时才有样式与 `spy()` 高亮）。
9. **assets 清单写成「候选池」** → 声明清单口径是双向差集，清单要写**本文实际内嵌的那几张**，
   不是目录里所有页图。（章级形态请改用目录口径，它天然没有这个问题。）
10. **心理库目前没有 `_scripts/vault-profile.json`**（2026-10-19 查实）→ 所以走内置默认
    1600 / 82 / 720 是对的，与既有 `embed.py` 产物一致。画像由 L2 的
    `build_vault_profile.py` 生成；**画像一落地就要核对优先级链**（`--flag` > 画像 > 内置默认）是否与
    `build_vault_profile.py` 写出的字段名（`imageMaxEdgePx` / `imageWidthAttr` / `maxBytes` / `outDir` / `mode`）一致。
11. **同一 `.quiz` 里两个 `.q` 共用组名** → 两组 radio 的 `name` 相同，浏览器会把它们当**同一道题**：
    选 A 题的选项会清掉 B 题的已选项，判分串台（本层写自测样例时真的这么写过一次）。
    组名约定：`name` / `data-group` **每个题块各自唯一**；自检⑥ 会拦「跨题组重复」。

---

## 9. 交付前核对

- [ ] md 真源与 HTML 正文同源；证据标记与不确定性说明保留。
- [ ] `{{IMG:` / `{{[A-Z]*}}` 残留为 0；`data:image/` 数 = 图数；体积 ≤ 画像上限。
- [ ] 每张图都是 `max-width:min(Npx,100%)`，窄屏不溢出。
- [ ] 测验：`data-answer` 指向真实选项、`name` 每组唯一（不跨题块重复）、每题有解析且解析指回来源。
- [ ] **assets 口径已确认并写进报告**：章级用目录口径（`assets/` 双向差集），单文件用声明清单口径；
      两者都缺 → SKIP 行里要有真实引用数。构建器打印的口径与 L5 `check_html_assets.py` 用的口径一致。
- [ ] 章级：`hero .chips`、每节一组小测、`#paperScore` + `data-resetpaper`、一页速查表齐全。
- [ ] 产物落在画像 `explainer.outDir`；没有往知识库写临时文件。
