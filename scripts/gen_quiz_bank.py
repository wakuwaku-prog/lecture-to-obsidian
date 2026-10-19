#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_quiz_bank.py — lecture-to-obsidian L4 考题层生成器。

从**题源**（`.quizsrc.json` 或 `.quizsrc.md`）生成题库 JSON v1，并**同源**输出三种形态：

  ① `<base>.fence.md`  —— `dsh-ui` 卷子围栏（radio × n + 一个 submit，groups 列全）
  ② `<base>.quiz.md`   —— md 题目 + `> [!success]- 答案与解析` 折叠答案块
  ③ `<base>.json`      —— 题库 JSON v1（可被 刷题工具/开始刷题.html 直接导入）

三种形态都由同一份内存对象 `bank` 派生（`build_bank()` 只跑一次），
**不各写一遍**——正确答案、选项顺序、解析文本不存在第二处来源。

题源与题库的区别：题源里正确项用选项上的 `"correct": true` 标记，
`answer`（选项 id / 布尔值 / 参考答案数组）由生成器推导，因此不可能出现
「围栏答案」与「题库 answer」不一致。

用法：
    # 从题源生成三种形态
    python gen_quiz_bank.py --src questions.quizsrc.json --out "<vault>/题库/"

    # 顺带用 manifest 做页序交叉校验
    python gen_quiz_bank.py --src q.md --manifest "<work>/manifest.json" --out "<vault>/题库/"

    # 只有 manifest 时，产出一份待填写的题源骨架
    python gen_quiz_bank.py --manifest "<work>/manifest.json" --out "<work>/" --emit-source-template

    # 只校验不落盘
    python gen_quiz_bank.py --src q.json --out out/ --dry-run --print all

