# -*- coding: utf-8 -*-
"""质检分析：文本 IAA / 图像框一致性 / 语音 CER。

用法（在项目根目录）：
    python scripts/analyze.py \
        --text exports/text.json \
        --image exports/image.json \
        --audio exports/audio.json

只分析某一类也可以，例如：
    python scripts/analyze.py --text exports/text.json

输入是 Label Studio 的 JSON 导出（Project -> Export -> JSON）。
输出到 reports/：
    iaa_summary.md          汇总报告（可直接改写成作品集报告）
    metrics.json            机器可读指标
    disagreements_text.csv  需要人工裁决的分歧清单
    label_noise.csv         与原数据集标签不一致的样本
    image_iaa.csv           图像逐图/逐对标注员指标
    audio_cer.csv           语音逐条 CER 前后对比
"""
import argparse
import csv
import itertools
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import krippendorff
from sklearn.metrics import cohen_kappa_score

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# 通用
# --------------------------------------------------------------------------
def load_annotations(path):
    """读取 LS JSON 导出，返回每个 (task, annotator) 的最新一条标注。"""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("results") or raw.get("tasks") or [raw]

    amap = {}
    map_path = ROOT / "data/annotators.json"
    if map_path.exists():
        try:
            amap = json.loads(map_path.read_text(encoding="utf-8"))
        except Exception:
            amap = {}

    records = []
    for t in raw:
        data = t.get("data") or {}
        tid = data.get("task_id") or data.get("item_id") or str(t.get("id"))
        for a in t.get("annotations") or []:
            if a.get("was_cancelled"):
                continue
            cb = a.get("completed_by")
            if isinstance(cb, dict):
                user = cb.get("email") or cb.get("username") or cb.get("id")
            else:
                user = cb
            user = amap.get(str(user), user)
            records.append({
                "task_id": str(tid),
                "annotator": str(user),
                "annotation_id": a.get("id") or 0,
                "data": data,
                "result": a.get("result") or [],
                "raw_task": t,
            })

    best = {}
    for r in records:
        key = (r["task_id"], r["annotator"])
        if key not in best or r["annotation_id"] >= best[key]["annotation_id"]:
            best[key] = r
    return list(best.values())


def load_meta(path):
    p = Path(path)
    if not p.exists():
        return {}
    df = pd.read_csv(p, dtype=str).fillna("")
    idcol = "task_id" if "task_id" in df.columns else "item_id"
    return {str(row[idcol]): row.to_dict() for _, row in df.iterrows()}


def attach_split(rows, meta, default="formal"):
    for r in rows:
        r["split"] = meta.get(r["task_id"], {}).get("split", default)
    return rows


def get_choice(result, name):
    for r in result:
        if r.get("from_name") == name:
            ch = (r.get("value") or {}).get("choices")
            if ch:
                return ch[0] if len(ch) == 1 else tuple(sorted(ch))
    return None


def parse_conf(v):
    if not v:
        return None
    m = re.match(r"\s*(\d)", str(v))
    return int(m.group(1)) if m else None


def pivot(rows, field):
    d = defaultdict(dict)
    for r in rows:
        d[r["task_id"]][r["annotator"]] = get_choice(r["result"], field)
    return d


def pairwise_agreement(piv):
    vals = []
    for m in piv.values():
        x = [v for v in m.values() if v is not None]
        for a, b in itertools.combinations(x, 2):
            vals.append(a == b)
    return float(np.mean(vals)) if vals else None


def cohen_pairs(piv):
    anns = sorted({a for m in piv.values() for a in m})
    out = {}
    for a, b in itertools.combinations(anns, 2):
        xs, ys = [], []
        for m in piv.values():
            if a in m and b in m and m[a] is not None and m[b] is not None:
                xs.append(m[a]); ys.append(m[b])
        if len(xs) >= 2 and len(set(xs + ys)) >= 2:
            out[f"{a} vs {b}"] = (float(cohen_kappa_score(xs, ys)), len(xs))
    return out


