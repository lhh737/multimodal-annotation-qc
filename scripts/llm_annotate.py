# -*- coding: utf-8 -*-
"""用大模型模拟标注员，对文本任务做标注。

模型走火山方舟 OpenAI 兼容接口：
    POST https://ark.cn-beijing.volces.com/api/v3/chat/completions

用法：
    python scripts/llm_annotate.py --model A
    python scripts/llm_annotate.py --model B --limit 5
    python scripts/llm_annotate.py --model deepseek-v4-flash

输出：
    data/text/llm_runs/<model>.json

注意：这是“LLM as annotator”实验，不是人类标注。报告里必须明确区分。
"""
import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]

SENTIMENTS = {"正面", "负面", "中性", "无法判断"}
ASPECTS = {"口味", "配送", "价格", "服务", "卫生", "包装", "无"}
FLAGS = {"广告推广", "含隐私信息", "表述不清", "疑似模板/刷单", "无"}

SYSTEM_PROMPT = """你是数据标注员。请严格按下面的规范，对一条中文外卖评论做标注。

只输出一个 JSON 对象，不要 Markdown 代码块，不要解释。字段：
{
  "sentiment": "正面|负面|中性|无法判断",
  "aspects": ["口味|配送|价格|服务|卫生|包装|无"],
  "flags": ["广告推广|含隐私信息|表述不清|疑似模板/刷单|无"],
  "confidence": 1-5 的整数,
  "reason": "一句话依据"
}

规范：
1. 判断整条评论对本次消费体验的总体态度，不要逐词做情感分析。
2. 有明确结论句时以结论句为准；反讽按真实语义判断。
3. 混合评论：核心体验严重受损（送错/洒漏/严重超时/卫生问题）判负面；轻微抱怨不影响总体好评判正面；正负相当且态度平淡判中性。
4. 广告、无关内容、无意义符号、信息严重不足判“无法判断”。
5. aspects 只标文本中明确提到的方面；选“无”时不能选其他方面。
6. flags 选“无”时不能选其他标记；含手机号/门牌号等要标“含隐私信息”。
7. confidence 如实填写：5 非常确定，4 比较确定，3 一般，2 比较不确定，1 纯猜测。

示例：
评论：味道不错，就是有点咸。
输出：{"sentiment":"正面","aspects":["口味"],"flags":["无"],"confidence":4,"reason":"轻微负向细节，总体肯定"}
评论：等了一个小时，饭都凉了。
输出：{"sentiment":"负面","aspects":["配送","口味"],"flags":["无"],"confidence":5,"reason":"严重超时且餐品变凉"}
评论：呵呵，真是又快又好，两个小时才到。
输出：{"sentiment":"负面","aspects":["配送"],"flags":["无"],"confidence":4,"reason":"反讽，实际表达不满"}
评论：请问可以开发票吗？
输出：{"sentiment":"中性","aspects":["服务"],"flags":["无"],"confidence":4,"reason":"纯询问，无褒贬"}
评论：招外卖兼职，日结，加微信。
输出：{"sentiment":"无法判断","aspects":["无"],"flags":["广告推广"],"confidence":5,"reason":"广告，非消费评价"}"""


PROVIDERS = {
    "ark": ("ARK_BASE_URL", "ARK_API_KEY", None,
            "https://ark.cn-beijing.volces.com/api/v3"),
    "deepseek": ("GEN_BASE_URL", "GEN_API_KEY", "GEN_MODEL_ID",
                 "https://api.deepseek.com"),
    "tokenhub": ("TOKENHUB_BASE_URL", "TOKENHUB_API_KEY", None,
                 "https://tokenhub.tencentmaas.com/v1"),
    "dashscope": ("DASHSCOPE_BASE_URL", "DASHSCOPE_API_KEY", None,
                  "https://dashscope.aliyuncs.com/compatible-mode/v1"),
}


def load_env(paths):
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def extract_json(text):
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object found")
    return json.loads(text[start:end + 1])


def validate(obj):
    s = obj.get("sentiment")
    if s not in SENTIMENTS:
        raise ValueError(f"bad sentiment: {s}")

    aspects = obj.get("aspects") or []
    if isinstance(aspects, str):
        aspects = [aspects]
    aspects = [a for a in aspects if a in ASPECTS]
    if not aspects:
        aspects = ["无"]
    if "无" in aspects:
        aspects = ["无"]

    flags = obj.get("flags") or []
    if isinstance(flags, str):
        flags = [flags]
    flags = [f for f in flags if f in FLAGS]
    if not flags:
        flags = ["无"]
    if "无" in flags:
        flags = ["无"]

    try:
        conf = int(obj.get("confidence"))
    except Exception:
        conf = 3
    conf = max(1, min(5, conf))

    return {
        "sentiment": s,
        "aspects": aspects,
        "flags": flags,
        "confidence": conf,
        "reason": str(obj.get("reason", ""))[:200],
    }


