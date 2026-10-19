"""审计：文档里提到的每个脚本 / 模板 / schema 路径是否真实存在。

动机（这条是有来历的）：`better-awesome-sjtu-canvas-ppt` 的 README 指向了本机
不存在的 `docs/OBSIDIAN-NOTES.md` 与 `templates/`。**文档承诺了没交付的东西**，
接手者会以为某道防护已生效——比没有防护更危险。

用法：
    python check_doc_paths.py [--skill-root DIR] [--quiet]

退出码：0 = 无缺失；1 = 有引用了但不存在的路径。

判据（两条，缺一不可）：
  ① 文档里出现形如 `scripts/x.py` / `templates/y.md` 的引用 → 该文件必须存在。
  ② 允许在**否定语境**里提到不存在的路径（例如「本机不存在的 docs/OBSIDIAN-NOTES.md」），
     这类提到不算承诺。判定方式是同一行内出现否定标记词。

已知边界（不要把本脚本当成万能）：
  - 正则匹配的是**路径形态的引用**；纯文字提到的文件名（不带目录）不在此列。
  - 反向检查（交付物里哪些文件没被文档提到）只作提示，不判失败——例如 SKILL.md
    自身、以及只在代码里 import 的共用模块。
"""

import argparse
import re
import sys
from pathlib import Path
from pathlib import PurePath

TRACKED_DIRS = ("scripts", "templates", "schemas", "references", "adapters", "docs", "pilot")

# 允许出现在路径前的前缀（会先被剥掉）
PREFIX_RE = re.compile(r"(?:\$SKILL/|\$HOME/\.dsh/skills/lecture-to-obsidian/|<skill>/|\.\./|\./)")

# 否定语境标记：同行出现这些词，说明该处是在说「这个路径不存在 / 没交付」，不算承诺
NEGATIVE_MARKERS = (
    "不存在",
    "未交付",
    "缺失",
    "未创建",
    "尚未生成",
    "未落地",
    "没交付",
    "缺 `docs/`",
    # 以下是本工具**自己的已知误报**在文档里被讨论的情形：
    # `<vault>/_scripts/vault-profile.json` 会被抽成 `scripts/vault-profile.json`，
    # 那是目标库里的路径，不是本 skill 的文件。
    "占位路径",
    "不是本 skill 的文件",
    "目标库里的路径",
    "会被抽成",
)

# 故意用作反面例子的**精确文件名**。必须精确匹配，不能用子串——
# 我第一版用 `missing_` 之类子串，结果把真缺失的 `really_missing_file.py` 也豁免了，
# 校验器退化成橡皮图章。**过宽的允许名单比没有名单更危险。**
DELIBERATE_BASENAMES = {
    "does_not_exist.py",
    "nonexistent.py",
    "not_exist.py",
    "xxx.py",
    "placeholder.py",
}

PATH_RE = re.compile(
    r"(?<![\w.-])((?:" + "|".join(TRACKED_DIRS) + r")/[A-Za-z0-9_./\u4e00-\u9fff-]+)"
)

TAIL_CHARS = ".,;:、。）)】」"


def docs_of(root: Path):
    """所有「承诺了路径」的文档。新增文档时必须加进来，否则审计会漏。"""
    out = [root / "SKILL.md", root / "README.md"]
    refs = root / "references"
    if refs.is_dir():
        out += sorted(refs.glob("*.md"))
    plan = root / "docs" / "PLAN.md"
    if plan.exists():
        out.append(plan)
    return [p for p in out if p.exists()]


def mentions(text: str):
    """产出 (路径, 是否否定语境) 对。

    否定语境 = 该处不是「承诺这个路径存在」，而是：
      - 在说明某个路径不存在 / 未交付；
      - 在讨论本工具自己的误报（如 `_scripts/…` 被抽成 `scripts/…`）；
      - 文件名精确等于 DELIBERATE_BASENAMES 里的反面例子。
    """
    for line in text.splitlines():
        neg = any(mark in line for mark in NEGATIVE_MARKERS)
        for m in PATH_RE.finditer(line):
            raw = PREFIX_RE.sub("", m.group(1)).rstrip(TAIL_CHARS)
            is_example = PurePath(raw).name in DELIBERATE_BASENAMES
            yield raw, neg or is_example


def main() -> int:
    ap = argparse.ArgumentParser(description="审计文档里引用的路径是否真实存在")
    ap.add_argument("--skill-root", default=str(Path(__file__).resolve().parents[1]))
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    root = Path(args.skill_root).resolve()
    if not root.is_dir():
        print(f"ERROR: skill 根目录不存在: {root}", file=sys.stderr)
        return 1

    docs = docs_of(root)
    checked = skipped_negative = 0
    missing = []

    for doc in docs:
        text = doc.read_text(encoding="utf-8")
        for raw, neg in mentions(text):
            if neg:
                skipped_negative += 1
                continue
            checked += 1
            if not (root / raw).exists():
                missing.append((doc.relative_to(root).as_posix(), raw))

    print("=" * 72)
    print(f"check_doc_paths.py — {root}")
    print("=" * 72)
    print(f"扫描文档 {len(docs)} 份；实质引用 {checked} 处；否定语境跳过 {skipped_negative} 处")

    if missing:
        uniq = sorted(set(missing))
        print(f"\n!! 引用了但不存在的路径 {len(uniq)} 处：")
        for doc, raw in uniq:
            print(f"  {doc}  ->  {raw}")
        print("\nRESULT: FAIL — 文档承诺了不存在的路径")
        return 1

    print("\nOK：文档提到的每个路径都真实存在")

    # 反向提示（不判失败）
    all_files = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        if p.is_file() and "__pycache__" not in p.parts
    }
    mentioned = set()
    for doc in docs:
        for raw, neg in mentions(doc.read_text(encoding="utf-8")):
            if not neg:
                mentioned.add(raw)
    orphan = sorted(all_files - mentioned)
    if orphan and not args.quiet:
        print(f"\n提示（不判失败）：{len(orphan)} 个交付物未被文档按路径提到：")
        for f in orphan:
            print("  -", f)

    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
