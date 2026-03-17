"""
gemini_review.py
~~~~~~~~~~~~~~~~
使用 Google Gemini 对候选股票进行图表分析评分，适配统一配置 review.yaml。
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict

from google import genai
from google.genai import types
from base_reviewer import BaseReviewer


class GeminiReviewer(BaseReviewer):
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        opts = config.get("provider_options") or {}
        api_key = os.environ.get(opts.get("api_key_env", "GEMINI_API_KEY"), "")
        if not api_key:
            print("[ERROR] 未找到环境变量，请设置 " + opts.get("api_key_env", "GEMINI_API_KEY"), file=sys.stderr)
            sys.exit(1)
        self.client = genai.Client(api_key=api_key)
        self._model = opts.get("model", "gemini-2.0-flash")

    @staticmethod
    def image_to_part(path: Path) -> types.Part:
        suffix = path.suffix.lower()
        mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
        mime_type = mime_map.get(suffix, "image/jpeg")
        data = path.read_bytes()
        return types.Part.from_bytes(data=data, mime_type=mime_type)

    def review_stock(self, code: str, day_chart: Path, prompt: str) -> dict:
        user_text = (
            f"股票代码：{code}\n\n"
            "以下是该股票的 **日线图**，请按照系统提示中的框架进行分析，"
            "并严格按照要求输出 JSON。"
        )
        parts: list[types.Part] = [
            types.Part.from_text(text="【日线图】"),
            self.image_to_part(day_chart),
            types.Part.from_text(text=user_text),
        ]
        opts = self.config.get("provider_options") or {}
        response = self.client.models.generate_content(
            model=self._model,
            contents=[types.Content(role="user", parts=parts)],
            config=types.GenerateContentConfig(
                system_instruction=prompt,
                temperature=opts.get("temperature", 0.2),
            ),
        )
        response_text = response.text
        if response_text is None:
            raise RuntimeError(f"Gemini 返回空响应（code={code}）")
        result = self.extract_json(response_text)
        result["code"] = code
        return result
