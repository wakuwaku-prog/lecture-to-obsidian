#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_all.py — L5 质量门总入口。

串起本 skill 的四个校验器 + **复用** better-awesome-sjtu-canvas-ppt 的两个校验器，
打印一张汇总表；任一红即退出 1。

复用的两个校验器（读它们的真实 CLI，用 subprocess 调用，不复制代码）：

  better-awesome-sjtu-canvas-ppt/scripts/check_vault_links.py <vault_root>
      无 argparse：位置参数就是库根；**永远 exit 0**，
      结果只能从 stdout 解析（"UNRESOLVED (N):" / "OK: ..."）。

  better-awesome-sjtu-canvas-ppt/scripts/check_note_structure.py <vault_or_dir>
      [--min-recall N] [--quiet]；也**永远 exit 0**，
      结果从末行 "检查 N 篇笔记，M 个问题" 解析。

用法
----
python check_all.py --vault "<vault root>" [--work DIR]
                    [--profile FILE] [--manifest FILE] [--html FILE ...]
                    [--assets DIR]
                    [--canvas-ppt-skill DIR] [--min-recall N]
                    [--skip canvas-ppt,links,structure,profile,manifest,html]
                    [--quiet] [--json]

退出码
------
0 = 全绿（无 ERROR）；1 = 任一红；2 = 用法错误