def call_model(base_url, api_key, model, text, timeout, max_retries, max_tokens=1200):
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"评论：{text}"},
        ],
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    last_err = None
    for attempt in range(1, max_retries + 1):
        t0 = time.time()
        try:
            r = requests.post(
                f"{base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json=payload,
                timeout=timeout,
            )
            latency = time.time() - t0
            if not r.ok:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:400]}")
            data = r.json()
            msg = data["choices"][0]["message"]
            content = msg.get("content") or ""
            if not content.strip():
                raise ValueError(f"empty content; message keys={list(msg)}")
            parsed = validate(extract_json(content))
            return parsed, content, data.get("usage", {}), latency
        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(1.5 * attempt)
    raise RuntimeError(f"failed after {max_retries} attempts: {last_err}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", default="ark", choices=sorted(PROVIDERS))
    ap.add_argument("--model", help="A / B（仅 ark），或直接写模型 ID")
    ap.add_argument("--limit", type=int, help="只跑前 N 条")
    ap.add_argument("--task-ids", help="逗号分隔，如 T01,T02")
    ap.add_argument("--out", help="输出文件")
    ap.add_argument("--env-file", action="append", default=[], help="额外 env 文件，可重复")
    ap.add_argument("--base-url", help="覆盖 provider 的 base url")
    ap.add_argument("--api-key-env", help="覆盖 key 的 env 变量名")
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--sleep", type=float, default=0.5)
    args = ap.parse_args()

    load_env([Path(x) for x in args.env_file] + [ROOT / ".env"])

    base_env, key_env, model_env, default_base = PROVIDERS[args.provider]
    base_url = args.base_url or os.environ.get(base_env) or default_base
    if args.api_key_env:
        key_env = args.api_key_env
    api_key = os.environ.get(key_env, "").strip()
    if not api_key or api_key.startswith("your_"):
        raise SystemExit(
            f"缺少 {key_env}。请把 key 放进 .env（或 --env-file 指定的文件）。"
        )

    if args.provider == "ark" and args.model and args.model.upper() in {"A", "B"}:
        model = os.environ.get(f"ARK_MODEL_{args.model.upper()}", args.model)
    else:
        model = args.model or (os.environ.get(model_env) if model_env else None)
    if not model:
        raise SystemExit("未指定模型：加 --model <模型ID>")

    print(f"provider={args.provider}  model={model}  base={base_url}")

    tasks = json.loads((ROOT / "data/text/tasks.json").read_text(encoding="utf-8"))
    items = [(t["data"]["task_id"], t["data"]["text"]) for t in tasks]
    if args.task_ids:
        keep = {x.strip() for x in args.task_ids.split(",") if x.strip()}
        items = [(i, t) for i, t in items if i in keep]
    if args.limit:
        items = items[: args.limit]

    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", model).strip("-")
    out_dir = ROOT / "data/text/llm_runs"
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = "" if args.provider == "ark" else f"{args.provider}-"
    out_path = Path(args.out) if args.out else out_dir / f"{prefix}{slug}.json"

    prev = {"model": model, "provider": args.provider, "base_url": base_url, "items": []}
    if out_path.exists():
        try:
            prev = json.loads(out_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    done = {x["task_id"] for x in prev.get("items", [])}
    items = [(i, t) for i, t in items if i not in done]

    print(f"模型：{model}")
    print(f"待标：{len(items)} 条（已完成 {len(done)} 条，结果写入 {out_path}）")

    timeout = float(os.environ.get("ARK_TIMEOUT", 120))
    retries = int(os.environ.get("ARK_MAX_RETRIES", 3))
    total_usage = prev.get("total_usage", {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})

    for n, (tid, text) in enumerate(items, 1):
        try:
            label, raw, usage, latency = call_model(
                base_url, api_key, model, text, timeout, retries, args.max_tokens)
        except Exception as e:
            print(f"[{n}/{len(items)}] {tid} 失败：{e}")
            continue
        prev.setdefault("items", []).append({
            "task_id": tid,
            "text": text,
            "label": label,
            "raw": raw,
            "usage": usage,
            "latency": round(latency, 3),
        })
        for k in total_usage:
            total_usage[k] = total_usage.get(k, 0) + int(usage.get(k, 0) or 0)
        prev["total_usage"] = total_usage
        prev["updated_at"] = datetime.now().isoformat(timespec="seconds")
        out_path.write_text(json.dumps(prev, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[{n}/{len(items)}] {tid} -> {label['sentiment']} "
              f"(conf={label['confidence']}, {latency:.1f}s, "
              f"tokens={usage.get('total_tokens', '?')})")
        time.sleep(args.sleep)

    print(f"\n完成。累计 token：{total_usage}")
    print(f"结果：{out_path}")


if __name__ == "__main__":
    main()
