# 多模态数据标注与质检 · 最小可运行项目

用 Label Studio 跑通一条真实的数据质检链路：

**标注规范 → 试标校准 → 多人独立标注 → 交叉复核 → IAA 指标 → 分歧裁决 → 质检报告**

> 定位：个人实训 / 作品集项目，不写成“线上兼职”。所有数字都来自你实际跑出来的结果，面试可逐条讲、可现场演示。

## 0. 本轮结果（2026-10-20）

| 模态 | 实际完成 | 关键指标 |
|---|---|---|
| 文本 | 24 条 × 3 路（人工 + DeepSeek-V4-Flash + GLM-5.3） | 两两一致率 84.1%；Fleiss κ 0.756；α 0.760；16/21 全体一致 |
| 图像 | 6 张，52 个框（ann1 单人） | 单人完成，未做 IAA |
| 语音 | 10 条转写质检（ann1） | CER 5.5% → 1.1%，相对下降 80.2% |

人工 vs 模型（21 条裁决金标）：DeepSeek 100%、GLM 95.2%、人工 76.2%；人工 5 条错误全部落在边界样本。

配套材料：

- PPT：`reports/多模态数据标注与质检_评测文档.pptx`（PDF 同名）
- 报告：`reports/质检报告.md`
- 模型对比：`reports/model_comparison.md`

> 三路中的两路是 LLM，不是三名真人。报告统一称“三路一致性”，不冒充人类 IAA。

---

## 1. 当前环境（已就绪）

| 项 | 值 |
|---|---|
| Label Studio | 1.23.2，装在 `.venv/` |
| 地址 | http://localhost:8080 |
| 数据服务 | http://localhost:8000（提供图片/音频） |
| 项目 | 1 文本、2 图像、3 语音 |
| 管理员 | `admin@local.test` / `Admin123!` |
| 人工标注 | `ann1@local.test` / `Ann1pass!` |
| 模型标注 | `model-deepseek@local.test`、`model-glm@local.test`（结果由脚本写入） |
| 预留账号 | `ann2@local.test`、`ann3@local.test`（用于补第二人复标） |

重新启动（如果电脑重启）：

```bat
start_label_studio.bat
start_data_server.bat
```

两个黑窗口都不要关。浏览器打开 http://localhost:8080。

---

## 2. 本次实际完成的范围

| 项目 | 完成量 | 谁标 | 正式集 |
|---|---|---|---|
| 01 文本 | T01–T24 全部 | ann1 + DeepSeek-V4-Flash + GLM-5.3 | T04–T24（21 条） |
| 02 图像 | I01–I06 全部 | ann1 | I02–I06（5 张） |
| 03 语音 | A01–A10 全部 | ann1 | A02–A10（9 条） |

说明：

- 文本 T01–T03 是试标轮，分析脚本默认不计入正式一致性。
- 三路标注 = 1 名人工 + 2 个模型；不是三名真人。
- 图像只有 ann1 一人，本轮无法算 IAA；要补第二人复标，用 `ann2@local.test` 再标 5 张正式图。
- 语音只有 1 人标，不做 IAA，做 CER（修正前后对比）。

---

## 3. 标注操作

### 3.1 登录 / 切换账号

1. 打开 http://localhost:8080
2. 人工标注用 `ann1@local.test` 登录。
3. 模型账号不需要登录：`scripts/push_llm_annotations.py` 通过 API 写入。
4. 需要补第二人复标时，用 `ann2@local.test` / `ann3@local.test`，不要互相看结果；独立标注是 IAA 有意义的前提。

### 3.2 文本项目（01）

1. 点项目 → **Label All Tasks**（或 Start Labeling）。
2. 每条依次选择：
   - 情感（必填）：正面 / 负面 / 中性 / 无法判断
   - 方面（可多选）：口味 / 配送 / 价格 / 服务 / 卫生 / 包装 / 无
   - 质量标记（可多选）：广告推广 / 含隐私信息 / 表述不清 / 疑似模板或刷单 / 无
   - 置信度（必填）：5 非常确定 → 1 纯猜测
3. 点 **Submit**，自动进入下一条。
4. 标完 24 条；只做快速验证时至少标到 T12（T04–T12 为 9 条正式集）。

判定规则见 `标注规范.md`。遇到拿不准的，按规范判断，置信度如实选 3 或 2。

### 3.3 图像项目（02）

1. 点项目 → Label All Tasks。
2. 左侧工具栏选 **RectangleLabels**（方框图标）。
3. 拖框圈住目标 → 选类别（人/动物/车辆/食物/其他）。
4. 每个目标一个框；同一目标不要重复框。
5. 图片质量单选（清晰可标 / 部分遮挡 / 模糊过暗 / 无可标目标）。
6. Submit，标完 6 张。

### 3.4 语音项目（03）

只用 `ann1` 登录。

1. 点项目 → Label All Tasks。
2. 播放音频，对照页面上方的 `asr_text`。
3. 在文本框里输出**修正后的完整转写**（只改错听处，不润色）。
4. 勾选错误类型（多字/漏字/错字/专有名词/标点/无错误）。
5. 选可懂度，Submit，标完 10 条。

---

## 4. 导出

用管理员账号 `admin@local.test` 登录：

1. 进入项目 → 右上角 **Export**。
2. 格式选 **JSON**。
3. 勾选 **Export all annotations**（导出所有标注员的标注，不是只导最新一条）。
4. 下载后放到 `exports/`，命名为：
   - `exports/text.json`
   - `exports/image.json`
   - `exports/audio.json`

