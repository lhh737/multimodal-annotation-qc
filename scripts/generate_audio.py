# -*- coding: utf-8 -*-
"""生成语音转写质检任务：Windows 中文 TTS + 模拟 ASR 输出。

用法：
    python scripts/generate_audio.py            # 只生成缺失的 wav
    python scripts/generate_audio.py --force    # 全部重新生成

输出：
    data/audio/A01.wav ... A10.wav
    data/audio/tasks.json   -> 导入 Label Studio（含 asr_text）
    data/audio/items.csv    -> 分析用（gold / asr / 基线 CER）

说明：语音由 Windows 内置中文语音合成，ASR 文本为人工构造的受控错误。
这是一套完全可复现的“转写质检”练习数据，不是真实商业数据。
"""
import argparse
import csv
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "audio"
OUT.mkdir(parents=True, exist_ok=True)

# (item_id, split, gold, asr_hypothesis)
ITEMS = [
    ("A01", "pilot",
     "您好，您点的餐已经到楼下了，请到一号门取餐。",
     "您点的餐已经到楼下了，请到乙号门取餐。"),
    ("A02", "formal",
     "这家店的招牌菜是红烧牛肉面，分量很足，但是价格有点贵。",
     "这家店的招牌菜是红烧牛肉棉，分量很足，但是价格有点贵。"),
    ("A03", "formal",
     "请在周五下午三点前把报告发到我的邮箱。",
     "请在周五下午三点前把报告发到我的油香。"),
    ("A04", "formal",
     "今天天气不错，我们一起去公园散步吧。",
     "今天天气不错，我们一起去公元散步吧。"),
    ("A05", "formal",
     "订单编号是甲二三五七，请在二十四小时内完成支付。",
     "订单编号是假二三五七，请在二十四小时内完成支付。"),
    ("A06", "formal",
     "他说他马上就到，结果等了半个小时还没来。",
     "他说他马上就到，结果等了半小时还没来。"),
    ("A07", "formal",
     "这款耳机的降噪效果很好，续航大约三十个小时。",
     "这款耳机的降噪效果很好，续航大约三十小时。"),
    ("A08", "formal",
     "请把空调温度调到二十六度，谢谢。",
     "请把空调温度调到二十六渡，谢谢。"),
    ("A09", "formal",
     "附近的地铁站是四号线人民广场站，从二号出口出去最近。",
     "附近的地铁站是四号线人民广场站，从二号出口出去最近。"),
    ("A10", "formal",
     "不好意思，您拨打的电话暂时无法接通，请稍后再拨。",
     "不好意思，您拨打的电话暂时无法接通，请稍后在拨。"),
]

PUNCT = set("，。！？、；：“”‘’（）《》…—,.!?;:\"'()[]{}<>-· \t\n\r")
CN_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
             "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def cn_num_to_arabic(seq: str) -> str:
    if not any(u in seq for u in CN_UNITS):
        return "".join(str(CN_DIGITS[c]) for c in seq if c in CN_DIGITS)
    total, current = 0, 0
    for ch in seq:
        if ch in CN_DIGITS:
            current = CN_DIGITS[ch]
        elif ch in CN_UNITS:
            total += (current or 1) * CN_UNITS[ch]
            current = 0
    total += current
    return str(total)


def normalize(s: str) -> str:
    s = re.sub(r"[零一二两三四五六七八九十百千]+",
               lambda m: cn_num_to_arabic(m.group()), s)
    return "".join(ch for ch in s if ch not in PUNCT)


def cer(ref: str, hyp: str) -> float:
    """字符错误率 = (替换 + 删除 + 插入) / 参考字符数。"""
    r, h = list(normalize(ref)), list(normalize(hyp))
    if not r:
        return 0.0 if not h else 1.0
    prev = list(range(len(h) + 1))
    for i, rc in enumerate(r, 1):
        cur = [i]
        for j, hc in enumerate(h, 1):
            cur.append(min(
                prev[j] + 1,              # 删除
                cur[j - 1] + 1,           # 插入
                prev[j - 1] + (rc != hc), # 替换/匹配
            ))
        prev = cur
    return prev[-1] / len(r)


PS_TEMPLATE = r"""
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
$v = $s.GetInstalledVoices() | Where-Object { $_.VoiceInfo.Culture.Name -like 'zh*' } | Select-Object -First 1
if ($v) { $s.SelectVoice($v.VoiceInfo.Name) }
$s.Rate = -1
$s.SetOutputToWaveFile($env:TTS_OUT)
$s.Speak($env:TTS_TEXT)
$s.Dispose()
"""


def synth(text: str, wav: Path):
    env = os.environ.copy()
    env["TTS_TEXT"] = text
    env["TTS_OUT"] = str(wav)
    r = subprocess.run(
        ["powershell", "-NoProfile", "-Command", PS_TEMPLATE],
        env=env, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if r.returncode != 0 or not wav.exists():
        raise RuntimeError(f"TTS 失败：{wav.name}\n{r.stderr[-800:]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true", help="重新生成所有 wav")
    args = ap.parse_args()

    tasks, rows = [], []
    for item_id, split, gold, asr in ITEMS:
        wav = OUT / f"{item_id}.wav"
        if args.force or not wav.exists():
            synth(gold, wav)
        url = f"http://localhost:8000/audio/{item_id}.wav"
        tasks.append({"data": {
            "item_id": item_id,
            "audio": url,
            "asr_text": asr,
        }})
        rows.append([item_id, split, gold, asr, f"{cer(gold, asr):.4f}"])

    (OUT / "tasks.json").write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with open(OUT / "items.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "split", "gold", "asr", "baseline_cer"])
        w.writerows(rows)

    base = sum(float(r[-1]) for r in rows) / len(rows)
    print(f"已生成 {len(ITEMS)} 条语音任务（试标 1 条，正式 {len(ITEMS)-1} 条）")
    print(f"ASR 基线平均 CER = {base:.2%}")
    print(f"导入文件：{OUT / 'tasks.json'}")
    print("确认数据服务器已启动，然后在浏览器试听任一 URL。")


if __name__ == "__main__":
    main()
