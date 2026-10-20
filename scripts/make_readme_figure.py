# -*- coding: utf-8 -*-
"""生成 README 主图：人工与模型的一致率 / 两两 κ。

数据：reports/model_comparison.csv
输出：docs/figures/results-summary.png
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import cohen_kappa_score

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/figures/results-summary.png"

INK = "#0B0B0B"
SECONDARY = "#52514E"
MUTED = "#898781"
GRID = "#E1E0D9"
SURFACE = "#FCFCFB"
BLUE = "#2A78D6"
ORANGE = "#EB6834"
AQUA = "#1BAF7A"

LABELS = ["人工 ann1", "DeepSeek-V4-Flash", "GLM-5.3"]
COLORS = [ORANGE, BLUE, AQUA]


def load():
    df = pd.read_csv(ROOT / "reports/model_comparison.csv", dtype=str)
    df["confidence"] = pd.to_numeric(df.get("confidence"), errors="coerce")
    acc = (df.assign(ok=df.gold == df.pred)
             .groupby("annotator")["ok"].mean().to_dict())
    kappas = []
    for a, b in [("人工 ann1", "DeepSeek-V4-Flash"),
                 ("人工 ann1", "GLM-5.3"),
                 ("DeepSeek-V4-Flash", "GLM-5.3")]:
        x = df[df.annotator == a][["task_id", "pred"]]
        y = df[df.annotator == b][["task_id", "pred"]]
        m = x.merge(y, on="task_id", suffixes=("_x", "_y"))
        kappas.append(cohen_kappa_score(m.pred_x, m.pred_y))
    return [acc[n] for n in LABELS], kappas


def style_axis(ax, xmax, xticks, tick_labels):
    ax.set_xlim(0, xmax)
    ax.set_xticks(xticks)
    ax.set_xticklabels(tick_labels, fontsize=8.5, color=MUTED)
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color("#C3C2B7")
    ax.tick_params(axis="y", length=0, labelsize=10, colors=SECONDARY)
    ax.tick_params(axis="x", length=0, pad=6)


def main():
    acc, kappas = load()

    plt.rcParams["font.family"] = "Microsoft YaHei"
    plt.rcParams["axes.unicode_minus"] = False

    fig = plt.figure(figsize=(11.5, 5.6), facecolor=SURFACE)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.3, 1.0],
                          left=0.17, right=0.97, top=0.75, bottom=0.13,
                          wspace=0.55)

    fig.text(0.04, 0.955, "人工与模型标注对比", fontsize=19, fontweight="bold",
             color=INK, ha="left", va="top")
    fig.text(0.04, 0.895,
             "21 条裁决金标；模型 system prompt 含完整规范，人工仅阅读文档",
             fontsize=9.2, color=MUTED, ha="left", va="top")

    ax1 = fig.add_subplot(gs[0, 0])
    y = list(range(len(LABELS)))[::-1]
    ax1.barh(y, acc, height=0.34, color=COLORS, edgecolor="none", zorder=3)
    for yi, v in zip(y, acc):
        ax1.text(v + 0.015, yi, f"{v:.1%}", va="center", ha="left",
                 fontsize=11, fontweight="bold", color=INK)
    ax1.set_yticks(y)
    ax1.set_yticklabels(LABELS)
    style_axis(ax1, 1.10, [0, 0.25, 0.5, 0.75, 1.0],
               ["0", "25", "50", "75", "100%"])
    ax1.set_title("与金标的一致率（n=21）", loc="left", pad=14,
                  fontsize=10.8, fontweight="bold", color=INK)

    ax2 = fig.add_subplot(gs[0, 1])
    pair_labels = ["人工–DeepSeek", "人工–GLM", "DeepSeek–GLM"]
    y2 = list(range(len(pair_labels)))[::-1]
    ax2.barh(y2, kappas, height=0.34, color=BLUE, alpha=0.85,
             edgecolor="none", zorder=3)
    for yi, v in zip(y2, kappas):
        ax2.text(v + 0.015, yi, f"{v:.3f}", va="center", ha="left",
                 fontsize=11, fontweight="bold", color=INK)
    ax2.set_yticks(y2)
    ax2.set_yticklabels(pair_labels)
    style_axis(ax2, 1.05, [0, 0.25, 0.5, 0.75, 1.0],
               ["0", "0.25", "0.50", "0.75", "1.0"])
    ax2.set_title("两两一致性（Cohen's κ, n=21）", loc="left", pad=14,
                  fontsize=10.8, fontweight="bold", color=INK)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, dpi=260, facecolor=SURFACE, bbox_inches="tight")
    print(f"saved {OUT}")


if __name__ == "__main__":
    main()
