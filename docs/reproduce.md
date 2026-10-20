# 复现指南

环境：Windows 11，Python 3.12，Label Studio 1.23.2。
分析脚本跨平台；语音生成依赖 Windows 的中文 TTS 语音。

## 1. 安装

```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

国内网络较慢时：

```bat
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple
```

## 2. 启动服务

两个窗口分别运行，或直接双击 `.bat`：

```bat
.venv\Scripts\label-studio.exe start --port 8080 --data-dir "%~dp0ls_data" --enable-legacy-api-token
.venv\Scripts\python.exe scripts\serve_data.py 8000 "%~dp0data"
```

打开 http://localhost:8080，创建管理员账号。
进入 **Account & Settings → Access Token**，把 token 保存到项目根目录的 `.ls_token`（单行纯文本）。这个文件已被 `.gitignore` 忽略。

## 3. 生成任务文件

```bat
.venv\Scripts\python.exe scripts\prepare_text.py
.venv\Scripts\python.exe scripts\prepare_images.py
.venv\Scripts\python.exe scripts\generate_audio.py
```

- 文本：24 条，固定写在 `scripts/prepare_text.py`。
- 图像：读取 `data/images/`，仓库已带 6 张。
- 语音：用 Windows 中文语音合成生成 10 条 wav，并写入受控 ASR 错误；wav 不提交。

## 4. 建项目

```bat
.venv\Scripts\python.exe scripts\setup_projects.py
```

脚本会创建 3 个项目、导入任务、设置 overlap（文本/图像 3，语音 1）。项目已存在时跳过创建，任务已导入时跳过导入。

脚本不创建用户。账号需要在 Label Studio 界面注册：

- 人工标注：`ann1@local.test`
- 模型标注：`model-deepseek@local.test`、`model-glm@local.test`
- 需要在每个项目的 **Settings → Members** 中加入这些账号

模型账号的 token 写入 `.ls_tokens.json`：

```json
{
  "model-deepseek@local.test": "<token>",
  "model-glm@local.test": "<token>"
}
```

该文件同样被 `.gitignore` 忽略。

`data/annotators.json` 是本次运行的 Label Studio 用户 ID 到邮箱的映射。重建数据库后 ID 会变化，需要同步更新这个文件，否则分析结果里的标注员会显示为数字。

## 5. 标注

文本：情感、方面、质量标记、置信度。
图像：RectangleLabels 拖框，选择类别。
语音：回听并修正 ASR 文本，选择错误类型与可懂度。

试标样本不纳入正式统计。正式标注要求同一批任务由 3 个账号独立完成。

## 6. 导出

界面导出：项目 → Export → JSON → 勾选所有标注。

或用 API：

```bat
curl -H "Authorization: Token <TOKEN>" "http://localhost:8080/api/projects/1/export?exportType=JSON&download_all_tasks=true" -o exports/text.json
curl -H "Authorization: Token <TOKEN>" "http://localhost:8080/api/projects/2/export?exportType=JSON&download_all_tasks=true" -o exports/image.json
curl -H "Authorization: Token <TOKEN>" "http://localhost:8080/api/projects/3/export?exportType=JSON&download_all_tasks=true" -o exports/audio.json
```

## 7. 分析

```bat
.venv\Scripts\python.exe scripts\analyze.py --text exports\text.json --image exports\image.json --audio exports\audio.json
```

输出：

- `reports/metrics.json`
- `reports/disagreements_text.csv`
- `reports/audio_cer.csv`
- `reports/gold_text.csv`（裁决后生成）

裁决：在 `disagreements_text.csv` 中填写 `final_label` 和 `reason`，再运行 `scripts/compare_models.py`。

## 8. 模型标注

`.env.example` 列出了 4 个 provider 的配置：`ark`、`deepseek`、`tokenhub`、`dashscope`。
复制为 `.env` 并填入自己的 key。

```bat
.venv\Scripts\python.exe scripts\llm_annotate.py --provider dashscope --model glm-5.3
.venv\Scripts\python.exe scripts\push_llm_annotations.py --run data\text\llm_runs\dashscope-glm-5.3.json --user model-glm@local.test
.venv\Scripts\python.exe scripts\compare_models.py
```

## 9. 生成幻灯片

```bat
.venv\Scripts\python.exe scripts\make_ppt.py
```

输出 `docs/slides/multimodal-annotation-qc.pptx`。PDF 需要本机 PowerPoint 导出，仓库已带一份。

## 说明

- `ls_data/`、`exports/`、`.env`、`.ls_token`、`.ls_tokens.json` 都不提交。
- 音频 wav 不提交，运行 `generate_audio.py` 可重建。
- 图像来自 Unsplash，见 `data/images/ATTRIBUTION.md`。
- 文本样本来自 waimai_10k 与人工边界样本，任务固定写在脚本里，不依赖原始数据集。