def fleiss_kappa(piv, min_raters=2):
    """只使用所有评分者都齐的任务；变量评分者时 Fleiss 仅作参考。"""
    usable = {t: m for t, m in piv.items()
              if len([v for v in m.values() if v is not None]) >= min_raters}
    if not usable:
        return None, 0
    n = min(len([v for v in m.values() if v is not None]) for m in usable.values())
    usable = {t: {a: v for a, v in m.items() if v is not None} for t, m in usable.items()}
    usable = {t: m for t, m in usable.items() if len(m) == n}
    if len(usable) < 2:
        return None, 0
    cats = sorted({v for m in usable.values() for v in m.values()})
    idx = {c: i for i, c in enumerate(cats)}
    table = np.zeros((len(usable), len(cats)))
    for i, m in enumerate(usable.values()):
        for v in m.values():
            table[i, idx[v]] += 1
    P_i = (np.sum(table ** 2, axis=1) - n) / (n * (n - 1))
    P_bar = P_i.mean()
    p_j = table.sum(axis=0) / (len(usable) * n)
    P_e = np.sum(p_j ** 2)
    if P_e >= 1:
        return None, len(usable)
    return float((P_bar - P_e) / (1 - P_e)), len(usable)


def kripp_alpha(piv, field_values=None):
    anns = sorted({a for m in piv.values() for a in m})
    units = sorted(piv)
    cats = sorted({v for m in piv.values() for v in m.values() if v is not None})
    if len(anns) < 2 or len(cats) < 2:
        return None
    idx = {c: i for i, c in enumerate(cats)}
    data = np.full((len(anns), len(units)), np.nan)
    for j, u in enumerate(units):
        for i, a in enumerate(anns):
            v = piv[u].get(a)
            if v is not None:
                data[i, j] = idx[v]
    try:
        return float(krippendorff.alpha(reliability_data=data, level_of_measurement="nominal"))
    except Exception:
        return None


def majority(m):
    vals = [v for v in m.values() if v is not None]
    if not vals:
        return None, 0.0
    c = Counter(vals)
    top = c.most_common()
    if len(top) > 1 and top[0][1] == top[1][1]:
        return None, 0.0  # 平票，不给伪金标
    return top[0][0], top[0][1] / len(vals)


def fmt(x, pct=False, nd=3):
    if x is None:
        return "—"
    return f"{x:.{nd}f}" if not pct else f"{x:.1%}"


