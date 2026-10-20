# -*- coding: utf-8 -*-
"""人工 vs 模型：准确率 / 每类 P-R-F1 / 混淆矩阵 / 置信度校准 / token 成本。

前置：
  - exports/text.json
  - reports/gold_text.csv（由裁决生成）
  - data/text/llm_runs/*.json

用法：
    python scripts/compare_models.py
输出：
    reports/model_comparison.md
    reports/model_comparison.csv
"""
import json
import re
from pathlib import Path

import pandas as pd
from sklearn.metrics import (accuracy_score, cohen_kappa_score, confusion_matrix,
                             f1_score, precision_recall_fscore_support)

ROOT = Path(__file__).resolve().parents[1]
LABELS = ["正面", "负面", "中性", "无法判断"]
NAME = {
    "ann1@local.test": "人工 ann1",
    "model-deepseek@local.test": "DeepSeek-V4-Flash",
    "model-glm@local.test": "GLM-5.3",
}
RUNS = {
    "DeepSeek-V4-Flash": ROOT / "data/text/llm_runs/tokenhub-deepseek-v4-flash.json",
    "GLM-5.3": ROOT / "data/text/llm_runs/dashscope-glm-5.3.json",
}


def choice(result, name):
    for r in result:
        if r.get("from_name") == name:
            ch = (r.get("value") or {}).get("choices") or []
            return ch[0] if len(ch) == 1 else tuple(ch)
    return None


def conf_int(v):
    m = re.match(r"\s*(\d)", str(v or ""))
    return int(m.group(1)) if m else None


def load():
    raw = json.loads((ROOT / "exports/text.json").read_text(encoding="utf-8"))
    amap = json.loads((ROOT / "data/annotators.json").read_text(encoding="utf-8"))
    gold = pd.read_csv(ROOT / "reports/gold_text.csv", dtype=str)
    gold_map = dict(zip(gold.task_id, gold.gold_label))
    rows = []
    for t in raw:
        tid = t["data"]["task_id"]
        if tid not in gold_map:
            continue
        for a in t.get("annotations") or []:
            u = a.get("completed_by")
            u = amap.get(str(u), str(u))
            if u not in NAME:
                continue
            rows.append({
                "task_id": tid,
                "annotator": NAME[u],
                "gold": gold_map[tid],
                "pred": choice(a["result"], "sentiment"),
                "confidence": conf_int(choice(a["result"], "confidence")),
                "aspects": choice(a["result"], "aspects"),
                "flags": choice(a["result"], "flags"),
            })
    return pd.DataFrame(rows)


