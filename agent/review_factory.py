"""
review_factory.py
~~~~~~~~~~~~~~~~
根据 config 中的 provider 创建对应的 Reviewer 实例，支持多厂商。
"""

import sys
from typing import Any, Dict

from base_reviewer import BaseReviewer

# 延迟导入各厂商实现，避免未安装 SDK 时直接报错
def _get_gemini_reviewer_class():
    from gemini_review import GeminiReviewer
    return GeminiReviewer

def _get_openai_reviewer_class():
    from openai_review import OpenAIReviewer
    return OpenAIReviewer

def _get_anthropic_reviewer_class():
    from anthropic_review import ClaudeReviewer
    return ClaudeReviewer

def _get_qwen_reviewer_class():
    from openai_review import OpenAIReviewer
    return OpenAIReviewer

def _get_zhipu_reviewer_class():
    from openai_review import OpenAIReviewer
    return OpenAIReviewer

def _get_moonshot_reviewer_class():
    from openai_review import OpenAIReviewer
    return OpenAIReviewer

def _get_deepseek_reviewer_class():
    from openai_review import OpenAIReviewer
    return OpenAIReviewer

_PROVIDER_LOADERS = {
    "gemini": _get_gemini_reviewer_class,
    "openai": _get_openai_reviewer_class,
    "anthropic": _get_anthropic_reviewer_class,
    "qwen": _get_qwen_reviewer_class,
    "zhipu": _get_zhipu_reviewer_class,
    "moonshot": _get_moonshot_reviewer_class,
    "deepseek": _get_deepseek_reviewer_class,
}


def create_reviewer(config: Dict[str, Any]) -> BaseReviewer:
    """根据 config['provider'] 创建对应 Reviewer。"""
    provider = (config.get("provider") or "gemini").strip().lower()
    loader = _PROVIDER_LOADERS.get(provider)
    if not loader:
        raise ValueError(
            f"不支持的 provider: {provider}。"
            f"支持: {', '.join(_PROVIDER_LOADERS)}"
        )
    try:
        cls = loader()
    except Exception as e:
        print(f"[ERROR] 加载 {provider} 实现失败: {e}", file=sys.stderr)
        raise
    return cls(config)
