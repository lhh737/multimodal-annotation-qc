# -*- coding: utf-8 -*-
"""一键创建 3 个 Label Studio 项目、导入任务、设置 overlap。

前置：
  1. Label Studio 已在 http://localhost:8080 启动
  2. 项目根目录有 .ls_token（管理员 API Token）

用法：python scripts/setup_projects.py
"""
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://localhost:8080"
TOKEN = (ROOT / ".ls_token").read_text(encoding="utf-8").strip()
HEADERS = {"Authorization": f"Token {TOKEN}"}

SPECS = [
    {
        "title": "01 文本情感与质量标注",
        "config": ROOT / "configs/text.xml",
        "tasks": ROOT / "data/text/tasks.json",
        "overlap": 3,
        "description": "24 条中文外卖评论：情感 / 方面 / 质量标记 / 置信度",
    },
    {
        "title": "02 图像目标框标注",
        "config": ROOT / "configs/image.xml",
        "tasks": ROOT / "data/images/tasks.json",
        "overlap": 3,
        "description": "6 张图片：人 / 动物 / 车辆 / 食物 / 其他",
    },
    {
        "title": "03 语音转写质检",
        "config": ROOT / "configs/audio.xml",
        "tasks": ROOT / "data/audio/tasks.json",
        "overlap": 1,
        "description": "10 条中文语音：修正 ASR 转写并标注错误类型",
    },
]


def main():
    existing = requests.get(f"{BASE}/api/projects", headers=HEADERS, timeout=20).json()
    by_title = {p["title"]: p for p in existing.get("results", [])}

    for spec in SPECS:
        p = by_title.get(spec["title"])
        if p is None:
            r = requests.post(
                f"{BASE}/api/projects", headers=HEADERS, timeout=20,
                json={
                    "title": spec["title"],
                    "description": spec["description"],
                    "label_config": spec["config"].read_text(encoding="utf-8"),
                },
            )
            r.raise_for_status()
            p = r.json()
            print(f"创建项目 {p['id']}: {p['title']}")
        else:
            print(f"项目已存在 {p['id']}: {p['title']}")

        pid = p["id"]
        info = requests.get(f"{BASE}/api/projects/{pid}", headers=HEADERS, timeout=20).json()
        n_tasks = info.get("task_number", 0)
        if n_tasks == 0:
            tasks = json.loads(spec["tasks"].read_text(encoding="utf-8"))
            r = requests.post(f"{BASE}/api/projects/{pid}/import",
                              headers=HEADERS, json=tasks, timeout=60)
            r.raise_for_status()
            print(f"  导入 {len(tasks)} 条任务")
        else:
            print(f"  已有 {n_tasks} 条任务，跳过导入")

        r = requests.patch(
            f"{BASE}/api/projects/{pid}", headers=HEADERS, timeout=20,
            json={
                "maximum_annotations": spec["overlap"],
                "overlap_cohort_percentage": 100,
                "show_overlap_first": True,
            },
        )
        r.raise_for_status()
        print(f"  overlap = {spec['overlap']}")

    print("\n项目列表：")
    for p in requests.get(f"{BASE}/api/projects", headers=HEADERS, timeout=20).json()["results"]:
        print(f"  {p['id']}  {p['title']}  tasks={p.get('task_number')}")


if __name__ == "__main__":
    main()
