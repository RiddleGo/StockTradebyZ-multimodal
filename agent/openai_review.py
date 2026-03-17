"""
openai_review.py
~~~~~~~~~~~~~~~~
使用 OpenAI 或兼容 OpenAI 接口的多模态模型（OpenAI / 通义 / 智谱 / 月之暗面 / DeepSeek 等）
对候选股票进行图表分析评分，适配统一配置 review.yaml。
"""

import base64
import os
import sys
from pathlib import Path
from typing import Any, Dict

from base_reviewer import BaseReviewer

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None


def _mime_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}.get(
        suffix, "image/jpeg"
    )


class OpenAIReviewer(BaseReviewer):
    """OpenAI GPT-4o / 以及兼容 OpenAI API 的厂商（通义、智谱、Moonshot、DeepSeek 等）。"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        if OpenAI is None:
            print("[ERROR] 请安装: pip install openai", file=sys.stderr)
            sys.exit(1)
        opts = config.get("provider_options") or {}
        api_key = os.environ.get(opts.get("api_key_env", "OPENAI_API_KEY"), "")
        if not api_key:
            print("[ERROR] 未找到环境变量，请设置 " + opts.get("api_key_env", "OPENAI_API_KEY"), file=sys.stderr)
            sys.exit(1)
        self._client = OpenAI(
            api_key=api_key,
            base_url=opts.get("base_url"),  # 不传则默认 OpenAI 官方
        )
        self._model = opts.get("model", "gpt-4o")
        self._temperature = opts.get("temperature", 0.2)
        self._max_tokens = opts.get("max_tokens", 4096)

    def review_stock(self, code: str, day_chart: Path, prompt: str) -> dict:
        image_url = f"data:{_mime_type(day_chart)};base64,{base64.b64encode(day_chart.read_bytes()).decode()}"
        user_content = [
            {"type": "text", "text": (
                f"股票代码：{code}\n\n"
                "以下是该股票的 **日线图**，请按照系统提示中的框架进行分析，"
                "并严格按照要求输出 JSON。"
            )},
            {"type": "image_url", "image_url": {"url": image_url}},
        ]
        response = self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=self._temperature,
            max_tokens=self._max_tokens,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text:
            raise RuntimeError(f"模型返回空响应（code={code}）")
        result = self.extract_json(text)
        result["code"] = code
        return result