# --------------------------------------------------------------------------
# 文本
# --------------------------------------------------------------------------
def analyze_text(path, meta_path, out_dir, include_pilot=False):
    rows = attach_split(load_annotations(path), load_meta(meta_path))
    if not include_pilot:
        rows = [r for r in rows if r["split"] != "pilot"]
    meta = load_meta(meta_path)

    piv = pivot(rows, "sentiment")
    anns = sorted({r["annotator"] for r in rows})
    n_tasks = len(piv)
    n_ann = len(rows)
    pct = pairwise_agreement(piv)
    cohens = cohen_pairs(piv)
    fleiss, fleiss_n = fleiss_kappa(piv)
    alpha = kripp_alpha(piv)

    dist = Counter(get_choice(r["result"], "sentiment") for r in rows)
    unanimous = sum(1 for m in piv.values()
                    if len({v for v in m.values() if v is not None}) == 1)

    # 置信度校准
    conf_rows = []
    for t, m in piv.items():
        gold, _ = majority(m)
        if gold is None:
            continue
        for a, v in m.items():
            if v is None:
                continue
            rec = next(r for r in rows if r["task_id"] == t and r["annotator"] == a)
            conf = parse_conf(get_choice(rec["result"], "confidence"))
            if conf:
                conf_rows.append((conf, v == gold))
    calib = []
    for c in range(5, 0, -1):
        xs = [ok for cc, ok in conf_rows if cc == c]
        if xs:
            calib.append((c, len(xs), float(np.mean(xs))))

    # 方面一致性（Jaccard）
    jac = []
    for t, m in pivot(rows, "aspects").items():
        vals = [set(v) - {"无"} for v in m.values() if v]
        for a, b in itertools.combinations(vals, 2):
            u = a | b
            jac.append(1.0 if not u else len(a & b) / len(u))

    # 分歧清单
    disagree = []
    for t, m in piv.items():
        vals = [v for v in m.values() if v is not None]
        if len(set(vals)) < 2:
            continue
        recs = [r for r in rows if r["task_id"] == t]
        text = recs[0]["data"].get("text", "")
        detail = "; ".join(f"{r['annotator']}={get_choice(r['result'],'sentiment')}"
                           f"(conf={get_choice(r['result'],'confidence')})"
                           for r in recs)
        asp = "; ".join(f"{r['annotator']}={','.join(get_choice(r['result'],'aspects') or [])}"
                        for r in recs)
        disagree.append({
            "task_id": t, "split": recs[0]["split"], "text": text,
            "labels": detail, "aspects": asp,
            "n_distinct": len(set(vals)), "final_label": "", "reason": "",
        })
    disagree.sort(key=lambda x: (-x["n_distinct"], x["task_id"]))
    pd.DataFrame(disagree).to_csv(out_dir / "disagreements_text.csv",
                                  index=False, encoding="utf-8-sig")

    # 与原数据集标签对比（只对 source=waimai_10k 的正式样本）
    noise = []
    for t, m in piv.items():
        info = meta.get(t, {})
        gold, _ = majority(m)
        orig = str(info.get("original_label", "")).strip()
        if gold is None or orig not in {"0", "1"}:
            continue
        orig_map = "正面" if orig == "1" else "负面"
        if gold != orig_map:
            noise.append({"task_id": t, "text": info.get("text", ""),
                          "original_label": orig_map, "majority_label": gold,
                          "raters": "; ".join(f"{a}={m[a]}" for a in m)})
    if noise:
        pd.DataFrame(noise).to_csv(out_dir / "label_noise.csv",
                                   index=False, encoding="utf-8-sig")

    result = {
        "n_tasks": n_tasks, "n_annotations": n_ann, "annotators": anns,
        "percent_agreement": pct,
        "cohen": {k: {"kappa": v[0], "n": v[1]} for k, v in cohens.items()},
        "fleiss": fleiss, "fleiss_n_tasks": fleiss_n,
        "krippendorff_alpha": alpha,
        "unanimous_tasks": unanimous,
        "label_distribution": {str(k): v for k, v in dist.items()},
        "confidence_calibration": [
            {"confidence": c, "n": n, "accuracy_vs_majority": a} for c, n, a in calib
        ],
        "aspect_jaccard": float(np.mean(jac)) if jac else None,
        "n_disagreements": len(disagree),
        "label_noise_count": len(noise),
        "label_noise_checked": sum(
            1 for t in piv
            if str(meta.get(t, {}).get("original_label", "")) in {"0", "1"}
        ),
    }
    return result


# --------------------------------------------------------------------------
# 图像
# --------------------------------------------------------------------------
def rectangles(result):
    out = []
    for r in result:
        if r.get("type") != "rectanglelabels":
            continue
        v = r.get("value") or {}
        labs = v.get("rectanglelabels") or []
        out.append({
            "label": labs[0] if labs else "",
            "x": float(v.get("x", 0)), "y": float(v.get("y", 0)),
            "w": float(v.get("width", 0)), "h": float(v.get("height", 0)),
        })
    return out


def iou(a, b):
    ax2, ay2 = a["x"] + a["w"], a["y"] + a["h"]
    bx2, by2 = b["x"] + b["w"], b["y"] + b["h"]
    iw = max(0.0, min(ax2, bx2) - max(a["x"], b["x"]))
    ih = max(0.0, min(ay2, by2) - max(a["y"], b["y"]))
    inter = iw * ih
    union = a["w"] * a["h"] + b["w"] * b["h"] - inter
    return inter / union if union > 0 else 0.0


def match_boxes(ra, rb, thr=0.5):
    cand = []
    for i, a in enumerate(ra):
        for j, b in enumerate(rb):
            if a["label"] != b["label"]:
                continue
            v = iou(a, b)
            if v >= thr:
                cand.append((v, i, j))
    cand.sort(reverse=True)
    ua, ub, matched = set(), set(), []
    for v, i, j in cand:
        if i in ua or j in ub:
            continue
        ua.add(i); ub.add(j); matched.append(v)
    tp = len(matched)
    fp, fn = len(ra) - tp, len(rb) - tp
    return tp, fp, fn, (float(np.mean(matched)) if matched else None)


