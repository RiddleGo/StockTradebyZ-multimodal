"""
anthropic_review.py
~~~~~~~~~~~~~~~~
使用 Anthropic Claude 多模态对候选股票进行图表分析评分，适配统一配置 review.yaml。
"""

import base64
import os
import sys
from pathlib import Path
from typing import Any, Dict

from base_reviewer import BaseReviewer

try:
    import anthropic
except ImportError:
    anthropic = None


def _media_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(
        suffix, "image/jpeg"
    )


class ClaudeReviewer(BaseReviewer):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if anthropic is None:
            print("[ERROR] 请安装: pip install anthropic", file=sys.stderr)
            sys.exit(1)
        opts = config.get("provider_options") or {}
        api_key = os.environ.get(opts.get("api_key_env", "ANTHROPIC_API_KEY"), "")
        if not api_key:
            print("[ERROR] 未找到环境变量，请设置 " + opts.get("api_key_env", "ANTHROPIC_API_KEY"), file=sys.stderr)
            sys.exit(1)
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = opts.get("model", "claude-sonnet-4-20250514")
        self._temperature = opts.get("temperature", 0.2)
        self._max_tokens = opts.get("max_tokens", 4096)

    def review_stock(self, code: str, day_chart: Path, prompt: str) -> dict:
        image_data = base64.b64encode(day_chart.read_bytes()).decode()
        user_text = (
            f"股票代码：{code}\n\n"
            "以下是该股票的 **日线图**，请按照系统提示中的框架进行分析，"
            "并严格按照要求输出 JSON。"
        )
        msg = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=prompt,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "source": {"type": "base64", "media_type": _media_type(day_chart), "data": image_data}},
                        {"type": "text", "text": user_text},
                    ],
                }
            ],
            temperature=self._temperature,
        )
        text = ""
        for b in msg.content:
            if getattr(b, "text", None):
                text += b.text
        if not text.strip():
            raise RuntimeError(f"Claude 返回空响应（code={code}）")
        result = self.extract_json(text)
        result["code"] = code
        return result
