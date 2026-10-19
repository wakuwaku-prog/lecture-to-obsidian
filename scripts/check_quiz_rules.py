#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""check_quiz_rules.py — lecture-to-obsidian L4 出题规则检查器。

把《心理与精神健康》AGENTS.md §7「随堂测验的出题规则」逐条实现成**可执行检查**，
每条违例都报出**具体题目 id**（必要时连选项 id 一起报）。

规则一览（详见 references/04-quiz.md）：

  S   结构前置检查：题库 JSON v1 契约 + 刷题工具/开始刷题.html 导入器实际校验
  R1  正确项不得是最长的选项（逐题数字符数，且至少一个干扰项严格更长）
  R2  正确项下标在 0–3 之间打散（不集中、不成规律）
  R3  干扰项非荒谬（非空、不与正确项近乎同义、不互相重复）
  R4  去掉措辞暗示（正确项不独占「通常/可能/一定/主要/最直接」等限定词）
  R5  同卷不自相矛盾（某题正确项不在别题解析里被排除）
  R6  解析必须指回来源（source.ref / source.pages / 解析里的页码）

用法：
    python check_quiz_rules.py <bank.json> [<bank2.json> ...]
    python check_quiz_rules.py <bank.json> --json
    python check_quiz_rules.py <bank.json> --rules R1,R2,R6 --strict
    python check_quiz_rules.py --list-rules

