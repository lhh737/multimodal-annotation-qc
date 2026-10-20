# -*- coding: utf-8 -*-
"""生成简洁版评测文档 PPT：多模态数据标注与质检。

数据来自：
  reports/metrics.json
  reports/model_comparison.csv
  reports/gold_text.csv

输出：
  reports/多模态数据标注与质检_评测文档.pptx
"""
import json
from pathlib import Path

import pandas as pd
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, PP_ALIGN
from pptx.util import Inches, Pt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/多模态数据标注与质检_评测文档.pptx"

# ---- design tokens (dataviz reference palette, validated for 3 slots) ----
INK = RGBColor(0x0B, 0x0B, 0x0B)
SECONDARY = RGBColor(0x52, 0x51, 0x4E)
MUTED = RGBColor(0x89, 0x87, 0x81)
SURFACE = RGBColor(0xFC, 0xFC, 0xFB)
CARD = RGBColor(0xF0, 0xEF, 0xEC)
ALT = RGBColor(0xF7, 0xF7, 0xF5)
GRID = RGBColor(0xE1, 0xE0, 0xD9)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BLUE = RGBColor(0x2A, 0x78, 0xD6)
ORANGE = RGBColor(0xEB, 0x68, 0x34)
AQUA = RGBColor(0x1B, 0xAF, 0x7A)
DARK = RGBColor(0x0B, 0x0B, 0x0B)

FONT = "Microsoft YaHei"
W, H = 13.333, 7.5


def add_text(slide, x, y, w, h, text, size=14, bold=False, color=INK,
             align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, spacing=1.08):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_right = tf.margin_top = tf.margin_bottom = 0
    tf.vertical_anchor = anchor
    p = tf.paragraphs[0]
    p.alignment = align
    p.line_spacing = spacing
    r = p.add_run()
    r.text = text
    f = r.font
    f.name = FONT
    f.size = Pt(size)
    f.bold = bold
    f.color.rgb = color
    return tb


def add_rect(slide, x, y, w, h, fill, line=None, rounded=False):
    shape_type = MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE
    shp = slide.shapes.add_shape(shape_type, Inches(x), Inches(y), Inches(w), Inches(h))
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line is None:
        shp.line.fill.background()
    else:
        shp.line.color.rgb = line
        shp.line.width = Pt(0.75)
    shp.shadow.inherit = False
    if rounded:
        try:
            shp.adjustments[0] = 0.12
        except Exception:
            pass
    return shp


def add_line(slide, x, y, w, color=GRID, width=1.0):
    shp = slide.shapes.add_connector(1, Inches(x), Inches(y), Inches(x + w), Inches(y))
    shp.line.color.rgb = color
    shp.line.width = Pt(width)


def add_table(slide, rows, x, y, w, col_widths, font_size=10.5, row_h=0.38,
              header=True, align_right_cols=()):
    nrows, ncols = len(rows), len(rows[0])
    shape = slide.shapes.add_table(nrows, ncols, Inches(x), Inches(y),
                                   Inches(w), Inches(row_h * nrows))
    table = shape.table
    for j, cw in enumerate(col_widths):
        table.columns[j].width = Inches(cw)
    for i in range(nrows):
        table.rows[i].height = Inches(row_h)
        for j in range(ncols):
            cell = table.cell(i, j)
            cell.text = str(rows[i][j])
            cell.margin_left = Inches(0.08)
            cell.margin_right = Inches(0.08)
            cell.margin_top = Inches(0.03)
            cell.margin_bottom = Inches(0.03)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.fill.solid()
            cell.fill.fore_color.rgb = CARD if (header and i == 0) else (
                ALT if i % 2 == 0 else SURFACE)
            for p in cell.text_frame.paragraphs:
                p.alignment = PP_ALIGN.RIGHT if j in align_right_cols else PP_ALIGN.LEFT
                for r in p.runs:
                    r.font.name = FONT
                    r.font.size = Pt(font_size)
                    r.font.bold = bool(header and i == 0)
                    r.font.color.rgb = INK if (header and i == 0) or i > 0 else SECONDARY
    return table


def new_slide(prs, title, kicker=None):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    bg = s.background.fill
    bg.solid()
    bg.fore_color.rgb = SURFACE
    if kicker:
        add_text(s, 0.8, 0.32, 9, 0.25, kicker, size=9, color=MUTED)
    add_text(s, 0.8, 0.55, 11.8, 0.55, title, size=25, bold=True, color=INK)
    add_rect(s, 0.8, 1.18, 0.62, 0.05, BLUE)
    return s


