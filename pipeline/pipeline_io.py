"""
pipeline/pipeline_io.py — 统一路径解析 + 原子写入 candidates*.json
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Union

from .schemas import CandidateRun

logger = logging.getLogger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CANDIDATES_DIR = _PROJECT_ROOT / "data" / "candidates"


def _resolve_path(path_like: Union[str, Path]) -> Path:
    p = Path(path_like)
    return p if p.is_absolute() else (_PROJECT_ROOT / p)


def _ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, content: str) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def save_candidates(
    run: CandidateRun,
    *,
    candidates_dir: Union[str, Path, None] = None,
    write_dated: bool = True,
    write_latest: bool = True,
) -> dict:
    out_dir = _resolve_path(candidates_dir) if candidates_dir else _DEFAULT_CANDIDATES_DIR
    _ensure_dir(out_dir)
    payload = json.dumps(run.to_dict(), ensure_ascii=False, indent=2)
    written = {}
    if write_dated:
        dated_path = out_dir / f"candidates_{run.pick_date}.json"
        _atomic_write(dated_path, payload)
        written["dated"] = dated_path
    if write_latest:
        latest_path = out_dir / "candidates_latest.json"
        _atomic_write(latest_path, payload)
        written["latest"] = latest_path
    return written
