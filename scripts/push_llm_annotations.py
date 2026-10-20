# -*- coding: utf-8 -*-
"""把 llm_annotate.py 的结果写进 Label Studio，作为模型账号的标注。

前置：
  - .ls_tokens.json 里有 {"模型账号邮箱": "legacy token"}
  - 模型账号已是项目成员

用法：
    python scripts/push_llm_annotations.py \
        --run data/text/llm_runs/deepseek-v4-flash.json \
        --user model-deepseek@local.test
"""
import argparse
import json
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
BASE = "http://localhost:8080"
CONF = {
    5: "5 非常确定",
    4: "4 比较确定",
    3: "3 一般",
    2: "2 比较不确定",
    1: "1 纯猜测",
}


def choice(name, values, to_name="text"):
    return {
        "from_name": name,
        "to_name": to_name,
        "type": "choices",
        "value": {"choices": values},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--user", required=True)
    ap.add_argument("--project", type=int, default=1)
    ap.add_argument("--url", default=BASE)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tokens = json.loads((ROOT / ".ls_tokens.json").read_text(encoding="utf-8"))
    if args.user not in tokens:
        raise SystemExit(f"{args.user} 不在 .ls_tokens.json 里")
    headers = {"Authorization": f"Token {tokens[args.user]}"}

    run = json.loads(Path(args.run).read_text(encoding="utf-8"))
    labels = {x["task_id"]: x["label"] for x in run["items"]}

    me = requests.get(f"{args.url}/api/current-user/whoami", headers=headers, timeout=20).json()
    my_id = me.get("id")
    tasks = requests.get(
        f"{args.url}/api/tasks", headers=headers,
        params={"project": args.project, "page_size": 100}, timeout=20,
    ).json()
    id_map = {t["data"]["task_id"]: t["id"] for t in tasks.get("tasks", [])}
    print(f"当前用户：{args.user} (id={my_id})；任务映射：{len(id_map)} 条；待写入：{len(labels)} 条")

    for i, (tid, label) in enumerate(labels.items(), 1):
        if tid not in id_map:
            print(f"[{i}] {tid} 不在项目里，跳过")
            continue
        task_id = id_map[tid]
        existing = requests.get(
            f"{args.url}/api/tasks/{task_id}/annotations/", headers=headers, timeout=20,
        ).json()
        mine = [
            a for a in existing
            if (isinstance(a.get("completed_by"), dict)
                and (a["completed_by"].get("email") == args.user
                     or a["completed_by"].get("id") == my_id))
            or a.get("completed_by") == my_id
        ]
        if mine:
            print(f"[{i}] {tid} 当前账号已有标注，跳过")
            continue

        result = [
            choice("sentiment", [label["sentiment"]]),
            choice("aspects", label["aspects"] or ["无"]),
            choice("flags", label["flags"] or ["无"]),
            choice("confidence", [CONF[label["confidence"]]]),
        ]
        if args.dry_run:
            print(f"[{i}] {tid} -> {label['sentiment']} (dry-run)")
            continue
        r = requests.post(
            f"{args.url}/api/tasks/{task_id}/annotations/",
            headers=headers, json={"result": result}, timeout=30,
        )
        if r.ok:
            print(f"[{i}] {tid} 写入成功")
        else:
            print(f"[{i}] {tid} 失败 HTTP {r.status_code}: {r.text[:300]}")

    print("完成。")


if __name__ == "__main__":
    main()
