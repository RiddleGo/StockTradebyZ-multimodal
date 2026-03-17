# 多模态图表复评 — 多厂商统一配置

本目录是对 [StockTradebyZ](https://github.com/SebastienZh/StockTradebyZ) 中「Gemini 看图打分」的抽象：**一份统一配置、多厂商可切换**，并已补全**完整选股流水线**（拉 K 线 → 量化初选 → 导出 K 线图 → 复评 → 推荐），可独立运行。

- **一键运行**：[完整流程（一键运行）](#完整流程一键运行)
- **API 与配置**：[配置与 API 清单（必读）](#配置与-api-清单必读)
- **仅跑复评**：[使用文档（仅复评）](#使用文档仅复评--快速开始)

---

## 完整流程（一键运行）

本仓库包含 5 步流水线，在项目根目录执行：

```bash
pip install -r requirements.txt
python run_all.py
```

| 步骤 | 说明 | 前置 |
|------|------|------|
| 1 | 拉取 K 线（Tushare） | 设置环境变量 `TUSHARE_TOKEN` |
| 2 | 量化初选（生成候选列表） | 需 `pipeline/stocklist.csv`（见下） |
| 3 | 导出候选 K 线图（日线 JPG） | 步骤 1、2 已跑通 |
| 4 | 多模态图表复评（生成 HTML 报告） | 配置 `config/review.yaml` 及对应 API Key |
| 5 | 打印推荐购买列表 | 读 `data/review/<日期>/suggestion.json` |

- 跳过步骤 1（已有 K 线）：`python run_all.py --skip-fetch`
- 从第 N 步开始：`python run_all.py --start-from 2`

### 前置文件

- **pipeline/stocklist.csv**：股票列表。从 [StockTradebyZ](https://github.com/SebastienZh/StockTradebyZ) 的 `pipeline/stocklist.csv` 复制到本仓库 `pipeline/` 下，否则步骤 1 会报错。
- **agent/prompt.md**：复评提示词，需从原仓库复制到本仓库 `agent/` 下或自备。

---

## 配置与 API 清单（必读）

全流程涉及的环境变量和配置文件集中如下，**按步骤配置即可**。

### 环境变量（API Key 等）

| 变量名 | 用途 | 使用步骤 | 获取方式 |
|--------|------|----------|----------|
| `TUSHARE_TOKEN` | Tushare 行情接口 | 步骤 1 拉 K 线 | [Tushare 官网](https://tushare.pro) 注册后获取 |
| `GEMINI_API_KEY` | Google Gemini 多模态 | 步骤 4 复评（当 `provider: gemini`） | Google AI Studio |
| `OPENAI_API_KEY` | OpenAI GPT-4o 等 | 步骤 4（当 `provider: openai`） | OpenAI 控制台 |
| `ANTHROPIC_API_KEY` | Claude | 步骤 4（当 `provider: anthropic`） | Anthropic 控制台 |
| `DASHSCOPE_API_KEY` | 通义千问 | 步骤 4（当 `provider: qwen`） | 阿里云 DashScope |
| `ZHIPU_API_KEY` | 智谱 GLM | 步骤 4（当 `provider: zhipu`） | 智谱开放平台 |
| `MOONSHOT_API_KEY` | 月之暗面 | 步骤 4（当 `provider: moonshot`） | 月之暗面开放平台 |
| `DEEPSEEK_API_KEY` | DeepSeek | 步骤 4（当 `provider: deepseek`） | DeepSeek 开放平台 |

步骤 4 使用的具体变量名由 **`config/review.yaml`** 里 `provider_options.api_key_env` 指定，上表为常用示例。设置后需**重新打开终端**生效。

**Windows PowerShell 示例（当前用户）：**
```powershell
[Environment]::SetEnvironmentVariable("TUSHARE_TOKEN", "你的TushareToken", "User")
[Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "你的GeminiKey", "User")
```

### 配置文件一览

| 文件 | 步骤 | 必填/可选 | 说明 |
|------|------|-----------|------|
| `config/fetch_kline.yaml` | 1 | 必填 | 日期范围 `start`/`end`、`stocklist` 路径、`out` 输出目录、`workers` 并发数 |
| `config/rules_preselect.yaml` | 2 | 可选 | 初选规则：`global.data_dir`/`output_dir`、B1/砖型图开关与参数 |
| `config/review.yaml` | 4 | 必填 | 复评入口：`provider`、`provider_options.model`、`api_key_env`；通义/智谱等需填 `base_url` |

**复评 API 配置（config/review.yaml 提炼）：**

- 选厂商：`provider: gemini | openai | anthropic | qwen | zhipu | moonshot | deepseek`
- 必填：`provider_options.model`、`provider_options.api_key_env`（环境变量名）
- 国内/兼容 OpenAI 的厂商需在 `provider_options` 下增加 `base_url`（见该文件内注释）

其余项（`candidates`、`kline_dir`、`prompt_path`、`request_delay`、`suggest_min_score` 等）已有默认值，一般无需修改。

项目根目录提供 **`.env.example`**，列出全部环境变量名，可复制后填入本地值作备忘（本程序从系统环境变量读取，不自动加载 `.env` 文件）。

---

## 使用文档（仅复评 / 快速开始）

若只运行**步骤 4（复评）**，可忽略完整流程，按下面操作。

### 前置条件

- 已安装 Python 3.9+
- 已有**步骤 1～3** 的结果：`data/raw/*.csv`、`data/candidates/candidates_latest.json`、`data/kline/<日期>/*.jpg`（可从原 StockTradebyZ 跑出，或本仓库执行步骤 1～3）
- 已获取任意一家多模态 API 的 Key（如 Gemini / OpenAI / 通义 / 智谱等）

### 第一步：合并到 StockTradebyZ 项目

将本仓库的以下内容合并到已克隆的 StockTradebyZ 项目根目录：

- `config/review.yaml` → 放到项目的 `config/` 下
- `agent/` 目录下所有文件 → 覆盖或合并到项目的 `agent/` 下

**提示词文件 `agent/prompt.md`**：复评时会让模型按该提示词对 K 线图打分。本仓库不包含该文件，需从 [StockTradebyZ](https://github.com/SebastienZh/StockTradebyZ) 的 `agent/prompt.md` 复制到本项目的 `agent/` 下，或按原项目格式自备。合并到 StockTradebyZ 时无需额外操作（原项目已有）。

若只使用本仓库独立运行（不合并），还需自行准备：`data/candidates/candidates_latest.json`、`data/kline/<日期>/` 下的 K 线图，以及上述 `agent/prompt.md`。

### 第二步：安装依赖

在项目根目录执行：

```bash
pip install -r requirements.txt
```

`requirements.txt` 中列出了 PyYAML 与各厂商 SDK。若只使用一家厂商，可只安装基础与对应 SDK 以减小依赖，例如仅用 Gemini 时：

```bash
pip install PyYAML google-genai
```

### 第三步：配置与环境变量

1. 编辑 `config/review.yaml`，将 `provider` 设为要使用的厂商（如 `gemini`、`openai`）。
2. 在 `provider_options` 中填写该厂商的 `model`、`api_key_env`（环境变量名）。
3. 在系统中设置对应的 API Key 环境变量，例如：

   **Windows PowerShell（当前用户）：**
   ```powershell
   [Environment]::SetEnvironmentVariable("GEMINI_API_KEY", "你的Key", "User")
   ```
   设置后需**重新打开终端**才会生效。

### 第四步：运行复评

在项目根目录执行：

```bash
python agent/run_review.py
```

- 程序会按配置调用多模态 API 对候选股票逐只看图打分，结束后**自动生成 HTML 报告并在浏览器中打开**。
- 报告路径：`data/review/<选股日期>/report.html`。

### 第五步：查看结果

- **浏览器**：打开自动弹出的报告页，可查看推荐列表、日线图、一键复制代码、导出 CSV；点击某行可展开该只股票的维度得分与推理详情。
- **终端**：控制台会打印每只股票的评审进度与最终推荐数量。
- **JSON**：`data/review/<日期>/suggestion.json` 为汇总结果，`data/review/<日期>/<代码>.json` 为单股详情。

### 命令行速查

| 命令 | 说明 |
|------|------|
| `python agent/run_review.py` | 执行复评（默认生成并打开 HTML 报告） |
| `python agent/run_review.py --check` | 仅检查配置与候选文件是否存在，不调 API |
| `python agent/run_review.py --no-export-html` | 复评但不生成 HTML |
| `python agent/run_review.py --no-open` | 生成 HTML 但不自动打开浏览器 |
| `python agent/export_review_html.py` | 对已有复评结果单独导出 HTML 报告 |
| `python agent/export_review_html.py --open` | 导出报告并在浏览器中打开 |

---

## 用法（与 StockTradebyZ 集成）

1. **将本目录内容合并到 StockTradebyZ 项目**  
   - 把 `config/review.yaml` 放到项目 `config/` 下（可保留原 `gemini_review.yaml` 作备份）。  
   - 把 `agent/` 下新增/修改的文件覆盖或合并到项目 `agent/`。

2. **统一入口（推荐）**  
   在项目根目录执行：
   ```bash
   python agent/run_review.py
   python agent/run_review.py --config config/review.yaml
   ```
   - 会根据 `config/review.yaml` 里的 `provider` 自动选择厂商并跑复评。  
   - **默认**：复评结束后自动生成 HTML 报告并在浏览器打开。  
   - 仅检查配置与候选文件：`python agent/run_review.py --check`  
   - 不生成报告 / 不打开浏览器：`--no-export-html`、`--no-open`

3. **切换厂商**  
   编辑 `config/review.yaml`：
   ```yaml
   provider: openai   # 或 anthropic / qwen / zhipu / moonshot / deepseek
   provider_options:
     model: gpt-4o
     api_key_env: OPENAI_API_KEY
     # 国内或兼容 OpenAI 的厂商可加 base_url
     # base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
   ```
   并设置对应环境变量（如 `OPENAI_API_KEY`）。

## 支持的 provider

| provider     | 说明           | 环境变量示例        | 依赖           |
|-------------|----------------|---------------------|----------------|
| gemini      | Google Gemini  | GEMINI_API_KEY      | google-genai   |
| openai      | OpenAI GPT-4o 等 | OPENAI_API_KEY    | openai         |
| anthropic   | Claude         | ANTHROPIC_API_KEY   | anthropic      |
| qwen        | 通义千问（兼容 OpenAI 接口） | DASHSCOPE_API_KEY | openai + base_url |
| zhipu       | 智谱 GLM（兼容 OpenAI 接口） | ZHIPU_API_KEY    | openai + base_url |
| moonshot    | 月之暗面       | MOONSHOT_API_KEY    | openai + base_url |
| deepseek    | DeepSeek       | DEEPSEEK_API_KEY    | openai + base_url |

未安装某厂商 SDK 时，仅在使用该 provider 时会报错；其他厂商不受影响。

## 配置说明（config/review.yaml）

- **prompt_path**：提示词文件路径，默认 `agent/prompt.md`。需与 [StockTradebyZ 的 prompt 格式](https://github.com/SebastienZh/StockTradebyZ/blob/main/agent/prompt.md) 兼容（含趋势/位置/量价/异动等维度与 JSON 输出要求）。

- **通用**：`candidates`、`kline_dir`、`output_dir`、`prompt_path`、`request_delay`、`skip_existing`、`suggest_min_score` 与原先含义一致。  
- **provider**：必填，取值见上表。  
- **provider_options**：  
  - 通用：`model`、`api_key_env`、`temperature`、`max_tokens`。  
  - 仅 OpenAI 及兼容接口：`base_url`（通义/智谱/月之暗面/DeepSeek 等需填写对应 base_url）。

原 `run_all.py` 第 4 步可改为调用统一入口，例如：
```python
_run("4/4 多模态图表复评（run_review）", [PYTHON, str(ROOT / "agent" / "run_review.py"), "--config", str(ROOT / "config" / "review.yaml")])
```

---

## HTML 报告展示

复评结果除终端打印和 JSON 外，可**生成 HTML 报告**，在浏览器中直接打开查看：

- **复评时自动生成**（默认已开启）：运行 `python agent/run_review.py` 结束后会自动生成报告并打开浏览器。若需关闭：`--no-export-html` 或 `--no-open`。

- **对已有结果单独导出**：
  ```bash
  python agent/export_review_html.py
  python agent/export_review_html.py --suggestion data/review/2026-03-17/suggestion.json -o data/review/2026-03-17/report.html --open
  ```

报告路径默认为 `data/review/<选股日期>/report.html`，内容包含：

- 选股日期、评审统计、**生成时间**
- 推荐列表表格：排名 / 代码 / 总分 / 信号 / 研判 / 日线图 / 备注（**小屏可横向滚动**）
- **一键复制推荐代码**（换行分隔，便于粘贴到交易软件）、**导出 CSV**
- **浅色/深色主题切换**（按钮在工具栏右侧，偏好会保存到本地）
- 点击表格行可展开/折叠该只股票的**维度得分与推理详情**（美化展示，非原始 JSON）
- 未达门槛代码、**免责声明**

日线图默认内嵌进 HTML，单文件即可拷贝或分享；加 `--no-embed` 则改为相对路径引用（适合本地目录不变时打开）。

---

## 常见问题

| 现象 | 处理 |
|------|------|
| 报错「环境变量 xxx 未设置」 | 在系统或当前终端设置对应 API Key（如 `GEMINI_API_KEY`），设置后需重开终端。 |
| 报错「候选列表文件不存在」 | 先完成 StockTradebyZ 流程中的「量化初选」和「导出 K 线图」，再运行复评。 |
| 单只股票评分失败 | 默认会自动重试 1 次；若仍失败可检查网络或 API 限流，必要时调大 `request_delay`。 |
| 不想每次打开浏览器 | 使用 `python agent/run_review.py --no-open`，或在 `review.yaml` 中设 `open_report: false`。 |