def analyze_image(path, meta_path, out_dir, include_pilot=False):
    rows = attach_split(load_annotations(path), load_meta(meta_path))
    if not include_pilot:
        rows = [r for r in rows if r["split"] != "pilot"]
    meta = load_meta(meta_path)
    by_task = defaultdict(dict)
    for r in rows:
        by_task[r["task_id"]][r["annotator"]] = rectangles(r["result"])

    n_boxes = sum(len(v) for m in by_task.values() for v in m.values())
    label_counts = Counter(
        b["label"] for m in by_task.values() for v in m.values() for b in v
    )

    records = []
    for t, m in by_task.items():
        anns = sorted(m)
        for a, b in itertools.combinations(anns, 2):
            ra, rb = m[a], m[b]
            tp, fp, fn, miou = match_boxes(ra, rb)
            prec = tp / (tp + fp) if tp + fp else None
            rec = tp / (tp + fn) if tp + fn else None
            f1 = (2 * prec * rec / (prec + rec)) if prec and rec else (0.0 if tp + fp + fn else None)
            records.append({
                "item_id": t, "pair": f"{a} vs {b}",
                "n_a": len(ra), "n_b": len(rb),
                "tp": tp, "fp": fp, "fn": fn,
                "precision": prec, "recall": rec, "f1": f1,
                "mean_iou": miou,
            })
    df = pd.DataFrame(records)
    if not df.empty:
        df.to_csv(out_dir / "image_iaa.csv", index=False, encoding="utf-8-sig")

    tp = int(df["tp"].sum()) if not df.empty else 0
    fp = int(df["fp"].sum()) if not df.empty else 0
    fn = int(df["fn"].sum()) if not df.empty else 0
    micro_p = tp / (tp + fp) if tp + fp else None
    micro_r = tp / (tp + fn) if tp + fn else None
    micro_f1 = (2 * micro_p * micro_r / (micro_p + micro_r)
                if micro_p and micro_r else None)
    mious = [x for x in (df["mean_iou"].tolist() if not df.empty else []) if x is not None]

    result = {
        "n_images": len({r["task_id"] for r in rows}),
        "n_annotations": len(rows),
        "n_boxes": n_boxes,
        "label_counts": dict(label_counts),
        "annotators": sorted({r["annotator"] for r in rows}),
        "pairs": len(df),
        "micro_precision": micro_p,
        "micro_recall": micro_r,
        "micro_f1": micro_f1,
        "mean_matched_iou": float(np.mean(mious)) if mious else None,
        "total_tp": tp, "total_fp": fp, "total_fn": fn,
        "per_pair_f1": ({k: float(v) for k, v in df.groupby("pair")["f1"].mean().items()}
                        if not df.empty else {}),
    }
    return result


# --------------------------------------------------------------------------
# 语音
# --------------------------------------------------------------------------
PUNCT = set("，。！？、；：“”‘’（）《》…—,.!?;:\"'()[]{}<>-· \t\n\r")

CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def cn_num_to_arabic(seq):
    """把中文数字串转成阿拉伯数字：二十四→24，二三五七→2357，十二→12。"""
    if not any(u in seq for u in CN_UNITS):
        return "".join(str(CN_DIGITS[c]) for c in seq if c in CN_DIGITS)
    total, current = 0, 0
    for ch in seq:
        if ch in CN_DIGITS:
            current = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            unit = CN_UNITS[ch]
            total += (current or 1) * unit
            current = 0
    total += current
    return str(total)


def normalize(s):
    # 数字归一化：避免“二十四”vs“24”被算成错字
    s = re.sub(r"[零一二两三四五六七八九十百千]+",
               lambda m: cn_num_to_arabic(m.group()), s)
    return "".join(ch for ch in s if ch not in PUNCT)


def cer(ref, hyp):
    r, h = list(normalize(ref)), list(normalize(hyp))
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i]
        for j, hc in enumerate(h, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (rc != hc)))
        prev = cur
    return prev[-1] / len(r)


