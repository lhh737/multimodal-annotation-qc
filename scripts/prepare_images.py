# -*- coding: utf-8 -*-
"""把 data/images/ 下的图片生成为 Label Studio 任务。

用法：
  1. 把 6 张左右照片放进 data/images/（jpg/jpeg/png/webp）
  2. 先启动数据服务器：start_data_server.bat（端口 8000）
  3. python scripts/prepare_images.py

输出：
  data/images/tasks.json  -> 导入 Label Studio
  data/images/items.csv   -> 分析用
"""
import csv
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
IMG_DIR = ROOT / "data" / "images"
BASE_URL = "http://localhost:8000/images"
EXTS = {".jpg", ".jpeg", ".png", ".webp"}


def main():
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in IMG_DIR.iterdir() if p.suffix.lower() in EXTS)
    if len(files) < 4:
        raise SystemExit(
            f"data/images/ 里只有 {len(files)} 张图。至少放 4 张，建议 6 张。\n"
            "拍照建议：桌面、餐桌、街景、宠物、货架、人物合影各一张。"
        )

    rows = []
    tasks = []
    for i, p in enumerate(files, 1):
        item_id = f"I{i:02d}"
        split = "pilot" if i <= 1 else "formal"
        url = f"{BASE_URL}/{quote(p.name)}"
        tasks.append({"data": {"item_id": item_id, "image": url, "filename": p.name}})
        rows.append([item_id, split, p.name, url])

    (IMG_DIR / "tasks.json").write_text(
        json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    with open(IMG_DIR / "items.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(["item_id", "split", "filename", "url"])
        w.writerows(rows)

    n_pilot = min(1, len(files))
    print(f"已生成 {len(files)} 条图像任务：试标 {n_pilot} 条，正式 {len(files)-n_pilot} 条")
    print(f"导入文件：{IMG_DIR / 'tasks.json'}")
    print("确认数据服务器已启动，然后在浏览器打开任一 URL 检查图片是否能显示。")


if __name__ == "__main__":
    main()
