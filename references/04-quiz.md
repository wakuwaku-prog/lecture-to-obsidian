# 04 · 考题层（L4）

**一句话**：一份题源 → 三种同源产物（对话卷子 / md 折叠答案 / 题库 JSON v1），并且**出题规则由脚本强制执行**，不靠自觉。

```
题源 .quizsrc.json / .quizsrc.md
        │
        ▼  build_bank()  ← 只跑一次，正确答案在这一步唯一确定
   题库对象（内存）
        ├── render_fence()  → <base>.fence.md   dsh-ui 卷子围栏
        ├── render_md()     → <base>.quiz.md    md 题目 + [!success]- 折叠答案
        └── json.dumps()    → <base>.json       题库 JSON v1（可直接导入刷题工具）
```

**「同源」的判据**：`answer` / 选项顺序 / 解析文本只有一处来源。改题只改题源；
三种产物不可能出现「围栏说 B、题库说 C」。自测里用「同一份内容的 `.md` 题源与 `.json` 题源生成的题库必须逐字节等价」来证明这一点。

---

## 0. 为什么这一层非有不可（实测事实，不是规范要求）

> **`开始刷题.html` 的导入器只做结构校验，不执行 §7 的出题规则。**
>
> 实测：一份「答案下标 0,1,0,1 成规律」（§7 明令禁止）的题库，用**真实 headless Chrome**
> 走页面自己的 `importFiles()` → `validateBank()` → `installBank()` 全链路，
> 前端提示 **「已导入 4 道题」**——**它被接受了**。
>
> 也就是说：**没有 `check_quiz_rules.py`，§7 就只是一句没人执行的建议。**
> 这是这个脚本存在的唯一理由，也是它必须「对违规样例报错、对合规样例通过」的原因。
> 复现方法见 [§9.2](#92-复现导入器一致性测试验证-accepted--rejected)。

**推论**：`check_quiz_rules.py` 不是「锦上添花的 lint」，而是**唯一的执行点**。
任何绕过它直接把题库写进 `<vault>/题库/` 的做法，都等于放弃 §7。

> ### ⚠ 另一条同等重要的结论：**§7 比既有实践更严，演示题库不能当合规样板**
>
> 对细胞生物学库 `刷题工具/题库/` 两个**既有真实题库**跑 `check_quiz_rules.py`（只读）：
> `演示题库.json`（8 题）**R1 FAIL 4e/3w**——**4 处正确项就是最长选项**；
> `图片演示题库.json`（4 题）则全过。
>
> 它们是**演示题库**，用途是展示题型与图片，不是按 §7 出的题。
> 所以：**结构可以照抄（S 全过），选项长度绝不能照抄（R1 会挂）。**
> 下一个接手者若拿 `演示题库.json` 当模板出题，会被 R1 拦下却不知道为什么——
> 这条就是答案。详见 [§2.7](#27-兼容性证据既有真实题库对-7-的满足情况)。

---

## 1. 权威来源（写代码前必须先读）

| 来源 | 地位 |
|---|---|
| `细胞生物学和组织学/刷题工具/题库格式规范.md`（`status: verified`） | **格式权威**。字段、题型、图片、导入与更新规则 |
| `细胞生物学和组织学/刷题工具/开始刷题.html` | **校验权威**。真实导入器的 `validateBank` / `validateImages` |
| `细胞生物学和组织学/刷题工具/题库/演示题库.json`、`图片演示题库.json` | 真实可导入样例 |
| `心理与精神健康/AGENTS.md` §7「随堂测验的出题规则」 | **出题规则权威**（R1–R6 的唯一来源） |
| `这是一个文件夹/大三/有机化学/讲解格式.md` §6「自测题规范」 | 卷子形态：`radio` × n + 一个 `submit`；答案写 `> [!success]- 答案与解析` |
| `schemas/quiz-bank.schema.json` | 冻结契约；比规范更严（`additionalProperties: false`） |

**规范与前端的关系**：规范是文档，前端是执行者。两者冲突时**以前端为准**——下面第 2 节的每条规则都是从 `开始刷题.html` 的实际代码里读出来的，不是从规范文字推断的。

---

## 2. 导入器实际校验（逐条抄自 `开始刷题.html`）

> 行号对应 2026-10-19 的 `开始刷题.html`（47,537 字节）。改动那个文件后必须重新核对本节。

### 2.1 ID（`safeId`，L99）

```
^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$        长度 1–100
不能是 constructor / prototype / __proto__
```

题库 id、题目 id、选项 id 都走这一条。题目 id 题库内唯一；选项 id 题目内唯一。

### 2.2 `validateBank`（L100–124）

| 检查 | 失败信息（原文） |
|---|---|
| `schemaVersion !== 1`（**`"1"` 字符串不通过**） | `schemaVersion 必须为 1` |
| `id` 走 `safeId` | `题库 id：ID 仅允许字母、数字…` |
| `title` 双语，**英文不能为空**，**不允许 images** | `title：需要英文 en 和可选中文 zh` |
| `version` 非空字符串 | `version 必须为非空字符串` |
| `questions` 数组，**1–10000** 道 | `questions 需要 1–10000 道题` |
| 题目 id 唯一 | `questions[i]：重复题目 id X` |
| `type ∈ {single, multiple, boolean, fill}` | `questions[i]：未知题型 X` |
| `prompt` / `explanation` 双语 | `…：需要英文 en 和可选中文 zh` |
| `tags` 非空字符串数组（**导入时去重**） | `…tags 必须为非空字符串数组` |
| `single`/`multiple`：选项 **2–26** 个，选项 id 不重复 | `…：选择题需要 2–26 个选项` |
| `single`：`answer` 是**存在的一个选项 id 字符串** | `…：answer 必须为存在的一个选项 id` |
| `multiple`：`answer` 非空、**无重复**、都是存在的选项 id | `…：answer 需要不重复的正确选项 id 数组` |
| `boolean`：`answer` 是 **JSON 布尔值**（`"true"` 字符串不通过） | `…：判断题 answer 必须为 true 或 false` |
| `fill`：`answer` 1–20 个双语块；**英文题干 `___` 个数 = 参考答案个数**，中文题干同 | `…：英文题干中 ___ 空位数量必须与参考答案数量一致` |
| `source`：对象；`ref`/`note` 字符串；`pages` **正整数**数组 | `…source.pages 需要正整数数组` |
| `answerContent` 双语 | — |
| `difficulty ∈ {basic, applied}` | `…difficulty 仅支持 basic/applied` |

`bilingual(v, path, required, allowImages)`（L91–97）：`en` 必须是字符串；
`required` 且 `en` 去空白后为空 **且没有 images** → 报错（`英文或图片不能同时为空`）；
`allowImages=false` 时出现 `images` → 报错。

### 2.3 图片（`validateImages`，L75–90）

```js
/^data:image\/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/]+={0,2})$/
```

除正则外还做三件事：`atob` 解码（失败 → `base64 无效`）、**魔术字节**校验
（PNG `\x89PNG\r\n\x1a\n`／JPEG `\xff\xd8\xff`／GIF `GIF8[79]a`／WebP `RIFF….WEBP`）、
长度 ≥ 20 字节。任一不符 → `图片内容与格式不符`。

- 每处（`prompt` / `options[].text` / `answerContent` / `explanation` / `fill` 的 `answer[]`）**最多 8 张**。
- `alt` 必填、双语、**英文非空**、不允许再嵌 `images`；`caption` 可选、纯文字。
- **不接受**网络 URL、本机路径、相对路径、SVG。`data:image/svg+xml` 会被正则直接拒绝。

### 2.4 导入循环（L217）

- **单文件上限 10 MB**（`file.size > 10*1024*1024` → `文件超过 10 MB`）。base64 计入体积。
- 先 `JSON.parse`（**剥掉 UTF-8 BOM**：`.replace(/^\uFEFF/,'')`），再整份 `validateBank`，**最后**才 `installBank`——**不做部分导入**。
- 多文件各自校验，单个失败不影响其它文件。

### 2.5 更新语义（`installBank`，L211）

同一 id = 更新（弹 `confirm`），**不看版本号大小**；不同 id = 独立题库。
按**题目 id** 匹配记录；题型／双语题干／选项／答案变化会重置该题作答与错题状态、保留收藏。
只改 `answerContent`／解析／标签／来源**不**重置；选项数组换序**会**重置。

### 2.6 关键结论：导入器**不**执行出题规则

`validateBank` 只做**结构**校验。实测（见 §9.2）：一份「答案下标 0,1,0,1 成规律」的题库
**能正常导入**，前端不会拦。所以 §7 的六条规则**必须**由 `check_quiz_rules.py` 强制——
这正是这个脚本存在的理由（详见开头 §0）。

另一条实测结论：`validateBank` 是**白名单**实现（它重建 `out`，只拷已知字段），
所以**未知字段既不执行也不保留，但也不报错**。规范那句「额外未知字段不执行且不保留」说的就是这个。
本项目选择**更严**：`schemas/quiz-bank.schema.json` 用 `additionalProperties: false`，
`check_quiz_rules.py` 的 S 规则把未知字段报成 error。

### 2.7 兼容性证据：既有真实题库对 §7 的满足情况

对细胞生物学库 `刷题工具/题库/` 里两个**既有真实题库**跑 `check_quiz_rules.py`（**只读，未修改**）：

| 题库 | S | R1 | R2 | R3 | R4 | R5 | R6 | 退出码 |
|---|---|---|---|---|---|---|---|---|
| `演示题库.json`（8 题，四种题型） | PASS | **FAIL 4e / 3w** | PASS | PASS | PASS | PASS | PASS | 1 |
| `图片演示题库.json`（4 题，全部含图） | PASS | **N/A 2** | PASS | PASS | PASS | PASS | PASS | 0 |

> `图片演示题库.json` 的 R1 是 **`N/A`（规则不适用）**，不是 PASS 也不是 SKIP——4 题里
> `IMG-001`/`IMG-002` 的选项全是「标签 + 图」，R1 的目的（查文字选项的措辞暗示）在此不适用（见 §7 R1）。
> 加 `--r1-image-strict` 后它会变成 `R1 FAIL 2 → exit 1`（`IMG-002` 三选项等长并列）。

两个库**结构上都是干净的**（S 全过、能被真实导入器接受），差异只在 R1。

**结论：§7 比既有实践更严。** 既有题库在「正确项不得最长」这一条上并不满足——
`演示题库.json` 有 4 处正确项在 `en` 或 `zh` 下就是最长选项，例如：

```
DEMO-002 [zh] 正确项最长 10 字符，最长干扰项 8 字符   选项字符数：A=6、B=8、C=10
DEMO-005 [zh] 正确项最长  8 字符，最长干扰项 7 字符   选项字符数：A=6、B=8、C=7
DEMO-006 [en] 正确项最长 32 字符，最长干扰项 28 字符  选项字符数：A=28、B=32、C=15
DEMO-006 [zh] 正确项最长  9 字符，最长干扰项 7 字符   选项字符数：A=7、B=8、C=9
```

这两个是**演示题库**（`cell-practice-demo` / `course-practice-image-demo`），
用途是展示题型与图片，不是按 §7 出的题——所以它们违规**不代表**前端或规范有问题，
只说明：**§7 是本课程自己加的更严标准**，不能拿既有题库当「合规样板」。

> **给后来者的提醒**：不要复制 `演示题库.json` 当模板来出题。
> 它的结构可以抄（S 全过），选项长度不能抄（R1 会挂）。
> 要模板就用 `gen_quiz_bank.py --emit-source-template`。

---

## 3. v1 字段白名单（**不要新增字段**）

```
题库      schemaVersion id version title description questions
题目      id type prompt options answer answerContent explanation tags difficulty source
选项      id text
内容块    en zh images          （en 必填字符串；zh 可选；images 最多 8）
图片      src alt caption       （src 必填 data URL；alt 必填；caption 可选）
来源      ref pages note
```

**为什么不能加字段**：规范明确「额外未知字段不执行且不保留」。
你加的 `acceptedAnswers`、`regex`、`hint`、`notes`、`explanationZh` 之类，
导入时会被静默丢掉——**不会报错**，所以作者会以为自己写的东西生效了。
这是本层最容易踩的坑，`S` 规则专门拦它。

规范也明确「无需增加 `acceptedAnswers`、正则表达式或匹配方式字段」——
填空题的 `answer` 只提供参考内容，自评由学习者点按钮判定。

---

## 4. `pages` 是 PDF 阅读器页序

`source.pages` = **PDF 阅读器的页序**，**不是**幻灯片印刷页码。
心理库 L08 有现成的反例：p24 页脚印着 42，阅读页是 24（`pageNoStatus: verified-offset`）。
引用页脚数字会让学习者回查时定位到错误的页。

生成器可以用 `--manifest` 做交叉校验：题源里 `source.pages` 出现 manifest 的
`slides[].pdfPage` 集合之外的页 → 打 `[WARN]`（不阻断，因为 manifest 可能只覆盖选页）。

---

## 5. 题源格式（两种，任选其一）

题源**不是**题库：正确项用选项上的 `"correct": true` 标记，`answer` 由生成器推导。
这样「哪个是正确答案」在题源里只有一处。

### 5.1 `.quizsrc.json`

```json
{
  "id": "psych-l08-memory",
  "version": "1.0.0",
  "title": {"en": "L08 Memory", "zh": "L08 记忆"},
  "description": {"en": "", "zh": ""},
  "defaultSource": {"ref": "S84", "note": "第8次课.pdf"},
  "questions": [
    {
      "id": "L08-001", "type": "single",
      "prompt": {"en": "…", "zh": "…"},
      "options": [
        {"id": "A", "text": {"en": "…", "zh": "…"}},
        {"id": "B", "text": {"en": "…", "zh": "…"}, "correct": true}
      ],
      "explanation": {"en": "… See 课件 p12.", "zh": "… 见课件 p12。"},
      "tags": ["Memory"], "difficulty": "basic",
      "source": {"pages": [12]}
    }
  ]
}
```

- `defaultSource.ref` 会补到所有没写 `ref` 的题上（省得每题重复）。
- `source.pages` 用阅读页序；`ref` 缺省时从 `defaultSource` 取。
- 也可以直接写 `answer`（`single` 写 id 字符串、`multiple` 写数组、`boolean` 写布尔值、
  `fill` 写双语块数组）；若与 `correct` 标记冲突，以 `answer` 为准并打 `[WARN]`。

### 5.2 `.quizsrc.md`

```markdown
# L08 记忆 | L08 Memory

- id: psych-l08-memory
- version: 1.0.0
- ref: S84
- desc: 课后自测。
- desc-en: Post-lecture self-test.

## L08-001 [single] | Memory, Models
工作记忆一次约保存几个项目？
EN: How many items does working memory hold at one time?

- [ ] A. 两个
  EN: Two
- [x] B. 四个
  EN: Four
- [ ] C. 七个
  EN: Seven

工作记忆容量约四个组块。见课件 p12。
EN: Capacity is about four chunks. See 课件 p12.

- pages: 12
- difficulty: basic

## L08-002 [boolean]
眼动仪记录注视位置随时间的变化。
EN: The eye tracker records gaze position over time.

- answer: true

眼动仪按时间记录注视位置。见课件 p20。

- pages: 20
```

解析规则（写题源时按这个来）：

| 位置 | 写法 |
|---|---|
| 标题 | 第一个非空行 `# 中文标题 \| English title`（英文可省） |
| 题库元数据 | 第一个 `## ` 之前的 `- key: value`：`id` `version` `ref` `desc` `desc-en` |
| 题目头 | `## <题目id> [<题型>] \| tag1, tag2`（题型缺省 `single`） |
| 题干 | 题目头之后的段落；`EN: ` 开头的行是英文题干 |
| 选项 | `- [ ] A. 文本` / `- [x] B. 文本`；紧跟的缩进 `EN: ` 行是英文选项 |
| 解析 | 选项之后（判断题/填空题在首个空行之后）的段落；`EN: ` 行是英文解析 |
| 题内元数据 | `- answer:` `- answer-en:` `- pages:` `- difficulty:` `- note:` `- ref:` |

**限制（已知且刻意）**：
- 题干段落不要以 `- key: value` 开头（会被当成元数据）。这是解析器的取舍，换来的规则足够简单。
- 选择题的题干在**第一个选项**处结束；判断题/填空题的题干在**第一个空行**处结束。
  所以选择题题干可以有多段，判断题题干只能有一段。
- 填空题英文用 `- answer: 中文参考1 | 中文参考2`，英文用 `- answer-en: en1 | en2`（可省，省了用中文兜底）。

---

## 6. 三种产物的形态契约

### 6.1 `dsh-ui` 卷子围栏（`<base>.fence.md`）

```json
{"title":"…","gap":14,"items":[
  {"type":"radio","group":"q1","label":"1. 题干","options":["A","B","C","D"],
   "answer":1,"explanation":"解析（含课件页码）"},
  …,
  {"type":"submit","label":"交卷（共 N 题）","action":"grade",
   "groups":["q1","q2",…],"resetAction":"redo"}
]}
```

- 每题一个 `radio`，`group` 唯一（`q1`…`qN`），`answer` 是**正确项下标**，
  `explanation` 是解析。`submit` 的 `groups` **列全**。
- **`answer` 下标与题库 `answer` 由同一个对象推导**，不可能不一致（自测里有逐题断言）。
- 题型映射：
  - `single` / `boolean` → `radio`（判断题选项固定为「正确 / 错误」，`en` 用 `True / False`）
  - `multiple` → 一条 `text` 提示 + 每题一组同 `group` 的 `checkbox`（多选聚合，交卷时一并收集）
  - `fill` → 一条 `text` 提示（参考答案在题库或 md 折叠块里）
- **只有纯 `radio` 范围才能本地即时判分**。一旦同块里混入 `checkbox`/`text`，
  交卷会走一次 `[genui-action]`。想要「零往返判分」，就让题库只含 `single`/`boolean`。
- 围栏必须过 `validate_dsh_ui`（**这一步由调用者做**，脚本不能替你调工具）。
  生成器负责保证：JSON 合法、**字符串内不出现半角 `"`**
  （`quote_cn()` 把成对半角引号换成中文引号，符合有机化学 §5.3）、
  节点数 ≤200（超出会打 `[WARN]` 并要求按单元分卷，因为渲染器会裁掉超预算部分）。
  自测里实测 `validate_dsh_ui` 返回 `status=valid rendered=14 next=emit_fence`。

### 6.2 md 折叠答案（`<base>.quiz.md`）

题目在上、答案在下，学习者先作答再展开：

```markdown
**1.** 题干

- A. …
- B. …

> [!success]- 答案与解析
> **1. L08-001**　答案 **B（四个）**
> 工作记忆容量约四个组块。见课件 p12。
> 来源：S84 p12
```

用 `[!success]-`（**折叠**）：答案默认不可见。这与图片块的 `[!example]+`（展开）是两条相反的约定，
别混。

### 6.3 题库 JSON v1（`<base>.json`）

UTF-8、无 BOM 亦可（导入器会剥）、缩进 2。必须过：

```bash
python "$SKILL/scripts/check_quiz_rules.py" "<vault>/题库/<id>.json"     # 退出码 0 才算过
```

### 6.4 交付流程（**必做，不是备注**）

出题这一层有**三道门**，缺一道就不算交付。**谁生成谁跑门**——生成题源/题库的那个执行者
负责把三道门跑完并把原始输出贴进交付说明；不要指望「下一层会发现」。

| # | 门 | 命令 / 动作 | 通过判据 | 失败怎么办 |
|---|---|---|---|---|
| 1 | **规则门** | `python "$SKILL/scripts/check_quiz_rules.py" "<vault>/题库/<id>.json"` | **退出码 0**，且 `error 0` | 按报告里的题目 id 改**题源**（不要手改题库 JSON），重新生成。**不要**用 `--allow-rule-violations` 当成通过 |
| 2 | **契约门** | 生成器已内置：`jsonschema` 对 `schemas/quiz-bank.schema.json` 校验 | 打印 `schema 校验：PASS` | 说明题源里有 v1 不认的字段或形状，按报错行改题源 |
| 3 | **围栏门** | **生成者本人**对 `<base>.fence.md` 里的 JSON 调 `validate_dsh_ui` | 返回 `status=valid`（`next=emit_fence`） | 见下 |

**第 3 道门为什么必须由人生成者来调**：`validate_dsh_ui` 是**模型工具**，脚本调不到它。
所以生成器只能保证「JSON 合法 + 字符串内无半角 `"` + 节点数 ≤200」，
**不能**替你确认渲染器接受这份 spec。这一步必须由生成者显式执行。

失败时的处理顺序：

1. `next=emit_repaired_fence` → **直接照抄 `repaired_json`**，不要再改，重新走第 1 道门（题库没变，通常直接过）。
2. `next=fix_and_revalidate` → 按诊断改 `gen_quiz_bank.py` 的 `build_fence_spec()`（**不是**手改 `.fence.md`，
   手改会在下次生成时丢失），重新生成 + 重新校验。
3. 报「节点数超限」或围栏被裁 → 按单元/题型**分卷**（一个题库一个 Unit），而不是删题。
4. 修不了（例如渲染器不支持你要的组合）→ **降级为纯 `radio` 卷子**（只保留 `single`/`boolean`），
   把 `multiple`/`fill` 留在题库 JSON 与 md 折叠块里。**不要**交付一份没验过的围栏。

> 实测记录（可作为对照）：9 题样例（7 radio + 4 checkbox + 1 submit = 14 节点）
> → `status=valid rendered=14 next=emit_fence`。

---

## 7. 出题规则 → 可执行检查（`check_quiz_rules.py`）

六条规则全部来自 `心理与精神健康/AGENTS.md` §7。**每条都能报出具体题目 id**（必要时连选项 id）。

**四级严重度（`N/A ≠ PASS`、`N/A ≠ SKIP` 是本 skill 的纪律）**：

| 级别 | 含义 | 影响退出码 |
|---|---|---|
| `error` | 违规 | 是（→ 1） |
| `warn` | 需人工复核 / 建议 | 仅 `--strict` 时 |
| **`N/A`** | **该规则本来就不适用**（不是「没查」，是「没什么可查」） | **否** |
| **`SKIP`** | **该规则应执行而未执行** | **是（→ INCOMPLETE / 1）** |

**`N/A` 与 `SKIP` 必须分桶，不能混**——这是「本来不适用」和「该跑没跑」的分界：

- `boolean` / `fill` 天然没有选项 → 规则**目的不适用**；它们**不产生任何记录**
  （连 N/A 都不记：那是规则定义上就不覆盖的题型，不是豁免）。
- **纯图片题的 R1** → 规则**目的不适用**（文本只是标签，长度不承载信息）
  → 记 **`N/A`**，打印，**不影响退出码**。
- **将来真正的「应跑没跑」**（某检查因缺输入而没能执行）→ 记 **`SKIP`**，打印，
  **并使结果非通过**（`INCOMPLETE` / exit 1）。

> **与 gates 层语义一致**：`check_html_assets.py` 在 SKIP 时给 `RESULT: INCOMPLETE` → exit 1；
> 本脚本的 `SKIP` 采用**同一语义**。目前**没有任何规则产生 SKIP**——这个桶为将来的「应跑没跑」预留，
> 并已用合成用例验证：`skip=1 → 未通过（INCOMPLETE）→ exit 1`，而 `n/a=1 → 通过 → exit 0`。

规则状态位、`小结`、汇总行**三处都单独计数** `n/a` 与 `skip`。读者看到 `R1 PASS` 才能认为长度检查真跑过了；
看到 `R1 N/A 2` 要知道那两题是「规则不适用」；看到 `R1 SKIP 2` 则**必须当作未通过**。

退出码：无违例 `0`；有违例（含 `SKIP`）`1`。`--strict` 时 `warn` 也算违例。

### S · 结构前置检查

把 §2 的导入器校验**本地重放一遍**（不依赖浏览器），并额外强制 §3 的字段白名单。
12 类错误实测可抓：未知字段（顶层/题目/选项/内容块）、`schemaVersion` 是字符串、
非法 id、`answer` 指向不存在的选项、`difficulty` 非枚举、`pages` 含 0、
填空 `___` 个数不匹配、重复题目 id、布尔 `answer` 写成字符串、图片不是合法 data URL、空选项。
`tags` 重复报 `warn`（导入器会去重，不算错）。

### R1 · 正确项不得是最长的选项

§7 原文：**逐题数字符数**核对，且**至少有一个干扰项比正确项更长**。

对 `single`/`multiple`，**按语言分别判**（`en`、`zh`；某语言有选项缺文本则跳过该语言）：

```
cmax = 正确项文本长度的最大值
dmax = 干扰项文本长度的最大值
dmax <= cmax  →  error（含并列：必须严格更长）
```

长度 = `len(str.strip())`（Unicode 码点，一个汉字算 1）。
实测反例：`en` 正确项 24 字符、最长干扰项 11 字符 → 报错；`zh` 9 vs 4 → 另报一次。

附带 `warn`：`max(所有选项长度) >= 2 * min(所有选项长度)` → 「选项长度差异过大」，
对应 §7 的「四个选项字符数要接近」。

> **为什么按语言分开判**：中英长度并不同比例。英文过关不代表中文过关，
> 而学习者会切换语言看选项——任一语言漏了就构成暗示。

> **纯图片选项：N/A（规则不适用），不是 PASS，也不是 SKIP**
> （2026-10-19 经 Lead 复核批准的有意收窄）
>
> **规则**：当**所有**选项的 `text` 都带 `images` 时，文本只是 `Shape A` / `形状 A` 这类**标签**，
> 长度不承载任何信息 → R1（含长度差异 warn）**不适用**。
>
> **为什么是有意收窄而不是放水**：§7 的长度规则**目的**是查**文字选项的措辞暗示**
> （正确项写得最长/最细，读者能靠长度猜）。图片题的选项内容是图，文本只是标签，
> 长度差异不构成任何暗示——按字面判只会制造假阳性。
>
> **证据**：`图片演示题库.json` 的 `IMG-002`，三个选项是
> `Shape A` / `Shape B` / `Shape C` + 各一张图（`en` 7/7/7、`zh` 4/4/4，等长并列）。
> 按字面判 → `[en] 正确项最长 7，最长干扰项 7` 报错；但那是图片题。
>
> **为什么归 `N/A` 而不是 `SKIP`**：这条规则的**目的**在此不适用，
> 不是「该跑却没跑」。归 SKIP 会让 `图片演示题库.json` 在默认模式下 exit 1，
> 而它其实**没有任何未执行的检查**。
>
> **`N/A` 必须显式可见**（不能静默变成 PASS），输出形如：
>
> ```
> R1 正确项不得是最长的选项                    N/A 2
>   [N/A] R1  IMG-002 选项 A,C
>         纯图片题：全部选项仅含 images，文本为标签，长度不承载信息——R1 不适用
>         要按字面严格检查，请加 --r1-image-strict
>  小结：error 0 / warn 0 / n/a 2 / skip 0 → 通过
>  ℹ 2 条 N/A = 该规则本来就不适用（不是 PASS，也不影响退出码）；要按字面严格检查请加 --r1-image-strict
> ```
>
> 规则状态位、`小结`、汇总行**三处都单独计数** `n/a`，绝不混进 `PASS`，也**不计入 SKIP 桶**。
>
> **逃生门**：`--r1-image-strict` 关掉豁免、回到字面严格（审查者不必改代码）。
> 实测 `图片演示题库.json` 在该开关下 `R1 FAIL 2 → exit 1`。
>
> **边界**：
> - **混合题（仍有文字选项）照常检查**——只有「全部选项都含图」才 N/A。
> - `boolean` / `fill` 天然无选项，**不产生任何记录**（不是 N/A，也不是 SKIP）。
> - `N/A` **不影响退出码**（含 `--strict`）。

### R2 · 正确项下标打散

只统计 `single`（`boolean` 无下标可言，`multiple` 的「下标」是集合，另做提示）。

| 判据 | 级别 |
|---|---|
| 题量 ≥4 且某下标占比 **> 50%** | error（报出该下标上的全部题目 id + 下标序列） |
| 题量 2–3 且全部同下标 | warn（题量太少，不足以判违规） |
| 下标序列以周期 `p ∈ 2..4` 循环（`n ≥ 2p` 且 `seq[i] == seq[i%p]` 全部成立） | error（「不交替成规律」） |
| 题量 ≥8 且只用到 <3 个下标 | warn |
| ≥3 道 `multiple` 的正确项下标集合完全相同 | warn |

实测：`0,1,0,1` → 报「以 2 为周期循环重复」；`0,0,0,0,1,0,2`（7 题 5 个 0）→ 报「71% 落在下标 0」。

### R3 · 干扰项非荒谬

§7 给了两个可执行的启发式，逐条实现：

| 判据 | 级别 |
|---|---|
| 选项文本（en+zh）去空白后为空且无图片 | error（「属于凑数选项」） |
| 干扰项 ↔ 正确项 相似度 ≥ 0.85（同语言） | error（「近乎同义，不是真实易错点」） |
| 两个干扰项之间相似度 ≥ 0.85 | error（「互相重复」） |

相似度 = `difflib.SequenceMatcher` 对**归一化文本**（小写、去空白与标点）的 `ratio()`。
阈值 `--similarity`（默认 0.85）。

**不可机器判定的部分**：「避免只有一个选项说得通」是语义判断，脚本不假装能判。
它只保证干扰项非空、不与正确项同义、不互相重复——剩下的仍需人读一遍。

### R4 · 去掉措辞暗示

§7 原文：不让**正确项独占**「通常」「可能」「一定」「主要」等限定词。

判据：某语言下，正确项命中限定词、而**该语言下所有干扰项都没命中** → error（独占即暗示）。
若正确项与某个干扰项都用了同一个词，读者无法靠它排除，**不算违规**。

中文词表（正则，`(?<!不)` 防止把「不一定／不可能／不总是」误判成限定词）：

```
通常 一般 可能 往往 常常 主要 最直接 最主要 一定 必然 总是 绝不 唯一 全部 所有
```

英文词表（`\b` 词边界）：`usually generally may might maybe typically often mainly
primarily most directly always never only must necessarily all every`

**刻意排除**：裸字「最」太吵（「最近」「最后」都会命中），只保留「最直接」「最主要」。

附带 `warn`：题干含 `最直接|最主要|主要|唯一|只能|必须|首先|最` 且题型为 `single`
→ 「需人工确认只有一项满足该限定」。**§7 这条的后半句是语义判断，脚本只负责把题挑出来让人看。**

### R5 · 同卷不自相矛盾

§7 原文：某题的正确项不能在另一题的解释里被排除。

两条互补的判据：

**(a) 同一段文本，在一题里是正确项、在另一题里是干扰项**
→ 报「矛盾对」，并把两题 id 都写出来。
若那另一题的解析里，该文本**紧接在一个排除信号之后** → `error`；否则 `warn`（需人工确认）。

**(b) 某题解析把另一题（或本题）的正确项当作被排除的对象**
→ `error`。

排除信号必须**紧接在被排除内容之前**（默认窗口 12 字符，`--r5-cue-window` 可调）：

```
不是 并非 不属于 不算 不对 错误 排除 而非 而不是 不能算 不再 不同于 有别于
not  isn't  aren't  rather than  instead of  no longer  incorrect  excluded  wrong  false
```

> **为什么必须「紧接其前」**：中文的对比句是「X 不是 Y」。
> 若 Q1 答案是 Y，`"X 不是 Y"` 里 Y 前面紧跟着「不是」→ 命中，判对了。
> 若 Q1 答案是 X，X 前面没有信号 → 不命中，也判对了。
> 这个方向性把「定义性对比」和「真矛盾」区分开，实测误报率很低。

**已知限制**：R5 是启发式。把正确项文本与别题解析做包含检查，天然会碰到
「同一术语在别题里做对比」的情形。真被误报时用 `--allow-pairs "Q1|Q7"` 白名单跳过，
并在题源里改掉措辞——**不要**关掉整条规则。

### R6 · 解析必须指回来源

§7 原文：判分后给解释，解释里指回课件页码或原文。

按顺序判：

1. `source.ref` 非空 → **通过**
2. 只有 `source.pages` 没有 `ref` → **warn**（有页码但指不到具体文档，建议补 `ref`）
3. 解析（或 `source.note`）命中页码模式 → **通过**
4. 以上都不满足 → **error**

页码模式：`课件 p12`、`第 12 页`、`页 12`、`12 页`、`p.12`、`p12`、`page 12`、`slide 12`、`S84`。

---

## 8. CLI（真实签名）

### `gen_quiz_bank.py`

```bash
# 题源 → 三种形态（最常用）
python "$SKILL/scripts/gen_quiz_bank.py" \
    --src "<work>/questions.quizsrc.json" \
    --out "<vault>/题库/"

# 带 manifest：默认 source.ref + 页序交叉校验
python "$SKILL/scripts/gen_quiz_bank.py" \
    --src "<work>/questions.quizsrc.md" \
    --manifest "<work>/manifest.json" \
    --out "<vault>/题库/"

# 只有 manifest 时，产出待填写的题源骨架（SKILL.md 快速上手用的就是这条）
python "$SKILL/scripts/gen_quiz_bank.py" \
    --manifest "<work>/manifest.json" --out "<work>/" --emit-source-template

# 只校验不落盘 / 顺便打到 stdout
python "$SKILL/scripts/gen_quiz_bank.py" --src q.json --out out/ --dry-run --print all
```

| 参数 | 说明 |
|---|---|
| `--src` | 题源（`.quizsrc.json` / `.md`）。省略时等价于 `--emit-source-template` |
| `--manifest` | `manifest.json`；提供默认 `source.ref` 与页序校验 |
| `--out` | 目录，或 `.json` 文件路径（三种产物按同一个 base 命名） |
| `--bank-id` | 覆盖题库 id |
| `--lang` | `zh`（默认）／`en`／`both`：围栏与 md 的呈现语言 |
| `--schema` | 冻结 schema 路径（默认 `schemas/quiz-bank.schema.json`） |
| `--emit-source-template` | 只产出题源骨架 |
| `--print` | `all`／`fence`／`md`／`json` |
| `--dry-run` | 不写文件 |
| `--allow-rule-violations` | 规则未通过时仍返回 0（报告里明确标注「已放行」） |
| `--similarity` | R3 阈值 |
| `--r1-image-strict` | 同 `check_quiz_rules.py`：关掉 R1 的纯图片题豁免（生成器的规则闸门也用严格口径） |
| `--quiet` | 只输出关键行 |

**生成器自带闸门**（`00-pipeline.md` 说「出题规则不可关闭」，这里落实为）：
默认在生成后立即跑六条规则，**有 error 就退出 1**；`--allow-rule-violations` 是显式逃生舱，
放行时打印 `[WARN] 未通过但已用 --allow-rule-violations 放行`——**不可能静默跳过**。

题源骨架里的 `TODO` 占位题**故意**过不了闸门，这样骨架不会被误当成成品交付。

### `check_quiz_rules.py`

```bash
python "$SKILL/scripts/check_quiz_rules.py" "<vault>/题库/<id>.json"
python "$SKILL/scripts/check_quiz_rules.py" bank1.json bank2.json --json
python "$SKILL/scripts/check_quiz_rules.py" bank.json --rules S,R1,R6
python "$SKILL/scripts/check_quiz_rules.py" bank.json --strict
python "$SKILL/scripts/check_quiz_rules.py" --list-rules
```

| 参数 | 说明 |
|---|---|
| `banks`（位置参数） | 一个或多个题库 JSON |
| `--json` | 机器可读报告（含 `exitCode`） |
| `--rules` | 子集，如 `S,R1,R6`（默认全跑） |
| `--strict` | `warn` 也算违例 |
| `--similarity` | R3 近乎同义阈值（默认 0.85） |
| `--max-index-share` | R2 单一答案下标最大占比（默认 0.5） |
| `--r5-cue-window` | R5 排除信号窗口字符数（默认 12） |
| `--allow-pairs` | R5 白名单，如 `Q1|Q7,Q2|Q9` |
| `--r1-image-strict` | 关掉 R1 的**纯图片题豁免**，回到字面严格（纯图片题也按字符数判） |
| `--list-rules` | 打印规则表 |

只读，不修改任何文件。**不依赖 `jsonschema`**（自己重放导入器校验），所以任何 Python 3 环境都能跑。

---

## 9. 自测证据（可复现）

### 9.1 规则与生成（本层自己的四个 fixture）

```bash
SKILL="$HOME/.dsh/skills/lecture-to-obsidian"
T="/tmp/lto-quiz-selftest"     # 或任意临时目录

# 1) 违规样例：六条规则必须都报出来，且报出具体题目 id
python "$SKILL/scripts/check_quiz_rules.py" "$T/violating-bank.json"           # → exit 1，error 14 / warn 2
python "$SKILL/scripts/check_quiz_rules.py" "$T/violating-periodic-bank.json"  # → 只有 R2 周期，exit 1

# 2) 合规样例：全过
python "$SKILL/scripts/check_quiz_rules.py" "$T/compliant-bank.json"           # → exit 0，error 0 / warn 0

# 3) 结构违规：S 规则（12 类错误）
python "$SKILL/scripts/check_quiz_rules.py" "$T/structure-violating-bank.json" --rules S

# 4) 生成 + schema 校验 + 规则闸门（生成器内置）
python "$SKILL/scripts/gen_quiz_bank.py" --src "$T/compliant.quizsrc.json" --out "$T/gen1"

# 5) 同源证明：md 题源与 json 题源生成的题库必须完全相等
python "$SKILL/scripts/gen_quiz_bank.py" --src "$T/compliant.quizsrc.md"  --out "$T/gen_md"
python "$SKILL/scripts/gen_quiz_bank.py" --src "$T/md-equivalent.quizsrc.json" --out "$T/gen_json"
python -c "import json;a=json.load(open(r'$T/gen_md/selftest-md.json',encoding='utf-8'));b=json.load(open(r'$T/gen_json/selftest-md.json',encoding='utf-8'));print('identical:',a==b)"
```

### 9.2 复现「导入器一致性测试」（验证 ACCEPTED / REJECTED）

这是可信度最高的一类验证：**不重写校验逻辑，而是把前端真正的 `validateBank` 抽出来跑**。
下面这段是**逐字可复现**的（已在 2026-10-19 实跑通过）：

```bash
T="/tmp/lto-quiz-selftest"; mkdir -p "$T"
HTML="<Obsidian 库根>/细胞生物学和组织学/刷题工具/开始刷题.html"

python - "$HTML" "$T/extracted-validateBank.js" <<'PY'
import sys, pathlib
src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")

def grab(name):
    i = src.index("function " + name + "(")
    depth = 0
    k = src.index("{", i)
    while True:
        c = src[k]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return src[i:k + 1]
        k += 1

line = src.index("const TYPES=")
parts = [src[line:src.index("\n", line)]]
parts += [grab(f) for f in ("validateImages", "bilingual", "safeId", "validateBank")]
pathlib.Path(sys.argv[2]).write_text(
    "\n".join(parts) + "\nmodule.exports={validateBank,TYPES};\n", encoding="utf-8")
print("已抽出 validateBank →", sys.argv[2])
PY

node -e '
const fs = require("fs");
const { validateBank } = require(process.argv[1]);
for (const f of process.argv.slice(2)) {
  const raw = fs.readFileSync(f, "utf8").replace(/^\uFEFF/, "");
  if (Buffer.byteLength(raw) > 10 * 1024 * 1024) { console.log("REJECTED(>10MB)", f); continue; }
  try {
    const b = validateBank(JSON.parse(raw));
    console.log("ACCEPTED", String(b.questions.length).padStart(3), "题", f);
  } catch (e) {
    console.log("REJECTED", "".padStart(3), "  ", f, "—", e.message);
  }
}' "$T/extracted-validateBank.js" \
   "$T/gen1/selftest-compliant.json" \
   "$T/structure-violating-bank.json" \
   "$T/violating-periodic-bank.json" \
   "<Obsidian 库根>/细胞生物学和组织学/刷题工具/题库/演示题库.json" \
   "<Obsidian 库根>/细胞生物学和组织学/刷题工具/题库/图片演示题库.json"
```

实跑输出（2026-10-19）：

```
已抽出 validateBank → …/extracted-validateBank.js
ACCEPTED   9 题 …/gen1/selftest-compliant.json
REJECTED         …/structure-violating-bank.json — schemaVersion 必须为 1
ACCEPTED   4 题 …/violating-periodic-bank.json          ← 关键：§7 违规但导入器接受
ACCEPTED   8 题 …/题库/演示题库.json
ACCEPTED   4 题 …/题库/图片演示题库.json
```

三条读法：
1. 生成器产出 **ACCEPTED** → 本层产物确实能被真实导入器接受（不是「我以为能」）。
2. 结构违规 **REJECTED** → 抽取出来的校验确实在工作，不是空壳。
3. **§7 违规 ACCEPTED** → 导入器不执行 §7，本脚本是唯一防线（回到 §0）。

> **注意**：`grab()` 靠**花括号配对**截取函数体。这段代码里字符串与正则中的花括号都是配平的，
> 所以成立。**改了 `开始刷题.html` 的校验函数后必须重跑本配方**——行号会漂，函数体也可能被重写。

### 9.3 真实浏览器导入（端到端）

用**独立 profile** 的 headless Chrome 打开 `开始刷题.html`，构造 `File` + `DataTransfer`
塞进 `#bankFiles` 并派发 `change`，走页面自己的 `importFiles()` → `validateBank()` → `installBank()`。

实跑输出（2026-10-19，独立 profile，非 MCP profile）：

```
[1] selftest-compliant.json      → 「已导入 9 道题」   db.banks = [{id: selftest-compliant, q: 9}]
[2] structure-violating-bank.json → 「导入失败 — schemaVersion 必须为 1」  banks 不变
[3] violating-periodic-bank.json  → 「已导入 4 道题」   db.banks 增至 2 个
```

第 3 条再次印证 §0 的结论。

---

## 10. 踩坑表（实测踩过的，按需更新）

| 坑 | 现象 | 处理 | 证据 |
|---|---|---|---|
| **加了 v1 没有的字段** | 不报错、也不生效——导入器静默丢弃 | 只写 §3 白名单里的字段；S 规则会把未知字段报成 error | `validateBank` 是白名单实现（§2.2）；实测把 `notes`/`hint` 塞进去 → 被丢弃、导入照常成功 |
| **`schemaVersion` 写成 `"1"`** | 导入失败：`schemaVersion 必须为 1` | 必须是**数字** `1` | 实测 REJECTED（§9.2） |
| **以为导入器会执行 §7** | 正确项最长 / 答案下标成规律的库**照样导入成功** | 必须自己跑 `check_quiz_rules.py` | headless Chrome 实测「已导入 4 道题」（§0、§9.3） |
| **图片写成 URL / 本机路径 / SVG** | 导入失败：`仅支持 PNG/JPEG/WebP/GIF 的 base64 内嵌图片` | 只能内嵌 `data:image/...;base64,`，且魔术字节要对 | `validateImages`（§2.3） |
| **base64 是占位串** | 导入失败：`base64 无效` 或 `图片内容与格式不符` | 用真实图片；规范里的 `BASE64_DATA` 是占位 | 规范 §图片内容明确说明 |
| **判断题 `answer` 写成 `"true"`** | 导入失败：`判断题 answer 必须为 true 或 false` | 用 JSON 布尔值 | `validateBank` L116 |
| **填空题 `___` 个数与参考答案不等** | 导入失败，且中英题干分别校验 | 英文题干空位数 = `answer` 长度；有中文题干时中文也要等 | `validateBank` L117 |
| **`source.pages` 用了幻灯片印刷页码** | 不报错，但学习者回查会定位到错页 | 一律用 **PDF 阅读器页序** | 心理库 L08 p24：页脚印 42、阅读页 24（§4） |
| **复制 `演示题库.json` 当模板** | 结构能过，但 R1 会挂 4 处 | 结构可抄、选项长度不可抄；模板用 `--emit-source-template` | §2.7 实测 |
| **纯图片题的选项等长** | R1 报「没有干扰项严格更长」（假阳性） | **已收窄**：所有选项都带 `images` 时 R1 **`N/A`**（显式打印 + 单独计数，不是静默 PASS，也不进 SKIP 桶）；要字面严格加 `--r1-image-strict` | `图片演示题库.json` IMG-001/IMG-002（§7 R1） |
| **把 `N/A` 或 `SKIP` 读成 `PASS`** | 看到 `R1 N/A 2` / `R1 SKIP 2` 以为长度检查过了 | `N/A` = **规则目的不适用**（不影响退出码）；`SKIP` = **应执行而未执行**（→ INCOMPLETE / exit 1）。两者都单独计数、都不等于 PASS；`--r1-image-strict` 可强制真查 | §7 四级严重度表 |
| **把「本来不适用」记成「该跑没跑」** | 纯图片题记 SKIP → 库被误判 exit 1 | 分桶：目的不适用 → `N/A`；应跑没跑 → `SKIP`。本 skill 两个校验器（`check_quiz_rules.py` / `check_html_assets.py`）的 SKIP 语义已统一为 INCOMPLETE | §7 四级严重度表 |
| **`gen_quiz_bank.py --manifest` 却忘了 `--src`** | 不会生成题库，而是产出题源骨架 | 这是**刻意**的：只有 manifest 时无法凭空出题，先给骨架 | 生成器 `--emit-source-template` 分支 |
| **想用 `--allow-rule-violations` 交差** | 退出码 0，但会打印「未通过但已放行」 | 只能用于临时排查；交付必须真过 | §6.4 第 1 道门 |
| **DSH 内置浏览器不可用** | `dsh_browser_open` 报 `browser provider(s) electron are registered but report themselves unavailable … run npx install-electron or set ELECTRON_PATH` | 见下条替代方案 | 2026-10-19 实测 |
| **chrome-devtools MCP 浏览器 profile 被占用** | `The browser is already running for ~/.dsh\chrome-devtools-profile. Use --isolated …` | **不要抢占别人的 profile**（同一台机上别的任务可能正在用）。改用**独立 profile 的 headless Chrome + CDP** 做导入测试 | 2026-10-19 实测 |
| **需要一个能跑本地 HTML 的浏览器做导入测试** | 上面两条都走不通 | 用本机 Chrome（`C:\Program Files\Google\Chrome\Application\chrome.exe`）起一个**全新 `--user-data-dir`**：`--headless=new --disable-gpu --allow-file-access-from-files --remote-allow-origins=* --remote-debugging-port=<port>`，再用 **Node 24 内置的全局 `WebSocket`** 连 CDP；`Runtime.evaluate` 里构造 `File`+`DataTransfer` 塞进 `#bankFiles` 并派发 `change`，最后读 `db.banks` 与 `#notice` 文本。**用完 kill 掉进程并删掉临时 profile** | 本节配方；结果见 §9.3 |

> **关于浏览器环境的边界**：本机**没有** `jsdom` / `puppeteer` / `playwright`（实测 `require.resolve` 全 missing），
> 所以端到端导入测试只能走「真实 Chrome + CDP」这条路。上面那条替代方案已经跑通；
> 若将来内置浏览器恢复可用，**优先用它**（更省事），但不要把 MCP profile 当成自己的。

---

## 11. 交付前核对

- [ ] `check_quiz_rules.py` 对题库返回 **0**（不是靠 `--allow-rule-violations` 放行）
- [ ] 报告里的 `n/a` 与 `skip` 都已逐条看过：**两者都不等于 PASS**
      - `n/a` = 规则**目的不适用**（目前只有 R1 的纯图片题会产生）；有疑问就加 `--r1-image-strict` 真查一遍
      - `skip` = 规则**应执行而未执行** → 必须视为**未通过**（`INCOMPLETE` / exit 1），不得当成交付通过
- [ ] 题库过 `schemas/quiz-bank.schema.json`（`jsonschema` 可用时）
- [ ] 题库**没有**任何 v1 未定义字段（S 规则绿）
- [ ] 图片全是 `data:image/(png|jpeg|webp|gif);base64,` 且魔术字节对得上
- [ ] `source.pages` 是 **PDF 阅读器页序**，且能被 manifest 的 `pdfPage` 覆盖
- [ ] 围栏**由生成者本人**过了 `validate_dsh_ui`（§6.4 第 3 道门；失败按 §6.4 的四步处理）
- [ ] 三种产物同源：改一处题源后重新生成，三种产物同步变化
- [ ] 题库体积 < 10 MB
- [ ] 没有把签名 URL、cookie、token、本机绝对路径写进题库或题源
