"""
review_config.py
~~~~~~~~~~~~~~~~
加载多模态复评统一配置（config/review.yaml），解析路径与 provider_options。
"""

from pathlib import Path
from typing import Any, Dict

import yaml

_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = _ROOT / "config" / "review.yaml"

# 通用默认（与厂商无关）
COMMON_DEFAULTS: Dict[str, Any] = {
    "candidates": "data/candidates/candidates_latest.json",
    "kline_dir": "data/kline",
    "output_dir": "data/review",
    "prompt_path": "agent/prompt.md",
    "request_delay": 5,
    "skip_existing": False,
    "suggest_min_score": 4.0,
    "export_html": True,
    "open_report": True,
    "retry_on_fail": 1,
}

# 各厂商 provider_options 默认
PROVIDER_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "gemini": {"model": "gemini-2.0-flash", "api_key_env": "GEMINI_API_KEY", "temperature": 0.2, "max_tokens": 4096},
    "openai": {"model": "gpt-4o", "api_key_env": "OPENAI_API_KEY", "temperature": 0.2, "max_tokens": 4096},
    "anthropic": {"model": "claude-sonnet-4-20250514", "api_key_env": "ANTHROPIC_API_KEY", "temperature": 0.2, "max_tokens": 4096},
    "qwen": {"model": "qwen-vl-max", "api_key_env": "DASHSCOPE_API_KEY", "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1", "temperature": 0.2, "max_tokens": 4096},
    "zhipu": {"model": "glm-4v", "api_key_env": "ZHIPU_API_KEY", "base_url": "https://open.bigmodel.cn/api/paas/v4", "temperature": 0.2, "max_tokens": 4096},
    "moonshot": {"model": "moonshot-v1", "api_key_env": "MOONSHOT_API_KEY", "base_url": "https://api.moonshot.cn/v1", "temperature": 0.2, "max_tokens": 4096},
    "deepseek": {"model": "deepseek-chat", "api_key_env": "DEEPSEEK_API_KEY", "base_url": "https://api.deepseek.com/v1", "temperature": 0.2, "max_tokens": 4096},
}


def _resolve_path(path_like: str | Path, base_dir: Path = _ROOT) -> Path:
    p = Path(path_like)
    return p if p.is_absolute() else (base_dir / p)


def load_review_config(config_path: Path | None = None) -> Dict[str, Any]:
    """加载统一配置，解析路径，合并 provider_options 默认值。"""
    cfg_path = config_path or _DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"找不到配置文件：{cfg_path}")

    with open(cfg_path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}

    provider = (raw.get("provider") or "gemini").strip().lower()
    opts = raw.get("provider_options") or {}
    provider_defaults = PROVIDER_DEFAULTS.get(provider, PROVIDER_DEFAULTS["gemini"].copy())
    provider_options = {**provider_defaults, **opts}

    cfg = {**COMMON_DEFAULTS, **raw}
    cfg["provider"] = provider
    cfg["provider_options"] = provider_options
    # 路径解析
    cfg["candidates"] = _resolve_path(cfg["candidates"])
    cfg["kline_dir"] = _resolve_path(cfg["kline_dir"])
    cfg["output_dir"] = _resolve_path(cfg["output_dir"])
    cfg["prompt_path"] = _resolve_path(cfg["prompt_path"])
    return cfg