def textarea(result):
    for r in result:
        if r.get("type") == "textarea":
            v = (r.get("value") or {}).get("text")
            if isinstance(v, list):
                return v[0] if v else ""
            return v or ""
    return ""


def analyze_audio(path, meta_path, out_dir, include_pilot=False):
    rows = attach_split(load_annotations(path), load_meta(meta_path))
    if not include_pilot:
        rows = [r for r in rows if r["split"] != "pilot"]
    meta = load_meta(meta_path)

    recs = []
    for r in rows:
        info = meta.get(r["task_id"], {})
        gold, asr = info.get("gold", ""), info.get("asr", "")
        if not gold:
            continue
        corrected = textarea(r["result"])
        if not corrected:
            continue
        recs.append({
            "item_id": r["task_id"], "split": r["split"], "annotator": r["annotator"],
            "gold": gold, "asr": asr, "corrected": corrected,
            "cer_before": cer(gold, asr), "cer_after": cer(gold, corrected),
            "error_types": ",".join(get_choice(r["result"], "error_types") or []),
            "intelligibility": get_choice(r["result"], "intelligibility"),
        })
    df = pd.DataFrame(recs)
    if not df.empty:
        df["delta"] = df["cer_before"] - df["cer_after"]
        df.to_csv(out_dir / "audio_cer.csv", index=False, encoding="utf-8-sig")

    result = {
        "n_items": len(df),
        "mean_cer_before": float(df["cer_before"].mean()) if not df.empty else None,
        "mean_cer_after": float(df["cer_after"].mean()) if not df.empty else None,
        "absolute_reduction": float((df["cer_before"] - df["cer_after"]).mean()) if not df.empty else None,
        "relative_reduction": (
            float((df["cer_before"].mean() - df["cer_after"].mean()) / df["cer_before"].mean())
            if not df.empty and df["cer_before"].mean() > 0 else None
        ),
        "improved": int((df["delta"] > 1e-9).sum()) if not df.empty else 0,
        "unchanged": int((df["delta"].abs() <= 1e-9).sum()) if not df.empty else 0,
        "worse": int((df["delta"] < -1e-9).sum()) if not df.empty else 0,
        "perfect_after": int((df["cer_after"] == 0).sum()) if not df.empty else 0,
    }
    return result


