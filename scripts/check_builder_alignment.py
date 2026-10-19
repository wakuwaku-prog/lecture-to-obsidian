#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_builder_alignment.py — 构建器 ↔ L5 校验器的常量对齐自测。

**为什么需要它**：`check_html_assets.py` 与 `build_explainer_html.py` 必须对
assets 口径**逐字对齐**（`IMAGE_EXT`、兜底候选清单、几个镜像的 helper）。
一处有意差异就是一处漂移源：将来有人改了构建器，不会想到校验器那边。

本脚本直接读**两份源码**、用 AST 取出常量再比对，所以能真的抓到漂移，
而不是把「已核对」写死在文档里。

用法
----
python check_builder_alignment.py [--scripts DIR]

默认 `--scripts` 是本脚本所在目录（两个文件都在 `scripts/` 下）。

退出码
------
0 = 常量集完全一致；1 = 有漂移或文件读不到；2 = 用法错误

本脚本**只读**：解析两个源文件，不写任何文件。
"""
import argparse
import ast
import os
import pathlib
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

BUILDER_NAME = "build_explainer_html.py"
CHECKER_NAME = "check_html_assets.py"

# 需要逐字一致的模块级常量
PAIR_CONSTANTS = ("IMAGE_EXT",)
# 兜底候选：构建器可能是内联字面量，不一定是模块常量
FALLBACK_CONST = "FALLBACK_LIST_CANDIDATES"
FALLBACK_INLINE = re.compile(r"for\s+cand\s+in\s+\((.*?)\)\s*:", re.S)
# 被镜像的 helper 函数名（两边都要有）
MIRRORED_HELPERS = ("norm_rel", "parse_assets", "list_image_files")


def constants(path):
    """取出模块级字面量常量（只认 str / tuple / list）。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if not isinstance(tgt, ast.Name):
                continue
            try:
                val = ast.literal_eval(node.value)
            except (ValueError, SyntaxError):
                continue
            if isinstance(val, (str, tuple, list)):
                out[tgt.id] = val
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="check_builder_alignment.py",
        description="比对 build_explainer_html.py 与 check_html_assets.py 的常量集，防漂移")
    ap.add_argument("--scripts", default=None,
                    help="两个脚本所在目录；默认本脚本所在目录")
    args = ap.parse_args(argv)

    scripts = pathlib.Path(args.scripts).resolve() if args.scripts \
        else pathlib.Path(os.path.dirname(os.path.abspath(__file__)))
    builder = scripts / BUILDER_NAME
    checker = scripts / CHECKER_NAME

    print("=" * 72)
    print("alignment self-test:  %s  vs  %s" % (BUILDER_NAME, CHECKER_NAME))
    print("=" * 72)

    for p in (builder, checker):
        if not p.is_file():
            print("ERROR: 找不到 %s" % p)
            return 1

    b_src = builder.read_text(encoding="utf-8")
    c_src = checker.read_text(encoding="utf-8")
    b, c = constants(builder), constants(checker)

    failures = 0

    # ---- 逐字一致的常量 ----
    for name in PAIR_CONSTANTS:
        bv, cv = b.get(name), c.get(name)
        print("\n%s" % name)
        print("  builder: %s" % (bv,))
        print("  checker: %s" % (cv,))
        if bv == cv and bv is not None:
            print("  MATCH: True  (%d 项)" % len(bv))
        else:
            print("  MATCH: **False**")
            failures += 1

    # ---- 兜底候选（构建器可能内联）----
    if FALLBACK_CONST in b:
        bv = b[FALLBACK_CONST]
        where_b = "常量 %s" % FALLBACK_CONST
    else:
        m = FALLBACK_INLINE.search(b_src)
        bv = tuple(re.findall(r'"([^"]+)"', m.group(1))) if m else None
        where_b = "内联 for 循环字面量"
    cv = c.get(FALLBACK_CONST)
    print("\n兜底候选清单")
    print("  builder: %s  (%s)" % (bv, where_b))
    print("  checker: %s  (常量 %s)" % (cv, FALLBACK_CONST))
    if bv == cv and bv is not None:
        print("  MATCH: True  (%d 个候选，顺序一致)" % len(bv))
    else:
        print("  MATCH: **False**")
        failures += 1

    # ---- 被镜像的 helper ----
    print("\n被镜像的 helper（两边都应有）")
    for name in MIRRORED_HELPERS:
        ok_b, ok_c = ("def %s(" % name) in b_src, ("def %s(" % name) in c_src
        ok = ok_b and ok_c
        print("  %-18s builder=%-5s checker=%-5s  %s"
              % (name, ok_b, ok_c, "OK" if ok else "**MISSING**"))
        if not ok:
            failures += 1

    print("\n" + "-" * 72)
    if failures:
        print("RESULT: FAIL（%d 处不一致）—— 构建器改了常量，校验器必须同步" % failures)
    else:
        print("RESULT: PASS（常量集完全一致，无漂移）")
    print("=" * 72)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