def run_stats():
    out = []
    for name, path in RUNS.items():
        if not path.exists():
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        items = d.get("items", [])
        usage = d.get("total_usage", {})
        lat = [x.get("latency", 0) for x in items]
        out.append({
            "model": name,
            "calls": len(items),
            "prompt_tokens": usage.get("prompt_tokens", 0),
            "completion_tokens": usage.get("completion_tokens", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "avg_latency": sum(lat) / len(lat) if lat else None,
        })
    return out


def metrics(df):
    out = []
    for ann, g in df.groupby("annotator"):
        y_true, y_pred = g.gold.tolist(), g.pred.tolist()
        out.append({
            "annotator": ann,
            "n": len(g),
            "accuracy": accuracy_score(y_true, y_pred),
            "macro_f1": f1_score(y_true, y_pred, labels=LABELS, average="macro", zero_division=0),
            "weighted_f1": f1_score(y_true, y_pred, labels=LABELS, average="weighted", zero_division=0),
            "avg_confidence": g.confidence.mean(),
            "errors": int((g.gold != g.pred).sum()),
        })
    return pd.DataFrame(out).sort_values("accuracy", ascending=False)


def per_label(df):
    rows = []
    for ann, g in df.groupby("annotator"):
        p, r, f, s = precision_recall_fscore_support(
            g.gold, g.pred, labels=LABELS, zero_division=0)
        for i, lab in enumerate(LABELS):
            rows.append({"annotator": ann, "label": lab, "precision": p[i],
                         "recall": r[i], "f1": f[i], "support": s[i]})
    return pd.DataFrame(rows)


def calib(df):
    rows = []
    for ann, g in df.groupby("annotator"):
        for c in range(5, 0, -1):
            x = g[g.confidence == c]
            if len(x):
                rows.append({"annotator": ann, "confidence": c, "n": len(x),
                             "accuracy": (x.gold == x.pred).mean()})
    return pd.DataFrame(rows)


def kappas(df):
    out = []
    anns = sorted(df.annotator.unique())
    for i, a in enumerate(anns):
        for b in anns[i + 1:]:
            x = df[df.annotator == a][["task_id", "pred"]]
            y = df[df.annotator == b][["task_id", "pred"]]
            m = x.merge(y, on="task_id", suffixes=("_a", "_b"))
            if len(m) >= 2:
                out.append({"pair": f"{a} vs {b}", "n": len(m),
                            "kappa": cohen_kappa_score(m.pred_a, m.pred_b),
                            "agreement": (m.pred_a == m.pred_b).mean()})
    return pd.DataFrame(out)


def markdown(df, met, pl, cf, kap, runs):
    L = ["# 人工 vs 模型标注对比", ""]
    best = met.iloc[0]
    L += ["## 摘要", "",
          f"- 金标 {len(df.task_id.unique())} 条（16 条全体一致 + 5 条裁决）。",
          f"- 准确率最高：**{best.annotator} {best.accuracy:.1%}**；"
          f"人工 ann1 {met[met.annotator=='人工 ann1'].accuracy.iloc[0]:.1%}。",
          f"- 人工与 DeepSeek 的 κ = {kap[kap.pair.str.contains('人工') & kap.pair.str.contains('DeepSeek')].kappa.iloc[0]:.3f}；"
          f"人工与 GLM 的 κ = {kap[kap.pair.str.contains('人工') & kap.pair.str.contains('GLM')].kappa.iloc[0]:.3f}；"
          f"两模型之间 κ = {kap[kap.pair.str.contains('DeepSeek') & kap.pair.str.contains('GLM')].kappa.iloc[0]:.3f}。",
          "- 模型在 prompt 中获得了完整规范，人工只阅读了文档；差异反映“规范执行”，不等于模型标注能力全面更强。",
          ""]

    L += ["## 1. 总体表现", "",
          "| 标注员 | n | 准确率 | Macro-F1 | Weighted-F1 | 平均置信度 | 错误数 |",
          "|---|---:|---:|---:|---:|---:|---:|"]
    for _, r in met.iterrows():
        L.append(f"| {r.annotator} | {r.n} | {r.accuracy:.1%} | {r.macro_f1:.3f} | "
                 f"{r.weighted_f1:.3f} | {r.avg_confidence:.2f} | {r.errors} |")

    L += ["", "## 2. 每类 P / R / F1", "",
          "| 标注员 | 标签 | Precision | Recall | F1 | 支持数 |",
          "|---|---|---:|---:|---:|---:|"]
    for _, r in pl.iterrows():
        L.append(f"| {r.annotator} | {r.label} | {r.precision:.3f} | {r.recall:.3f} | "
                 f"{r.f1:.3f} | {r.support} |")

    L += ["", "## 3. 混淆矩阵（行=金标，列=预测）", ""]
    for ann in met.annotator:
        g = df[df.annotator == ann]
        cm = confusion_matrix(g.gold, g.pred, labels=LABELS)
        L += [f"**{ann}**", "", "| 金标 \\ 预测 | " + " | ".join(LABELS) + " |",
              "|---|" + "---:|" * len(LABELS)]
        for i, lab in enumerate(LABELS):
            L.append(f"| {lab} | " + " | ".join(str(x) for x in cm[i]) + " |")
        L.append("")

    L += ["## 4. 置信度校准", "",
          "| 标注员 | 置信度 | n | 准确率 |", "|---|---:|---:|---:|"]
    for _, r in cf.iterrows():
        L.append(f"| {r.annotator} | {r.confidence} | {r.n} | {r.accuracy:.1%} |")

    L += ["", "## 5. 两两一致性", "",
          "| 标注员对 | n | 一致率 | Cohen's κ |", "|---|---:|---:|---:|"]
    for _, r in kap.iterrows():
        L.append(f"| {r.pair} | {r.n} | {r.agreement:.1%} | {r.kappa:.3f} |")

    L += ["", "## 6. Token 与延迟", "",
          "| 模型 | 调用数 | Prompt tokens | Completion tokens | 总 tokens | 平均延迟(s) |",
          "|---|---:|---:|---:|---:|---:|"]
    for r in runs:
        L.append(f"| {r['model']} | {r['calls']} | {r['prompt_tokens']} | "
                 f"{r['completion_tokens']} | {r['total_tokens']} | {r['avg_latency']:.2f} |")

    L += ["", "## 7. 错误样本", "",
          "| 任务 | 金标 | 标注员 | 预测 | 置信度 |", "|---|---|---|---|---:|"]
    err = df[df.gold != df.pred].sort_values(["task_id", "annotator"])
    for _, r in err.iterrows():
        L.append(f"| {r.task_id} | {r.gold} | {r.annotator} | {r.pred} | {r.confidence} |")

    L += ["", "## 8. 读数说明", "",
          "- 模型在 system prompt 中获得了完整规范，人工只阅读文档，条件并不对等。",
          "- 样本仅 21 条，准确率与 κ 的置信区间较宽，结论只代表本轮。",
          "- 模型置信度缺少区分度，预标注时应优先复核模型间不一致的样本。",
          "- 结论与限制见 `docs/model-evaluation.md`。"]
    return "\n".join(L)


def main():
    df = load()
    met = metrics(df)
    pl = per_label(df)
    cf = calib(df)
    kap = kappas(df)
    runs = run_stats()

    out = ROOT / "reports"
    df.to_csv(out / "model_comparison.csv", index=False, encoding="utf-8-sig")
    md = markdown(df, met, pl, cf, kap, runs)
    (out / "model_comparison.md").write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