# --------------------------------------------------------------------------
# 报告
# --------------------------------------------------------------------------
def build_report(text_r, image_r, audio_r):
    lines = ["# 多模态数据标注质检报告（自动生成初稿）", ""]
    lines += ["## 1. 文本标注一致性", ""]
    if text_r:
        lines += [
            f"- 任务数：{text_r['n_tasks']}；标注条数：{text_r['n_annotations']}；标注员：{', '.join(text_r['annotators'])}",
            f"- 两两一致率：**{fmt(text_r['percent_agreement'], pct=True)}**",
            f"- Cohen's κ（两两）：" + "；".join(
                f"{k} = {fmt(v['kappa'])}（n={v['n']}）"
                for k, v in text_r["cohen"].items()),
            f"- Fleiss' κ：**{fmt(text_r['fleiss'])}**（{text_r['fleiss_n_tasks']} 个完整任务）",
            f"- Krippendorff's α (nominal)：**{fmt(text_r['krippendorff_alpha'])}**",
            f"- 全体一致任务：{text_r['unanimous_tasks']} / {text_r['n_tasks']}",
            f"- 方面集合平均 Jaccard：{fmt(text_r['aspect_jaccard'])}",
            f"- 分歧任务数：{text_r['n_disagreements']}（见 `disagreements_text.csv`）",
            f"- 与原数据集标签不一致：{text_r['label_noise_count']} / {text_r['label_noise_checked']}（见 `label_noise.csv`）",
            "",
            "### 置信度校准",
            "",
            "| 置信度 | 样本数 | 与多数标签一致率 |",
            "|---|---:|---:|",
        ]
        for c in text_r["confidence_calibration"]:
            lines.append(f"| {c['confidence']} | {c['n']} | {fmt(c['accuracy_vs_majority'], pct=True)} |")
        lines += ["", "### 标签分布", "",
                  "| 标签 | 次数 |", "|---|---:|"]
        for k, v in text_r["label_distribution"].items():
            lines.append(f"| {k} | {v} |")
        lines += ["", "> 判定参考：κ/α > 0.80 可视为较好；0.67–0.80 需讨论规范；< 0.67 应重写规范或重训。", ""]
    else:
        lines.append("未提供文本导出文件。")
        lines.append("")

    lines += ["## 2. 图像框标注一致性", ""]
    if image_r:
        lines += [
            f"- 图片数：{image_r['n_images']}；标注条数：{image_r['n_annotations']}；标注员：{', '.join(image_r['annotators'])}",
            f"- 标注框数：{image_r['n_boxes']}；类别分布："
            + "、".join(f"{k} {v}" for k, v in image_r["label_counts"].items()),
            f"- IoU≥0.5 且同标签匹配：micro Precision **{fmt(image_r['micro_precision'], pct=True)}**，"
            f"Recall **{fmt(image_r['micro_recall'], pct=True)}**，F1 **{fmt(image_r['micro_f1'], pct=True)}**",
            f"- 匹配框平均 IoU：{fmt(image_r['mean_matched_iou'])}",
            f"- TP / FP / FN：{image_r['total_tp']} / {image_r['total_fp']} / {image_r['total_fn']}",
            "",
            "| 标注员对 | 平均 F1 |", "|---|---:|",
        ]
        for k, v in image_r["per_pair_f1"].items():
            lines.append(f"| {k} | {fmt(v)} |")
        lines.append("")
    else:
        lines.append("未提供图像导出文件。")
        lines.append("")

    lines += ["## 3. 语音转写质检", ""]
    if audio_r:
        lines += [
            f"- 条目数：{audio_r['n_items']}",
            f"- 平均 CER：**{fmt(audio_r['mean_cer_before'], pct=True)} → {fmt(audio_r['mean_cer_after'], pct=True)}**",
            f"- 绝对下降：{fmt(audio_r['absolute_reduction'], pct=True)}；"
            f"相对下降：{fmt(audio_r['relative_reduction'], pct=True)}",
            f"- 改善 / 不变 / 变差：{audio_r['improved']} / {audio_r['unchanged']} / {audio_r['worse']}",
            f"- 修正后 CER=0 的条目：{audio_r['perfect_after']} / {audio_r['n_items']}",
            "",
        ]
    else:
        lines.append("未提供语音导出文件。")
        lines.append("")

    lines += [
        "## 4. 需要人工补写的部分",
        "",
        "1. 逐条查看 `disagreements_text.csv`，填写 `final_label` 与 `reason`（裁决理由）。",
        "2. 把分歧归入错误类型：规范歧义 / 任务本身歧义 / 标注员疏忽 / 原数据标签噪声。",
        "3. 给出 3 条可执行的规范修改建议，并说明修改后预计影响。",
        "4. 总结 2 条流程改进（如：重叠率、试标题、低置信度复核路由）。",
        "",
        "> 注意：自动报告只负责算数，不替你解释原因。面试官会追问“为什么 κ 是这个数”。",
    ]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text")
    ap.add_argument("--image")
    ap.add_argument("--audio")
    ap.add_argument("--text-meta", default=str(ROOT / "data/text/items.csv"))
    ap.add_argument("--image-meta", default=str(ROOT / "data/images/items.csv"))
    ap.add_argument("--audio-meta", default=str(ROOT / "data/audio/items.csv"))
    ap.add_argument("--out", default=str(ROOT / "reports"))
    ap.add_argument("--include-pilot", action="store_true", help="把试标轮也纳入统计")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    text_r = analyze_text(args.text, args.text_meta, out, args.include_pilot) if args.text else None
    image_r = analyze_image(args.image, args.image_meta, out, args.include_pilot) if args.image else None
    audio_r = analyze_audio(args.audio, args.audio_meta, out, args.include_pilot) if args.audio else None

    metrics = {"text": text_r, "image": image_r, "audio": audio_r}
    (out / "metrics.json").write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    report = build_report(text_r, image_r, audio_r)
    (out / "iaa_summary.md").write_text(report, encoding="utf-8")

    print(report)


if __name__ == "__main__":
    main()