本脚本**只读**：不写、不改、不创建任何文件。子进程也是只读校验器。
"""
import argparse
import glob
import json
import os
import re
import subprocess
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_CANVAS_PPT = os.path.expanduser(
    "~/.dsh/skills/better-awesome-sjtu-canvas-ppt")
# 笔记层（画像 / manifest / gen_notes / 笔记校验器）已迁到 better skill；
# 本 skill 只留讲解 + 考题 + 总门。下面的路径由 main() 依据 --notes-skill 赋值。
NOTES_SKILL = DEFAULT_CANVAS_PPT

STATUS_OK = "OK"
STATUS_WARN = "WARN"
STATUS_FAIL = "FAIL"
STATUS_SKIP = "SKIP"

# 只看 RESULT 行本身（用 splitlines 定位，避免被 headline 行干扰）。
# headline「检查项 N 条；ERROR x，WARN y，INFO z」出现在 RESULT 之前，
# 直接全文搜 ERROR 会搜到 headline —— 所以必须先定位 RESULT 行。
RESULT_LINE = re.compile(r"^RESULT:\s*(PASS|FAIL|INCOMPLETE)")
HEADLINE = re.compile(r"ERROR\s*(\d+)[，,]\s*WARN\s*(\d+)")
RESULT_ERRS = re.compile(r"(\d+)\s*个\s*ERROR")
LINKS_UNRESOLVED = re.compile(r"UNRESOLVED\s*\((\d+)\)")
LINKS_OK = re.compile(r"OK:\s*every wikilink")
LINKS_CHECKED = re.compile(r"checked\s*(\d+)\s*links")
STRUCT_TOTAL = re.compile(r"检查\s*(\d+)\s*篇笔记，\s*(\d+)\s*个问题")
STRUCT_NONE = re.compile(r"没有找到\s*L##")
STRUCT_TOTAL_LINE = re.compile(r"^检查\s*(\d+)\s*篇笔记，\s*(\d+)\s*个问题")
# 复用校验器把 frontmatter 字段名硬编码成 `type`；别的库用 `note_type` 时
# 会全库误报。这类发现由画像复核后降级为 INFO（见 check_note_structure）。
FM_MISSING = re.compile(r"frontmatter\s*缺字段\s*[:：]\s*(.+)$")
UNKNOWN = "UNKNOWN"

# 复用校验器 check_note_structure.py 的**结构类**发现 → 画像里的对应阈值键。
# 降级只在「画像驱动的检查对该笔记判为通过」时发生 —— 即复用的启发式与
# 本库约定不符。若画像检查也判失败，发现照旧保留（绝不把真红灯降级）。
# (复用校验器的措辞, 内部 rule key, 画像 demoteReusedFindings 里的类别)
# 类别取值与 schema 的枚举严格一致：summary / recall / to-verify / frontmatter
STRUCT_RULE_MAP = [
    ("缺少中文总结小节", "summarySection", "summary"),
    ("主动回忆题只有", "recallQuestions", "recall"),
    ("缺少「待核实」清单", "toVerifyList", "to-verify"),
    ("「待核实」清单为空", "uncheckedItem", "to-verify"),
]
NOTE_HEADER = re.compile(r"^(?:FAIL|OK|SKIP)\s+(\S.*?\.md)\s")

# 未解析链接行的形态：  <笔记相对路径>  ->  <原始链接>
UNRESOLVED_LINE = re.compile(r"^\s*(\S.*?)\s+->\s+(.+?)\s*$")
# 路径里未替换的占位符 —— 真实断链的特征
PLACEHOLDER = re.compile(r"#page=[A-Za-z]|[#|][A-Za-z]\b|…|\.\.\.|\{|\}")
# 文档里的写法示例（不是真链接）
DOC_EXAMPLE = re.compile(r"附件路径|宽度|路径/to/|<[^>]+>")


def assert_vault_root(vault):
    """调用任何复用校验器之前先断言库根存在且是目录。

    `check_vault_links.py` 对不存在的路径会打印 `checked 0` + `OK: every
    wikilink…` —— 路径写错就等于「全过」，这是最危险的一类假绿灯。
    """
    if not os.path.exists(vault):
        return "库根不存在：%s" % vault
    if not os.path.isdir(vault):
        return "库根不是目录：%s" % vault
    return None


class Row(object):
    def __init__(self, name, status, counts, detail, command):
        self.name = name
        self.status = status
        self.counts = counts
        self.detail = detail
        self.command = command

    def as_dict(self):
        return {"name": self.name, "status": self.status,
                "counts": self.counts, "detail": self.detail,
                "command": self.command}


def run_proc(cmd):
    """跑一个只读校验器，返回 (returncode, stdout, stderr)。"""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=900,
        )
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError as exc:
        return 127, "", "找不到命令：%s" % exc
    except subprocess.TimeoutExpired:
        return 124, "", "超时（900 秒）"


def parse_own_report(stdout, stderr, rc):
    """解析本 skill 四个校验器的输出（它们有明确的 RESULT 行）。

    RESULT 行两种形态：
      RESULT: PASS（无 ERROR）
      RESULT: FAIL（3 个 ERROR）
    先用 splitlines 定位 RESULT 行，再从 headline 取 ERROR/WARN 计数。
    """
    text = stdout or ""
    result_line = None
    for line in text.splitlines():
        if RESULT_LINE.match(line.strip()):
            result_line = line.strip()
            break
    if result_line is None:
        if rc == 127:
            return STATUS_FAIL, {"errors": 1, "warns": 0, "reason": "命令缺失"}
        return STATUS_FAIL, {"errors": 1, "warns": 0,
                             "reason": "无法解析输出（rc=%d）" % rc}

    passed = result_line.startswith("RESULT: PASS")
    incomplete = result_line.startswith("RESULT: INCOMPLETE")
    errs = warns = 0
    hm = HEADLINE.search(text)
    if hm:
        errs, warns = int(hm.group(1)), int(hm.group(2))
    else:
        rm = RESULT_ERRS.search(result_line)
        errs = int(rm.group(1)) if rm else 0
    if incomplete:
        # 无 ERROR 但有检查项没执行（如 assets 口径 SKIP）→ WARN，绝不当 PASS
        return STATUS_WARN, {"errors": errs, "warns": warns,
                             "incomplete": "yes"}
    status = STATUS_OK if passed else STATUS_FAIL
    if status == STATUS_OK and warns:
        status = STATUS_WARN
    return status, {"errors": errs, "warns": warns}


def classify_unresolved(out, vault):
    """把 check_vault_links.py 的未解析行分成「真断链」与「已知局限」。

    复用校验器的三类已知局限（见 references/05-quality-gates.md §4）：
      ① 目录型 wikilink —— 目标目录真实存在，但它只建文件索引
      ② 文档写法示例 —— AGENTS.md 里的 `![[附件路径|宽度]]`
      ③ 路径里未替换的占位符（如 `#page=N`）—— 这条是**真断链**

    返回 (真断链列表, 已知局限列表)，每项是 (笔记相对路径, 原始链接, 原因)。
    """
    real, known = [], []
    for line in (out or "").splitlines():
        if "->" not in line or line.strip().startswith(("UNRESOLVED", "checked")):
            continue
        m = UNRESOLVED_LINE.match(line)
        if not m:
            continue
        note, link = m.group(1), m.group(2)

        # ② 文档写法示例
        if DOC_EXAMPLE.search(link):
            known.append((note, link, "文档写法示例（非真链接）"))
            continue

        # ③ 占位符未替换 → 真断链
        if PLACEHOLDER.search(link):
            real.append((note, link, "路径含未替换占位符"))
            continue

        # ① 目录型 wikilink：目标目录真实存在
        target = link.lstrip("!").strip("[]")
        target = target.split("|")[0].split("#")[0].strip()
        cand = os.path.join(vault, target.replace("/", os.sep))
        if target and os.path.isdir(cand):
            known.append((note, link, "目录型 wikilink（目标目录存在）"))
            continue

        real.append((note, link, "目标既非文件也非目录"))
    return real, known


def parse_vault_links(stdout, stderr, rc):
    """check_vault_links.py **永远 exit 0**，只能解析 stdout。

    假绿灯防线：
    * 扫描对象数 = 0 → FAIL（路径写错 = 全过，绝不能当通过）
    * 找不到预期统计行 → FAIL（脚本改版/输出格式变了，UNKNOWN 也要红）
    """
    text = stdout or ""
    if rc == 127:
        return STATUS_FAIL, {"errors": 1, "reason": "命令缺失"}
    checked = LINKS_CHECKED.search(text)
    if not checked:
        return STATUS_FAIL, {"errors": 1, "scanned": UNKNOWN,
                             "reason": "找不到统计行「checked N links/embeds」"
                                       "——输出格式可能已变，按 UNKNOWN 处理"}
    n_checked = int(checked.group(1))
    m = LINKS_UNRESOLVED.search(text)
    if m:
        return STATUS_FAIL, {"errors": int(m.group(1)), "warns": 0,
                             "scanned": n_checked}
    if LINKS_OK.search(text):
        if n_checked == 0:
            return STATUS_FAIL, {"errors": 1, "scanned": 0,
                                 "reason": "扫描到 0 个链接 —— 路径写错就等于全过，"
                                           "按 FAIL 处理"}
        return STATUS_OK, {"errors": 0, "warns": 0, "scanned": n_checked}
    return STATUS_FAIL, {"errors": 1, "scanned": n_checked,
                         "reason": "既没有 UNRESOLVED 也没有 OK 行"
                                   "——输出格式可能已变，按 UNKNOWN 处理"}


def parse_note_structure(stdout, stderr, rc):
    """check_note_structure.py **也永远 exit 0**，解析末行汇总。

    同样：找不到统计行或扫到 0 篇 → FAIL，不静默通过。
    """
    text = stdout or ""
    if rc == 127:
        return STATUS_FAIL, {"errors": 1, "reason": "命令缺失"}
    m = STRUCT_TOTAL.search(text)
    if not m:
        return STATUS_FAIL, {"errors": 1, "notes": UNKNOWN,
                             "reason": "找不到统计行「检查 N 篇笔记，M 个问题」"
                                       "——输出格式可能已变，按 UNKNOWN 处理"}
    n_notes, n_problems = int(m.group(1)), int(m.group(2))
    if n_notes == 0:
        return STATUS_FAIL, {"errors": 1, "notes": 0,
                             "reason": "扫描到 0 篇笔记 —— 路径写错就等于全过，"
                                       "按 FAIL 处理"}
    status = STATUS_OK if n_problems == 0 else STATUS_FAIL
    return status, {"errors": n_problems, "warns": 0, "notes": n_notes}


# ---------------------------------------------------------------- 各检查

def check_manifest(vault, work, manifest_path, rep_rows, quiet):
    path = manifest_path
    if not path and work:
        cand = os.path.join(work, "manifest.json")
        if os.path.isfile(cand):
            path = cand
    if not path:
        rep_rows.append(Row("manifest", STATUS_SKIP, {},
                            "没给 --work 也找不到 manifest.json（采集层还没跑）", ""))
        return
    if not os.path.isfile(path):
        rep_rows.append(Row("manifest", STATUS_FAIL, {"errors": 1},
                            "指定的 manifest 不存在：%s" % path, ""))
        return
    schema = os.path.join(NOTES_SKILL, "schemas", "manifest.schema.json")
    cmd = [sys.executable, os.path.join(NOTES_SKILL, "scripts", "check_manifest.py"), path]
    if os.path.isfile(schema):
        cmd += ["--schema", schema]
    rc, out, err = run_proc(cmd)
    status, counts = parse_own_report(out, err, rc)
    detail = _first_error(out) or "manifest 自洽"
    rep_rows.append(Row("manifest", status, counts, detail, " ".join(cmd)))
    if not quiet:
        print(out)


def check_html(vault, html_paths, assets_dir, rep_rows, quiet, declared_list=None):
    if not html_paths:
        rep_rows.append(Row("html-assets", STATUS_SKIP, {},
                            "没给 --html（本次没有讲解 HTML 产物）", ""))
        return
    cmd = [sys.executable, os.path.join(HERE, "check_html_assets.py")] + list(html_paths)
    if assets_dir:
        cmd += ["--assets-dir", assets_dir]
    if declared_list:
        cmd += ["--declared-list", declared_list]
    rc, out, err = run_proc(cmd)
    # SKIP ≠ PASS：校验器自己会报 RESULT: INCOMPLETE（口径走到 SKIP 且确有引用），
    # parse_own_report 已把它降为 WARN 并标 incomplete —— 不要再用文本猜一遍，
    # 否则「无 assets 引用的单文件形态」会被误判。
    status, counts = parse_own_report(out, err, rc)
    detail = _first_error(out) or ("%d 份 HTML" % len(html_paths))
    rep_rows.append(Row("html-assets", status, counts, detail, " ".join(cmd)))
    if not quiet:
        print(out)


def check_profile(vault, profile_path, rep_rows, quiet):
    path = profile_path
    if not path:
        for cand in (os.path.join(vault, "_scripts", "vault-profile.json"),
                     os.path.join(vault, "vault-profile.json")):
            if os.path.isfile(cand):
                path = cand
                break
    if not path:
        rep_rows.append(Row("vault-profile", STATUS_WARN, {"warns": 1},
                            "画像还没生成（build_vault_profile.py 未跑）", ""))
        return
    cmd = [sys.executable, os.path.join(NOTES_SKILL, "scripts", "check_vault_profile.py"),
           path, "--vault", vault]
    rc, out, err = run_proc(cmd)
    status, counts = parse_own_report(out, err, rc)
    if status == STATUS_FAIL:
        # 画像缺失目录是否致命，取决于是否已人工复核——这里保持 FAIL，让 lead 判断
        pass
    detail = _first_error(out) or "画像路径全部存在"
    rep_rows.append(Row("vault-profile", status, counts, detail, " ".join(cmd)))
    if not quiet:
        print(out)


def check_vault_links(vault, skill_dir, rep_rows, quiet):
    script = os.path.join(skill_dir, "scripts", "check_vault_links.py")
    if not os.path.isfile(script):
        rep_rows.append(Row("vault-links", STATUS_SKIP, {},
                            "复用的 check_vault_links.py 不存在：%s" % script, ""))
        return
    bad = assert_vault_root(vault)
    if bad:
        rep_rows.append(Row("vault-links", STATUS_FAIL, {"errors": 1, "scanned": 0},
                            "未调用复用校验器：%s" % bad, ""))
        return
    cmd = [sys.executable, script, vault]
    rc, out, err = run_proc(cmd)
    status, counts = parse_vault_links(out, err, rc)

    # 把未解析行分成「真断链」与「已知局限」，避免读者以为库里有 N 处坏链接
    real, known = ([], [])
    if status == STATUS_FAIL and LINKS_UNRESOLVED.search(out or ""):
        real, known = classify_unresolved(out, vault)
        counts = dict(counts)
        counts["realBroken"] = len(real)
        counts["knownLimitation"] = len(known)
        if not real and known:
            # 全部是复用校验器的已知局限 → 不当作库的问题
            status = STATUS_WARN

    if status == STATUS_FAIL:
        detail = counts.get("reason") or (
            "真断链 %d 条" % counts.get("realBroken", counts.get("errors", 0)))
    elif status == STATUS_WARN and known:
        detail = ("%d 处未解析全部是复用校验器已知局限（真断链 0）" % len(known))
    else:
        detail = "扫描 %s 个链接/嵌入" % counts.get("scanned", UNKNOWN)

    rep_rows.append(Row("vault-links", status, counts, detail, " ".join(cmd)))

    if not quiet:
        print(out)
        if real or known:
            print("  [INFO] links.classified — 上面 %d 处未解析的区分："
                  % (len(real) + len(known)))
            for note, link, why in real:
                print("         真断链    %s -> %s   （%s）" % (note, link, why))
            for note, link, why in known:
                print("         已知局限  %s -> %s   （%s）" % (note, link, why))
            if real:
                print("         → %d 条真断链需要处理；%d 条为复用校验器已知局限，"
                      "不是库的问题" % (len(real), len(known)))
            else:
                print("         → 真断链 0 条；全部为复用校验器已知局限，"
                      "不是库的问题")


def own_frontmatter_verdicts(profile_path, vault):
    """跑一遍画像驱动的检查，取回每篇笔记的结构/字段判定。

    返回 {note_basename: {"missingFields": set, "failedRules": set}}。
    取不到（无画像/脚本缺失）时返回 None —— 此时**不做任何降级**。
    """
    if not profile_path or not os.path.isfile(profile_path):
        return None
    script = os.path.join(NOTES_SKILL, "scripts", "check_note_frontmatter.py")
    if not os.path.isfile(script):
        return None
    cmd = [sys.executable, script, "--profile", profile_path,
           "--vault", vault, "--json"]
    rc, out, err = run_proc(cmd)
    try:
        data = json.loads(out)
    except (ValueError, TypeError):
        return None

    # 复用校验器硬编码的字段名 —— 用来判断「它报的字段名本库根本不用」
    reused_fields = set()
    for cand in ("type", "course_code", "status", "tags", "source"):
        reused_fields.add(cand)
    # 画像自己要求的字段名：从 profile 读
    own_required = set()
    demote_whitelist = None
    try:
        with open(profile_path, encoding="utf-8") as fh:
            prof = json.load(fh)
        own_required = set((prof.get("frontmatter") or {}).get("required") or [])
        demote_whitelist = (prof.get("structure") or {}).get("demoteReusedFindings")
    except (OSError, ValueError):
        pass

    # 白名单：只有画像列出的类才允许降级（保守 —— 宁可多报，不可漏报）。
    # 画像没写该键时按「全允许」以兼容旧画像；写了就严格按它执行。
    if not isinstance(demote_whitelist, list):
        demote_whitelist = ["summary", "recall", "to-verify", "frontmatter"]

    verdicts = {}
    for f in data.get("findings", []):
        if f.get("level") != "ERROR":
            continue
        rule = f.get("rule", "")
        msg = f.get("message", "")
        # 用**结构化字段** note，不解析 message 文本：
        # message 里的文件名会被截断，靠文本匹配会误归属（实测踩过）。
        rel = f.get("note")
        if not rel:
            continue
        base = os.path.basename(rel)
        rec = verdicts.setdefault(base, {"missingFields": set(),
                                         "failedRules": set()})
        if rule == "frontmatter.required":
            fm = re.search(r"缺必填字段\s*(.+?)（", msg)
            if fm:
                for k in fm.group(1).split(","):
                    rec["missingFields"].add(k.strip())
        elif rule == "structure.summarySection":
            rec["failedRules"].add("summarySection")
        elif rule == "structure.recallQuestions":
            rec["failedRules"].add("recallQuestions")
        elif rule == "structure.toVerifyList":
            rec["failedRules"].add("toVerifyList")
        elif rule == "structure.uncheckedToVerify":
            rec["failedRules"].add("uncheckedItem")

    return {"verdicts": verdicts, "ownRequired": own_required,
            "reusedFields": reused_fields,
            "demoteWhitelist": demote_whitelist}


def reclassify_frontmatter(out, info):
    """把复用校验器「硬编码判据」的发现降级为 INFO，但**只降它判错的那部分**。

    两类可降级：
      ① frontmatter 缺字段 —— 字段名硬编码 `type`；画像声明了别的字段名
         （如 `note_type`）时，该字段名不在画像必填清单里 → 复用的判据不适用
      ② 结构类发现（总结小节/回忆题/待核实清单）—— 阈值硬编码；
         当**画像驱动检查对该笔记判为通过**时，说明复用启发式与本库约定不符

    任何一条若画像检查同样判失败，则**保留原样**（绝不隐藏真红灯）。
    """
    info = info or {}
    verdicts = info.get("verdicts") or {}
    own_required = info.get("ownRequired") or set()
    whitelist = info.get("demoteWhitelist")
    if not isinstance(whitelist, list):
        whitelist = ["summary", "recall", "to-verify", "frontmatter"]
    allowed = set(whitelist)

    lines = (out or "").splitlines()
    demoted, kept = [], []
    current = None
    n_removed = 0

    for line in lines:
        s = line.strip()
        hm = NOTE_HEADER.match(s)
        if hm:
            current = os.path.basename(hm.group(1))
        if s.startswith("-") and current is not None:
            v = verdicts.get(current, {})
            missing = v.get("missingFields") or set()
            failed = v.get("failedRules") or set()

            # ① frontmatter 缺字段：画像根本没要求这个字段名 → 复用判据不适用
            fm = FM_MISSING.search(s)
            if fm:
                fields = [x.strip() for x in fm.group(1).split(",") if x.strip()]
                if "frontmatter" in allowed and fields \
                        and not (set(fields) & own_required) \
                        and not (set(fields) & missing):
                    n_removed += 1
                    demoted.append((current, s.lstrip("- ").strip(),
                                    "frontmatter 字段名", "frontmatter"))
                    continue
                kept.append(line)
                continue

            # ② 结构类发现：画像检查判为通过 → 复用启发式不适用
            hit, cat = None, None
            for needle, rule_key, _cfg in STRUCT_RULE_MAP:
                if needle in s:
                    hit, cat = rule_key, _cfg
                    break
            if hit:
                # 白名单：画像没列出的类一律不降级
                if cat in allowed and hit not in failed:
                    n_removed += 1
                    demoted.append((current, s.lstrip("- ").strip(),
                                    "结构判据", cat))
                    continue
                kept.append(line)
                continue
        kept.append(line)

    # 修正末行汇总的问题数（否则输出与汇总自相矛盾）
    total = None
    for i, line in enumerate(kept):
        m = STRUCT_TOTAL_LINE.match(line.strip())
        if m:
            total = (i, int(m.group(1)), int(m.group(2)))
    if total and n_removed:
        i, n_notes, n_problems = total
        kept[i] = ("检查 %d 篇笔记，%d 个问题（另有 %d 项硬编码判据的发现已按画像复核，"
                   "见下）" % (n_notes, max(0, n_problems - n_removed), n_removed))
    return "\n".join(kept), demoted


def check_note_structure(vault, skill_dir, min_recall, rep_rows, quiet,
                         profile_path=None):
    script = os.path.join(skill_dir, "scripts", "check_note_structure.py")
    if not os.path.isfile(script):
        rep_rows.append(Row("note-structure", STATUS_SKIP, {},
                            "复用的 check_note_structure.py 不存在：%s" % script, ""))
        return
    bad = assert_vault_root(vault)
    if bad:
        rep_rows.append(Row("note-structure", STATUS_FAIL, {"errors": 1, "notes": 0},
                            "未调用复用校验器：%s" % bad, ""))
        return
    cmd = [sys.executable, script, vault, "--min-recall", str(min_recall), "--quiet"]
    rc, out, err = run_proc(cmd)
    status, counts = parse_note_structure(out, err, rc)

    # 画像复核：复用校验器的 frontmatter 字段名与**结构判据**都是硬编码的，
    # 按画像逐条复核后，把它判错的那部分降级为 INFO（真红灯保留）。
    display = out
    demoted = []
    if status == STATUS_FAIL:
        info = own_frontmatter_verdicts(profile_path, vault)
        display, demoted = reclassify_frontmatter(out, info)
        if demoted:
            counts = dict(counts)
            counts["errors"] = max(0, counts.get("errors", 0) - len(demoted))
            counts["demoted"] = len(demoted)
            if counts["errors"] == 0:
                status = STATUS_WARN

    detail = ("%d 篇笔记 / %d 个问题" % (counts.get("notes", 0), counts.get("errors", 0))
              if isinstance(counts.get("notes"), int) else counts.get("reason", ""))
    if demoted:
        detail += "；另有 %d 项硬编码判据的发现已按画像复核" % len(demoted)
    rep_rows.append(Row("note-structure", status, counts, detail, " ".join(cmd)))

    if not quiet:
        print(display)
        if demoted:
            # 用第 4 个元素（类别）判断，**不要**用 why 字符串去猜语义
            # （字符串推断是踩过的坑：assets.skipped 那次）
            fm_n = sum(1 for *_, cat in demoted if cat == "frontmatter")
            st_n = len(demoted) - fm_n
            print("  [INFO] structure.reclassified — 复用校验器"
                  "**结构要求硬编码**（总结小节别名、回忆题数、待核实清单），"
                  "字段名也硬编码为 `type`；以下 %d 项已按画像复核后降级为 INFO"
                  "（不当作 ERROR）：" % len(demoted))
            for note, finding, why, cat in demoted:
                print("         - [%s] %s — %s" % (why, finding, note))
            if fm_n:
                print("         · frontmatter 字段名 %d 项：本库用画像 "
                      "`frontmatter.required` 声明的字段名" % fm_n)
            if st_n:
                print("         · 结构判据 %d 项：画像 `structure` 段对该类型"
                      "不要求（或阈值不同）" % st_n)
            print("  [INFO] structure.verified — 画像驱动的检查见 "
                  "note-frontmatter 一行；真问题仍在上面的 FAIL 清单里。")


def check_frontmatter(vault, profile_path, rep_rows, quiet):
    """画像驱动的 frontmatter 必填字段检查（本 skill 自己的，不是复用的）。"""
    if not profile_path or not os.path.isfile(profile_path):
        rep_rows.append(Row("note-frontmatter", STATUS_SKIP, {},
                            "没有画像文件，跳过画像驱动的必填字段检查", ""))
        return
    script = os.path.join(NOTES_SKILL, "scripts", "check_note_frontmatter.py")
    if not os.path.isfile(script):
        rep_rows.append(Row("note-frontmatter", STATUS_SKIP, {},
                            "check_note_frontmatter.py 不存在：%s" % script, ""))
        return
    cmd = [sys.executable, script, "--profile", profile_path, "--vault", vault]
    rc, out, err = run_proc(cmd)
    status, counts = parse_own_report(out, err, rc)
    detail = _first_error(out) or "画像驱动的必填字段全部存在"
    rep_rows.append(Row("note-frontmatter", status, counts, detail, " ".join(cmd)))
    if not quiet:
        print(out)


SECTION = re.compile(r"^---\s+(ERROR|WARN|INFO)\s+\((\d+)\)\s*---\s*$", re.M)


def _first_error(text):
    """取最有代表性的一条 finding：ERROR 段优先，其次 WARN，再退到 INFO。

    本 skill 的四个校验器都按 ERROR → WARN → INFO 分段输出，
    所以先定位段落标题，再取该段第一条「[rule] ...」行。
    """
    text = text or ""
    sections = list(SECTION.finditer(text))
    for want in ("ERROR", "WARN", "INFO"):
        for i, m in enumerate(sections):
            if m.group(1) != want:
                continue
            end = sections[i + 1].start() if i + 1 < len(sections) else len(text)
            for line in text[m.end():end].splitlines():
                s = line.strip()
                if s.startswith("[") and "]" in s:
                    return s[:110]
    return None


# ---------------------------------------------------------------- 汇总表

def render_table(rows):
    width = max([len(r.name) for r in rows] + [10])
    lines = ["", "=" * 78, "L5 质量门汇总 SUMMARY", "=" * 78]
    lines.append("%-*s  %-6s  %-22s  %s" % (width, "CHECK", "STATUS",
                                            "COUNTS", "DETAIL"))
    lines.append("-" * 78)
    for r in rows:
        counts = " ".join("%s=%s" % (k, v) for k, v in sorted(r.counts.items())
                          if k not in ("reason",))
        lines.append("%-*s  %-6s  %-22s  %s"
                     % (width, r.name, r.status, counts, r.detail[:60]))
    lines.append("-" * 78)
    n_fail = sum(1 for r in rows if r.status == STATUS_FAIL)
    n_warn = sum(1 for r in rows if r.status == STATUS_WARN)
    n_ok = sum(1 for r in rows if r.status == STATUS_OK)
    n_skip = sum(1 for r in rows if r.status == STATUS_SKIP)
    lines.append("OK %d | WARN %d | FAIL %d | SKIP %d" % (n_ok, n_warn, n_fail, n_skip))
    lines.append("")
    if n_fail:
        lines.append("RESULT: FAIL — 任一红即未交付（%d 项红）" % n_fail)
    else:
        lines.append("RESULT: PASS — 全绿%s" % (
            "（%d 项 WARN，需人工判断）" % n_warn if n_warn else ""))
    lines.append("=" * 78)
    return "\n".join(lines)


# ---------------------------------------------------------------- 主流程

def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="check_all.py",
        description="L5 质量门总入口：四个校验器 + 复用 canvas-ppt 的两个校验器")
    ap.add_argument("--vault", required=True, help="目标知识库根目录")
    ap.add_argument("--work", default=None, help="工作目录（找 manifest.json）")
    ap.add_argument("--profile", default=None, help="vault-profile.json 路径")
    ap.add_argument("--manifest", default=None, help="manifest.json 路径")
    ap.add_argument("--html", nargs="*", default=None,
                    help="讲解 HTML（可多个；默认扫 <vault>/10 讲解 HTML/*.html）")
    ap.add_argument("--assets", "--assets-dir", dest="assets_dir", default=None,
                    help="HTML 的 assets/ 目录（目录口径）；"
                         "与 build_explainer_html.py 的 --assets-dir 同名同义")
    ap.add_argument("--declared-list", "--assets-list", dest="declared_list",
                    default=None,
                    help="assets 声明清单文件；与构建器 --assets-list 同义")
    ap.add_argument("--canvas-ppt-skill", default=DEFAULT_CANVAS_PPT,
                    help="better-awesome-sjtu-canvas-ppt 的 skill 目录（提供采集 adapter、画像、manifest、gen_notes 与笔记校验器）")
    ap.add_argument("--min-recall", type=int, default=3,
                    help="传给 check_note_structure.py 的 --min-recall")
    ap.add_argument("--skip", default="",
                    help="逗号分隔：canvas-ppt,links,structure,frontmatter,"
                         "profile,manifest,html")
    ap.add_argument("--quiet", action="store_true", help="只打印汇总表")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    global NOTES_SKILL
    NOTES_SKILL = args.canvas_ppt_skill

    skip = set(s.strip() for s in args.skip.split(",") if s.strip())
    vault = args.vault
    rows = []

    # 库根断言：任何检查之前。路径写错 = 假绿灯，必须 FAIL。
    bad = assert_vault_root(vault)
    if bad:
        print("ERROR: %s" % bad)
        print("       路径写错时复用校验器会报 checked 0 + OK —— 按 FAIL 处理，"
              "不静默通过。")
        return 1

    profile_path = args.profile
    if not profile_path:
        for cand in (os.path.join(vault, "_scripts", "vault-profile.json"),
                     os.path.join(vault, "vault-profile.json")):
            if os.path.isfile(cand):
                profile_path = cand
                break

    html_paths = args.html
    if html_paths is None:
        guess = os.path.join(vault, "10 讲解 HTML")
        if os.path.isdir(guess):
            html_paths = sorted(glob.glob(os.path.join(guess, "*.html")))
        else:
            html_paths = []

    if "manifest" not in skip:
        check_manifest(vault, args.work, args.manifest, rows, args.quiet)
    if "html" not in skip:
        check_html(vault, html_paths, args.assets_dir, rows, args.quiet,
                   declared_list=args.declared_list)
    if "profile" not in skip:
        check_profile(vault, args.profile, rows, args.quiet)
    if "frontmatter" not in skip and "canvas-ppt" not in skip:
        check_frontmatter(vault, profile_path, rows, args.quiet)
    if "links" not in skip and "canvas-ppt" not in skip:
        check_vault_links(vault, args.canvas_ppt_skill, rows, args.quiet)
    if "structure" not in skip and "canvas-ppt" not in skip:
        check_note_structure(vault, args.canvas_ppt_skill, args.min_recall,
                             rows, args.quiet, profile_path=profile_path)

    if args.json:
        print(json.dumps({
            "vault": vault,
            "ok": not any(r.status == STATUS_FAIL for r in rows),
            "rows": [r.as_dict() for r in rows],
        }, ensure_ascii=False, indent=2))
    else:
        print(render_table(rows))

    return 0 if not any(r.status == STATUS_FAIL for r in rows) else 1


if __name__ == "__main__":
    sys.exit(main())
