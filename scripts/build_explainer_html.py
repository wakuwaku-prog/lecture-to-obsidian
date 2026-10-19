#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""构建单文件讲解 HTML（lecture-to-obsidian / L3 讲解层）。

md 是唯一真源；本脚本只把「源片段」编译成**单文件、离线可看**的 HTML：
图片按画像的长边上限等比缩小后 base64 内嵌，CSS/JS 全部来自 templates/explainer.html。

用法
----
  python build_explainer_html.py --src <src.html> --out <out.html> [--vault <知识库根>]
      [--profile <vault-profile.json>] [--template <explainer.html>]
      [--mode single-file-html|chapter-html]
      [--max-edge 1600] [--quality 82] [--width 720]
      [--assets-dir <assets 目录>] [--assets-list <清单.txt>]
      [--force] [--no-check] [--dry-run]

源片段格式（与 心理库 _scripts/讲解HTML/SPEC 一致，向后兼容 embed.py）
--------------------------------------------------------------------
  <!--TITLE: L06 — 全课讲解 眼动追踪-->
  <!--SUBTITLE: Eye Tracking: Active Sampling, Measurement and Inference-->
  <!--META: 讲解来源：… · 页图来源：… · 内嵌 14 张-->
  <!--MODE: chapter-html-->          ← 可选，覆盖画像
  <!--CHIPS: 约 3 节课内容|{{NIMG}} 张页图|{{NQ}} 道题-->   ← 可选，仅章级
  <!--ASSETS: 09 参考资料/附件/…/PDF p01.jpg|09 参考资料/附件/…/PDF p02.jpg-->  ← 可选，自检③
  随后是正文 HTML；图片写成 {{IMG:相对知识库根的路径|caption|w=720}}（w= 可省）。

占位符（脚本只做占位替换，不改 CSS/JS）
--------------------------------------
  {{TITLE}} {{SUBTITLE}} {{META}} {{CHIPS}} {{CONTENT}} {{BUILT}}
  源片段里还可用 {{NIMG}} / {{NQ}} / {{NQUIZ}}，会被换成**真实**张数/题数（防止徽章数字漂移）。

自检（默认执行，任一 FAIL → 退出码 3，不写出文件）
-------------------------------------------------
  ① 占位符残留：`{{IMG:` = 0 且 `{{大写}}` = 0
  ② `data:image/` 出现次数 = 声明图数 = 成功内嵌张数
  ③ 正文引用的 assets 与 assets 清单/目录双向差集为空。口径**显式打印、不无声降级**：
     --assets-dir > --assets-list > 自动探测（--out 旁有 assets/ 就用目录口径）
     > <!--ASSETS:--> / assets.txt / 图片清单.txt > 未声明（SKIP）
     目录口径与 L5 的 check_html_assets.py 一致，能同时抓「引用了但不存在」与「存在但没被引用」。
  ④ 窄屏：每个 <img> 都是 max-width:min(Npx,100%)，写死 px 宽度 = 0
  ⑤ 体积 ≤ 画像 maxBytes
  ⑥ 测验：data-answer/data-a 指向真实选项；同一题组 radio name 不重复

