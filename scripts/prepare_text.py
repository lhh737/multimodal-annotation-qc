# -*- coding: utf-8 -*-
"""生成文本标注任务（24 条：5 条试标 + 19 条正式）。

数据来源：
  - 16 条来自 waimai_10k 中文外卖评论数据集（已去重、人工挑选）
  - 8 条为人工构造的边界案例（混合情感、反讽、广告、隐私、无意义等）

输出：
  data/text/tasks.json   -> 直接导入 Label Studio
  data/text/items.csv    -> 留存原始标签 / 难度说明，供质检报告分析（不要导入 LS）
"""
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "text"
OUT.mkdir(parents=True, exist_ok=True)

# (task_id, split, text, source, original_label, note)
ITEMS = [
    # ---------- 试标轮：5 条，用于校准规范和发现歧义 ----------
    ("T01", "pilot", "骑士服务很好，商品质量也可。", "waimai_10k", 1, ""),
    ("T02", "pilot", "送餐员太差！慢！餐凉！不送上楼！态度不好！！", "waimai_10k", 0, ""),
    ("T03", "pilot", "菜很好吃，但是等了一个多小时才送到，汤都洒了。", "edge", "", "混合情感"),
    ("T04", "formal", "加微信 wxid_88888 领红包，每天都有大额优惠券，速度来！", "edge", "", "广告/无关"),
    ("T05", "formal", "还行。", "edge", "", "超短文本"),

    # ---------- 正式轮：19 条 ----------
    ("T06", "formal", "包装好用心呀，点赞！", "waimai_10k", 1, ""),
    ("T07", "formal", "感谢骑士小哥，这么冷的天", "waimai_10k", 1, ""),
    ("T08", "formal", "太棒了，速度快，优惠也大！", "waimai_10k", 1, ""),
    ("T09", "formal", "味道很正，速度超快，定过好几次了", "waimai_10k", 1, ""),
    ("T10", "formal", "蔬菜一起煮汤里就不太好了，味道还是没的说，在这家买过好几次了，很喜欢。", "waimai_10k", 1, ""),
    ("T11", "formal", "京酱肉丝味道不错，要是能再便宜点就好了！毕竟量不是很大", "waimai_10k", 1, ""),
    ("T12", "formal", "配送快很满意就是炒饭将有太多啦", "waimai_10k", 1, ""),
    ("T13", "formal", "米线是碎的，太难吃了，吃过的最难吃米线，还38块钱", "waimai_10k", 0, ""),
    ("T14", "formal", "送餐时间延误1个小时，但外送人员态度较好，希望下次能快点儿。", "waimai_10k", 0, ""),
    ("T15", "formal", "菜太少了，饼有点厚，酱汁味道浅", "waimai_10k", 0, ""),
    ("T16", "formal", "不好吃，太油腻、有些干！", "waimai_10k", 0, ""),
    ("T17", "formal", "订餐1个半小时不见餐，催了还挂电话！", "waimai_10k", 0, ""),
    ("T18", "formal", "说好的发票呢，不是说要补一张送过来么。票没了体谅你们下，但是说好的补票呢。", "waimai_10k", 0, ""),
    ("T19", "formal", "外卖不给餐巾纸的吗？", "waimai_10k", 0, ""),
    ("T20", "formal", "分量一般，味道一般，价格也一般，没什么特别的。", "edge", "", "中性"),
    ("T21", "formal", "真是“神速”啊，下单两小时还没到，饿得我都快升仙了。", "edge", "", "反讽"),
    ("T22", "formal", "我住阳光小区3栋502，骑手直接送上来了，电话13812345678。", "edge", "", "隐私信息"),
    ("T23", "formal", "。。。", "edge", "", "无意义"),
    ("T24", "formal", "味道特别好，但是再也不会点了，太难吃了。", "edge", "", "自相矛盾"),
]


def main():
    tasks = [
        {"data": {"task_id": tid, "text": text}}
        for tid, split, text, source, label, note in ITEMS
    ]
    (OUT / "tasks.json").write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    with open(OUT / "items.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task_id", "split", "text", "source", "original_label", "note"])
        w.writerows(ITEMS)

    n_pilot = sum(1 for x in ITEMS if x[1] == "pilot")
    print(f"已生成 {len(ITEMS)} 条文本任务：试标 {n_pilot} 条，正式 {len(ITEMS)-n_pilot} 条")
    print(f"导入文件：{OUT / 'tasks.json'}")
    print(f"分析用文件：{OUT / 'items.csv'}（不要导入 Label Studio）")


if __name__ == "__main__":
    main()
