"""
pipeline/schemas.py — 候选股票数据结构（纯 dataclass，无第三方依赖）。
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List


@dataclass
class Candidate:
    """单只候选股票的结构化信息。"""
    code: str
    date: str
    strategy: str
    close: float
    turnover_n: float
    brick_growth: Any = None
    extra: Dict[str, Any] = None

    def __post_init__(self):
        if self.extra is None:
            self.extra = {}

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if not d.get("extra"):
            d.pop("extra", None)
        if d.get("brick_growth") is None:
            d.pop("brick_growth", None)
        return d


@dataclass
class CandidateRun:
    """一次完整初选运行的结果。"""
    run_date: str
    pick_date: str
    candidates: List[Candidate] = None
    meta: Dict[str, Any] = None

    def __post_init__(self):
        if self.candidates is None:
            self.candidates = []
        if self.meta is None:
            self.meta = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_date": self.run_date,
            "pick_date": self.pick_date,
            "candidates": [c.to_dict() for c in self.candidates],
            "meta": self.meta,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CandidateRun":
        candidates = [
            Candidate(**{k: v for k, v in c.items() if k in ("code", "date", "strategy", "close", "turnover_n", "brick_growth", "extra")})
            for c in d.get("candidates", [])
        ]
        return cls(
            run_date=d["run_date"],
            pick_date=d["pick_date"],
            candidates=candidates,
            meta=d.get("meta", {}),
        )
