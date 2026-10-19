"""生成 lecture-to-obsidian 的 L08 基准 fixture，并用 manifest.schema.json 校验它。

数据全部来自心理与精神健康知识库的真实记录，不是编的：
- 放映时间表：01 课程资料/P08 …md 第 51–87 行「课堂放映记录」
- 页脚对照表：同文件第 102–138 行「页脚与 PDF 阅读页对照」
- 逐页标题：同文件第 145–465 行「逐页索引」
- 素材元数据：09 参考资料/Source Register.md 的 S84 / S85 / S88 / S89 / S90
"""

import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "L08.manifest.json"
SCHEMA = Path(__file__).resolve().parents[2] / "schemas" / "manifest.schema.json"

IMG_DIR = "09 参考资料/附件/L08 课件 PDF"
SUB_DIR = "09 参考资料/附件/L08 字幕"
S1, S2 = "L08 第15节 1355", "L08 第16节 1450"

# (pdfPage, 标题, 页脚读数, 所属单元, 放映 [(session, "MM:SS", 是否重放, endMmss)])
PAGES = [
    (1, "Memory-guided saccades：延迟眼跳任务", "01", "EYE TRACKING", [(1, "35:07", False, None)]),
    (2, "Why does the task include a delay?（延迟的作用）", "02", "EYE TRACKING", [(1, "37:32", False, None)]),
    (3, "Spatial accuracy：终点与目标的差多少？", "03", "EYE TRACKING", [(1, "39:18", False, None)]),
    (4, "Timing: when did the eyes move?", None, "EYE TRACKING", [(1, "40:54", False, None)]),
    (5, "Common metrics for saccade", None, "EYE TRACKING", [(1, "42:15", False, None)]),
    (6, "Applications of memory-guided saccades", "04", "EYE TRACKING", [(1, "43:35", False, None)]),
    (7, "单元导入：Memory systems and knowledge representation", "02", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(1, "45:46", False, None)]),
    (8, "Taxonomy of long-term memory", "03", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(1, "47:28", False, None)]),
    (9, "Three forms of long-term memory", "03", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(1, "49:13", False, None), (2, "00:01", False, None)]),
    (10, "Procedural memory and implicit learning", "实验心理学 11", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "06:03", False, None)]),
    (11, "Declarative vs. procedural memory", "03", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "08:39", False, None)]),
    (12, "What H.M. taught us about memory", "实验心理学 06", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "10:16", False, None)]),
    (13, "Formation of memory", None, "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "12:51", False, "15:47")]),
    (14, "The evidence for sleep to consolidate memory（两个方框）", None, "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "17:00", False, None)]),
    (15, "The evidence for sleep to consolidate memory（时机与阶段）", None, "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "18:49", False, None)]),
    (16, "Semantic and episodic memory tests", "05", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "22:22", False, None)]),
    (17, "Tulving (1972) 对两类记忆的定义", "06", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "23:58", False, None)]),
    (18, "Long-term memory: capacity and duration", "06", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "26:41", False, None)]),
    (19, "Visual memory retains more than object categories", "07", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "29:25", False, None)]),
    (20, "长时记忆没有已知的时长上限", "07", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "31:35", False, None)]),
    (21, "How our knowledge is represented", "07", "KNOWLEDGE REPRESENTATION（记忆系统导入）", [(2, "33:25", False, None)]),
    (22, "单元导入（含第三个追问）", "02", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "35:12", False, None)]),
    (23, "Knowledge organization and retrieval", "08", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "35:34", False, None)]),
    (24, "Semantic and episodic memory in the brain", "42", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "37:28", False, None)]),
    (25, "Category verification: a simple experimental task", "09", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "38:44", False, None)]),
    (26, "Typicality: some members fit a category better", "10", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "39:17", False, None)]),
    (27, "Typicality effect", "10", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "40:23", False, None)]),
    (28, "金丝雀示例 1", "10", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "40:48", False, None)]),
    (29, "Semantic memory - Example 2：范畴大小效应", "10", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "41:12", False, None), (2, "42:49", True, None)]),
    (30, "狗示例 3", "10", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "41:59", False, None)]),
    (31, "Familiarity effect（熟悉性效应）", "10", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "42:19", False, None), (2, "42:52", True, None)]),
    (32, "Category level and familiarity", "11", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "43:15", False, None)]),
    (33, "Negative judgement effect（否定判断效应）", "10", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "44:03", False, None)]),
    (34, "Rejecting a false statement", "12", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "44:51", False, None)]),
    (35, "Four patterns", "13", "KNOWLEDGE REPRESENTATION（知识表征导入）", [(2, "45:42", False, None)]),
]

PURE_IMAGE = {8, 11, 13, 20, 21, 28, 29, 30, 31, 33}
NO_FOOTER = {4, 5, 13, 14, 15}
CONTENT_TYPE = {13: "video", 11: "activity"}


def mmss_to_sec(s):
    m, sec = s.split(":")
    return int(m) * 60 + int(sec)


def norm_footer(v):
    if v is None:
        return None
    digits = "".join(ch for ch in v if ch.isdigit())
    return digits or None