退出码：0 成功；2 缺图；3 自检失败；4 参数/画像不允许；5 环境缺依赖
"""
from __future__ import annotations

import argparse
import base64
import datetime
import io
import json
import os
import re
import sys

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

MARKER = re.compile(r"\{\{IMG:([^|}]+)\|([^}|]*)(?:\|([^}]*))?\}\}")
META_RE = re.compile(r"<!--\s*(TITLE|SUBTITLE|META|MODE|CHIPS|ASSETS)\s*:\s*(.*?)\s*-->", re.S)
PLACEHOLDER_RE = re.compile(r"\{\{[A-Z_]+\}\}")
TOKENS = ("{{TITLE}}", "{{SUBTITLE}}", "{{META}}", "{{CHIPS}}", "{{CONTENT}}", "{{BUILT}}")

Q_OPEN_RE = re.compile(r'<div class="q"([^>]*)>')
ATTR_RE = re.compile(r'data-([a-z]+)="([^"]*)"')
RADIO_RE = re.compile(r'<input[^>]*type="radio"[^>]*>')
VALUE_RE = re.compile(r'value="([^"]*)"')
NAME_RE = re.compile(r'name="([^"]*)"')

DEFAULTS = {
    "max_edge": 1600,
    "quality": 82,
    "width": 720,
    "max_bytes": 4 * 1024 * 1024,
    "mode": "single-file-html",
}

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff", ".svg")


class MissingDep(Exception):
    """缺少运行依赖（Pillow）；由调用方转成退出码 5。"""


# --------------------------------------------------------------------------- #
# 工具
# --------------------------------------------------------------------------- #
def norm_rel(p: str) -> str:
    """把路径统一成 `a/b/c.jpg` 形式，便于做差集比较。"""
    return os.path.normpath(p.strip().replace("\\", "/")).replace(os.sep, "/")


def parse_assets(raw: str) -> list:
    """ASSETS 声明：`|` 或换行分隔，允许 `#` 注释行。"""
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


def width_from_attr(attr) -> int:
    """从画像的 imageWidthAttr（如 max-width:min(720px,100%)）里取 N。"""
    if not attr:
        return DEFAULTS["width"]
    m = re.search(r"min\(\s*(\d+)\s*px", str(attr))
    return int(m.group(1)) if m else DEFAULTS["width"]


def encode_image(path: str, max_edge: int, quality: int):
    """长边缩到 max_edge 后编码。返回 (mime, bytes, (orig_w, orig_h))。"""
    if path.lower().endswith(".svg"):
        with open(path, "rb") as fh:
            return "image/svg+xml", fh.read(), (0, 0)
    if Image is None:
        raise MissingDep("需要 Pillow 才能缩放位图：请用带 Pillow 的 Python 运行（本机 python 自带）")
    with Image.open(path) as im:
        im.load()
        w, h = im.size
        scale = min(1.0, float(max_edge) / max(w, h)) if max(w, h) > max_edge else 1.0
        if scale < 1.0:
            im = im.resize((max(1, int(round(w * scale))), max(1, int(round(h * scale)))), Image.LANCZOS)
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)
        buf = io.BytesIO()
        if has_alpha:
            im.convert("RGBA").save(buf, format="PNG", optimize=True)
            mime = "image/png"
        else:
            im.convert("RGB").save(buf, format="JPEG", quality=quality, optimize=True, progressive=True)
            mime = "image/jpeg"
    return mime, buf.getvalue(), (w, h)


def load_profile(path: str) -> dict:
    try:
        with io.open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as exc:  # noqa: BLE001
        sys.stderr.write("画像读取失败：%s（%s）\n" % (path, exc))
        return {}
    return data if isinstance(data, dict) else {}


def list_image_files(base_dir: str) -> list:
    """递归列出 assets 目录里的图片，返回相对 base_dir 的 `a/b.jpg` 形式（排序、去隐藏）。"""
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


def ref_key_for_dir(rel: str, abs_path: str, base_dir: str) -> str:
    """把一次 {{IMG:}} 引用换算到 assets 目录口径；不在目录内则显式标出。"""
    try:
        rp = os.path.relpath(abs_path, base_dir)
    except ValueError:
        rp = None
    if rp is None or rp.startswith(".."):
        return "%s（不在 assets/ 内）" % norm_rel(rel)
    return norm_rel(rp)


# --------------------------------------------------------------------------- #
# 自检
# --------------------------------------------------------------------------- #
def scan_quiz(content: str) -> dict:
    """粗粒度解析 .q 块：够用就好，不做 HTML 解析器。"""
    opens = list(Q_OPEN_RE.finditer(content))
    blocks, problems, warns = [], [], []
    for i, m in enumerate(opens):
        end = opens[i + 1].start() if i + 1 < len(opens) else len(content)
        blocks.append((m.group(1), content[m.start():end]))
    for idx, (attrs_raw, block) in enumerate(blocks, 1):
        attrs = dict(ATTR_RE.findall(attrs_raw))
        radios = RADIO_RE.findall(block)
        values = [v for r in radios for v in VALUE_RE.findall(r)]
        opt_count = len(re.findall(r'class="opt"', block))
        if not radios and not opt_count:
            warns.append("第 %d 题既没有 radio 也没有 .opt 选项" % idx)
        if "answer" in attrs:
            if not values:
                problems.append("第 %d 题有 data-answer 但没有 radio 选项" % idx)
            elif attrs["answer"] not in values:
                problems.append("第 %d 题 data-answer=%s 不在选项 value %s 中"
                                % (idx, attrs["answer"], values))
        if "a" in attrs:
            try:
                a = int(attrs["a"])
            except ValueError:
                problems.append("第 %d 题 data-a=%r 不是整数" % (idx, attrs["a"]))
            else:
                if a < 0 or a >= opt_count:
                    problems.append("第 %d 题 data-a=%d 超出 .opt 数量 %d" % (idx, a, opt_count))
                if opt_count and opt_count != 4:
                    warns.append("第 %d 题有 %d 个选项（出题规范要求 4 个）" % (idx, opt_count))
        if "expl" not in block and "sol" not in block:
            warns.append("第 %d 题没有解析（.expl / .sol）" % idx)
    # radio name 只能在**同一个题组内部**重复（同一题的 4 个选项）；跨题组重复会串判分
    name_blocks = {}
    for idx, (_attrs, block) in enumerate(blocks, 1):
        for n in {n for r in RADIO_RE.findall(block) for n in NAME_RE.findall(r)}:
            name_blocks.setdefault(n, []).append(idx)
    dup = sorted(n for n, idxs in name_blocks.items() if len(idxs) > 1)
    if dup:
        problems.append("radio name 跨题组重复（会串判分）：%s"
                        % ", ".join("%s（第 %s 题）" % (n, "/".join(map(str, name_blocks[n]))) for n in dup))
    return {
        "questions": len(blocks),
        "quizzes": len(re.findall(r'class="quiz"', content)),
        "problems": problems,
        "warns": warns,
    }


def check_output(html: str, content: str, embedded_n: int, declared_n: int,
                 assets_scope: dict, max_bytes: int, mode: str) -> dict:
    """返回 {rows:[(level, text)], failed:bool, counts:{...}}"""
    rows, failed = [], False

    # ① 占位符残留
    img_left = html.count("{{IMG:")
    tok_left = [t for t in PLACEHOLDER_RE.findall(html) if t in TOKENS]
    ok1 = (img_left == 0 and not tok_left)
    rows.append(("PASS" if ok1 else "FAIL",
                 "① 占位符残留：`{{IMG:` %d 处 · 未替换模板占位 %d 个%s"
                 % (img_left, len(tok_left), ("（%s）" % ", ".join(sorted(set(tok_left)))) if tok_left else "")))
    failed |= not ok1

    # ② 内嵌图数
    data_uri = html.count('src="data:image/')
    grep_lines = sum(1 for line in html.splitlines() if "data:image/" in line)
    ok2 = (data_uri == embedded_n == declared_n)
    rows.append(("PASS" if ok2 else "FAIL",
                 "② 内嵌图：src=\"data:image/\" %d = 实际内嵌 %d = 声明图数 %d"
                 "（grep -c \"data:image/\" 得 %d 行%s）"
                 % (data_uri, embedded_n, declared_n, grep_lines,
                    "；差值来自正文里字面写出的 data:image/，建议改写" if grep_lines != data_uri else "")))
    failed |= not ok2

    # ③ assets 双向差集（口径显式打印，禁止无声降级）
    kind = assets_scope.get("kind", "none")
    refs = assets_scope.get("refs", [])
    declared = assets_scope.get("declared", [])
    label = assets_scope.get("label", "未声明")
    ref_set = {norm_rel(r) for r in refs}
    dec_set = {norm_rel(d) for d in declared}
    if kind == "none":
        rows.append(("SKIP",
                     "③ assets 双向差集（口径：**未声明 → SKIP**）：引用 %d 个，正向已确认存在于磁盘；"
                     "要启用反向差集请给 --assets-dir（章级 assets/ 目录）或 <!--ASSETS:-->（单文件声明清单）"
                     % len(ref_set)))
    else:
        only_ref = sorted(ref_set - dec_set)
        only_dec = sorted(dec_set - ref_set)
        ok3 = not only_ref and not only_dec
        side = "目录" if kind == "dir" else "声明"
        where = "（%s）" % assets_scope["path"] if assets_scope.get("path") else ""
        rows.append(("PASS" if ok3 else "FAIL",
                     "③ assets 双向差集（口径：%s%s）：引用 %d / %s %d / 仅引用 %d / 仅%s %d%s%s"
                     % (label, where, len(ref_set), side, len(dec_set),
                        len(only_ref), side, len(only_dec),
                        ("　仅引用=" + ", ".join(only_ref[:8])) if only_ref else "",
                        ("　仅%s=" % side + ", ".join(only_dec[:8])) if only_dec else "")))
        failed |= not ok3

    # ④ 窄屏宽度（踩过的坑：写死 px 会顶破卡片）
    #    只看**行内 style**：模板 CSS 里的 max-width:1280px 是布局，不算问题。
    imgs = re.findall(r"<img\b[^>]*>", html)
    inline_styles = re.findall(r'style="([^"]*)"', html)
    bad_fixed = [s for s in inline_styles
                 if re.search(r"max-width:\s*\d+px", s) and "min(" not in s]
    bad_fixed += [s for s in inline_styles if re.search(r"(?<!max-)\bwidth:\s*\d+px", s)
                  and "max-width" not in s]
    bad_fixed += [t for t in imgs if re.search(r'\swidth="\d+"', t)]
    no_min = [t for t in imgs if "data:image/" in t and 'max-width:min(' not in t]
    ok4 = (not bad_fixed and not no_min)
    rows.append(("PASS" if ok4 else "FAIL",
                 "④ 窄屏宽度：内嵌图 %d 张全部带 max-width:min(Npx,100%%) · 写死 px %d 处 · 缺 min() %d 张"
                 % (len([t for t in imgs if "data:image/" in t]), len(bad_fixed), len(no_min))))
    failed |= not ok4

    # ⑤ 体积
    size = len(html.encode("utf-8"))
    ok5 = size <= max_bytes
    rows.append(("PASS" if ok5 else "FAIL",
                 "⑤ 体积：%.2f MB %s 上限 %.2f MB"
                 % (size / 1048576.0, "≤" if ok5 else ">", max_bytes / 1048576.0)))
    failed |= not ok5

    # ⑥ 测验
    q = scan_quiz(content)
    ok6 = not q["problems"]
    rows.append(("PASS" if ok6 else "FAIL",
                 "⑥ 测验：%d 组 / %d 题 · 答案下标越界或 name 重复 %d 条%s"
                 % (q["quizzes"], q["questions"], len(q["problems"]),
                    ("　" + "；".join(q["problems"])) if q["problems"] else "")))
    failed |= not ok6
    for w in q["warns"]:
        rows.append(("WARN", "　· " + w))

    # 章级结构（提醒，不判失败）
    if mode == "chapter-html":
        missing = []
        if 'id="paperScore"' not in html:
            missing.append("#paperScore")
        if "data-resetpaper" not in html:
            missing.append("data-resetpaper")
        if 'class="chip"' not in html:
            missing.append(".hero .chips > span.chip")
        if missing:
            rows.append(("WARN", "章级结构缺：%s（章级范式要求 hero 徽章 + 章末综合卷）" % "、".join(missing)))

    return {"rows": rows, "failed": failed, "size": size, "quiz": q}


# --------------------------------------------------------------------------- #
# 主流程
# --------------------------------------------------------------------------- #
def main(argv=None) -> int:
    try:  # 控制台可能是 GBK；统一 UTF-8 输出，避免中文乱码
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass

    ap = argparse.ArgumentParser(description="把讲解源片段编译成单文件 HTML（图片 base64 内嵌）")
    ap.add_argument("--src", required=True, help="源片段 html（含 {{IMG:…}} 标记）")
    ap.add_argument("--out", help="输出 html；省略时用画像 explainer.outDir + TITLE")
    ap.add_argument("--vault", help="知识库根（相对图片路径的基准）；默认画像所在库，其次 --src 所在目录")
    ap.add_argument("--profile", help="vault-profile.json；默认 <vault>/_scripts/vault-profile.json")
    ap.add_argument("--template", help="模板路径；默认 <skill>/templates/explainer.html")
    ap.add_argument("--mode", choices=["single-file-html", "chapter-html"], help="覆盖画像 mode")
    ap.add_argument("--max-edge", type=int, help="内嵌前等比缩小长边（默认取画像 imageMaxEdgePx）")
    ap.add_argument("--quality", type=int, default=DEFAULTS["quality"], help="JPEG 质量（默认 82）")
    ap.add_argument("--width", type=int, help="默认图宽 N（max-width:min(Npx,100%%)）")
    ap.add_argument("--assets-list", help="assets 清单文件（每行一个路径）；声明清单口径")
    ap.add_argument("--assets-dir", help="assets 目录；目录口径（与 L5 check_html_assets.py 一致）。"
                                        "不给时：--out 所在目录有 assets/ 就自动用目录口径，"
                                        "否则退回声明清单口径")
    ap.add_argument("--force", action="store_true", help="画像 mode 为 none/markdown-only 时仍构建")
    ap.add_argument("--no-check", action="store_true", help="跳过自检（不推荐；默认执行）")
    ap.add_argument("--dry-run", action="store_true", help="只统计，不写文件")
    args = ap.parse_args(argv)

    src_path = os.path.abspath(args.src)
    if not os.path.isfile(src_path):
        sys.stderr.write("源片段不存在：%s\n" % src_path)
        return 4
    src_dir = os.path.dirname(src_path)

    # ---- 画像 ----
    vault = os.path.abspath(args.vault) if args.vault else None
    profile_path = args.profile
    if not profile_path:
        for cand_root in ([vault] if vault else []) + [src_dir]:
            cand = os.path.join(cand_root, "_scripts", "vault-profile.json")
            if os.path.isfile(cand):
                profile_path = cand
                break
    profile = load_profile(profile_path) if profile_path else {}
    if profile and not vault:
        vault = os.path.dirname(os.path.dirname(os.path.abspath(profile_path)))
    if not vault:
        vault = src_dir
    exp = profile.get("explainer") or {}
    media = profile.get("media") or {}

    # ---- 参数合并：CLI > 源片段 > 画像 > 默认 ----
    src_text = io.open(src_path, encoding="utf-8").read()
    meta = {"TITLE": "", "SUBTITLE": "", "META": "", "MODE": "", "CHIPS": "", "ASSETS": ""}
    for m in META_RE.finditer(src_text):
        key = m.group(1).upper()
        meta[key] = re.sub(r"[ \t]+", " ", m.group(2)).strip()
    content = META_RE.sub("", src_text)

    # 画像优先做「能不能派生 HTML」的总闸：画像说 none / markdown-only 就停，
    # 不允许源片段的 <!--MODE:--> 把它顶掉（铁律 2：以目标库为准）。
    prof_mode = exp.get("mode")
    if prof_mode in ("none", "markdown-only") and not args.force:
        sys.stderr.write("画像 explainer.mode=%r：该库不派生 HTML（markdown-only / none）。"
                         "确需构建请加 --force。\n" % prof_mode)
        return 4
    mode = args.mode or meta["MODE"] or prof_mode or DEFAULTS["mode"]
    if mode not in ("single-file-html", "chapter-html"):
        if not args.force:
            sys.stderr.write("无法确定的 explainer.mode=%r；请用 --mode 指定。\n" % mode)
            return 4
        mode = DEFAULTS["mode"]
    if meta["CHIPS"] and mode != "chapter-html":
        sys.stderr.write("提示：源片段有 <!--CHIPS:-->，但模式是 %s（徽章只在章级出现）。\n" % mode)

    max_edge = args.max_edge or exp.get("imageMaxEdgePx") or DEFAULTS["max_edge"]
    width = args.width or width_from_attr(exp.get("imageWidthAttr")) or DEFAULTS["width"]
    max_bytes = exp.get("maxBytes") or DEFAULTS["max_bytes"]
    out_dir = exp.get("outDir")

    # ---- 输出路径（提前解析：assets 口径要探测 --out 旁边的 assets/）----
    out = args.out
    if not out:
        if out_dir:
            out = os.path.join(vault, out_dir, "%s.html" % (meta["TITLE"] or "讲解"))
        else:
            sys.stderr.write("未给 --out，且画像没有 explainer.outDir\n")
            return 4
    out = os.path.abspath(out)

    template_path = args.template or os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "templates", "explainer.html")
    if not os.path.isfile(template_path):
        sys.stderr.write("模板不存在：%s\n" % template_path)
        return 5

    # ---- 图片 ----
    refs, ref_abs, missing, embedded, total_orig, total_new = [], [], [], [], 0, 0

    def repl(m: "re.Match") -> str:
        nonlocal total_orig, total_new
        rel = m.group(1).strip()
        cap = (m.group(2) or "").strip()
        extra = (m.group(3) or "").strip()
        path = rel if os.path.isabs(rel) else os.path.normpath(
            os.path.join(vault, rel.replace("/", os.sep)))
        refs.append(rel)
        ref_abs.append(path)
        if not os.path.isfile(path):
            missing.append(rel)
            return '<figure class="fig"><figcaption>⚠️ 缺图：%s</figcaption></figure>' % rel
        try:
            mime, data, size = encode_image(path, max_edge, args.quality)
        except MissingDep as exc:
            sys.stderr.write("%s\n" % exc)
            raise SystemExit(5)
        total_orig += os.path.getsize(path)
        total_new += len(data)
        embedded.append((rel, os.path.getsize(path), len(data), size))
        n = width
        if extra.startswith("w="):
            try:
                n = max(120, min(2000, int(extra[2:])))
            except ValueError:
                n = width
        # 硬约束：必须是 min(Npx,100%)，写死 px 会在窄屏顶破卡片
        style = ' style="max-width:min(%dpx,100%%)"' % n
        cap_html = ('<figcaption>%s</figcaption>' % cap) if cap else ""
        return ('<figure class="fig"><img alt="%s" src="data:%s;base64,%s"%s>%s</figure>'
                % (re.sub(r"[<>\"]", "", cap or rel), mime,
                   base64.b64encode(data).decode("ascii"), style, cap_html))

    content = MARKER.sub(repl, content)

    if missing:
        sys.stderr.write("缺图（未找到文件，按提示修路径重跑）：\n  " + "\n  ".join(missing) + "\n")
        return 2

    # 模板不渲染数学：把残留的 LaTeX 包成 <code>（内容原样保留）
    content = re.sub(r"\$\$([^$]{1,300})\$\$",
                     lambda m: "<p><code>%s</code></p>" % m.group(1).strip(), content)
    content = re.sub(r"(?<!\$)\$([^$\n]{1,120})\$(?!\$)",
                     lambda m: "<code>%s</code>" % m.group(1).strip(), content)

    # ---- assets 口径（两条路径都显式可见，禁止无声降级）----
    # 优先级：--assets-dir > --assets-list > 自动探测（--out 旁边有 assets/ 就用目录口径）
    #         > <!--ASSETS:--> / assets.txt / 图片清单.txt > 未声明（SKIP）
    # 目录口径与 L5 check_html_assets.py 一致，且更强：能同时抓「引用了但不存在」与「存在但没被引用」。
    assets_scope = {"kind": "none", "path": None, "refs": [], "declared": [], "label": "未声明"}
    if args.assets_dir:
        d = os.path.abspath(args.assets_dir)
        if not os.path.isdir(d):
            sys.stderr.write("assets 目录不存在：%s\n" % d)
            return 4
        assets_scope = {"kind": "dir", "path": d, "label": "assets/ 目录（--assets-dir）"}
    elif args.assets_list:
        if not os.path.isfile(args.assets_list):
            sys.stderr.write("assets 清单不存在：%s\n" % args.assets_list)
            return 4
        assets_scope = {"kind": "list", "path": os.path.abspath(args.assets_list),
                        "label": "源片段声明清单（--assets-list）"}
    else:
        auto_dir = os.path.join(os.path.dirname(out), "assets")
        if os.path.isdir(auto_dir):
            assets_scope = {"kind": "dir", "path": auto_dir,
                            "label": "assets/ 目录（自动探测 --out 旁 assets/）"}
        elif meta["ASSETS"]:
            assets_scope = {"kind": "list", "path": None, "label": "源片段声明清单（<!--ASSETS:-->）"}
        else:
            for cand in ("assets.txt", "图片清单.txt"):
                p = os.path.join(src_dir, cand)
                if os.path.isfile(p):
                    assets_scope = {"kind": "list", "path": p,
                                    "label": "源片段声明清单（%s）" % cand}
                    break

    if assets_scope["kind"] == "dir":
        d = assets_scope["path"]
        assets_scope["declared"] = list_image_files(d)
        assets_scope["refs"] = [ref_key_for_dir(rel, ab, d) for rel, ab in zip(refs, ref_abs)]
    elif assets_scope["kind"] == "list":
        raw = (io.open(assets_scope["path"], encoding="utf-8").read()
               if assets_scope["path"] else meta["ASSETS"])
        assets_scope["declared"] = parse_assets(raw)
        assets_scope["refs"] = [norm_rel(r) for r in refs]
    else:
        # 未声明口径也要把引用数报出来，SKIP 行不能显示成「引用 0 个」
        assets_scope["refs"] = [norm_rel(r) for r in refs]

    # ---- 占位替换 ----
    qinfo = scan_quiz(content)
    chips = meta["CHIPS"]
    if chips:
        chips = (chips.replace("{{NIMG}}", str(len(embedded)))
                      .replace("{{NQ}}", str(qinfo["questions"]))
                      .replace("{{NQUIZ}}", str(qinfo["quizzes"])))
        chips = '<div class="chips">%s</div>' % "".join(
            '<span class="chip">%s</span>' % c.strip()
            for c in re.split(r"[|\n]", chips) if c.strip())

    with io.open(template_path, encoding="utf-8") as fh:
        html = fh.read()
    # 模板自检：CONTENT/CHIPS 必须**恰好各出现一次**，否则正文会被注入多次
    # （踩过的坑：把占位符字面量写进模板注释，注释里的那份也被替换 → 正文出现两遍）
    for tok in ("{{CONTENT}}", "{{CHIPS}}"):
        n = html.count(tok)
        if n != 1:
            sys.stderr.write("模板异常：%s 在 %s 中出现 %d 次（必须恰好 1 次）\n"
                             % (tok, template_path, n))
            return 5
    values = {
        "{{TITLE}}": meta["TITLE"] or os.path.splitext(os.path.basename(src_path))[0],
        "{{SUBTITLE}}": meta["SUBTITLE"],
        "{{META}}": meta["META"],
        "{{CHIPS}}": chips,
        "{{CONTENT}}": content,
        "{{BUILT}}": datetime.date.today().isoformat(),
    }
    for tok, val in values.items():
        html = html.replace(tok, val)

    declared_n = len(assets_scope["declared"]) if assets_scope["kind"] == "list" else len(refs)

    # ---- 自检 ----
    report = None
    if not args.no_check:
        report = check_output(html, content, len(embedded), declared_n,
                              assets_scope, max_bytes, mode)
        if report["failed"]:
            sys.stderr.write("自检未通过，未写出文件：\n")
            for lvl, text in report["rows"]:
                sys.stderr.write("  [%s] %s\n" % (lvl, text))
            return 3

    size_mb = len(html.encode("utf-8")) / 1048576.0
    if args.dry_run:
        print("dry-run：模式 %s，%d 张图，原图 %.2f MB → 内嵌 %.2f MB，预计 HTML %.2f MB"
              % (mode, len(embedded), total_orig / 1048576.0, total_new / 1048576.0, size_mb))
        print("  assets 口径：%s%s" % (assets_scope["label"],
                                      ("（%s）" % assets_scope["path"]) if assets_scope.get("path") else ""))
        if report:
            for lvl, text in report["rows"]:
                print("  [%s] %s" % (lvl, text))
        return 0

    os.makedirs(os.path.dirname(out), exist_ok=True)
    with io.open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(html)

    print("已生成：%s" % out)
    print("  模式 %s · 模板 %s" % (mode, template_path))
    print("  内嵌图片 %d 张，原图合计 %.2f MB → 内嵌 %.2f MB（长边 ≤%dpx，quality %d，默认图宽 %dpx）"
          % (len(embedded), total_orig / 1048576.0, total_new / 1048576.0,
             max_edge, args.quality, width))
    print("  文件体积 %.2f MB" % size_mb)
    print("  assets 口径：%s%s" % (assets_scope["label"],
                                  ("（%s）" % assets_scope["path"]) if assets_scope.get("path") else ""))
    for rel, o, n, size in embedded:
        dim = "%dx%d" % size if size[0] else "矢量"
        print("    - %s  %s  %d KB → %d KB" % (rel, dim, o // 1024, n // 1024))
    if report:
        print("  自检：")
        for lvl, text in report["rows"]:
            print("    [%s] %s" % (lvl, text))
    else:
        print("  自检：已用 --no-check 跳过（交付前必须补跑）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