退出码：无违例 → 0；有违例 → 1（--strict 时 warn 也算违例）。
只读：本脚本不修改任何文件。
"""

from __future__ import annotations

import argparse
import base64
import binascii
import difflib
import json
import re
import sys
from pathlib import Path

# --------------------------------------------------------------------------
# 常量
# --------------------------------------------------------------------------

SEV_ERROR = "error"
SEV_WARN = "warn"
# N/A：规则**本来就不适用**（boolean/fill 没有选项；纯图片题的文本只是标签，
#      长度不承载信息 → 该规则的**目的**在此不适用）。
#      必须打印，但**不影响退出码**——它不是「没查」，是「没什么可查」。
SEV_NA = "n/a"
# SKIP：规则**应执行而未执行**。必须打印，且**必须使结果非通过**（INCOMPLETE → exit 1）。
#      这是「没查却显示通过」的那类风险，与 N/A 严格区分，两者不可混桶。
#      目前没有规则产生 SKIP；保留此桶给将来真正的「应跑没跑」用例
#      （与 gates 层 check_html_assets.py 的 INCOMPLETE → exit 1 语义一致）。
SEV_SKIP = "skip"

ALL_RULES = ["S", "R1", "R2", "R3", "R4", "R5", "R6"]

RULE_TITLES = {
    "S": "S  结构前置检查（v1 契约 + 导入器实际校验）",
    "R1": "R1 正确项不得是最长的选项",
    "R2": "R2 正确项下标打散（不集中、不成规律）",
    "R3": "R3 干扰项非荒谬（非空、不与正确项近乎同义）",
    "R4": "R4 去掉措辞暗示（正确项不独占限定词）",
    "R5": "R5 同卷不自相矛盾",
    "R6": "R6 解析指回来源",
}

# 与 开始刷题.html 的 safeId 完全一致
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$")
RESERVED_IDS = {"constructor", "prototype", "__proto__"}
Q_TYPES = {"single", "multiple", "boolean", "fill"}
DIFFICULTIES = {"basic", "applied"}

# 与 开始刷题.html 的 validateImages 完全一致
IMG_SRC_RE = re.compile(r"^data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/]+={0,2})$")

# 冻结 schema（schemas/quiz-bank.schema.json）的 additionalProperties:false 白名单
BANK_FIELDS = {"schemaVersion", "id", "version", "title", "description", "questions"}
QUESTION_FIELDS = {
    "id", "type", "prompt", "options", "answer", "answerContent",
    "explanation", "tags", "difficulty", "source",
}
OPTION_FIELDS = {"id", "text"}
BLOCK_FIELDS = {"en", "zh", "images"}
IMAGE_FIELDS = {"src", "alt", "caption"}
SOURCE_FIELDS = {"ref", "pages", "note"}

# ---------------------------------------------------------------- R4 词表
# 中文限定词用正则：`(?<!不)` 防止把「不一定 / 不可能 / 不总是」误判成限定词。
HEDGE_ZH = [
    ("通常", r"通常"),
    ("一般", r"一般"),
    ("可能", r"(?<!不)可能"),
    ("往往", r"往往"),
    ("常常", r"常常"),
    ("主要", r"主要"),
    ("最直接", r"最直接"),
    ("最主要", r"最主要"),
    ("一定", r"(?<!不)一定"),
    ("必然", r"(?<!不)必然"),
    ("总是", r"(?<!不)总是"),
    ("绝不", r"绝不"),
    ("唯一", r"唯一"),
    ("全部", r"全部"),
    ("所有", r"所有"),
]
# 英文限定词用 \b 词边界，避免 "may" 命中 "maybe" 之外的噪声（"maybe" 本身也是限定词，故单列）
HEDGE_EN = [
    "usually", "generally", "may", "might", "maybe", "typically", "often",
    "mainly", "primarily", "most directly", "always", "never", "only",
    "must", "necessarily", "all", "every",
]

# 题干里出现即需人工确认「只有一项满足该限定」的词
LIMIT_RE = re.compile(r"最直接|最主要|主要|唯一|只能|必须|首先|最")

# ---------------------------------------------------------------- R5 词表
# 排除信号：紧接在被否定的内容**之前**出现。
EXCLUSION_CUES = [
    "不是", "并非", "不属于", "不算", "不对", "错误", "排除", "而非",
    "而不是", "不能算", "不再", "不同于", "有别于",
    "not ", "isn't ", "aren't ", "rather than ", "instead of ", "no longer ",
    "incorrect", "excluded", "wrong", "false",
]

# ---------------------------------------------------------------- R6 页码
PAGE_RE = re.compile(
    r"课件\s*[pP]?\s*\d+"
    r"|第\s*\d+\s*页"
    r"|页\s*\d+"
    r"|\d+\s*页"
    r"|\b[pP]\.\s*\d+\b"
    r"|\b[pP]\d{1,4}\b"
    r"|\bpages?\s*\d+"
    r"|\bslides?\s*\d+"
    r"|\bS\d{2,}\b"
)


# --------------------------------------------------------------------------
# 通用文本工具
# --------------------------------------------------------------------------

def _str(v) -> str:
    return v if isinstance(v, str) else ""


def block_en(b) -> str:
    return _str(b.get("en")) if isinstance(b, dict) else ""


def block_zh(b) -> str:
    return _str(b.get("zh")) if isinstance(b, dict) else ""


def block_text(b) -> str:
    """双语合并文本（用于展示与来源检查）。"""
    if not isinstance(b, dict):
        return ""
    return " ".join(x for x in (block_en(b), block_zh(b)) if x.strip())


def block_lang_strict(b, lang: str) -> str:
    """严格取某语言文本；缺失返回空串（不回退，避免同一文本被数两次）。"""
    if not isinstance(b, dict):
        return ""
    return block_en(b) if lang == "en" else block_zh(b)


_PUNCT_RE = re.compile(
    r"[\s\u3000，。、；：？！,.;:?!\"'“”‘’「」『』（）()\[\]【】〈〉《》…—\-_/\\|·~`]+"
)


def norm_text(s: str) -> str:
    """归一化：小写、去空白与标点。用于「近乎同义」「包含」这类比较。"""
    return _PUNCT_RE.sub("", (s or "").lower())


def similarity(a: str, b: str) -> float:
    a, b = norm_text(a), norm_text(b)
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def max_similarity(block_a, block_b):
    """按语言取最大相似度，返回 (ratio, lang)。"""
    best, best_lang = 0.0, ""
    for lang in ("en", "zh"):
        ta, tb = block_lang_strict(block_a, lang), block_lang_strict(block_b, lang)
        if len(norm_text(ta)) < 2 or len(norm_text(tb)) < 2:
            continue
        r = similarity(ta, tb)
        if r > best:
            best, best_lang = r, lang
    return best, best_lang


def options_of(q) -> list:
    opts = q.get("options") if isinstance(q, dict) else None
    return opts if isinstance(opts, list) else []


def correct_ids(q) -> list:
    """single → [id]；multiple → [id, ...]；其它 → []。"""
    a = q.get("answer")
    t = q.get("type")
    if t == "single":
        return [a] if isinstance(a, str) else []
    if t == "multiple":
        return [x for x in a if isinstance(x, str)] if isinstance(a, list) else []
    return []


def finding(rule: str, severity: str, question: str, message: str, **extra) -> dict:
    rec = {
        "rule": rule,
        "severity": severity,
        "question": question,
        "message": message,
    }
    for k, v in extra.items():
        if v not in (None, "", [], {}):
            rec[k] = v
    return rec


def pair_key(a: str, b: str) -> str:
    return "|".join(sorted([a or "", b or ""]))


# --------------------------------------------------------------------------
# S · 结构前置检查
# --------------------------------------------------------------------------

def _check_block(b, path: str, findings: list, *, required: bool = True,
                 allow_images: bool = True, qid: str = "-") -> None:
    if b is None:
        if required:
            findings.append(finding("S", SEV_ERROR, qid, f"{path} 缺失"))
        return
    if not isinstance(b, dict) or isinstance(b, list):
        findings.append(finding("S", SEV_ERROR, qid, f"{path} 必须是对象"))
        return
    unknown = set(b) - BLOCK_FIELDS
    if unknown:
        findings.append(finding(
            "S", SEV_ERROR, qid,
            f"{path} 含 v1 未定义字段 {sorted(unknown)}；规范「额外未知字段不执行且不保留」，"
            f"导入器会静默丢弃",
        ))
    if "en" not in b or not isinstance(b.get("en"), str):
        findings.append(finding("S", SEV_ERROR, qid, f"{path}.en 必须是字符串"))
    if "zh" in b and not isinstance(b.get("zh"), str):
        findings.append(finding("S", SEV_ERROR, qid, f"{path}.zh 必须是字符串"))
    images = b.get("images")
    if images is None:
        if required and not _str(b.get("en")).strip():
            findings.append(finding("S", SEV_ERROR, qid, f"{path}：英文或图片不能同时为空"))
        return
    if not allow_images:
        findings.append(finding("S", SEV_ERROR, qid, f"{path} 此处不支持 images"))
        return
    if not isinstance(images, list) or len(images) > 8:
        findings.append(finding("S", SEV_ERROR, qid, f"{path}.images 最多允许 8 张图片"))
        return
    for i, img in enumerate(images):
        loc = f"{path}.images[{i}]"
        if not isinstance(img, dict):
            findings.append(finding("S", SEV_ERROR, qid, f"{loc} 必须是对象"))
            continue
        unknown = set(img) - IMAGE_FIELDS
        if unknown:
            findings.append(finding("S", SEV_ERROR, qid, f"{loc} 含 v1 未定义字段 {sorted(unknown)}"))
        src = img.get("src")
        if not isinstance(src, str):
            findings.append(finding("S", SEV_ERROR, qid, f"{loc}：需要内嵌图片 src"))
            continue
        m = IMG_SRC_RE.match(src)
        if not m:
            findings.append(finding(
                "S", SEV_ERROR, qid,
                f"{loc}：仅支持 data:image/(png|jpeg|webp|gif);base64, 内嵌图片；"
                f"不接受 URL / 本机路径 / 相对路径 / SVG",
            ))
            continue
        try:
            raw = base64.b64decode(m.group(2), validate=True)
        except (binascii.Error, ValueError):
            findings.append(finding("S", SEV_ERROR, qid, f"{loc}：base64 无效"))
            continue
        kind = m.group(1)
        sig = (
            raw.startswith(b"\x89PNG\r\n\x1a\n") if kind == "png"
            else raw.startswith(b"\xff\xd8\xff") if kind == "jpeg"
            else re.match(rb"^GIF8[79]a", raw) is not None if kind == "gif"
            else raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
        )
        if not sig or len(raw) < 20:
            findings.append(finding("S", SEV_ERROR, qid, f"{loc}：图片内容与声明格式不符"))
        _check_block(img.get("alt"), f"{loc}.alt", findings, required=True,
                     allow_images=False, qid=qid)
        if "caption" in img:
            _check_block(img.get("caption"), f"{loc}.caption", findings, required=False,
                         allow_images=False, qid=qid)


def check_structure(bank) -> list:
    f: list = []
    if not isinstance(bank, dict):
        return [finding("S", SEV_ERROR, "-", "题库根必须是 JSON 对象")]

    unknown = set(bank) - BANK_FIELDS
    if unknown:
        f.append(finding("S", SEV_ERROR, "-",
                         f"题库含 v1 未定义字段 {sorted(unknown)}；规范「额外未知字段不执行且不保留」"))

    sv = bank.get("schemaVersion")
    if isinstance(sv, bool) or not isinstance(sv, (int, float)) or sv != 1:
        f.append(finding("S", SEV_ERROR, "-", f"schemaVersion 必须是数字 1（当前 {sv!r}）"))

    bid = bank.get("id")
    if not isinstance(bid, str) or not ID_RE.match(bid) or bid in RESERVED_IDS:
        f.append(finding("S", SEV_ERROR, "-", f"题库 id 非法：{bid!r}（字母或数字开头，1–100 字符，不能是保留名）"))

    ver = bank.get("version")
    if not isinstance(ver, str) or not ver.strip():
        f.append(finding("S", SEV_ERROR, "-", "version 必须为非空字符串"))

    if "title" not in bank:
        f.append(finding("S", SEV_ERROR, "-", "title 缺失"))
    else:
        _check_block(bank.get("title"), "title", f, required=True,
                     allow_images=False, qid="-")
    if "description" in bank:
        _check_block(bank.get("description"), "description", f, required=False,
                     allow_images=False, qid="-")

    qs = bank.get("questions")
    if not isinstance(qs, list) or not (1 <= len(qs) <= 10000):
        f.append(finding("S", SEV_ERROR, "-", "questions 需要 1–10000 道题"))
        return f

    seen_qid: set = set()
    for i, q in enumerate(qs):
        path = f"questions[{i}]"
        if not isinstance(q, dict):
            f.append(finding("S", SEV_ERROR, path, "题目必须是对象"))
            continue
        qid = q.get("id") if isinstance(q.get("id"), str) else path
        unknown = set(q) - QUESTION_FIELDS
        if unknown:
            f.append(finding("S", SEV_ERROR, qid, f"{path} 含 v1 未定义字段 {sorted(unknown)}"))
        if not isinstance(q.get("id"), str) or not ID_RE.match(q["id"]) or q["id"] in RESERVED_IDS:
            f.append(finding("S", SEV_ERROR, qid, f"{path}.id 非法：{q.get('id')!r}"))
        elif q["id"] in seen_qid:
            f.append(finding("S", SEV_ERROR, qid, f"{path}：重复题目 id {q['id']}"))
        else:
            seen_qid.add(q["id"])

        qtype = q.get("type")
        if qtype not in Q_TYPES:
            f.append(finding("S", SEV_ERROR, qid, f"{path}：未知题型 {qtype!r}"))
            continue

        _check_block(q.get("prompt"), f"{path}.prompt", f, qid=qid)
        _check_block(q.get("explanation"), f"{path}.explanation", f, qid=qid)
        if "answerContent" in q:
            _check_block(q.get("answerContent"), f"{path}.answerContent", f, qid=qid)

        tags = q.get("tags")
        if tags is not None:
            if (not isinstance(tags, list) or not tags
                    or any(not isinstance(t, str) or not t.strip() for t in tags)):
                f.append(finding("S", SEV_ERROR, qid, f"{path}.tags 必须为非空字符串数组"))
            elif len(set(tags)) != len(tags):
                f.append(finding("S", SEV_WARN, qid, f"{path}.tags 含重复项，导入器会去重"))

        if "difficulty" in q and q.get("difficulty") not in DIFFICULTIES:
            f.append(finding("S", SEV_ERROR, qid, f"{path}.difficulty 仅支持 basic/applied"))

        if "source" in q:
            src = q.get("source")
            if not isinstance(src, dict) or isinstance(src, list):
                f.append(finding("S", SEV_ERROR, qid, f"{path}.source 必须为对象"))
            else:
                unknown = set(src) - SOURCE_FIELDS
                if unknown:
                    f.append(finding("S", SEV_ERROR, qid, f"{path}.source 含 v1 未定义字段 {sorted(unknown)}"))
                if "ref" in src and not isinstance(src.get("ref"), str):
                    f.append(finding("S", SEV_ERROR, qid, f"{path}.source.ref 必须为字符串"))
                if "note" in src and not isinstance(src.get("note"), str):
                    f.append(finding("S", SEV_ERROR, qid, f"{path}.source.note 必须为字符串"))
                pages = src.get("pages")
                if pages is not None and (
                    not isinstance(pages, list)
                    or any(isinstance(p, bool) or not isinstance(p, int) or p < 1 for p in pages)
                ):
                    f.append(finding("S", SEV_ERROR, qid,
                                     f"{path}.source.pages 需要正整数数组（PDF 阅读器页序）"))

        # ---- 题型专属 ----
        opts = options_of(q)
        if qtype in ("single", "multiple"):
            if not (2 <= len(opts) <= 26):
                f.append(finding("S", SEV_ERROR, qid, f"{path}：选择题需要 2–26 个选项"))
            oids: list = []
            for j, o in enumerate(opts):
                loc = f"{path}.options[{j}]"
                if not isinstance(o, dict):
                    f.append(finding("S", SEV_ERROR, qid, f"{loc} 必须是对象"))
                    continue
                unknown = set(o) - OPTION_FIELDS
                if unknown:
                    f.append(finding("S", SEV_ERROR, qid, f"{loc} 含 v1 未定义字段 {sorted(unknown)}"))
                oid = o.get("id")
                if not isinstance(oid, str) or not ID_RE.match(oid) or oid in RESERVED_IDS:
                    f.append(finding("S", SEV_ERROR, qid, f"{loc}.id 非法：{oid!r}"))
                else:
                    oids.append(oid)
                _check_block(o.get("text"), f"{loc}.text", f, qid=qid)
            if len(set(oids)) != len(oids):
                f.append(finding("S", SEV_ERROR, qid, f"{path}：选项 id 重复"))
            if qtype == "single":
                a = q.get("answer")
                if not isinstance(a, str) or a not in set(oids):
                    f.append(finding("S", SEV_ERROR, qid,
                                     f"{path}：answer 必须为存在的一个选项 id（当前 {a!r}）"))
            else:
                a = q.get("answer")
                if (not isinstance(a, list) or not a
                        or any(not isinstance(x, str) or x not in set(oids) for x in a)
                        or len(set(a)) != len(a)):
                    f.append(finding("S", SEV_ERROR, qid,
                                     f"{path}：answer 需要不重复的正确选项 id 数组"))
        elif qtype == "boolean":
            if not isinstance(q.get("answer"), bool):
                f.append(finding("S", SEV_ERROR, qid, f"{path}：判断题 answer 必须为 true 或 false（JSON 布尔值）"))
        else:  # fill
            a = q.get("answer")
            if not isinstance(a, list) or not (1 <= len(a) <= 20):
                f.append(finding("S", SEV_ERROR, qid, f"{path}：填空 answer 需要 1–20 个双语参考答案"))
            else:
                for j, blk in enumerate(a):
                    _check_block(blk, f"{path}.answer[{j}]", f, qid=qid)
                en_blanks = len(re.findall(r"___", block_en(q.get("prompt"))))
                if en_blanks != len(a):
                    f.append(finding("S", SEV_ERROR, qid,
                                     f"{path}：英文题干 ___ 空位数（{en_blanks}）必须等于参考答案数量（{len(a)}）"))
                zh_prompt = block_zh(q.get("prompt"))
                if zh_prompt and len(re.findall(r"___", zh_prompt)) != len(a):
                    f.append(finding("S", SEV_ERROR, qid, f"{path}：中文题干空位数量与参考答案数量不一致"))
    return f


# --------------------------------------------------------------------------
# R1 · 正确项不得是最长的选项
# --------------------------------------------------------------------------

def _is_image_option(opt) -> bool:
    """选项文本里带 images → 该选项的内容是图，文本只是 "Shape A" 这类标签。"""
    blk = opt.get("text") if isinstance(opt, dict) else None
    return isinstance(blk, dict) and bool(blk.get("images"))


def check_r1(q, image_strict: bool = False) -> list:
    f: list = []
    if q.get("type") not in ("single", "multiple"):
        return f
    opts = options_of(q)
    cids = set(correct_ids(q))
    if len(opts) < 2 or not cids:
        return f
    # 纯图片选项：文本只是标签（如 Shape A / Shape B），长度不承载任何信息，
    # §7 的「正确项不得最长」**目的**（查文字选项的措辞暗示）在此不适用 → N/A。
    # 这是**有意收窄**，不是放水；混合题（仍有文字选项）照常检查。
    # N/A 必须打印（不能静默变成 PASS），但**不影响退出码**——它不是「没查」。
    # `--r1-image-strict` 关掉本豁免、回到字面严格。
    if all(_is_image_option(o) for o in opts) and not image_strict:
        return [finding(
            "R1", SEV_NA, q.get("id"),
            "纯图片题：全部选项仅含 images，文本为标签，长度不承载信息——R1 不适用",
            options=sorted(cids),
            detail="要按字面严格检查，请加 --r1-image-strict",
        )]

    for lang in ("en", "zh"):
        pairs = [(o.get("id"), block_lang_strict(o.get("text"), lang).strip()) for o in opts]
        if any(not txt for _, txt in pairs):
            continue  # 该语言有选项缺文本，无法在该语言上比较
        clen = [len(t) for oid, t in pairs if oid in cids]
        dlen = [len(t) for oid, t in pairs if oid not in cids]
        if not clen or not dlen:
            continue
        cmax, dmax = max(clen), max(dlen)
        if dmax <= cmax:
            lens = "、".join(f"{oid}={len(t)}" for oid, t in pairs)
            f.append(finding(
                "R1", SEV_ERROR, q.get("id"),
                f"[{lang}] 正确项最长 {cmax} 字符，最长干扰项 {dmax} 字符——"
                f"没有干扰项严格更长（逐题数字符数不通过）",
                options=sorted(cids), detail=f"{lang} 选项字符数：{lens}",
            ))
        # 附带的「长度接近」提示（§7：四个选项字符数要接近）
        # 判据：最长选项 ≥ 最短选项的 2 倍（因子判据，避免绝对差值的噪声）
        alllen = [len(t) for _, t in pairs]
        if min(alllen) > 0 and max(alllen) >= 2 * min(alllen):
            f.append(finding(
                "R1", SEV_WARN, q.get("id"),
                f"[{lang}] 选项长度差异过大（最短 {min(alllen)} / 最长 {max(alllen)} 字符），"
                f"§7 要求「字符数要接近」",
            ))
    return f


# --------------------------------------------------------------------------
# R2 · 正确项下标打散
# --------------------------------------------------------------------------

def check_r2(questions, max_index_share: float = 0.5) -> list:
    f: list = []
    seq: list = []
    for q in questions:
        if q.get("type") != "single":
            continue
        opts = options_of(q)
        ans = q.get("answer")
        idx = next((i for i, o in enumerate(opts) if o.get("id") == ans), None)
        if idx is not None:
            seq.append((q.get("id"), idx))
    n = len(seq)
    if n == 0:
        return f
    counts: dict = {}
    for _, i in seq:
        counts[i] = counts.get(i, 0) + 1
    dominant = max(counts, key=lambda k: (counts[k], -k))
    share = counts[dominant] / n
    shown = " → ".join(f"{qid}:{i}" for qid, i in seq)

    if n >= 4 and share > max_index_share:
        ids = [qid for qid, i in seq if i == dominant]
        f.append(finding(
            "R2", SEV_ERROR, ids[0],
            f"答案下标过于集中：{counts[dominant]}/{n} 题（{share:.0%}）落在下标 {dominant}",
            questions=ids, detail=f"下标序列：{shown}",
        ))
    elif 2 <= n <= 3 and share == 1.0:
        f.append(finding(
            "R2", SEV_WARN, seq[0][0],
            f"题量仅 {n} 题且答案下标全为 {dominant}；题量≥4 时判违规",
            questions=[qid for qid, _ in seq], detail=f"下标序列：{shown}",
        ))

    for p in range(2, min(4, n // 2) + 1):
        if n >= 2 * p and all(seq[i][1] == seq[i % p][1] for i in range(n)):
            f.append(finding(
                "R2", SEV_ERROR, seq[0][0],
                f"答案下标成规律：以 {p} 为周期循环重复（§7 要求「不集中，也不交替成规律」）",
                questions=[qid for qid, _ in seq], detail=f"下标序列：{shown}",
            ))
            break

    if n >= 8 and len(counts) < 3:
        f.append(finding(
            "R2", SEV_WARN, seq[0][0],
            f"{n} 道单选题只用到 {len(counts)} 个下标位置（0–3 之间应打散）",
            detail=f"下标序列：{shown}",
        ))

    # 多选题：正确项集合不应完全一致（提示级）
    msets = []
    for q in questions:
        if q.get("type") != "multiple":
            continue
        opts = options_of(q)
        cids = set(correct_ids(q))
        msets.append((q.get("id"), tuple(sorted(i for i, o in enumerate(opts) if o.get("id") in cids))))
    if len(msets) >= 3 and len({s for _, s in msets}) == 1:
        f.append(finding(
            "R2", SEV_WARN, msets[0][0],
            f"{len(msets)} 道多选题的正确项位置完全相同（下标 {list(msets[0][1])}）",
            questions=[qid for qid, _ in msets],
        ))
    return f


# --------------------------------------------------------------------------
# R3 · 干扰项非荒谬
# --------------------------------------------------------------------------

def check_r3(q, sim_threshold: float = 0.85) -> list:
    f: list = []
    if q.get("type") not in ("single", "multiple"):
        return f
    opts = options_of(q)
    cids = set(correct_ids(q))
    if not opts or not cids:
        return f

    for o in opts:
        blk = o.get("text")
        has_img = isinstance(blk, dict) and blk.get("images")
        if not block_text(blk).strip() and not has_img:
            f.append(finding("R3", SEV_ERROR, q.get("id"),
                             f"选项 {o.get('id')} 文本为空——属于凑数选项"))

    correct_opts = [o for o in opts if o.get("id") in cids]
    distract_opts = [o for o in opts if o.get("id") not in cids]

    for d in distract_opts:
        for c in correct_opts:
            r, lang = max_similarity(d.get("text"), c.get("text"))
            if r >= sim_threshold:
                f.append(finding(
                    "R3", SEV_ERROR, q.get("id"),
                    f"干扰项 {d.get('id')} 与正确项 {c.get('id')} 在 [{lang}] 下相似度 {r:.2f}"
                    f"（≥{sim_threshold}），近乎同义，不是真实易错点",
                    options=[d.get("id"), c.get("id")],
                ))

    for i in range(len(distract_opts)):
        for j in range(i + 1, len(distract_opts)):
            a, b = distract_opts[i], distract_opts[j]
            r, lang = max_similarity(a.get("text"), b.get("text"))
            if r >= sim_threshold:
                f.append(finding(
                    "R3", SEV_ERROR, q.get("id"),
                    f"两个干扰项 {a.get('id')} 与 {b.get('id')} 在 [{lang}] 下相似度 {r:.2f}"
                    f"（≥{sim_threshold}），互相重复",
                    options=[a.get("id"), b.get("id")],
                ))
    return f


# --------------------------------------------------------------------------
# R4 · 去掉措辞暗示
# --------------------------------------------------------------------------

def _hedge_patterns(lang: str):
    if lang == "zh":
        return [(name, re.compile(pat)) for name, pat in HEDGE_ZH]
    return [(w, re.compile(r"\b" + re.escape(w) + r"\b", re.IGNORECASE)) for w in HEDGE_EN]


def check_r4(q) -> list:
    f: list = []
    if q.get("type") not in ("single", "multiple"):
        return f
    opts = options_of(q)
    cids = set(correct_ids(q))
    if not opts or not cids:
        return f
    correct_opts = [o for o in opts if o.get("id") in cids]
    distract_opts = [o for o in opts if o.get("id") not in cids]

    for lang in ("en", "zh"):
        dtexts = [block_lang_strict(o.get("text"), lang) for o in distract_opts]
        dtexts = [t for t in dtexts if t.strip()]
        if not dtexts:
            continue
        for c in correct_opts:
            ctext = block_lang_strict(c.get("text"), lang)
            if not ctext.strip():
                continue
            for name, pat in _hedge_patterns(lang):
                if not pat.search(ctext):
                    continue
                if any(pat.search(d) for d in dtexts):
                    continue  # 干扰项也用了同一限定词 → 不构成暗示
                f.append(finding(
                    "R4", SEV_ERROR, q.get("id"),
                    f"正确项 {c.get('id')} 在 [{lang}] 下独占限定词「{name}」，"
                    f"其余选项都没有——构成措辞暗示",
                    options=[c.get("id")],
                ))

    # 题干限定词：语义部分不可机器判定，给提示要求人工确认「只有一项满足」
    prompt = block_text(q.get("prompt"))
    m = LIMIT_RE.search(prompt)
    if m and q.get("type") == "single":
        f.append(finding(
            "R4", SEV_WARN, q.get("id"),
            f"题干含限定词「{m.group(0)}」，§7 要求确保只有一项满足该限定——需人工确认",
        ))
    return f


# --------------------------------------------------------------------------
# R5 · 同卷不自相矛盾
# --------------------------------------------------------------------------

def _cue_before(text: str, idx: int, window: int) -> str:
    """检查 text[idx] 之前 window 字符内是否有排除信号（信号必须紧接其前）。"""
    if idx <= 0:
        return ""
    pre = text[max(0, idx - window):idx]
    for cue in EXCLUSION_CUES:
        if cue in pre:
            return cue
    return ""


def check_r5(questions, cue_window: int = 12, allow_pairs=None) -> list:
    f: list = []
    allow = {pair_key(*p.split("|", 1)) if "|" in p else p for p in (allow_pairs or set())}

    correct_map: dict = {}   # (lang, norm) -> [(qid, oid, orig)]
    distract_map: dict = {}  # (lang, norm) -> [(qid, oid, orig)]
    for q in questions:
        qid = q.get("id")
        opts = options_of(q)
        if not opts:
            continue
        cids = set(correct_ids(q))
        for o in opts:
            oid = o.get("id")
            for lang in ("en", "zh"):
                t = block_lang_strict(o.get("text"), lang).strip()
                if len(t) < 3:
                    continue
                key = (lang, norm_text(t))
                rec = (qid, oid, t)
                (correct_map if oid in cids else distract_map).setdefault(key, []).append(rec)

    def allowed(a, b):
        return pair_key(a, b) in allow

    # (a) 某题的正确项文本 = 另一题的干扰项文本
    for key in set(correct_map) & set(distract_map):
        lang = key[0]
        for qid_c, oid_c, orig_c in correct_map[key]:
            for qid_d, oid_d, _ in distract_map[key]:
                if qid_c == qid_d or allowed(qid_c, qid_d):
                    continue
                expl = block_lang_strict(
                    next((x.get("explanation") for x in questions if x.get("id") == qid_d), None), lang
                )
                cue = _cue_before(expl, expl.find(orig_c), cue_window) if orig_c in expl else ""
                f.append(finding(
                    "R5", SEV_ERROR if cue else SEV_WARN, qid_c,
                    f"矛盾对：{qid_c} 的正确项 {oid_c}「{orig_c}」同时是 {qid_d} 的干扰项 {oid_d}"
                    + (f"，且 {qid_d} 的解析用「{cue}」将其排除" if cue else "（未在解析中看到排除措辞，仍需人工确认）"),
                    other=qid_d,
                ))

    # (b) 某题解析把**另一题（或本题）的正确项文本**当作被排除的对象
    for q in questions:
        qid = q.get("id")
        for lang in ("en", "zh"):
            expl = block_lang_strict(q.get("explanation"), lang)
            if not expl.strip():
                continue
            for cue in EXCLUSION_CUES:
                start = 0
                while True:
                    pos = expl.find(cue, start)
                    if pos < 0:
                        break
                    start = pos + len(cue)
                    seg = norm_text(expl[pos + len(cue): pos + len(cue) + 24])
                    if len(seg) < 3:
                        continue
                    for (klang, knorm), recs in correct_map.items():
                        if klang != lang or len(knorm) < 3 or knorm not in seg:
                            continue
                        for qid_c, oid_c, orig_c in recs:
                            if allowed(qid_c, qid):
                                continue
                            f.append(finding(
                                "R5", SEV_ERROR, qid_c,
                                f"{qid} 的解析用「{cue}」排除了 {qid_c} 的正确项 {oid_c}「{orig_c}」"
                                f"——同卷自相矛盾",
                                other=qid,
                            ))
    # 去重（同一对可能被 (a)(b) 各报一次）
    seen, out = set(), []
    for rec in f:
        k = (rec["rule"], rec["severity"], rec["question"], rec.get("other"), rec["message"])
        if k not in seen:
            seen.add(k)
            out.append(rec)
    return out


# --------------------------------------------------------------------------
# R6 · 解析指回来源
# --------------------------------------------------------------------------

def check_r6(q) -> list:
    src = q.get("source") if isinstance(q.get("source"), dict) else {}
    ref = _str(src.get("ref")).strip()
    pages = src.get("pages") if isinstance(src.get("pages"), list) else []
    expl = block_text(q.get("explanation"))
    note = _str(src.get("note"))
    haystack = f"{expl} {note}"

    if ref:
        return []
    if pages:
        return [finding(
            "R6", SEV_WARN, q.get("id"),
            f"只有 source.pages {pages} 没有 source.ref——页码指不到具体文档，建议补 ref",
        )]
    m = PAGE_RE.search(haystack)
    if m:
        return []
    return [finding(
        "R6", SEV_ERROR, q.get("id"),
        "解析没有指回来源：既无 source.ref / source.pages，解析里也没有「课件 pN」「第 N 页」这类页码",
    )]


# --------------------------------------------------------------------------
# 汇总
# --------------------------------------------------------------------------

def check_bank(bank, *, rules=None, similarity: float = 0.85,
               max_index_share: float = 0.5, cue_window: int = 12,
               allow_pairs=None, r1_image_strict: bool = False) -> list:
    rules = list(rules or ALL_RULES)
    findings: list = []
    questions = bank.get("questions") if isinstance(bank, dict) else None
    questions = questions if isinstance(questions, list) else []

    if "S" in rules:
        findings += check_structure(bank)
    if "R1" in rules:
        for q in questions:
            if isinstance(q, dict):
                findings += check_r1(q, image_strict=r1_image_strict)
    if "R2" in rules:
        findings += check_r2([q for q in questions if isinstance(q, dict)], max_index_share)
    if "R3" in rules:
        for q in questions:
            if isinstance(q, dict):
                findings += check_r3(q, similarity)
    if "R4" in rules:
        for q in questions:
            if isinstance(q, dict):
                findings += check_r4(q)
    if "R5" in rules:
        findings += check_r5([q for q in questions if isinstance(q, dict)], cue_window, allow_pairs)
    if "R6" in rules:
        for q in questions:
            if isinstance(q, dict):
                findings += check_r6(q)
    return findings


def summarize(findings) -> dict:
    errors = [x for x in findings if x["severity"] == SEV_ERROR]
    warns = [x for x in findings if x["severity"] == SEV_WARN]
    nas = [x for x in findings if x["severity"] == SEV_NA]
    skips = [x for x in findings if x["severity"] == SEV_SKIP]
    per_rule: dict = {}
    for rule in ALL_RULES:
        rs = [x for x in findings if x["rule"] == rule]
        per_rule[rule] = {
            "total": len(rs),
            "error": len([x for x in rs if x["severity"] == SEV_ERROR]),
            "warn": len([x for x in rs if x["severity"] == SEV_WARN]),
            "na": len([x for x in rs if x["severity"] == SEV_NA]),
            "skip": len([x for x in rs if x["severity"] == SEV_SKIP]),
        }
    return {"error": len(errors), "warn": len(warns),
            "na": len(nas), "skip": len(skips), "per_rule": per_rule}


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------

def format_report(path: str, bank, findings, *, strict: bool = False) -> str:
    lines: list = []
    s = summarize(findings)
    qs = bank.get("questions") if isinstance(bank, dict) else None
    nq = len(qs) if isinstance(qs, list) else 0
    lines.append(f"[bank] {path}")
    lines.append(f"       id={bank.get('id') if isinstance(bank, dict) else '?'}  "
                 f"version={bank.get('version') if isinstance(bank, dict) else '?'}  题数={nq}")
    for rule in ALL_RULES:
        st = s["per_rule"][rule]
        bits = []
        if st["error"]:
            bits.append(f"FAIL {st['error']}")
        if st["warn"]:
            bits.append(f"WARN {st['warn']}")
        if st["na"]:
            bits.append(f"N/A {st['na']}")
        if st["skip"]:
            bits.append(f"SKIP {st['skip']}")
        status = " ".join(bits) if bits else "PASS"
        lines.append(f"       {RULE_TITLES[rule]:<44} {status}")
    if findings:
        lines.append("       " + "-" * 60)
        for rec in findings:
            tag = {SEV_ERROR: "FAIL", SEV_WARN: "WARN",
                   SEV_NA: "N/A", SEV_SKIP: "SKIP"}[rec["severity"]]
            loc = rec["question"]
            if rec.get("options"):
                loc += f" 选项 {','.join(str(x) for x in rec['options'])}"
            if rec.get("other"):
                loc += f" ↔ {rec['other']}"
            lines.append(f"       [{tag}] {rec['rule']}  {loc}")
            lines.append(f"              {rec['message']}")
            if rec.get("detail"):
                lines.append(f"              {rec['detail']}")
    if s["skip"]:
        verdict = "未通过（INCOMPLETE）"
    elif s["error"] or (strict and s["warn"]):
        verdict = "未通过"
    else:
        verdict = "通过"
    lines.append(f"       小结：error {s['error']} / warn {s['warn']} / n/a {s['na']} "
                 f"/ skip {s['skip']} → {verdict}")
    na_rules = sorted({x["rule"] for x in findings if x["severity"] == SEV_NA})
    if s["na"]:
        hint = "；要按字面严格检查请加 --r1-image-strict" if "R1" in na_rules else ""
        lines.append(f"       ℹ {s['na']} 条 N/A = 该规则本来就不适用"
                     f"（不是 PASS，也不影响退出码）{hint}")
    if s["skip"]:
        lines.append(f"       ⚠ {s['skip']} 条 SKIP = 该规则**应执行而未执行** "
                     f"→ INCOMPLETE / exit 1")
    return "\n".join(lines)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(
        prog="check_quiz_rules.py",
        description="出题规则检查器（心理库 AGENTS.md §7 的可执行实现）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("banks", nargs="*", help="题库 JSON v1 文件（可多个）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("--rules", default=",".join(ALL_RULES),
                    help=f"要跑的规则，逗号分隔（默认 {','.join(ALL_RULES)}）")
    ap.add_argument("--strict", action="store_true", help="warn 也算违例")
    ap.add_argument("--similarity", type=float, default=0.85,
                    help="R3 近乎同义阈值（默认 0.85）")
    ap.add_argument("--max-index-share", type=float, default=0.5,
                    help="R2 单一答案下标的最大占比（默认 0.5）")
    ap.add_argument("--r5-cue-window", type=int, default=12,
                    help="R5 排除信号紧接在内容之前的窗口字符数（默认 12）")
    ap.add_argument("--allow-pairs", default="",
                    help="R5 白名单，逗号分隔的题目 id 对，如 Q1|Q7,Q2|Q9")
    ap.add_argument("--r1-image-strict", action="store_true",
                    help="关掉 R1 的纯图片题豁免，回到字面严格（纯图片题也按字符数判）")
    ap.add_argument("--list-rules", action="store_true", help="打印规则表后退出")
    ap.add_argument("--quiet", action="store_true", help="只输出汇总行")
    args = ap.parse_args(argv)

    if args.list_rules:
        for rule in ALL_RULES:
            print(f"{rule}\t{RULE_TITLES[rule]}")
        return 0

    if not args.banks:
        ap.error("至少需要一个题库 JSON 文件（或用 --list-rules）")

    rules = [r.strip().upper() for r in args.rules.split(",") if r.strip()]
    bad = [r for r in rules if r not in ALL_RULES]
    if bad:
        ap.error(f"未知规则 {bad}；可用：{','.join(ALL_RULES)}")

    allow_pairs = {p.strip() for p in args.allow_pairs.split(",") if p.strip()}

    all_reports: list = []
    loaded: list = []
    exit_code = 0
    for path in args.banks:
        p = Path(path)
        if not p.exists():
            all_reports.append({"path": path, "error": "文件不存在"})
            loaded.append(None)
            exit_code = 1
            continue
        try:
            bank = json.loads(p.read_text(encoding="utf-8-sig"))
        except Exception as e:  # noqa: BLE001
            all_reports.append({"path": path, "error": f"JSON 解析失败：{e}"})
            loaded.append(None)
            exit_code = 1
            continue
        findings = check_bank(
            bank, rules=rules, similarity=args.similarity,
            max_index_share=args.max_index_share, cue_window=args.r5_cue_window,
            allow_pairs=allow_pairs, r1_image_strict=args.r1_image_strict,
        )
        s = summarize(findings)
        # SKIP（应执行而未执行）必须使结果非通过 → INCOMPLETE / exit 1，
        # 与 gates 层 check_html_assets.py 的语义一致。N/A 不影响退出码。
        failed = s["error"] > 0 or s["skip"] > 0 or (args.strict and s["warn"] > 0)
        if failed:
            exit_code = 1
        all_reports.append({
            "path": path,
            "bankId": bank.get("id") if isinstance(bank, dict) else None,
            "questions": len(bank.get("questions", [])) if isinstance(bank, dict) else 0,
            "summary": s,
            "findings": findings,
            "failed": failed,
        })
        loaded.append(bank)

    if args.json:
        print(json.dumps({"reports": all_reports, "exitCode": exit_code},
                         ensure_ascii=False, indent=2))
        return exit_code

    print("=" * 72)
    print(f"出题规则检查 · {len(args.banks)} 个题库 · 规则 {','.join(rules)}"
          + ("（--strict）" if args.strict else "")
          + ("（--r1-image-strict：R1 无豁免）" if args.r1_image_strict else ""))
    print("=" * 72)
    total_e = total_w = total_na = total_s = 0
    for rep, bank in zip(all_reports, loaded):
        if "error" in rep:
            print(f"[bank] {rep['path']}\n       [FAIL] {rep['error']}")
            continue
        if not args.quiet:
            print(format_report(rep["path"], bank, rep["findings"], strict=args.strict))
        total_e += rep["summary"]["error"]
        total_w += rep["summary"]["warn"]
        total_na += rep["summary"]["na"]
        total_s += rep["summary"]["skip"]
    print("-" * 72)
    print(f"汇总：{len(all_reports)} 个题库 · error {total_e} / warn {total_w} "
          f"/ n/a {total_na} / skip {total_s} → "
          + ("通过" if exit_code == 0 else ("未通过（INCOMPLETE）" if total_s else "未通过")))
    if total_na:
        print(f"      N/A {total_na} 条 = 该规则本来就不适用（不是 PASS，也不影响退出码）；"
              f"加 --r1-image-strict 可回到字面严格")
    if total_s:
        print(f"      SKIP {total_s} 条 = 该规则应执行而未执行 → INCOMPLETE / exit 1")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
