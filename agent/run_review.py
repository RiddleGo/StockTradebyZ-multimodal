"""
run_review.py
~~~~~~~~~~~~~
多模态图表复评统一入口：根据 config/review.yaml 中的 provider 自动选择厂商并运行。

用法（在项目根目录执行）：
  python agent/run_review.py
  python agent/run_review.py --config config/review.yaml
  python -m agent.run_review --config config/review.yaml

环境变量：由 review.yaml 中 provider_options.api_key_env 指定，例如：
  Gemini: GEMINI_API_KEY
  OpenAI: OPENAI_API_KEY
  通义: DASHSCOPE_API_KEY
  智谱: ZHIPU_API_KEY
  等。
"""

import argparse
import sys
from pathlib import Path

# 项目根 = 含 config/ 与 agent/ 的目录
_ROOT = Path(__file__).resolve().parent.parent
_AGENT = Path(__file__).resolve().parent
for _p in (_ROOT, _AGENT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

try:
    from agent.review_config import load_review_config
    from agent.review_factory import create_reviewer
except ImportError:
    from review_config import load_review_config
    from review_factory import create_reviewer


def main():
    parser = argparse.ArgumentParser(description="多模态图表复评（多厂商统一入口）")
    parser.add_argument(
        "--config",
        default=str(_ROOT / "config" / "review.yaml"),
        help="统一配置文件路径",
    )
    parser.add_argument("--no-export-html", action="store_true", help="复评结束后不生成 HTML 报告")
    parser.add_argument("--no-open", action="store_true", help="生成报告后不在浏览器中打开")
    args = parser.parse_args()
    config = load_review_config(Path(args.config))
    if args.no_export_html:
        config["export_html"] = False
    if args.no_open:
        config["open_report"] = False
    reviewer = create_reviewer(config)
    print(f"[INFO] 使用厂商: {config.get('provider', '?')}, 模型: {config.get('provider_options', {}).get('model', '?')}")
    reviewer.run()


if __name__ == "__main__":
    main()
