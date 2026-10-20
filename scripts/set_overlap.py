# -*- coding: utf-8 -*-
"""把项目的“每个任务最少标注数（overlap）”设为 N。

社区版 UI 里不一定有 Quality 面板，因此用 API 改。
Token 获取：Label Studio 右上角头像 -> Account & Settings -> Access Token。

用法：
    python scripts/set_overlap.py --project-id 1 --token <TOKEN> --n 3
    python scripts/set_overlap.py --list --token <TOKEN>
"""
import argparse
import requests

BASE = "http://localhost:8080"


def headers(token):
    return {"Authorization": f"Token {token}"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project-id", type=int)
    ap.add_argument("--token", required=True)
    ap.add_argument("--n", type=int, default=3, help="每个任务需要的标注数")
    ap.add_argument("--list", action="store_true", help="只列出项目")
    ap.add_argument("--url", default=BASE)
    args = ap.parse_args()

    if args.list or not args.project_id:
        r = requests.get(f"{args.url}/api/projects", headers=headers(args.token), timeout=20)
        r.raise_for_status()
        for p in r.json().get("results", []):
            print(p["id"], p["title"], "| maximum_annotations =", p.get("maximum_annotations"))
        return

    payload = {
        "maximum_annotations": args.n,
        "overlap_cohort_percentage": 100,
        "show_overlap_first": True,
    }
    r = requests.patch(
        f"{args.url}/api/projects/{args.project_id}",
        headers=headers(args.token), json=payload, timeout=20,
    )
    print("HTTP", r.status_code)
    print(r.text[:800])
    if r.ok:
        print(f"已把项目 {args.project_id} 的 overlap 设为 {args.n}（100% 任务覆盖）")


if __name__ == "__main__":
    main()