def page_no(slide, n):
    add_text(slide, 12.1, 7.12, 0.5, 0.2, f"{n:02d}", size=8.5,
             color=MUTED, align=PP_ALIGN.RIGHT)


def footnote(slide, text):
    add_text(slide, 0.8, 7.02, 11.2, 0.25, text, size=8.5, color=MUTED)


def load_data():
    m = json.loads((ROOT / "reports/metrics.json").read_text(encoding="utf-8"))
    df = pd.read_csv(ROOT / "reports/model_comparison.csv", dtype=str)
    for c in ["confidence"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    acc = df.groupby("annotator").apply(
        lambda g: (g.gold == g.pred).mean(), include_groups=False).to_dict()
    conf = df.groupby("annotator")["confidence"].mean().to_dict()
    return m, df, acc, conf


def bar_chart(slide, data, x, y, w, h):
    """Horizontal bars with direct labels; validated categorical colors."""
    max_v = 1.0
    label_w = 1.75
    plot_x = x + label_w + 0.15
    plot_w = w - label_w - 0.55
    row_h = h / len(data)
    bar_h = 0.26
    # gridlines
    for frac in (0, 0.25, 0.5, 0.75, 1.0):
        gx = plot_x + frac * plot_w
        add_line(slide, gx, y - 0.08, 0, GRID, 0.75)
        slide.shapes.add_connector(1, Inches(gx), Inches(y - 0.05),
                                   Inches(gx), Inches(y + h - 0.12))
        # connector color
        line = slide.shapes[-1].line
        line.color.rgb = GRID
        line.width = Pt(0.6)
    for i, (name, val, color) in enumerate(data):
        cy = y + i * row_h
        add_text(slide, x, cy + 0.02, label_w, 0.3, name, size=11,
                 color=SECONDARY, align=PP_ALIGN.RIGHT)
        add_rect(slide, plot_x, cy + 0.03, max(0.03, val / max_v * plot_w),
                 bar_h, color, rounded=True)
        add_text(slide, plot_x + val / max_v * plot_w + 0.08, cy + 0.02,
                 0.8, 0.3, f"{val:.1%}", size=12, bold=True, color=INK)
        add_text(slide, plot_x + val / max_v * plot_w + 0.08, cy + 0.25,
                 0.8, 0.2, "", size=8)
    # axis labels
    for frac, lab in [(0, "0"), (0.25, "25"), (0.5, "50"), (0.75, "75"), (1.0, "100%")]:
        add_text(slide, plot_x + frac * plot_w - 0.25, y + h + 0.02, 0.5, 0.2,
                 lab, size=8.5, color=MUTED, align=PP_ALIGN.CENTER)


def main():
    m, df, acc, conf = load_data()
    t = m["text"]
    a = m["audio"]
    img = m["image"]

    prs = Presentation()
    prs.slide_width = Inches(W)
    prs.slide_height = Inches(H)

    # ---------------- 1 cover ----------------
    s = prs.slides.add_slide(prs.slide_layouts[6])
    s.background.fill.solid()
    s.background.fill.fore_color.rgb = DARK
    add_text(s, 0.9, 0.7, 5, 0.3, "DATA QUALITY / EVALUATION", size=10, color=RGBColor(0xC3, 0xC2, 0xB7))
    add_rect(s, 0.9, 1.15, 0.9, 0.06, ORANGE)
    add_text(s, 0.9, 1.5, 10.5, 1.4, "多模态数据标注与质检", size=42, bold=True, color=WHITE)
    add_text(s, 0.9, 2.75, 10.5, 0.6, "从标注规范到人工 vs 模型一致性评估", size=18, color=RGBColor(0xC3, 0xC2, 0xB7))
    add_text(s, 0.9, 4.3, 10.5, 0.35,
             "24 条文本 · 6 张图像 · 10 条语音   |   Label Studio 1.23   |   2026.10",
             size=11, color=RGBColor(0x89, 0x87, 0x81))
    add_text(s, 0.9, 6.55, 10.5, 0.3,
             "个人实训项目 · 所有指标来自实际标注与脚本复算", size=9, color=RGBColor(0x89, 0x87, 0x81))

    # ---------------- 2 overview ----------------
    s = new_slide(prs, "一页看懂：三个模态，一条质检链路", "PROJECT OVERVIEW")
    cards = [
        ("TEXT", "24", "条文本任务", f"{t['n_tasks']} 条正式集 · 3 路标注", BLUE),
        ("IMAGE", "6", "张图像", f"5 张正式集 · {img['n_boxes']} 个框", ORANGE),
        ("AUDIO", str(a["n_items"] + 1), "条语音", f"CER {a['mean_cer_before']:.1%} → {a['mean_cer_after']:.1%}", AQUA),
    ]
    for i, (tag, num, unit, sub, color) in enumerate(cards):
        x = 0.8 + i * 3.95
        add_rect(s, x, 1.55, 3.6, 3.45, CARD, rounded=True)
        add_rect(s, x, 1.55, 3.6, 0.06, color)
        add_text(s, x + 0.3, 1.85, 3.0, 0.25, tag, size=9, color=MUTED)
        add_text(s, x + 0.3, 2.2, 3.0, 0.9, num, size=40, bold=True, color=INK)
        add_text(s, x + 0.3, 3.05, 3.0, 0.3, unit, size=13, color=SECONDARY)
        add_text(s, x + 0.3, 4.35, 3.0, 0.3, sub, size=10, color=SECONDARY)
    add_text(s, 0.8, 5.45, 11.8, 0.3, "流程", size=9, color=MUTED)
    steps = ["规范 v1.0", "3 条试标", "独立标注", "100% 复核", "分歧裁决", "质检报告"]
    for i, step in enumerate(steps):
        x = 0.8 + i * 1.98
        add_rect(s, x, 5.8, 1.72, 0.5, WHITE, line=GRID, rounded=True)
        add_text(s, x, 5.9, 1.72, 0.3, step, size=10.5, color=INK, align=PP_ALIGN.CENTER)
        if i < len(steps) - 1:
            add_text(s, x + 1.73, 5.9, 0.24, 0.3, "›", size=16, color=MUTED, align=PP_ALIGN.CENTER)
    footnote(s, "产出：标注规范、任务数据、可复现脚本、IAA 指标、裁决表与报告。")
    page_no(s, 2)

    # ---------------- 3 label system ----------------
    s = new_slide(prs, "标注体系：四组字段，单选与多选分开", "LABEL SCHEMA")
    groups = [
        ("情感（单选）", ["正面", "负面", "中性", "无法判断"], BLUE),
        ("方面（多选）", ["口味", "配送", "价格", "服务", "卫生", "包装", "无"], ORANGE),
        ("质量标记（多选）", ["广告推广", "含隐私", "表述不清", "模板/刷单", "无"], ORANGE),
        ("置信度（单选）", ["5 非常确定", "4", "3", "2", "1 纯猜测"], AQUA),
    ]
    for gi, (name, chips, color) in enumerate(groups):
        y = 1.55 + gi * 1.22
        add_text(s, 0.8, y + 0.08, 2.0, 0.3, name, size=12, bold=True, color=INK)
        x = 3.0
        for chip in chips:
            w = 0.28 + 0.155 * len(chip)
            add_rect(s, x, y, w, 0.38, WHITE, line=GRID, rounded=True)
            add_text(s, x, y + 0.085, w, 0.24, chip, size=9.5, color=SECONDARY,
                     align=PP_ALIGN.CENTER)
            x += w + 0.1
    add_rect(s, 9.55, 1.55, 2.95, 4.4, CARD, rounded=True)
    add_text(s, 9.85, 1.8, 2.4, 0.3, "设计原则", size=11, bold=True, color=INK)
    principles = [
        "情感只选一个，避免“又正又负”",
        "方面只标显式提及，不从情感反推",
        "质量标记独立，广告/隐私不混入情感",
        "置信度用于复核路由，不参与金标",
    ]
    yy = 2.25
    for p in principles:
        add_text(s, 9.85, yy, 2.35, 0.75, "· " + p, size=9.8, color=SECONDARY, spacing=1.1)
        yy += 0.78
    footnote(s, "完整规则见《标注规范.md》v1.0；试标后修订为 v1.1。")
    page_no(s, 3)

    # ---------------- 4 decision rules ----------------
    s = new_slide(prs, "判定规则：先看结论，再看证据强度", "DECISION RULES")
    rules = [
        ("01", "广告 / 无关 / 无意义", "→ 无法判断", "并打质量标记"),
        ("02", "有明确结论句", "→ 按结论句", "不要被前面的细节带偏"),
        ("03", "正负相当、态度平淡", "→ 中性", "没有明显褒贬"),
        ("04", "核心体验严重受损", "→ 负面", "否则判正面"),
    ]
    for i, (num, cond, res, note) in enumerate(rules):
        x = 0.8 + (i % 2) * 5.95
        y = 1.55 + (i // 2) * 1.55
        add_rect(s, x, y, 5.6, 1.3, CARD, rounded=True)
        add_text(s, x + 0.25, y + 0.18, 0.55, 0.4, num, size=18, bold=True, color=BLUE)
        add_text(s, x + 0.9, y + 0.18, 4.4, 0.3, cond, size=12, bold=True, color=INK)
        add_text(s, x + 0.9, y + 0.58, 4.4, 0.3, res, size=12, color=ORANGE, bold=True)
        add_text(s, x + 0.9, y + 0.92, 4.4, 0.25, note, size=9, color=MUTED)

    rows = [
        ["边界样本", "判定", "理由"],
        ["味道不错，就是有点咸", "正面", "轻微负向，总体肯定"],
        ["呵呵，真是“神速”", "负面", "反讽按真实语义"],
        ["还行。", "中性", "超短但可判断"],
        ["地址 + 手机号", "中性", "无褒贬，另标隐私"],
    ]
    add_table(s, rows, 0.8, 4.85, 7.2, [3.4, 1.0, 2.8], font_size=9.5, row_h=0.34)
    add_text(s, 8.45, 4.9, 4.0, 0.3, "易错点", size=10, bold=True, color=INK)
    add_text(s, 8.45, 5.3, 4.0, 1.2,
             "混合情感、反讽、超短文本、隐私文本\n是本轮 5 条分歧的全部来源。",
             size=10.5, color=SECONDARY, spacing=1.2)
    footnote(s, "规则写在标注文档里；模型标注的 system prompt 也使用同一套规则。")
    page_no(s, 4)

    # ---------------- 5 process ----------------
    s = new_slide(prs, "流程：试标校准，正式独立，分歧裁决", "WORKFLOW")
    stages = [
        ("01", "试标", "3 条边界样本\n先暴露歧义", BLUE),
        ("02", "正式标注", "3 个账号\noverlap=3", ORANGE),
        ("03", "复核", "100% 输出分歧\n逐条对照规范", AQUA),
        ("04", "裁决", "写入 final_label\n与 reason", BLUE),
    ]
    for i, (num, name, desc, color) in enumerate(stages):
        x = 0.8 + i * 3.05
        add_rect(s, x, 1.6, 2.65, 2.7, CARD, rounded=True)
        add_text(s, x + 0.25, 1.8, 0.6, 0.4, num, size=16, bold=True, color=color)
        add_text(s, x + 0.25, 2.3, 2.1, 0.35, name, size=14, bold=True, color=INK)
        add_text(s, x + 0.25, 2.85, 2.1, 1.1, desc, size=10, color=SECONDARY, spacing=1.2)
        if i < 3:
            add_text(s, x + 2.68, 2.75, 0.32, 0.4, "→", size=18, color=MUTED)
    add_text(s, 0.8, 4.65, 11.8, 0.3, "控制点", size=9, color=MUTED)
    controls = [
        ("独立性", "3 个账号互不看结果；试标不计入正式统计"),
        ("可追溯", "每条标注记录账号、时间、置信度与理由"),
        ("可复算", "导出 JSON → 脚本重算 κ / α / F1 / CER"),
    ]
    for i, (k, v) in enumerate(controls):
        y = 5.05 + i * 0.55
        add_text(s, 0.8, y, 1.3, 0.3, k, size=10.5, bold=True, color=INK)
        add_text(s, 2.1, y, 9.8, 0.3, v, size=10.5, color=SECONDARY)
    footnote(s, "试标 3 条 → 校准会 → 规范 v1.1 → 正式 21 条；正式集全部 3 路标注。")
    page_no(s, 5)

    # ---------------- 6 metrics ----------------
    s = new_slide(prs, "指标口径：先问“回答什么问题”，再看数值", "METRICS")
    rows = [
        ["指标", "回答的问题", "本轮用途"],
        ["一致率", "同一批任务有多少比例标签相同", "直观，但未校正随机一致"],
        ["Cohen's κ", "两个人之间，扣除随机一致后的一致性", "人工 vs 各模型"],
        ["Fleiss' κ", "多人、任务完整时的一致性", "三路整体"],
        ["Krippendorff's α", "允许缺失值的多标注员一致性", "稳健性参考"],
        ["F1 @ IoU≥0.5", "图像框位置与类别是否匹配", "图像框质量"],
        ["CER", "转写相对参考文本的字符错误率", "语音修正前后"],
    ]
    add_table(s, rows, 0.8, 1.55, 8.0, [1.7, 4.2, 2.6], font_size=10, row_h=0.55)
    add_rect(s, 9.15, 1.55, 3.35, 3.5, CARD, rounded=True)
    add_text(s, 9.45, 1.8, 2.8, 0.3, "读法", size=11, bold=True, color=INK)
    add_text(s, 9.45, 2.25, 2.85, 2.5,
             "κ / α > 0.80 较好\n0.67–0.80 需讨论规范\n< 0.67 应重写规范\n\n"
             "阈值不是硬标准，\n要结合任务难度和样本量。",
             size=10.5, color=SECONDARY, spacing=1.25)
    footnote(s, "本轮文本 κ=0.756、α=0.760，落在“需讨论规范”区间，不是“完美一致”。")
    page_no(s, 6)

    # ---------------- 7 results ----------------
    s = new_slide(prs, "本轮结果：文本中等一致，语音修正有效", "RESULTS")
    tiles = [
        ("文本三路一致性", f"{t['percent_agreement']:.1%}", f"Fleiss κ {t['fleiss']:.3f} · α {t['krippendorff_alpha']:.3f}", BLUE),
        ("图像框数", f"{img['n_boxes']}", f"6 张图 · 5 张正式集 · 单人完成", ORANGE),
        ("语音 CER", f"{a['mean_cer_after']:.1%}", f"修正前 {a['mean_cer_before']:.1%} · 下降 {a['relative_reduction']:.1%}", AQUA),
    ]
    for i, (name, value, sub, color) in enumerate(tiles):
        x = 0.8 + i * 3.95
        add_rect(s, x, 1.55, 3.6, 2.15, CARD, rounded=True)
        add_rect(s, x, 1.55, 0.06, 2.15, color)
        add_text(s, x + 0.3, 1.75, 3.0, 0.3, name, size=10, color=MUTED)
        add_text(s, x + 0.3, 2.15, 3.0, 0.65, value, size=30, bold=True, color=INK)
        add_text(s, x + 0.3, 3.15, 3.05, 0.4, sub, size=9.5, color=SECONDARY)
    rows = [
        ["文本指标", "值"],
        ["全体一致任务", f"{t['unanimous_tasks']} / {t['n_tasks']}"],
        ["分歧任务", f"{t['n_disagreements']} 条，全部裁决"],
        ["方面集合 Jaccard", f"{t['aspect_jaccard']:.3f}"],
        ["语音完全正确", f"{a['perfect_after']} / {a['n_items']}"],
    ]
    add_table(s, rows, 0.8, 4.15, 6.2, [4.2, 2.0], font_size=10, row_h=0.42)
    add_text(s, 7.45, 4.15, 5.0, 0.3, "一句话", size=9, color=MUTED)
    add_text(s, 7.45, 4.55, 4.9, 1.6,
             "文本一致性中等，主要风险在边界样本；\n语音修正把 CER 从 5.5% 降到 1.1%；\n图像只完成单人标注，暂不能算 IAA。",
             size=11, color=SECONDARY, spacing=1.3)
    footnote(s, "文本正式集 21 条、3 路标注共 63 条；图像为 6 张中的 5 张正式集。")
    page_no(s, 7)

    # ---------------- 8 human vs models ----------------
    s = new_slide(prs, "人工 vs 模型：模型更贴规范，但条件不完全对等", "EVALUATION")
    data = [
        ("人工 ann1", acc.get("人工 ann1", 0), ORANGE),
        ("DeepSeek-V4-Flash", acc.get("DeepSeek-V4-Flash", 0), BLUE),
        ("GLM-5.3", acc.get("GLM-5.3", 0), AQUA),
    ]
    bar_chart(s, data, 0.75, 1.95, 7.35, 3.15)
    add_text(s, 0.8, 5.2, 7.2, 0.3, "准确率（以 21 条裁决金标为准）", size=9, color=MUTED)
    add_text(s, 8.5, 1.6, 4.0, 0.3, "两两一致性", size=11, bold=True, color=INK)
    rows = [
        ["标注员对", "κ"],
        ["人工 vs DeepSeek", "0.634"],
        ["人工 vs GLM", "0.701"],
        ["DeepSeek vs GLM", "0.929"],
    ]
    add_table(s, rows, 8.5, 2.0, 4.0, [2.75, 1.25], font_size=10.5, row_h=0.45,
              align_right_cols=(1,))
    add_text(s, 8.5, 4.15, 4.0, 1.6,
             "模型之间高度一致，\n但与人只有中等一致。\n\n"
             "更像“规范执行差异”，\n不是模型全面更强。",
             size=10.5, color=SECONDARY, spacing=1.25)
    footnote(s, "n=21；模型 prompt 含完整规范，人工只阅读文档；样本小，结论不外推。")
    page_no(s, 8)

    # ---------------- 9 error analysis ----------------
    s = new_slide(prs, "错误集中在哪里：5 条人工错误，全是边界样本", "ERROR ANALYSIS")
    rows = [
        ["任务", "文本（截断）", "金标", "人工", "模型"],
        ["T04", "加微信领红包…", "无法判断", "中性", "✓"],
        ["T05", "还行。", "中性", "正面", "✓"],
        ["T11", "味道不错，但贵…", "正面", "中性", "✓"],
        ["T20", "分量一般，味道一般…", "中性", "负面", "✓"],
        ["T22", "地址 + 手机号", "中性", "正面", "GLM ✗"],
    ]
    add_table(s, rows, 0.8, 1.55, 7.6, [0.8, 3.0, 1.35, 1.2, 1.25],
              font_size=9.8, row_h=0.48)
    add_rect(s, 8.85, 1.55, 3.65, 4.3, CARD, rounded=True)
    add_text(s, 9.15, 1.8, 3.1, 0.3, "三个发现", size=11, bold=True, color=INK)
    findings = [
        ("5 / 5", "人工错误都落在边界样本"),
        ("4 / 5", "是“中性 / 无法判断”混淆"),
        ("1", "GLM 唯一错误：隐私文本判正面"),
    ]
    yy = 2.3
    for big, txt in findings:
        add_text(s, 9.15, yy, 1.0, 0.4, big, size=18, bold=True, color=BLUE)
        add_text(s, 10.05, yy + 0.03, 2.15, 0.6, txt, size=9.5, color=SECONDARY)
        yy += 1.05
    add_text(s, 0.8, 5.55, 11.6, 0.9,
             "含义：规范不是“写出来”就够了，边界样本需要试标、校准和低置信度复核。"
             "模型可以作为预标注，但必须保留人工裁决。",
             size=11.5, color=INK, spacing=1.25)
    footnote(s, "金标来源：16 条全体一致 + 5 条按规范裁决；错误列表来自 model_comparison.csv。")
    page_no(s, 9)

    # ---------------- 10 calibration ----------------
    s = new_slide(prs, "置信度校准：高置信度不等于高正确率", "CALIBRATION")
    rows = [
        ["标注员", "置信度 5", "置信度 4", "置信度 3", "置信度 ≤2"],
        ["人工 ann1", "90.9% (11)", "62.5% (8)", "0% (1)", "100% (1)"],
        ["DeepSeek-V4-Flash", "100% (12)", "100% (9)", "—", "—"],
        ["GLM-5.3", "100% (10)", "100% (9)", "50% (2)", "—"],
    ]
    add_table(s, rows, 0.8, 1.6, 10.0, [2.6, 1.9, 1.9, 1.9, 1.7],
              font_size=10.5, row_h=0.55, align_right_cols=(1, 2, 3, 4))
    add_text(s, 0.8, 4.35, 5.4, 0.3, "人工", size=9, color=MUTED)
    add_text(s, 0.8, 4.7, 5.3, 1.4,
             "置信度 5 仍有 1 条错；\n置信度 4 只有 62.5%。\n"
             "→ 不能只复核低置信度。",
             size=10.5, color=SECONDARY, spacing=1.25)
    add_text(s, 6.6, 4.35, 5.4, 0.3, "模型", size=9, color=MUTED)
    add_text(s, 6.6, 4.7, 5.4, 1.4,
             "置信度几乎全在 4–5，\n区分度不足，不能直接当\n“自动通过”信号。",
             size=10.5, color=SECONDARY, spacing=1.25)
    footnote(s, "准确率 = 与裁决金标一致；括号内为样本数。样本小，只作流程演示。")
    page_no(s, 10)

    # ---------------- 11 improvements ----------------
    s = new_slide(prs, "改进：把边界规则写死，把复核资源花在低置信度", "ACTIONS")
    cols = [
        ("规范", ["广告 / 隐私 / 超短 / 混合四类写成判定句",
                  "“无”与其他标签互斥，避免多选污染",
                  "数字归一化写入评测口径"]),
        ("流程", ["试标从 3 条扩到 8–10 条",
                  "置信度 ≤3 的样本 100% 复核",
                  "每轮输出 per-label κ，低于 0.6 单独校准"]),
        ("工具", ["模型预标注，人工只审分歧",
                  "脚本自动生成分歧表与报告",
                  "记录 token / 延迟 / 成本"]),
    ]
    for i, (name, items) in enumerate(cols):
        x = 0.8 + i * 3.95
        add_rect(s, x, 1.55, 3.6, 3.9, CARD, rounded=True)
        add_text(s, x + 0.3, 1.8, 3.0, 0.3, name, size=12, bold=True, color=BLUE)
        yy = 2.3
        for item in items:
            add_text(s, x + 0.3, yy, 3.0, 0.7, "· " + item, size=9.8,
                     color=SECONDARY, spacing=1.15)
            yy += 0.9
    add_text(s, 0.8, 5.85, 11.8, 0.6,
             "预期：边界样本错误从 5 条降到 ≤2 条；复核量集中到低置信度，而不是全量重标。",
             size=11.5, bold=True, color=INK)
    footnote(s, "下一轮可用同一批任务复标，对比 κ 与人工准确率是否提升。")
    page_no(s, 11)

    # ---------------- 12 conclusion ----------------
    s = new_slide(prs, "结论与局限", "CONCLUSION")
    add_text(s, 0.8, 1.55, 5.6, 0.3, "结论", size=10, color=MUTED)
    conclusions = [
        "规范可执行，但边界样本是主要风险：人工 5/21 偏离规范。",
        "模型间一致性高（κ 0.929），与人只有 0.63–0.70；可做预标注，不替代人工。",
        "语音修正有效（CER −80.2%）；图像需第二人复标才能算 IAA。",
    ]
    yy = 1.95
    for i, c in enumerate(conclusions):
        add_text(s, 0.8, yy, 0.4, 0.3, f"{i+1}", size=12, bold=True, color=BLUE)
        add_text(s, 1.25, yy - 0.02, 5.5, 0.9, c, size=10.5, color=SECONDARY, spacing=1.2)
        yy += 1.05
    add_text(s, 7.0, 1.55, 5.4, 0.3, "局限", size=10, color=MUTED)
    limits = [
        "样本量小：正式集 21 条，κ 置信区间宽。",
        "条件不对等：模型 prompt 含完整规范。",
        "人工只有 1 人，图像无第二人复标。",
        "语音为 TTS 合成 + 受控错误。",
    ]
    yy = 1.95
    for c in limits:
        add_text(s, 7.0, yy, 5.4, 0.7, "· " + c, size=10.5, color=SECONDARY, spacing=1.2)
        yy += 0.65
    add_rect(s, 0.8, 5.55, 11.75, 0.02, GRID)
    add_text(s, 0.8, 5.75, 11.8, 0.3,
             "复现：start_label_studio.bat + start_data_server.bat → scripts/analyze.py → scripts/compare_models.py",
             size=9.5, color=SECONDARY)
    add_text(s, 0.8, 6.2, 11.8, 0.3,
             "仓库：configs/ · data/ · scripts/ · 标注规范.md · reports/",
             size=9.5, color=MUTED)
    page_no(s, 12)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    prs.save(OUT)
    print(f"saved {OUT} ({len(prs.slides)} slides)")


if __name__ == "__main__":
    main()
