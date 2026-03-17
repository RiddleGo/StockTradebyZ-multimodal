# 多模态图表复评 — 多厂商统一配置

本目录是对 [StockTradebyZ](https://github.com/SebastienZh/StockTradebyZ) 中「Gemini 看图打分」的抽象：**一份统一配置、多厂商可切换**，便于支持市面上所有多模态模型。

## 用法

1. **将本目录内容合并到 StockTradebyZ 项目**  
   - 把 `config/review.yaml` 放到项目 `config/` 下（可保留原 `gemini_review.yaml` 作备份）。  
   - 把 `agent/` 下新增/修改的文件覆盖或合并到项目 `agent/`。

2. **统一入口（推荐）**  
   在项目根目录执行：
   ```bash
   python agent/run_review.py
   python agent/run_review.py --config config/review.yaml
   ```
   会根据 `config/review.yaml` 里的 `provider` 自动选择对应厂商并跑复评。

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

- **复评时顺带生成**（推荐）：
  ```bash
  python agent/run_review.py --export-html
  python agent/run_review.py --export-html --open   # 生成并在浏览器打开
  ```
  或在 `config/review.yaml` 中设置 `export_html: true`、`open_report: true`。

- **对已有结果单独导出**：
  ```bash
  python agent/export_review_html.py
  python agent/export_review_html.py --suggestion data/review/2026-03-17/suggestion.json -o data/review/2026-03-17/report.html --open
  ```

报告路径默认为 `data/review/<选股日期>/report.html`，内容包含：选股日期、评审统计、推荐列表（排名/代码/总分/信号/研判/日线图/备注）、未达门槛代码。日线图默认内嵌进 HTML，单文件即可拷贝或分享；加 `--no-embed` 则改为相对路径引用（适合本地目录不变时打开）。