退出码：生成并全部通过 → 0；schema 或出题规则未通过 → 1（详见 --allow-rule-violations）。
"""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import check_quiz_rules as rules  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCHEMA = SKILL_ROOT / "schemas" / "quiz-bank.schema.json"

# 题源允许出现的字段（题源不是题库，这里可以宽一点；落到题库时会被严格裁剪）
BANK_TOP = {"schemaVersion", "id", "version", "title", "description", "questions"}
QUESTION_FIELDS = {
    "id", "type", "prompt", "options", "answer", "answerContent",
    "explanation", "tags", "difficulty", "source",
}
OPTION_FIELDS = {"id", "text"}
BLOCK_FIELDS = {"en", "zh", "images"}
IMAGE_FIELDS = {"src", "alt", "caption"}
SOURCE_FIELDS = {"ref", "pages", "note"}

Q_TYPES = ("single", "multiple", "boolean", "fill")
DIFFICULTIES = ("basic", "applied")
IMG_SRC_RE = re.compile(r"^data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/]+={0,2})$")


class SourceError(Exception):
    """题源本身不合法（与出题规则无关）。"""


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------

def _s(v) -> str:
    return v if isinstance(v, str) else ""


def quote_cn(s: str) -> str:
    """把半角双引号成对换成中文引号。

    《有机化学 讲解格式.md》§5.3 要求 dsh-ui 围栏的 JSON 字符串里不出现半角 `"`。
    """
    out, opening = [], True
    for ch in (s or ""):
        if ch == '"':
            out.append("“" if opening else "”")
            opening = not opening
        else:
            out.append(ch)
    return "".join(out)


def _bilingual(v, *, required_en: bool = True, where: str = "block") -> dict:
    if not isinstance(v, dict):
        raise SourceError(f"{where} 必须是 {{en, zh}} 对象")
    out = {}
    if "en" in v:
        out["en"] = _s(v["en"])
    if "zh" in v:
        out["zh"] = _s(v["zh"])
    if "en" not in out:
        out["en"] = ""
    unknown = set(v) - BLOCK_FIELDS
    if unknown:
        raise SourceError(f"{where} 含不允许的字段 {sorted(unknown)}（只允许 {sorted(BLOCK_FIELDS)}）")
    if required_en and not out["en"].strip() and not v.get("images"):
        raise SourceError(f"{where}：英文 en 不能为空（除非该内容含图片）")
    return out


def _images(images, where: str) -> list:
    if images is None:
        return []
    if not isinstance(images, list):
        raise SourceError(f"{where}.images 必须是数组")
    if len(images) > 8:
        raise SourceError(f"{where}.images 最多 8 张（v1 限制）")
    out = []
    for i, img in enumerate(images):
        loc = f"{where}.images[{i}]"
        if not isinstance(img, dict):
            raise SourceError(f"{loc} 必须是对象")
        unknown = set(img) - IMAGE_FIELDS
        if unknown:
            raise SourceError(f"{loc} 含 v1 未定义字段 {sorted(unknown)}")
        src = _s(img.get("src"))
        m = IMG_SRC_RE.match(src)
        if not m:
            raise SourceError(
                f"{loc}.src 只接受 data:image/(png|jpeg|webp|gif);base64,；"
                f"不接受网络 URL、本机路径、相对路径或 SVG"
            )
        try:
            raw = base64.b64decode(m.group(2), validate=True)
        except (binascii.Error, ValueError):
            raise SourceError(f"{loc}.src base64 无效") from None
        kind = m.group(1)
        sig = (
            raw.startswith(b"\x89PNG\r\n\x1a\n") if kind == "png"
            else raw.startswith(b"\xff\xd8\xff") if kind == "jpeg"
            else re.match(rb"^GIF8[79]a", raw) is not None if kind == "gif"
            else raw.startswith(b"RIFF") and raw[8:12] == b"WEBP"
        )
        if not sig or len(raw) < 20:
            raise SourceError(f"{loc}.src 图片内容与声明格式（{kind}）不符")
        rec = {"src": src, "alt": _bilingual(img.get("alt"), required_en=True, where=f"{loc}.alt")}
        if "caption" in img:
            rec["caption"] = _bilingual(img["caption"], required_en=False, where=f"{loc}.caption")
        out.append(rec)
    return out


def _block(v, where: str, *, required_en: bool = True) -> dict:
    """题源 contentBlock → 题库 contentBlock（只保留 v1 允许的键）。"""
    if not isinstance(v, dict):
        raise SourceError(f"{where} 必须是 {{en, zh, images?}} 对象")
    unknown = set(v) - BLOCK_FIELDS
    if unknown:
        raise SourceError(f"{where} 含不允许的字段 {sorted(unknown)}")
    out = {"en": _s(v.get("en"))}
    if "zh" in v:
        out["zh"] = _s(v.get("zh"))
    imgs = _images(v.get("images"), where)
    if imgs:
        out["images"] = imgs
    if required_en and not out["en"].strip() and not imgs:
        raise SourceError(f"{where}：英文 en 不能为空（除非含图片）")
    return out


def _lang_text(block, lang: str) -> str:
    """渲染用取文本：zh 优先中文；en 优先英文；both 用「中文 ／ English」。"""
    if not isinstance(block, dict):
        return ""
    zh, en = _s(block.get("zh")).strip(), _s(block.get("en")).strip()
    if lang == "en":
        return en or zh
    if lang == "both":
        if zh and en and zh != en:
            return f"{zh} ／ {en}"
        return zh or en
    return zh or en


# --------------------------------------------------------------------------
# 题源：JSON
# --------------------------------------------------------------------------

def load_source_json(obj) -> dict:
    if not isinstance(obj, dict):
        raise SourceError("题源根必须是 JSON 对象")
    if "questions" not in obj:
        raise SourceError("题源缺少 questions")
    return obj


# --------------------------------------------------------------------------
# 题源：Markdown
# --------------------------------------------------------------------------

EN_RE = re.compile(r"^EN\s*[:：]\s*(.*)$")
META_RE = re.compile(r"^-\s*([A-Za-z][A-Za-z-]*)\s*[:：]\s*(.*)$")
OPT_RE = re.compile(r"^-\s*\[( |x|X)\]\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*[.、)．]\s*(.*)$")
QHEAD_RE = re.compile(r"^(\S+)\s*(?:\[([A-Za-z]+)\])?\s*(?:\|\s*(.*))?$")
KNOWN_META = {
    "id", "version", "ref", "desc", "desc-en", "tags", "difficulty",
    "pages", "note", "answer", "answer-en", "source",
}


def _split_pages(raw: str) -> list:
    out = []
    for tok in re.split(r"[,，、\s]+", raw or ""):
        tok = tok.strip()
        if tok:
            out.append(int(tok))
    return out


def _parse_md_question(qhead: str, body_lines: list) -> dict:
    m = QHEAD_RE.match(qhead)
    if not m:
        raise SourceError(f"题目标题无法解析：{qhead!r}（应为 `## QID [type] | tag1, tag2`）")
    qid = m.group(1)
    qtype = (m.group(2) or "single").lower()
    tags = [t.strip() for t in (m.group(3) or "").split(",") if t.strip()]
    if qtype not in Q_TYPES:
        raise SourceError(f"{qid}：未知题型 {qtype!r}（可用 {Q_TYPES}）")

    prompt_zh: list = []
    prompt_en: list = []
    expl_zh: list = []
    expl_en: list = []
    options: list = []
    meta: dict = {}
    phase = "prompt"     # prompt | options | expl
    cur_opt = None

    for raw in body_lines:
        s = raw.strip()
        if not s:
            # 选择题的题干在第一个选项处结束；判断题/填空题在第一个空行处结束
            if phase == "prompt" and qtype in ("boolean", "fill") and (prompt_zh or prompt_en):
                phase = "expl"
            cur_opt = None
            continue
        men = EN_RE.match(s)
        mopt = OPT_RE.match(s)
        mmeta = META_RE.match(s)

        if mopt:
            phase = "options"
            cur_opt = {
                "id": mopt.group(2),
                "zh": mopt.group(3).strip(),
                "en": "",
                "correct": mopt.group(1).lower() == "x",
            }
            options.append(cur_opt)
            continue
        if cur_opt is not None and raw[:1] in (" ", "\t") and men:
            cur_opt["en"] = men.group(1).strip()
            continue
        if mmeta and mmeta.group(1).lower() in KNOWN_META:
            key, val = mmeta.group(1).lower(), mmeta.group(2).strip()
            if key == "answer-en":
                meta["answer-en"] = val
            else:
                meta[key] = val
            if phase == "prompt":
                phase = "expl"
            cur_opt = None
            continue
        if men:
            (prompt_en if phase == "prompt" else expl_en).append(men.group(1).strip())
            continue
        if phase == "prompt":
            prompt_zh.append(s)
        else:
            phase = "expl"
            expl_zh.append(s)
            cur_opt = None

    q = {
        "id": qid,
        "type": qtype,
        "prompt": {"en": " ".join(prompt_en).strip(), "zh": " ".join(prompt_zh).strip()},
        "explanation": {"en": " ".join(expl_en).strip(), "zh": " ".join(expl_zh).strip()},
    }
    if tags:
        q["tags"] = tags
    if meta.get("difficulty"):
        q["difficulty"] = meta["difficulty"]
    if meta.get("note"):
        q.setdefault("source", {})["note"] = meta["note"]
    if meta.get("ref"):
        q.setdefault("source", {})["ref"] = meta["ref"]
    if meta.get("pages"):
        q.setdefault("source", {})["pages"] = _split_pages(meta["pages"])

    if qtype in ("single", "multiple"):
        q["options"] = [
            {"id": o["id"], "text": {"en": o["en"], "zh": o["zh"]}, "correct": o["correct"]}
            for o in options
        ]
        if meta.get("answer"):
            q["answer"] = meta["answer"]
    elif qtype == "boolean":
        raw_ans = (meta.get("answer") or "").strip().lower()
        if raw_ans in ("true", "1", "是", "正确", "对"):
            q["answer"] = True
        elif raw_ans in ("false", "0", "否", "错误", "错"):
            q["answer"] = False
        else:
            raise SourceError(f"{qid}：判断题需要 `- answer: true` 或 `- answer: false`")
    else:
        zh_items = [x.strip() for x in (meta.get("answer") or "").split("|") if x.strip()]
        en_items = [x.strip() for x in (meta.get("answer-en") or "").split("|") if x.strip()]
        if not zh_items:
            raise SourceError(f"{qid}：填空题需要 `- answer: 参考1 | 参考2`（可加 `- answer-en:` 提供英文）")
        q["answer"] = [
            {"en": en_items[i] if i < len(en_items) else zh_items[i], "zh": zh_items[i]}
            for i in range(len(zh_items))
        ]
    return q


def load_source_md(text: str) -> dict:
    lines = text.lstrip("\ufeff").splitlines()
    idx, title_zh, title_en = 0, "", ""
    while idx < len(lines):
        s = lines[idx].strip()
        if not s:
            idx += 1
            continue
        if s.startswith("# "):
            parts = [p.strip() for p in s[2:].split("|", 1)]
            title_zh = parts[0]
            title_en = parts[1] if len(parts) > 1 else ""
            idx += 1
            break
        raise SourceError("md 题源第一个非空行必须是 `# 中文标题 | English title`")

    meta: dict = {}
    while idx < len(lines) and not lines[idx].strip().startswith("## "):
        m = META_RE.match(lines[idx].strip())
        if m and m.group(1).lower() in KNOWN_META:
            meta[m.group(1).lower()] = m.group(2).strip()
        idx += 1

    questions: list = []
    while idx < len(lines):
        s = lines[idx].strip()
        if not s.startswith("## "):
            idx += 1
            continue
        qhead = s[3:].strip()
        idx += 1
        body: list = []
        while idx < len(lines) and not lines[idx].strip().startswith("## "):
            body.append(lines[idx])
            idx += 1
        questions.append(_parse_md_question(qhead, body))

    if not questions:
        raise SourceError("md 题源里没有找到任何题目（题目以 `## QID` 开头）")

    src = {
        "id": meta.get("id"),
        "version": meta.get("version") or "1.0.0",
        "title": {"en": title_en, "zh": title_zh},
        "questions": questions,
    }
    if meta.get("desc") or meta.get("desc-en"):
        src["description"] = {"en": meta.get("desc-en", ""), "zh": meta.get("desc", "")}
    if meta.get("ref"):
        src["defaultSource"] = {"ref": meta["ref"]}
    return src


def load_source(path: Path) -> dict:
    text = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() in (".md", ".markdown"):
        return load_source_md(text)
    try:
        return load_source_json(json.loads(text))
    except json.JSONDecodeError as e:
        raise SourceError(f"JSON 解析失败：{e}") from None


# --------------------------------------------------------------------------
# 题源 → 题库 JSON v1
# --------------------------------------------------------------------------

def _build_question(raw, default_source: dict, warnings: list) -> dict:
    if not isinstance(raw, dict):
        raise SourceError("每道题必须是对象")
    qid = _s(raw.get("id"))
    if not qid:
        raise SourceError("题目缺少 id")
    qtype = raw.get("type") or "single"
    if qtype not in Q_TYPES:
        raise SourceError(f"{qid}：未知题型 {qtype!r}")

    q: dict = {"id": qid, "type": qtype}
    q["prompt"] = _block(raw.get("prompt"), f"{qid}.prompt")
    if "explanation" not in raw:
        raise SourceError(f"{qid}：缺少 explanation（v1 必填，且必须指回来源）")
    q["explanation"] = _block(raw.get("explanation"), f"{qid}.explanation")
    if "answerContent" in raw:
        q["answerContent"] = _block(raw["answerContent"], f"{qid}.answerContent", required_en=False)

    if qtype in ("single", "multiple"):
        opts = raw.get("options")
        if not isinstance(opts, list) or not (2 <= len(opts) <= 26):
            raise SourceError(f"{qid}：选择题需要 2–26 个选项")
        built, correct = [], []
        for i, o in enumerate(opts):
            if not isinstance(o, dict):
                raise SourceError(f"{qid}.options[{i}] 必须是对象")
            unknown = set(o) - OPTION_FIELDS - {"correct"}
            if unknown:
                raise SourceError(f"{qid}.options[{i}] 含不允许的字段 {sorted(unknown)}")
            oid = _s(o.get("id"))
            if not oid:
                raise SourceError(f"{qid}.options[{i}] 缺少 id")
            built.append({"id": oid, "text": _block(o.get("text"), f"{qid}.options[{i}].text")})
            if o.get("correct") is True:
                correct.append(oid)
        if len({o["id"] for o in built}) != len(built):
            raise SourceError(f"{qid}：选项 id 重复")
        q["options"] = built
        explicit = raw.get("answer")
        if explicit is not None:
            if qtype == "single" and not isinstance(explicit, str):
                raise SourceError(f"{qid}：single 的 answer 必须是选项 id 字符串")
            if qtype == "multiple" and (not isinstance(explicit, list) or not explicit):
                raise SourceError(f"{qid}：multiple 的 answer 必须是非空选项 id 数组")
            flagged = set(correct)
            given = {explicit} if isinstance(explicit, str) else set(explicit)
            if flagged and flagged != given:
                warnings.append(
                    f"{qid}：显式 answer {sorted(given)} 与选项上的 correct 标记 {sorted(flagged)} 不一致，以 answer 为准"
                )
            q["answer"] = explicit
        else:
            if not correct:
                raise SourceError(f"{qid}：没有标记正确项（在选项上加 \"correct\": true，或显式写 answer）")
            if qtype == "single":
                if len(correct) > 1:
                    raise SourceError(f"{qid}：single 只能有一个正确项，标记了 {correct}")
                q["answer"] = correct[0]
            else:
                q["answer"] = correct
    elif qtype == "boolean":
        ans = raw.get("answer")
        if not isinstance(ans, bool):
            raise SourceError(f"{qid}：判断题 answer 必须是 JSON 布尔值 true/false")
        q["answer"] = ans
    else:  # fill
        ans = raw.get("answer")
        if not isinstance(ans, list) or not (1 <= len(ans) <= 20):
            raise SourceError(f"{qid}：填空 answer 需要 1–20 个双语参考答案")
        q["answer"] = [_block(a, f"{qid}.answer[{i}]") for i, a in enumerate(ans)]
        blanks = len(re.findall(r"___", _s(q["prompt"].get("en"))))
        if blanks != len(ans):
            raise SourceError(
                f"{qid}：英文题干 ___ 空位数（{blanks}）必须等于参考答案数量（{len(ans)}）"
            )
        zh_prompt = _s(q["prompt"].get("zh"))
        if zh_prompt and len(re.findall(r"___", zh_prompt)) != len(ans):
            raise SourceError(f"{qid}：中文题干空位数量与参考答案数量不一致")

    tags = raw.get("tags")
    if tags is not None:
        if (not isinstance(tags, list) or not tags
                or any(not isinstance(t, str) or not t.strip() for t in tags)):
            raise SourceError(f"{qid}：tags 必须为非空字符串数组")
        q["tags"] = list(dict.fromkeys(tags))
    if raw.get("difficulty") is not None:
        if raw["difficulty"] not in DIFFICULTIES:
            raise SourceError(f"{qid}：difficulty 仅支持 basic/applied")
        q["difficulty"] = raw["difficulty"]

    src = raw.get("source")
    src = dict(src) if isinstance(src, dict) else {}
    unknown = set(src) - SOURCE_FIELDS
    if unknown:
        raise SourceError(f"{qid}.source 含 v1 未定义字段 {sorted(unknown)}")
    if src or default_source:
        merged = {}
        ref = _s(src.get("ref")).strip() or _s(default_source.get("ref")).strip()
        if ref:
            merged["ref"] = ref
        if isinstance(src.get("pages"), list) and src["pages"]:
            merged["pages"] = [int(p) for p in src["pages"]]
        note = _s(src.get("note")).strip() or _s(default_source.get("note")).strip()
        if note:
            merged["note"] = note
        if merged:
            q["source"] = merged
    return q


def build_bank(src, *, warnings: list | None = None) -> dict:
    warnings = warnings if warnings is not None else []
    if not isinstance(src, dict):
        raise SourceError("题源根必须是对象")
    bank_id = _s(src.get("id")).strip()
    if not bank_id:
        raise SourceError("题源缺少 id（题库全局稳定 ID）")
    bank: dict = {
        "schemaVersion": 1,
        "id": bank_id,
        "version": _s(src.get("version")).strip() or "1.0.0",
        "title": _bilingual(src.get("title"), required_en=True, where="title"),
        "questions": [],
    }
    if src.get("description") is not None:
        bank["description"] = _bilingual(src["description"], required_en=False, where="description")

    default_source = src.get("defaultSource")
    default_source = default_source if isinstance(default_source, dict) else {}

    raw_qs = src.get("questions")
    if not isinstance(raw_qs, list) or not raw_qs:
        raise SourceError("题源 questions 必须是非空数组")
    seen: set = set()
    for raw in raw_qs:
        q = _build_question(raw, default_source, warnings)
        if q["id"] in seen:
            raise SourceError(f"题目 id 重复：{q['id']}")
        seen.add(q["id"])
        bank["questions"].append(q)
    return bank


# --------------------------------------------------------------------------
# 形态 ①：dsh-ui 卷子围栏
# --------------------------------------------------------------------------

def _radio_options(q, lang):
    """返回 (选项文本列表, 正确项下标)。"""
    if q["type"] == "boolean":
        if lang == "en":
            opts = ["True", "False"]
        elif lang == "both":
            opts = ["正确 / True", "错误 / False"]
        else:
            opts = ["正确", "错误"]
        return opts, (0 if q["answer"] is True else 1)
    opts = [_lang_text(o["text"], lang) for o in q["options"]]
    ans = q["answer"]
    idx = next((i for i, o in enumerate(q["options"]) if o["id"] == ans), 0)
    return opts, idx


def build_fence_spec(bank: dict, lang: str = "zh") -> dict:
    """构造 dsh-ui 卷子围栏的 spec 对象（单一来源，render_fence 只是它的序列化）。"""
    title = _lang_text(bank.get("title"), lang) or bank["id"]
    items: list = []
    groups: list = []
    for n, q in enumerate(bank["questions"], 1):
        gid = f"q{n}"
        prompt = quote_cn(_lang_text(q["prompt"], lang))
        if q["type"] in ("single", "boolean"):
            opts, idx = _radio_options(q, lang)
            items.append({
                "type": "radio",
                "group": gid,
                "label": f"{n}. {prompt}",
                "options": [quote_cn(t) for t in opts],
                "answer": idx,
                "explanation": quote_cn(_lang_text(q["explanation"], lang)),
            })
            groups.append(gid)
        elif q["type"] == "multiple":
            items.append({"type": "text", "size": "body", "content": f"**{n}.** {prompt}（多选）"})
            for o in q["options"]:
                items.append({
                    "type": "checkbox",
                    "group": gid,
                    "label": quote_cn(f"{o['id']}. {_lang_text(o['text'], lang)}"),
                })
            groups.append(gid)
        else:
            items.append({
                "type": "text",
                "size": "body",
                "content": f"**{n}.** {prompt}（填空题，参考答案见题库或笔记折叠块）",
            })
    label = f"交卷（{len(groups)} 题）" if lang == "en" else f"交卷（共 {len(groups)} 题）"
    items.append({
        "type": "submit",
        "label": label,
        "action": "grade",
        "groups": groups,
        "resetAction": "redo",
    })
    return {"title": f"{title} · 自测（{len(bank['questions'])} 题）", "gap": 14, "items": items}


def _count_nodes(node) -> int:
    """按 GenUI 口径数节点：容器 items/子节点各算 1。"""
    if isinstance(node, dict):
        n = 1
        for key in ("items", "tabs", "steps", "meshes", "diffs", "pairs", "series", "data"):
            v = node.get(key)
            if isinstance(v, list):
                n += sum(_count_nodes(x) for x in v)
        for key in ("items",):
            v = node.get(key)
            if isinstance(v, dict):
                n += _count_nodes(v)
        return n
    if isinstance(node, list):
        return sum(_count_nodes(x) for x in node)
    return 0


def fence_node_count(spec: dict) -> int:
    return _count_nodes(spec.get("items") or [])


def render_fence(bank: dict, lang: str = "zh") -> str:
    spec = build_fence_spec(bank, lang)
    return "```dsh-ui\n" + json.dumps(spec, ensure_ascii=False, indent=2) + "\n```\n"


# --------------------------------------------------------------------------
# 形态 ②：md 题目 + 折叠答案
# --------------------------------------------------------------------------

def _answer_display(q, lang) -> str:
    if q["type"] == "boolean":
        if lang == "en":
            return "True" if q["answer"] else "False"
        return "正确" if q["answer"] else "错误"
    if q["type"] == "multiple":
        return "、".join(q["answer"])
    if q["type"] == "single":
        oid = q["answer"]
        opt = next((o for o in q["options"] if o["id"] == oid), None)
        txt = _lang_text(opt["text"], lang) if opt else ""
        return f"{oid}（{txt}）" if txt else oid
    return " ／ ".join(_lang_text(a, lang) for a in q["answer"])


def _source_display(q) -> str:
    src = q.get("source") if isinstance(q.get("source"), dict) else {}
    bits = []
    if _s(src.get("ref")).strip():
        bits.append(_s(src["ref"]).strip())
    pages = src.get("pages")
    if isinstance(pages, list) and pages:
        bits.append("p" + ",".join(str(p) for p in pages))
    return " ".join(bits)


def render_md(bank: dict, lang: str = "zh") -> str:
    title = _lang_text(bank.get("title"), lang) or bank["id"]
    out = [f"## 自测（{len(bank['questions'])} 题）", ""]
    out.append(f"> 题源：`{bank['id']}` v{bank['version']}　·　{title}")
    out.append("")
    for n, q in enumerate(bank["questions"], 1):
        out.append(f"**{n}.** {_lang_text(q['prompt'], lang)}")
        out.append("")
        if q["type"] in ("single", "multiple"):
            for o in q["options"]:
                out.append(f"- {o['id']}. {_lang_text(o['text'], lang)}")
            out.append("")
        elif q["type"] == "boolean":
            out.append("- 正确")
            out.append("- 错误")
            out.append("")
        else:
            out.append(f"- 题干空位：{len(re.findall(r'___', _s(q['prompt'].get('en'))))} 个")
            out.append("")
    out.append("> [!success]- 答案与解析")
    for n, q in enumerate(bank["questions"], 1):
        out.append(f"> **{n}. {q['id']}**　答案 **{_answer_display(q, lang)}**")
        expl = _lang_text(q["explanation"], lang).strip()
        if expl:
            out.append(f"> {expl}")
        src = _source_display(q)
        if src:
            out.append(f"> 来源：{src}")
        out.append(">")
    while out and out[-1] == ">":
        out.pop()
    return "\n".join(out) + "\n"


# --------------------------------------------------------------------------
# schema 校验
# --------------------------------------------------------------------------

def validate_schema(bank: dict, schema_path: Path):
    """返回 (errors, note)。errors 为 None 表示 jsonschema 不可用。"""
    try:
        import jsonschema  # noqa: PLC0415
    except ImportError:
        return None, "jsonschema 未安装，跳过 schema 校验（已用内置 S 规则兜底）"
    if not schema_path.exists():
        return None, f"schema 文件不存在：{schema_path}"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = jsonschema.Draft7Validator(schema)
    errs = sorted(validator.iter_errors(bank), key=lambda e: [str(x) for x in e.path])
    return [f"{'/'.join(str(x) for x in e.path) or '<root>'}: {e.message}" for e in errs], None


# --------------------------------------------------------------------------
# manifest → 题源骨架
# --------------------------------------------------------------------------

def default_ref_from_manifest(manifest: dict) -> str:
    entries = manifest.get("sourceRegisterEntries")
    if isinstance(entries, list):
        for e in entries:
            if isinstance(e, dict) and _s(e.get("id")).strip():
                return _s(e["id"]).strip()
    pdf = manifest.get("pdf")
    if isinstance(pdf, dict) and _s(pdf.get("file")).strip():
        return Path(_s(pdf["file"]).strip()).stem
    course = manifest.get("source", {}).get("course", {}) if isinstance(manifest.get("source"), dict) else {}
    return _s(course.get("code")).strip() or _s(course.get("name")).strip()


def template_from_manifest(manifest: dict, bank_id: str | None = None) -> dict:
    course = {}
    if isinstance(manifest.get("source"), dict):
        course = manifest["source"].get("course") or {}
    pdf = manifest.get("pdf") if isinstance(manifest.get("pdf"), dict) else {}
    slides = manifest.get("slides") if isinstance(manifest.get("slides"), list) else []
    pages = sorted({s.get("pdfPage") for s in slides
                    if isinstance(s, dict) and isinstance(s.get("pdfPage"), int)})
    ref = default_ref_from_manifest(manifest)
    name_zh = _s(course.get("name")).strip() or _s(course.get("code")).strip() or "未命名课程"
    return {
        "id": bank_id or (re.sub(r"[^A-Za-z0-9._-]+", "-", _s(course.get("code")) or "quiz").strip("-")
                          + "-quiz"),
        "version": "0.1.0",
        "title": {"en": _s(course.get("code")).strip() or "Quiz bank", "zh": f"{name_zh} · 自测题"},
        "description": {"en": "", "zh": ""},
        "defaultSource": {"ref": ref, "note": _s(pdf.get("file")).strip()},
        "_pagesAvailable": pages,
        "_howto": [
            "题源（非题库）：正确项用选项上的 \"correct\": true 标记，answer 由 gen_quiz_bank.py 推导。",
            "每条 source.pages 用 PDF 阅读器页序；解析里写「课件 pN」或「第 N 页」以满足 R6。",
            "填好后：python gen_quiz_bank.py --src <本文件> --out <vault>/题库/",
            "生成后必须过：python check_quiz_rules.py <vault>/题库/<id>.json",
        ],
        "questions": [
            {
                "id": "L00-001",
                "type": "single",
                "prompt": {"en": "TODO: replace with a real question.", "zh": "TODO：替换为真实题目。"},
                "options": [
                    {"id": "A", "text": {"en": "TODO distractor (write it longer than the answer).", "zh": "TODO 干扰项（请写得比正确项长）。"}},
                    {"id": "B", "text": {"en": "TODO answer.", "zh": "TODO 正确项。"}, "correct": True},
                    {"id": "C", "text": {"en": "TODO distractor.", "zh": "TODO 干扰项。"}},
                    {"id": "D", "text": {"en": "TODO distractor.", "zh": "TODO 干扰项。"}},
                ],
                "explanation": {"en": "TODO: why correct, and why the others are wrong. Cite 课件 p1.",
                                "zh": "TODO：说明为什么对、其余为什么错。引用课件 p1。"},
                "tags": ["TODO"],
                "difficulty": "basic",
                "source": {"ref": ref, "pages": [1] if pages else []},
            },
            {
                "id": "L00-002",
                "type": "multiple",
                "prompt": {"en": "TODO: a question with more than one correct option.", "zh": "TODO：一道有多个正确项的题。"},
                "options": [
                    {"id": "A", "text": {"en": "TODO distractor.", "zh": "TODO 干扰项。"}},
                    {"id": "B", "text": {"en": "TODO correct one.", "zh": "TODO 正确项之一。"}, "correct": True},
                    {"id": "C", "text": {"en": "TODO correct two.", "zh": "TODO 正确项之二。"}, "correct": True},
                ],
                "explanation": {"en": "TODO. Cite 课件 p1.", "zh": "TODO。引用课件 p1。"},
                "tags": ["TODO"],
            },
            {
                "id": "L00-003",
                "type": "boolean",
                "prompt": {"en": "TODO: a statement to judge.", "zh": "TODO：一句需要判断的陈述。"},
                "answer": True,
                "explanation": {"en": "TODO. Cite 课件 p1.", "zh": "TODO。引用课件 p1。"},
                "tags": ["TODO"],
            },
            {
                "id": "L00-004",
                "type": "fill",
                "prompt": {"en": "TODO: a sentence with one ___ blank.", "zh": "TODO：一句含一个___空位的题干。"},
                "answer": [{"en": "reference answer", "zh": "参考答案"}],
                "explanation": {"en": "TODO. Cite 课件 p1.", "zh": "TODO。引用课件 p1。"},
                "tags": ["TODO"],
            },
        ],
    }


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def _ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def main(argv=None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(
        prog="gen_quiz_bank.py",
        description="题源 → 题库 JSON v1 + dsh-ui 卷子围栏 + md 折叠答案（三份同源）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    ap.add_argument("--src", help="题源文件（.quizsrc.json 或 .quizsrc.md）")
    ap.add_argument("--manifest", help="素材清单 manifest.json（默认 source.ref + 页序交叉校验）")
    ap.add_argument("--out", required=True, help="输出目录，或 .json 文件路径")
    ap.add_argument("--bank-id", default=None, help="覆盖题库 id")
    ap.add_argument("--lang", choices=["zh", "en", "both"], default="zh",
                    help="围栏与 md 的呈现语言（默认 zh）")
    ap.add_argument("--schema", default=str(DEFAULT_SCHEMA), help="冻结的 quiz-bank.schema.json")
    ap.add_argument("--emit-source-template", action="store_true",
                    help="不生成题库，只从 manifest 产出一份待填写的题源骨架")
    ap.add_argument("--print", dest="print_what", choices=["all", "fence", "md", "json"],
                    default=None, help="额外把指定形态打到 stdout")
    ap.add_argument("--dry-run", action="store_true", help="只校验与打印，不写文件")
    ap.add_argument("--allow-rule-violations", action="store_true",
                    help="出题规则未通过时仍返回 0（报告里会明确标注已放行）")
    ap.add_argument("--similarity", type=float, default=0.85, help="R3 近乎同义阈值")
    ap.add_argument("--r1-image-strict", action="store_true",
                    help="关掉 R1 的纯图片题豁免，回到字面严格（与 check_quiz_rules.py 同名参数一致）")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)

    manifest = None
    if args.manifest:
        mp = Path(args.manifest)
        if not mp.exists():
            print(f"[FAIL] manifest 不存在：{mp}")
            return 1
        manifest = json.loads(mp.read_text(encoding="utf-8-sig"))

    # ---- 模式 A：产出题源骨架 ----
    if args.emit_source_template or not args.src:
        if manifest is None:
            ap.error("需要 --src（题源）或 --manifest + --emit-source-template")
        tpl = template_from_manifest(manifest, args.bank_id)
        out = Path(args.out)
        if out.suffix.lower() == ".json":
            target = out
        else:
            _ensure_dir(out)
            target = out / f"{tpl['id']}.quizsrc.json"
        text = json.dumps(tpl, ensure_ascii=False, indent=2) + "\n"
        if args.dry_run:
            print(text)
            return 0
        _ensure_dir(target.parent)
        target.write_text(text, encoding="utf-8")
        print(f"[OK] 题源骨架已写出：{target}")
        print(f"     可用页序（PDF 阅读器页序，共 {len(tpl.get('_pagesAvailable') or [])} 页）："
              f"{(tpl.get('_pagesAvailable') or [])[:20]}")
        print("     下一步：填题 → gen_quiz_bank.py --src <该文件> --out <vault>/题库/")
        return 0

    # ---- 模式 B：题源 → 三种形态 ----
    src_path = Path(args.src)
    if not src_path.exists():
        print(f"[FAIL] 题源不存在：{src_path}")
        return 1
    try:
        src = load_source(src_path)
        if args.bank_id:
            src["id"] = args.bank_id
        if not _s(src.get("id")).strip():
            src["id"] = re.sub(r"[^A-Za-z0-9._-]+", "-", src_path.stem).strip("-") or "quiz-bank"
            print(f"[WARN] 题源没有 id，已从文件名推导：{src['id']}")
        warnings: list = []
        bank = build_bank(src, warnings=warnings)
    except SourceError as e:
        print(f"[FAIL] 题源不合法：{e}")
        return 1

    # 页序交叉校验（manifest 只是提示，不阻断）
    if manifest:
        slides = manifest.get("slides") if isinstance(manifest.get("slides"), list) else []
        known = {s.get("pdfPage") for s in slides if isinstance(s, dict)}
        known.discard(None)
        if known:
            for q in bank["questions"]:
                pages = (q.get("source") or {}).get("pages") or []
                for p in pages:
                    if p not in known:
                        warnings.append(
                            f"{q['id']}：source.pages 里的 {p} 不在 manifest 的 pdfPage 集合中"
                        )

    fence_spec = build_fence_spec(bank, args.lang)
    fence = "```dsh-ui\n" + json.dumps(fence_spec, ensure_ascii=False, indent=2) + "\n```\n"
    md = render_md(bank, args.lang)
    bank_text = json.dumps(bank, ensure_ascii=False, indent=2) + "\n"

    # GenUI 预算：整棵组件树 ≤200 节点（超出会被渲染器裁掉）
    nodes = fence_node_count(fence_spec)
    if nodes > 200:
        warnings.append(
            f"围栏 {nodes} 个节点，超过 GenUI 上限 200——请拆分题库（按单元或题型分卷）"
        )

    # ---- 校验：schema ----
    schema_errors, schema_note = validate_schema(bank, Path(args.schema))
    # ---- 校验：出题规则（不可静默跳过） ----
    findings = rules.check_bank(bank, similarity=args.similarity,
                                r1_image_strict=args.r1_image_strict)
    summary = rules.summarize(findings)

    out = Path(args.out)
    if out.suffix.lower() == ".json":
        bank_path = out
        base = out.with_suffix("")
    else:
        _ensure_dir(out)
        base = out / bank["id"]
        bank_path = out / f"{bank['id']}.json"
    fence_path = Path(str(base) + ".fence.md")
    md_path = Path(str(base) + ".quiz.md")

    if not args.dry_run:
        _ensure_dir(bank_path.parent)
        bank_path.write_text(bank_text, encoding="utf-8")
        fence_path.write_text(fence, encoding="utf-8")
        md_path.write_text(md, encoding="utf-8")

    if args.print_what:
        what = args.print_what
        if what in ("all", "json"):
            print("===== 题库 JSON v1 =====")
            print(bank_text, end="")
        if what in ("all", "fence"):
            print("===== dsh-ui 卷子围栏 =====")
            print(fence, end="")
        if what in ("all", "md"):
            print("===== md 折叠答案 =====")
            print(md, end="")

    if not args.quiet:
        print("=" * 72)
        print(f"生成题库：{bank['id']} v{bank['version']}　题数 {len(bank['questions'])}　语言 {args.lang}")
        if not args.dry_run:
            print(f"  {bank_path}")
            print(f"  {fence_path}")
            print(f"  {md_path}")
        else:
            print("  （--dry-run：未写文件）")
        size = len(bank_text.encode("utf-8"))
        print(f"  题库 JSON 大小 {size} 字节"
              + ("（接近导入器 10 MB 上限！）" if size > 8 * 1024 * 1024 else ""))
        print(f"  围栏节点数 {nodes} / 200"
              + ("（超预算，需分卷）" if nodes > 200 else ""))
        if schema_note:
            print(f"  schema 校验：{schema_note}")
        elif schema_errors:
            print(f"  schema 校验：FAIL {len(schema_errors)}")
            for e in schema_errors[:20]:
                print(f"    - {e}")
        else:
            print("  schema 校验：PASS（schemas/quiz-bank.schema.json）")
        for w in warnings:
            print(f"  [WARN] {w}")
        print(rules.format_report(str(bank_path), bank, findings))
        print("=" * 72)

    failed = bool(schema_errors) or summary["error"] > 0 or summary["skip"] > 0
    if failed and not args.allow_rule_violations:
        print(f"[FAIL] 未通过：schema {len(schema_errors or [])} 项 / "
              f"出题规则 error {summary['error']} 项 / SKIP {summary['skip']} 项")
        return 1
    if failed:
        print(f"[WARN] 未通过但已用 --allow-rule-violations 放行"
              f"（schema {len(schema_errors or [])} / 规则 error {summary['error']} "
              f"/ SKIP {summary['skip']}）")
    # N/A = 该规则本来就不适用（必须打印，但不影响退出码，也不等于 PASS）。
    if summary.get("na"):
        print(f"[注意] 出题规则有 {summary['na']} 条 N/A = 该规则本来就不适用（不是 PASS）；"
              f"要按字面严格检查请加 --r1-image-strict")
    return 0


if __name__ == "__main__":
    sys.exit(main())
