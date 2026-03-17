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
import os
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


def _check_config(config: dict) -> bool:
    """启动前检查：候选文件存在、API Key 已设置。返回 True 表示通过。"""
    candidates_path = config.get("candidates")
    if candidates_path is None or not Path(candidates_path).exists():
        print("[ERROR] 候选列表文件不存在，请先完成「量化初选」并导出图表。", file=sys.stderr)
        print(f"  期望路径: {candidates_path}", file=sys.stderr)
        return False
    opts = config.get("provider_options") or {}
    api_key_env = opts.get("api_key_env", "")
    if not api_key_env:
        print("[ERROR] 配置中未指定 api_key_env，无法调用 API。", file=sys.stderr)
        return False
    api_key = os.environ.get(api_key_env, "")
    if not api_key or api_key.strip() == "":
        print(f"[ERROR] 环境变量 {api_key_env} 未设置或为空，请先设置后再运行。", file=sys.stderr)
        print("  Windows PowerShell: [Environment]::SetEnvironmentVariable(\"" + api_key_env + "\", \"你的Key\", \"User\")", file=sys.stderr)
        print("  设置后请重新打开终端。", file=sys.stderr)
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="多模态图表复评（多厂商统一入口）")
    parser.add_argument(
        "--config",
        default=str(_ROOT / "config" / "review.yaml"),
        help="统一配置文件路径",
    )
    parser.add_argument("--no-export-html", action="store_true", help="复评结束后不生成 HTML 报告")
    parser.add_argument("--no-open", action="store_true", help="生成报告后不在浏览器中打开")
    parser.add_argument("--check", action="store_true", help="仅检查配置与候选文件，不执行复评")
    args = parser.parse_args()
    config = load_review_config(Path(args.config))
    if args.no_export_html:
        config["export_html"] = False
    if args.no_open:
        config["open_report"] = False
    if not _check_config(config):
        sys.exit(1)
    if args.check:
        print("[OK] 配置与候选文件检查通过。")
        print(f"  厂商: {config.get('provider')}, 模型: {config.get('provider_options', {}).get('model')}")
        return
    reviewer = create_reviewer(config)
    print(f"[INFO] 使用厂商: {config.get('provider', '?')}, 模型: {config.get('provider_options', {}).get('model', '?')}")
    reviewer.run()


if __name__ == "__main__":
    main()