def build():
    slides = []
    for page, title, footer, unit, projs in PAGES:
        projections = []
        for sess, mmss, replay, end_mmss in projs:
            p = {
                "sessionIndex": sess,
                "startSec": mmss_to_sec(mmss),
                "startMmss": mmss,
                "timecodeSource": "platform-imageSeekTime-sec",
                "rawTimecode": str(mmss_to_sec(mmss)),
                "isReplay": replay,
            }
            if end_mmss:
                p["endSec"] = mmss_to_sec(end_mmss)
            projections.append(p)

        if page in NO_FOOTER:
            status, note = "missing", "无页脚数字" + ("（底部为『数据来源』行）" if page == 5 else "") + "；按设计如此，保留原样"
        elif page == 24:
            status, note = "anomalous", "页脚显示 42，而该页内容属页脚 08–13 序列（前后页为 p23 页脚 08、p25 页脚 09），判断为排版笔误；按 AGENTS.md §5 保留原读数、不静默改名，引用以 PDF 阅读页 p24 为准"
        else:
            status, note = "verified", None

        s = {
            "index": page,
            "file": f"{IMG_DIR}/PDF p{page:02d}.jpg",
            "source": "pdf-render",
            "pdfPage": page,
            "projections": projections,
            "title": title,
            "contentType": CONTENT_TYPE.get(page, "slide"),
            "footerUnit": unit,
            "pageNoScope": "section",
            "pageNoExpected": footer,
            "pageNoFullOcr": footer,
            "pageNoFooterOcr": footer,
            "pageNoNormalized": norm_footer(footer),
            "pageNoStatus": status,
        }
        if note:
            s["pageNoNote"] = note
        if page in PURE_IMAGE:
            s["isPureImagePage"] = True
        if page == 14:
            s["textExtractionIssue"] = "文本顺序错乱：两方框标题与正文交错；核对图像后实际配对为 Declarative↔单词对、Procedural↔运动技能"
        slides.append(s)

    def session(label, sid, leti, begin, part, dur, segs, mishear, used_deck, coverage, rec_count):
        return {
            "label": label,
            "lectureId": "L08",
            "platformSessionId": sid,
            "letiNumber": leti,
            "beginTime": begin,
            "classDate": "2026-10-13",
            "partOfSplit": part,
            "durationSec": dur,
            "usedDeck": used_deck,
            "deckCoverageNote": coverage,
            "media": {
                "videoPath": None,
                "videoSha256": None,
                "recordVariant": None,
                "archived": False,
                "cleanedUpAt": "2026-10-15",
                "note": "原始 MP4 未随仓库提交，需从平台重新获取；16 kHz 单声道 WAV 处理完成后已删除",
            },
            "transcript": {
                "file": f"{SUB_DIR}/{label}.md",
                "model": "large-v3",
                "chunkSec": 600,
                "segmentCount": segs,
                "segments": [],
                "diarized": False,
                "speakerLabelsAreInferred": True,
                "knownMishearings": mishear,
                "qualityNote": "未做说话人分离；已知误听较多，不能作为逐字教师引语",
            },
            "platformArtifacts": [
                {"kind": "ai-summary", "file": f"{SUB_DIR}/{label} 平台AI概要.json"},
                {"kind": "platform-asr", "file": f"{SUB_DIR}/{label} 平台语音转写.json"},
                {
                    "kind": "ppt-track-manifest",
                    "file": f"{SUB_DIR}/{label} 平台课件轨清单.json",
                    "note": "imageSeekTime 单位为秒；showFlag 全为 true，不能用来判断『是否放映』",
                    "recordCount": rec_count,
                },
            ],
        }

    manifest = {
        "schemaVersion": 1,
        "source": {
            "platform": "canvas",
            "course": {
                "id": "unknown",
                "name": "心理与精神健康",
                "code": "HLT3202G",
                "extra": {"note": "Canvas 课程 id 未从现有证据取得；平台侧节次 id 见 sessions"},
            },
            "capturedAt": "2026-10-15T20:09:21+08:00",
            "platformSubtitles": "unusable",
            "sessions": [
                session(
                    S1, "179741", 15, "2026-10-13T13:55:00+08:00", 1, 3308.6, 533,
                    ["declarative→decorative", "2,500 objects→22 models", "saccade→second/circuit", "go cue→GoQ"],
                    "第9次课.pptx", "0:00–35:07 未使用 S84；该段先回顾 UNIT 5 眼动指标，再进入 UNIT 6 实验心理学", 68,
                ),
                session(
                    S2, "180045", 16, "2026-10-13T14:50:00+08:00", 2, 3289.0, 676,
                    [],
                    "第8次课.pdf", "00:01–45:42 覆盖 S84 p9–p35；46:41 与 48:28 还有两页不在 S84 内", 63,
                ),
            ],
        },
        "slides": slides,
        "pdf": {
            "file": "09 参考资料/附件/第8次课.pdf",
            "pageCount": 35,
            "sha256": "992C9069597A96A482AC8227E108340F7348FA06DC935F6A593F340DF21C1FC9",
            "author": "Chen Ji",
            "createdAt": "2026-10-12T21:29:24+08:00",
            "isSelection": True,
            "textExtractionIssues": [
                "p8/p11/p13/p20/p21/p28–p31/p33 为纯图页，文本提取为空，必须以页面图像为准",
                "p14 文本顺序错乱：两方框标题与正文交错",
            ],
            "note": "p13 的紫色区域是未导出的嵌入视频（The Science of Memory — Dr. Yewande Pearse），课堂上从第16节 12:51 播到约 15:47",
        },
        "sourceRegisterEntries": [
            {"id": "S84", "type": "教师课件 PDF Official course deck", "source": "09 参考资料/附件/第8次课.pdf", "date": "2026-10-13", "status": "已归档，可引用", "note": "35 个 PDF 阅读页；元数据作者 Chen Ji，创建于 2026-10-12 21:29（+08:00）；SHA-256 已核对"},
            {"id": "S85", "type": "课件页图 Deck page images", "source": f"{IMG_DIR}/（PDF p01.jpg–p35.jpg，共 35 张）", "date": "2026-10-13", "status": "已归档", "note": "从 S84 按 PDF 阅读页渲染的索引图；派生阅读材料，不是独立来源"},
            {"id": "S88", "type": "课堂录像 / 音轨来源 Class recordings", "source": "交大课堂实录平台 2026-10-13 第15节（courseId 179741）与第16节（courseId 180045）", "date": "2026-10-13", "status": "已提取并转写；原始媒体未归档", "note": "两节时长 3308.6 s / 3289.0 s；前 35 分钟使用教师端 第9次课.pptx（尚未归档）"},
            {"id": "S89", "type": "课堂转写 Machine transcripts", "source": f"{SUB_DIR}/L08 第15节 1355、L08 第16节 1450（各自 .json 与 .srt）", "date": "2026-10-15", "status": "已转写", "note": "faster-whisper large-v3，600 秒分段独立解码；第15节 533 段、第16节 676 段；未做说话人分离"},
            {"id": "S90", "type": "平台 AI 产物 Platform AI data", "source": f"{SUB_DIR}/（两节各一份平台AI概要、平台语音转写、平台课件轨清单，共 6 个）", "date": "2026-10-15", "status": "已登记", "note": "作交叉校验；课件轨 imageSeekTime 单位为秒"},
        ],
        "unarchivedMaterials": [
            {"what": "教师端 第9次课.pptx", "evidence": "S88：本次课的前 35 分钟使用教师端该文件；第15节 0:00–35:07 未使用 S84", "impact": "该段内容（UNIT 5 眼动指标回顾、UNIT 6 实验心理学）无法在 S84 索引中定位"},
            {"what": "S84 之外的两页讨论页", "evidence": "P08：第16节 46:41「Discussion: Would an expert respond differently?」、48:28 其回答页", "impact": "S84 的 35 页是选页而非课件全部；这两页未在本索引内编号"},
        ],
        "warnings": [
            "Canvas 课程 id 未从现有证据取得（平台侧只有节次 id 179741 / 180045），已在 course.id 写 unknown，未编造。",
            "平台课件轨两节共 131 条快照（68 / 63），而 S84 仅 35 页；showFlag 全为 true 不能作为『是否放映』依据，desktop 类画面必须在采集层过滤。",
            "本 fixture 的 slides[] 只覆盖 PDF 渲染的 35 张页图；平台快照轨条目未并入，因为它需要先做去重与 desktop 过滤。",
            "p10 与 p12 的页脚带版式标注（『实验心理学 11』『实验心理学 06』），说明这两页来自另一份课件版式，未做归一化以外的人工判断。",
            "转写已知误听较多，不能作为逐字教师引语；正式笔记只在标注『依据机器转写』处引用。",
        ],
    }
    return manifest


def main():
    m = build()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(m, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote:", OUT, OUT.stat().st_size, "bytes")
    print("slides:", len(m["slides"]), "| sessions:", len(m["source"]["sessions"]))
    from collections import Counter

    print("pageNoStatus:", dict(Counter(s["pageNoStatus"] for s in m["slides"])))
    print("contentType:", dict(Counter(s["contentType"] for s in m["slides"])))
    print("projections 总数:", sum(len(s["projections"]) for s in m["slides"]))
    multi = [s["pdfPage"] for s in m["slides"] if len(s["projections"]) > 1]
    print("多次放映的页:", multi)

    try:
        import jsonschema
    except ImportError:
        print("jsonschema 不可用，跳过校验")
        return 0
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    v = jsonschema.Draft7Validator(schema)
    errs = sorted(v.iter_errors(m), key=lambda e: list(e.path))
    if errs:
        print(f"\n!! fixture 未通过 schema 校验，{len(errs)} 个错误：")
        for e in errs[:20]:
            print("  -", "/".join(str(p) for p in e.path), "->", e.message[:200])
        return 1
    print("\nfixture 通过 manifest.schema.json 校验")
    return 0


if __name__ == "__main__":
    sys.exit(main())