> 如果导出文件里每个任务只有一条 annotation，说明没选“all annotations”，多人一致性会算不出来。

---

## 5. 跑分析

在项目根目录打开终端：

```bat
.venv\Scripts\python.exe scripts\analyze.py --text exports\text.json --image exports\image.json --audio exports\audio.json
```

输出到 `reports/`：

| 文件 | 内容 |
|---|---|
| `iaa_summary.md` | 自动汇总（一致率、κ、α、F1、CER） |
| `metrics.json` | 机器可读指标 |
| `disagreements_text.csv` | 文本分歧清单，填 `final_label` / `reason` 做裁决 |
| `label_noise.csv` | 与原数据集标签不一致的样本 |
| `image_iaa.csv` | 逐图/逐标注员对的框匹配指标 |
| `audio_cer.csv` | 逐条 CER 修正前后对比 |

只想先看文本：

```bat
.venv\Scripts\python.exe scripts\analyze.py --text exports\text.json
```

### 5.1 人工 vs 模型评测

模型标注脚本支持 4 个 provider：

| provider | 读取的 env | 本轮用途 |
|---|---|---|
| `ark` | `ARK_*` | 火山方舟（需要 `ark-` 开头的 key） |
| `deepseek` | `GEN_*` | DeepSeek 官方 |
| `tokenhub` | `TOKENHUB_*` | 腾讯 TokenHub |
| `dashscope` | `DASHSCOPE_*` | 阿里百炼 |

命令示例：

```bat
.venv\Scripts\python.exe scripts\llm_annotate.py --provider tokenhub --model deepseek-v4-flash --env-file "D:\cursor_env\rag-chinese-qa\repo\.env"
.venv\Scripts\python.exe scripts\llm_annotate.py --provider dashscope --model glm-5.3
.venv\Scripts\python.exe scripts\push_llm_annotations.py --run data\text\llm_runs\tokenhub-deepseek-v4-flash.json --user model-deepseek@local.test
.venv\Scripts\python.exe scripts\push_llm_annotations.py --run data\text\llm_runs\dashscope-glm-5.3.json --user model-glm@local.test
.venv\Scripts\python.exe scripts\compare_models.py
```

`compare_models.py` 输出：

- `reports/model_comparison.md`：准确率、每类 P/R/F1、混淆矩阵、置信度校准、token/延迟
- `reports/model_comparison.csv`：逐条预测与金标

再生成 PPT：

```bat
.venv\Scripts\python.exe scripts\make_ppt.py
```

> key 只放在 `.env` / `--env-file` 指向的本地文件；不要提交、不要贴到公开仓库。

---

## 6. 裁决与报告

1. 打开 `reports/disagreements_text.csv`，逐条填：
   - `final_label`：裁决后的最终标签
   - `reason`：依据规范哪一条 / 为什么这样判
2. 把分歧归因：规范歧义 / 任务本身歧义 / 标注员疏忽 / 原数据标签噪声。
3. 按 `reports/质检报告模板.md` 写 3–5 页报告。
4. 报告里必须写清楚样本量（本轮正式集 21 条，κ 只能当流程演示，不要吹成稳定结论）。

---

## 7. GitHub

已推送：https://github.com/lhh737/multimodal-annotation-qc

当前为 **private**。作品集要公开时：

```bat
gh repo edit lhh737/multimodal-annotation-qc --visibility public --accept-visibility-change-consequences
```

注意：

- `.env`、`.ls_token`、`.ls_tokens.json`、`ls_data/`、`exports/`、`.venv/` 已在 `.gitignore` 中，不会被推上去。
- 图片来自 Unsplash，见 `data/images/ATTRIBUTION.md`。
- `waimai_10k.csv` 原始数据未提交；文本任务已固定在 `data/text/tasks.json`。
- 推之前可用 `git grep --cached -nE "sk-|ARK_API_KEY=|TOKENHUB_API_KEY="` 再扫一遍密钥。

---

## 8. 文件结构

```
configs/                 Label Studio 标注界面 XML
data/text/               24 条文本任务 + 元数据
data/images/             6 张图 + 任务 + 来源说明
data/audio/              10 条 TTS 语音 + ASR 文本 + 任务
scripts/prepare_*.py     生成任务
scripts/generate_audio.py 生成语音
scripts/setup_projects.py 一键建项目/导入/设 overlap
scripts/analyze.py       算 κ / α / F1 / CER
标注规范.md               v1.0 规范（试标后改 v1.1）
reports/                 分析输出 + 报告模板
```

---

## 9. 常见问题

**打不开 localhost:8080**：看 `start_label_studio.bat` 窗口是否还在跑；端口被占用就改 `--port 8081`。

**图片/音频不显示**：确认 `start_data_server.bat` 在跑，浏览器直接打开 `http://localhost:8000/images/01_pug.jpg` 应能看到图。

**Submit 后没有下一条**：可能该任务已被当前账号标过，或 overlap 已满；换账号或看 Data Manager。

**导出的 JSON 里没有别人的标注**：导出时没勾 “Export all annotations”。

**κ 算出来是 —**：正式集任务太少，或某些任务只有一个人标。先保证三个人标的是同一批任务。

**改了规范怎么办**：在 `标注规范.md` 第 0 节加一行版本记录，不要口头改规则。
