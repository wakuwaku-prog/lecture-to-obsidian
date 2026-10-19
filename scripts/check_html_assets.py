#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_html_assets.py — 只读校验单文件讲解 HTML（L3 产物）。

检查项
------
1. `{{IMG:` 残留 = 0（构建占位符没被替换，页面会显示字面量）
2. `data:image/` 计数 = 声明图数（hero/meta 的「内嵌 N 张」）
3. 正文引用的 assets 与 assets/ 目录**双向差集**为空
   （引用了不存在的文件 = 破图；目录里有没被引用的 = 多带文件）
4. 每道题的 `data-a` / `data-answer` 与解析里的「答案 X」逐题一致
   （解析没写字母时跳过——不制造假红）
5. hero 徽章写的题数 = 实际题数（「共 N 题」/「做 N 道选择」/「N 组 M 题」）
6. `<img>` 上没有写死 px 宽度（窄屏会顶破卡片；应用 min(Npx,100%)）

用法
----
python check_html_assets.py <file.html> [more.html ...] [--assets DIR] [--quiet] [--json]

退出码
------
0 = 无 ERROR；1 = 有 ERROR 或文件读不了；2 = 用法错误

本脚本**只读**：不写、不改、不创建任何文件。
"""
import argparse
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

# ---------------------------------------------------------------- 解析器

QUIZ_BLOCK = re.compile(r'<div class="quiz"[^>]*>')
Q_DIV = re.compile(r'<div class="q"(?=[\s>])[^>]*>')
# data-a 优先，其次 data-answer
ATTR_ANSWER = re.compile(r'\bdata-(?:a|answer)="([^"]*)"')
ATTR_GROUP = re.compile(r'\bdata-group="([^"]*)"')
ATTR_GROUPS = re.compile(r'\bdata-groups="([^"]*)"')
RADIO = re.compile(r'<input\b[^>]*type="radio"[^>]*>')
INPUT_VALUE = re.compile(r'\bvalue="([^"]*)"')
INPUT_NAME = re.compile(r'\bname="([^"]*)"')
EXPL_P = re.compile(r'<p class="expl">(.*?)</p>', re.S)
IMG_TAG = re.compile(r"<img\b[^>]*>")
SRC_ATTR = re.compile(r'\b(?:src|href)="(assets/[^"]+)"')
# 与 build_explainer_html.py 的 IMAGE_EXT **逐字一致**（目录口径靠它收集图片）
IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg")
# 与 build_explainer_html.py 的兜底候选 **逐字一致**（被校验 HTML 同目录下的清单文件名）。
# 构建器以 --src 所在目录为基准（src_dir）；校验器没有 --src，以被校验 HTML 所在目录为基准。
FALLBACK_LIST_CANDIDATES = ("assets.txt", "图片清单.txt")

# 解析里写正确答案的几种常见写法
ANS_LETTER_PATTERNS = (
    re.compile(r"答案\s*[:：]?\s*([A-Z])\b"),
    re.compile(r"正确答案\s*[:：]?\s*(?:是\s*)?([A-Z])\b"),
    re.compile(r"应选\s*([A-Z])\b"),
)

DECLARED_IMG = (
    re.compile(r"内嵌\s*(\d+)\s*张"),
    re.compile(r"内嵌\s*(\d+)\s*处"),
    re.compile(r"(\d+)\s*张\s*内嵌"),
)
DECLARED_Q = (
    re.compile(r"共\s*(\d+)\s*题"),
    re.compile(r"做\s*(\d+)\s*道选择"),
    re.compile(r"(\d+)\s*道选择题"),
)


class Report(object):
    def __init__(self):
        self.findings = []
        self.checked = 0
        # SKIP ≠ PASS：口径走到 SKIP 时置 True，结论改报 INCOMPLETE
        self.assets_skipped = False

    def add(self, level, rule, message):
        self.findings.append((level, rule, message))

    def error(self, rule, message):
        self.add("ERROR", rule, message)

    def warn(self, rule, message):
        self.add("WARN", rule, message)

    def info(self, rule, message):
        self.add("INFO", rule, message)

    def count(self, level):
        return sum(1 for f in self.findings if f[0] == level)

    @property
    def ok(self):
        return self.count("ERROR") == 0

    @property
    def complete(self):
        """是否所有检查项都真的跑过。assets 口径 SKIP → 不完整。"""
        return not self.assets_skipped

    def render(self, title):
        lines = ["=" * 72, "check_html_assets.py — %s" % title, "=" * 72,
                 "检查项 %d 条；ERROR %d，WARN %d，INFO %d"
                 % (self.checked, self.count("ERROR"),
                    self.count("WARN"), self.count("INFO")), ""]
        for level in ("ERROR", "WARN", "INFO"):
            group = [f for f in self.findings if f[0] == level]
            if not group:
                continue
            lines.append("--- %s (%d) ---" % (level, len(group)))
            for _, rule, message in group:
                lines.append("  [%s] %s" % (rule, message))
            lines.append("")
        if self.count("ERROR"):
            lines.append("RESULT: FAIL（%d 个 ERROR）" % self.count("ERROR"))
        elif not self.complete:
            # 绝不把「没查」显示成 PASS
            lines.append("RESULT: INCOMPLETE（无 ERROR，但有检查项未执行："
                         "assets 口径 SKIP）—— **这不是 PASS**")
        else:
            lines.append("RESULT: PASS（无 ERROR）")
        return "\n".join(lines)


# ---------------------------------------------------------------- 题目解析

def split_questions(html):
    """返回 [(attrs, inner_html)]，每个 <div class="q"> 一块。"""
    marks = list(Q_DIV.finditer(html))
    blocks = []
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(html)
        # 截到下一个 quiz 容器开始处（多组题时）
        nxt_quiz = QUIZ_BLOCK.search(html, m.end())
        if nxt_quiz and nxt_quiz.start() < end:
            end = nxt_quiz.start()
        blocks.append((m.group(0), html[m.end():end]))
    return blocks


def parse_question(attrs, inner):
    """→ dict(answer_index, options[(value, letter, text)], expl_text, group)"""
    m = ATTR_ANSWER.search(attrs)
    answer = m.group(1) if m else None
    g = ATTR_GROUP.search(attrs)
    group = g.group(1) if g else None

    options = []
    for rm in RADIO.finditer(inner):
        tag = rm.group(0)
        vm = INPUT_VALUE.search(tag)
        val = vm.group(1) if vm else None
        nm = INPUT_NAME.search(tag)
        # 选项字母取自紧跟其后的标签文本
        tail = inner[rm.end():rm.end() + 400]
        lm = re.match(r"\s*([A-Z])[\.\、]", tail)
        letter = lm.group(1) if lm else None
        options.append({"value": val, "letter": letter,
                        "name": nm.group(1) if nm else None})

    em = EXPL_P.search(inner)
    expl = em.group(1) if em else ""
    expl_text = re.sub(r"<[^>]+>", "", expl)
    return {"answer": answer, "group": group, "options": options,
            "expl": expl_text, "has_expl": bool(em)}


def expl_letter(expl_text):
    for pat in ANS_LETTER_PATTERNS:
        m = pat.search(expl_text)
        if m:
            return m.group(1)
    return None


def check_questions(html, rep):
    blocks = split_questions(html)
    rep.info("html.questions", "题目数 %d" % len(blocks))
    for i, (attrs, inner) in enumerate(blocks):
        q = parse_question(attrs, inner)
        at = "q[%d]" % (i + 1)
        if q["group"]:
            at += " group=%s" % q["group"]

        # 4a. data-a / data-answer 必须存在且是合法下标
        rep.checked += 1
        ans = q["answer"]
        if ans is None:
            rep.error("quiz.answerMissing",
                      "%s 既没有 data-a 也没有 data-answer" % at)
            continue
        if not re.match(r"^\d+$", ans):
            rep.error("quiz.answerFormat",
                      "%s 的答案下标 %r 不是十进制数字" % (at, ans))
            continue
        idx = int(ans)
        n_opt = len(q["options"])
        rep.checked += 1
        if n_opt == 0:
            rep.error("quiz.optionsMissing", "%s 找不到任何 radio 选项" % at)
            continue
        if not (0 <= idx < n_opt):
            rep.error("quiz.answerRange",
                      "%s 的答案下标 %d 越界（共 %d 个选项，合法 0..%d）"
                      % (at, idx, n_opt, n_opt - 1))
            continue

        # 选项 value 应与位置一致（0-based）
        rep.checked += 1
        values = [o["value"] for o in q["options"]]
        if values != [str(k) for k in range(n_opt)]:
            rep.error("quiz.optionValues",
                      "%s 的 radio value 序列 %r 不是 0..%d" % (at, values, n_opt - 1))

        # radio name 必须同组
        rep.checked += 1
        names = set(o["name"] for o in q["options"])
        if len(names) > 1:
            rep.error("quiz.radioName",
                      "%s 的 radio name 不统一：%r" % (at, sorted(names)))

        # 4b. 解析里的「答案 X」必须与下标一致
        letter = expl_letter(q["expl"])
        rep.checked += 1
        if letter is None:
            rep.info("quiz.answerLetter",
                     "%s 解析未写答案字母，跳过逐题一致性核对" % at)
        else:
            opt_letter = q["options"][idx]["letter"]
            if opt_letter is None:
                rep.warn("quiz.optionLetter",
                         "%s 解析写「答案 %s」但正确项没有可识别的字母标签"
                         % (at, letter))
            elif letter != opt_letter:
                rep.error("quiz.answerLetterMismatch",
                          "%s 的 data-answer=%s（→ 选项 %s），"
                          "解析却写「答案 %s」" % (at, ans, opt_letter, letter))

        rep.checked += 1
        if not q["has_expl"]:
            rep.warn("quiz.explMissing", "%s 没有 <p class=\"expl\"> 解析" % at)

    # 容器 data-groups 与各题 data-group 自洽
    for gm in QUIZ_BLOCK.finditer(html):
        tail = html[gm.end():gm.end() + 200]
        dg = ATTR_GROUPS.search(gm.group(0) + tail)
        if not dg:
            continue
        declared = [g.strip() for g in dg.group(1).split(",") if g.strip()]
        end = QUIZ_BLOCK.search(html, gm.end())
        seg = html[gm.end():end.start() if end else len(html)]
        actual = [ATTR_GROUP.search(m.group(0)).group(1)
                  for m in Q_DIV.finditer(seg)
                  if ATTR_GROUP.search(m.group(0))]
        rep.checked += 1
        missing = [g for g in declared if g not in actual]
        if missing:
            rep.error("quiz.groupDeclared",
                      "quiz data-groups 声明了 %r，但容器内没有对应题目" % missing)
        rep.checked += 1
        extra = [g for g in actual if g not in declared]
        if extra:
            rep.error("quiz.groupUndeclared",
                      "容器内有题目 group %r 未出现在 data-groups=%r"
                      % (extra, dg.group(1)))
    return len(blocks)


# ---------------------------------------------------------------- 图片与资产

def check_images(html, rep, declared_override=None):
    residue = html.count("{{IMG:")
    rep.checked += 1
    if residue:
        rep.error("html.imgPlaceholder",
                  "{{IMG: 残留 %d 处（构建占位符未替换）" % residue)
    else:
        rep.info("html.imgPlaceholder", "{{IMG: 残留 0")

    actual = html.count("data:image/")
    declared = declared_override
    if declared is None:
        for pat in DECLARED_IMG:
            m = pat.search(html)
            if m:
                declared = int(m.group(1))
                break
    rep.checked += 1
    if declared is None:
        rep.warn("html.imgDeclared",
                 "页面没声明内嵌图数（找不到「内嵌 N 张」），"
                 "data:image/ 实际 %d 处；可用 --declared-images 指定" % actual)
    elif declared != actual:
        rep.error("html.imgCountMismatch",
                  "声明内嵌 %d 张，实际 data:image/ %d 处" % (declared, actual))
    else:
        rep.info("html.imgCount", "内嵌图数一致：%d" % actual)

    imgs = IMG_TAG.findall(html)
    rep.info("html.imgTags", "<img> 共 %d 个" % len(imgs))

    # 6. 写死 px 宽度
    hard_px = []
    for tag in imgs:
        sm = re.search(r'style="([^"]*)"', tag)
        if not sm:
            continue
        style = sm.group(1)
        if re.search(r"(?<!min\()\bmax-width:\s*\d+px", style) or \
           re.search(r"(?<!min\()\bwidth:\s*\d+px", style):
            hard_px.append(style[:90])
    rep.checked += 1
    if hard_px:
        rep.error("html.imgHardWidth",
                  "%d 个 <img> 写死了 px 宽度（窄屏会顶破卡片，"
                  "应写 max-width:min(Npx,100%%))：%r"
                  % (len(hard_px), hard_px[:3]))
    else:
        rep.info("html.imgHardWidth", "无写死 px 宽度的 <img>")

    # 内联 SVG 里的 width="N" 也提示一下（不报错）
    svg_px = re.findall(r"<svg\b[^>]*\bwidth=\"(\d+)\"", html)
    if svg_px:
        rep.info("html.svgWidth", "内联 SVG 带固定 width 属性 %d 处" % len(svg_px))
    return actual


def norm_rel(p):
    """与 build_explainer_html.py 的 norm_rel 一致：统一成 `a/b/c.jpg`。"""
    return os.path.normpath(p.strip().replace("\\", "/")).replace(os.sep, "/")


def parse_assets(raw):
    """与 build_explainer_html.py 的 parse_assets 逐字一致：`|` 或换行分隔，`#` 注释。

    名字也与构建器保持一致 —— 对齐自测会比对 helper 名，改名会让漂移检查失效。
    """
    out, seen = [], set()
    for chunk in re.split(r"[|\n]", raw):
        item = chunk.strip()
        if not item or item.startswith("#"):
            continue
        key = norm_rel(item)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def list_image_files(base_dir):
    """与 build_explainer_html.py 的 list_image_files 一致：递归、去隐藏、只收图片、排序。"""
    out = []
    for root, dirs, files in os.walk(base_dir):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if name.startswith("."):
                continue
            if not name.lower().endswith(IMAGE_EXT):
                continue
            out.append(norm_rel(os.path.relpath(os.path.join(root, name), base_dir)))
    return sorted(out)


def resolve_assets_scope(html, html_path, assets_dir, declared_list):
    """解析 assets 口径。**优先级与 build_explainer_html.py 逐字对齐**：

        --assets-dir > --declared-list > 自动探测（被校验 HTML 同级有 assets/）
        > 文件内 <!--ASSETS:--> > SKIP

    返回 dict(kind, path, label, refs, declared)。kind ∈ {dir, list, none}。
    口径**永远显式**，不无声降级。
    """
    refs = sorted(set(SRC_ATTR.findall(html)))
    scope = {"kind": "none", "path": None, "refs": [norm_rel(r) for r in refs],
             "declared": [], "label": "未声明（SKIP）"}

    if assets_dir:
        d = os.path.abspath(assets_dir)
        scope.update(kind="dir", path=d, label="assets/ 目录（--assets-dir）")
        return scope
    if declared_list:
        scope.update(kind="list", path=os.path.abspath(declared_list),
                     label="声明清单（--declared-list）")
        return scope

    # 自动探测：被校验 HTML 同级存在 assets/ → 目录口径
    auto_dir = os.path.join(os.path.dirname(os.path.abspath(html_path)), "assets")
    if os.path.isdir(auto_dir):
        scope.update(kind="dir", path=auto_dir,
                     label="assets/ 目录（自动探测：被校验 HTML 同级有 assets/）")
        return scope

    # 文件内 <!--ASSETS:--> 标记
    m = re.search(r"<!--\s*ASSETS\s*:(.*?)-->", html, re.S | re.I)
    if m and m.group(1).strip():
        scope.update(kind="list", path=None, declared=parse_assets(m.group(1)),
                     label="声明清单（HTML 内 <!--ASSETS:-->）")
        return scope

    # 兜底候选：与被校验 HTML 同目录下的 assets.txt / 图片清单.txt
    # （与构建器一致；构建器以 --src 所在目录为基准）
    html_dir = os.path.dirname(os.path.abspath(html_path))
    for cand in FALLBACK_LIST_CANDIDATES:
        p = os.path.join(html_dir, cand)
        if os.path.isfile(p):
            scope.update(kind="list", path=p,
                         label="声明清单（%s）" % cand)
            return scope

    return scope


def check_assets(html, rep, scope, html_path=None):
    """按已解析的口径做双向差集。返回 True=真的查了，False=SKIP。"""
    refs, kind = scope["refs"], scope["kind"]
    rep.info("assets.scope", "assets 口径：%s%s"
             % (scope["label"], ("（%s）" % scope["path"]) if scope.get("path") else ""))
    rep.info("html.assetRefs", "正文引用 assets 路径 %d 个" % len(refs))

    if kind == "none":
        # SKIP ≠ PASS：没查就不能显示成通过。
        # 但「没有任何 assets 引用」时不存在未校验的差集，属真空完成。
        if refs:
            rep.assets_skipped = True
            rep.info("assets.skipped",
                     "SKIP：正文引用了 %d 个 assets 路径，但没有任何口径信息"
                     "（无 --assets-dir / --declared-list、同级无 assets/、"
                     "HTML 内无 <!--ASSETS:-->）——**双向差集未校验**，"
                     "不代表通过" % len(refs))
        else:
            rep.info("assets.notApplicable",
                     "SKIP：正文没有任何 assets 引用（单文件 base64 形态），"
                     "没有需要校验的差集——此项为空操作，不影响结论")
        return False

    if kind == "dir":
        d = scope["path"]
        rep.checked += 1
        if not os.path.isdir(d):
            # 显式给了目录却不存在 → FAIL，不是 SKIP
            rep.error("assets.dirMissing", "assets 目录不存在：%s" % d)
            return True
        # 目录口径：declared 是 assets/ 内的图片（相对该目录），
        # refs 要换算到同一基准；不在 assets/ 内的引用显式标出。
        declared = list_image_files(d)
        base = os.path.dirname(os.path.abspath(html_path))
        mapped = []
        for r in refs:
            abs_p = os.path.abspath(os.path.join(base, r))
            try:
                rp = os.path.relpath(abs_p, d)
            except ValueError:
                rp = None
            if rp is None or rp.startswith(".."):
                mapped.append("%s（不在 assets/ 内）" % r)
            else:
                mapped.append(norm_rel(rp))
        refs = mapped
    else:
        # 声明清单口径：清单文件不存在 → FAIL；否则读清单或 HTML 内联标记
        if scope.get("path"):
            rep.checked += 1
            if not os.path.isfile(scope["path"]):
                rep.error("assets.listMissing",
                          "声明清单不存在：%s" % scope["path"])
                return True
            with open(scope["path"], encoding="utf-8") as fh:
                declared = parse_assets(fh.read())
        else:
            declared = scope["declared"]
        refs = [norm_rel(r) for r in refs]

    rep.checked += 1
    declared_set = set(norm_rel(x) for x in declared)
    ref_set = set(refs)

    only_ref = sorted(ref_set - declared_set)
    only_declared = sorted(declared_set - ref_set)

    if kind == "dir":
        # 目录口径：正向 = 引用了但磁盘上没有；反向 = 磁盘上有但没被引用
        if only_ref:
            rep.error("assets.brokenRef",
                      "正文引用了 %d 个 assets 文件但目录里没有（破图）：%r"
                      % (len(only_ref), only_ref[:5]))
        else:
            rep.info("assets.brokenRef", "正文引用的 assets 全部存在")
        if only_declared:
            rep.error("assets.unreferenced",
                      "assets/ 里有 %d 个文件没被正文引用（多带文件）：%r"
                      % (len(only_declared), only_declared[:5]))
        else:
            rep.info("assets.unreferenced", "assets/ 内文件全部被引用")
    else:
        if only_ref:
            rep.error("assets.brokenRef",
                      "正文引用了 %d 个路径但声明清单里没有（仅引用）：%r"
                      % (len(only_ref), only_ref[:5]))
        else:
            rep.info("assets.brokenRef", "正文引用的路径全部在声明清单里")
        if only_declared:
            rep.error("assets.unreferenced",
                      "声明清单里有 %d 个路径没被正文引用（仅声明）：%r"
                      % (len(only_declared), only_declared[:5]))
        else:
            rep.info("assets.unreferenced", "声明清单里的路径全部被引用")

    rep.info("assets.diff", "口径=%s；引用 %d / 声明 %d / 仅引用 %d / 仅声明 %d"
             % (kind, len(ref_set), len(declared_set),
                len(only_ref), len(only_declared)))
    return True


# ---------------------------------------------------------------- 徽章题数

def check_declared_counts(html, rep, n_questions):
    for pat in DECLARED_Q:
        for m in pat.finditer(html):
            declared = int(m.group(1))
            rep.checked += 1
            snippet = html[max(0, m.start() - 60):m.end() + 30]
            snippet = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", snippet))
            if declared != n_questions:
                rep.error("html.declaredQuestionCount",
                          "徽章/导语写「%s」= %d 题，实际题目 %d 道（上下文：%s）"
                          % (m.group(0), declared, n_questions, snippet[:80]))
            else:
                rep.info("html.declaredQuestionCount",
                         "「%s」与实际题数 %d 一致" % (m.group(0), n_questions))


# ---------------------------------------------------------------- 主流程

def run(html_path, assets_dir=None, declared_images=None, declared_list=None):
    rep = Report()
    if not os.path.isfile(html_path):
        rep.error("html.missing", "找不到 HTML：%s" % html_path)
        return rep, None, False
    try:
        with open(html_path, encoding="utf-8") as fh:
            html = fh.read()
    except OSError as exc:
        rep.error("html.unreadable", "读不了：%s" % exc)
        return rep, None, False
    except UnicodeDecodeError as exc:
        rep.error("html.encoding", "不是 UTF-8：%s" % exc)
        return rep, None, False

    rep.info("html.size", "%s（%d 字节）" % (os.path.basename(html_path),
                                             len(html.encode("utf-8"))))
    n_q = check_questions(html, rep)
    check_images(html, rep, declared_images)
    scope = resolve_assets_scope(html, html_path, assets_dir, declared_list)
    assets_checked = check_assets(html, rep, scope, html_path)
    check_declared_counts(html, rep, n_q)
    return rep, html, assets_checked


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="check_html_assets.py",
        description="只读校验单文件讲解 HTML（占位残留/图片数/资产双向差集/"
                    "答案一致/徽章题数/写死宽度）")
    ap.add_argument("html", nargs="+", help="一个或多个 .html")
    ap.add_argument("--assets-dir", "--assets", dest="assets_dir", default=None,
                    help="assets/ 目录口径（与 build_explainer_html.py 的 "
                         "--assets-dir 同名同义）")
    ap.add_argument("--declared-list", default=None,
                    help="声明清单文件，每行一个路径（与构建器 --assets-list 同义）；"
                         "也可用 HTML 内 <!--ASSETS:--> 标记")
    ap.add_argument("--declared-images", type=int, default=None,
                    help="覆盖页面里声明的内嵌图数")
    ap.add_argument("--quiet", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    results = []
    overall_ok = True
    any_assets_checked = False
    any_incomplete = False
    for path in args.html:
        rep, _, assets_checked = run(path, args.assets_dir, args.declared_images,
                                     args.declared_list)
        overall_ok = overall_ok and rep.ok
        any_assets_checked = any_assets_checked or assets_checked
        any_incomplete = any_incomplete or not rep.complete
        results.append((path, rep, assets_checked))
        if args.json:
            continue
        if args.quiet:
            verdict = ("FAIL" if not rep.ok
                       else ("INCOMPLETE" if not rep.complete else "PASS"))
            print("%s: %s (ERROR %d, WARN %d)  %s"
                  % (verdict, os.path.basename(path),
                     rep.count("ERROR"), rep.count("WARN"),
                     "" if rep.ok else "| " + "; ".join(
                         m for l, _, m in rep.findings if l == "ERROR")[:200]))
        else:
            print(rep.render(os.path.basename(path)))
            print()

    if args.json:
        print(json.dumps({
            "ok": overall_ok,
            # SKIP ≠ PASS：只要没有任何一份走到真实口径，就在顶层显式标出
            "assetsChecked": any_assets_checked,
            "assetsScopeSkipped": not any_assets_checked,
            "complete": not any_incomplete,
            "files": [{
                "path": p,
                "ok": r.ok,
                "complete": r.complete,
                "assetsChecked": ac,
                "checked": r.checked,
                "errors": r.count("ERROR"),
                "warns": r.count("WARN"),
                "findings": [{"level": l, "rule": ru, "message": m}
                             for l, ru, m in r.findings],
            } for p, r, ac in results],
        }, ensure_ascii=False, indent=2))

    # 「没查」不得退出 0：INCOMPLETE 也返回非零，避免被自动化当成通过
    return 0 if (overall_ok and not any_incomplete) else 1


if __name__ == "__main__":
    sys.exit(main())
