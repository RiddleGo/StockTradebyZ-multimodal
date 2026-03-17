"""
pipeline/select_stock.py
量化初选核心逻辑。

职责：
 - 读取 rules_preselect.yaml 参数
 - 加载 data/raw/*.csv 日线数据
 - 运行 B1 策略（KDJ + 知行均线）和砖型图策略
 - 返回 List[Candidate]（纯 Python 对象，不写文件）
 - 写文件由 cli.py 调用 io.py 完成
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yaml

from .schemas import Candidate
from .Selector import B1Selector, BrickChartSelector
from .pipeline_core import MarketDataPreparer, TopTurnoverPoolBuilder

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG = _PROJECT_ROOT / "config" / "rules_preselect.yaml"


def _resolve_cfg_path(path_like: str | Path, base_dir: Path = _PROJECT_ROOT) -> Path:
    """将配置中的相对路径解析为项目根目录下的绝对路径。"""
    p = Path(path_like)
    return p if p.is_absolute() else (base_dir / p)


# =============================================================================
# 配置 & 数据加载
# =============================================================================

def load_config(config_path: Optional[str] = None) -> dict:
    """加载 rules_preselect.yaml，返回原始 dict."""
    path = _resolve_cfg_path(config_path) if config_path else _DEFAULT_CONFIG
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg or {}


def resolve_preselect_output_dir(
    *,
    config_path: Optional[str] = None,
    output_dir: Optional[str] = None,
) -> Path:
    """返回候选输出目录，优先级：CLI参数 > 配置文件 global.output_dir > 默认值。"""
    if output_dir:
        return _resolve_cfg_path(output_dir)
    cfg = load_config(config_path)
    g = cfg.get("global", {})
    return _resolve_cfg_path(g.get("output_dir", "./data/candidates"))


def load_raw_data(
    data_dir: str,
    end_date: Optional[str] = None,
) -> Dict[str, pd.DataFrame]:
    """读取 data_dir 下所有 *.csv，统一处理列名/日期/排序."""
    if not os.path.isdir(data_dir):
        raise FileNotFoundError(f"data_dir 不存在: {data_dir}")

    end_ts = pd.to_datetime(end_date) if end_date else None
    data: Dict[str, pd.DataFrame] = {}

    for fname in os.listdir(data_dir):
        if not fname.lower().endswith(".csv"):
            continue
        code = fname.rsplit(".", 1)[0]
        fpath = os.path.join(data_dir, fname)

        df = pd.read_csv(fpath)
        df.columns = [c.lower() for c in df.columns]
        if "date" not in df.columns:
            logger.warning("跳过 %s：没有 date 列", fname)
            continue

        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date").reset_index(drop=True)

        if end_ts is not None:
            df = df[df["date"] <= end_ts].reset_index(drop=True)

        if not df.empty:
            data[code] = df

    if not data:
        raise ValueError(f"未找到任何 CSV 数据: {data_dir}")

    logger.info("读取股票数量: %d", len(data))
    return data


# =============================================================================
# 工具函数
# =============================================================================

def _sorted_zx(m1: int, m2: int, m3: int, m4: int) -> Tuple[int, int, int, int]:
    """保证均线参数从小到大排列."""
    a = sorted([int(m1), int(m2), int(m3), int(m4)])
    return a[0], a[1], a[2], a[3]


def _resolve_pick_date(
    prepared: Dict[str, pd.DataFrame],
    pick_date: Optional[str] = None,
) -> pd.Timestamp:
    """确定选股基准日期：None → 最晚可用交易日，否则向前搜索最近日期."""
    all_dates = sorted(
        {d for df in prepared.values() if isinstance(df.index, pd.DatetimeIndex) for d in df.index}
    )
    if not all_dates:
        raise ValueError("prepared 数据中没有可用日期。")
    if pick_date is None:
        return all_dates[-1]

    target = pd.to_datetime(pick_date)
    arr = np.array(all_dates, dtype="datetime64[ns]")
    idx = int(np.searchsorted(arr, target.to_datetime64(), side="right")) - 1
    if idx < 0:
        raise ValueError(f"pick_date={pick_date} 早于最早可用日期={all_dates[0].date()}")
    return all_dates[idx]


def _calc_warmup(cfg: dict, buffer: int) -> int:
    """根据启用策略的参数计算最长所需 warmup bars."""
    warmup = 120

    cfg_b1 = cfg.get("b1", {})
    if cfg_b1.get("enabled", True):
        warmup = max(warmup, int(cfg_b1.get("zx_m4", 371)) + buffer)

    cfg_brick = cfg.get("brick", {})
    if cfg_brick.get("enabled", True):
        warmup = max(
            warmup,
            int(cfg_brick.get("wma_long", 120)) * 5 + buffer,
            int(cfg_brick.get("zxdkx_m4", 114)) + buffer,
        )

    return warmup


# =============================================================================
# B1 策略
# =============================================================================

def run_b1(
    prepared: Dict[str, pd.DataFrame],
    pick_date: pd.Timestamp,
    pool_codes: List[str],
    cfg_b1: dict,
) -> List[Candidate]:
    """在流动性池内运行 B1 策略，返回 Candidate 列表.

    优化：对每只股票先调用 prepare_df() 预计算所有指标列，
    再用 vec_picks_from_prepared() 直接查表，避免重复计算。
    """
    zx_m1, zx_m2, zx_m3, zx_m4 = _sorted_zx(
        cfg_b1["zx_m1"], cfg_b1["zx_m2"], cfg_b1["zx_m3"], cfg_b1["zx_m4"]
    )
    selector = B1Selector(
        j_threshold=float(cfg_b1["j_threshold"]),
        j_q_threshold=float(cfg_b1["j_q_threshold"]),
        zx_m1=zx_m1, zx_m2=zx_m2, zx_m3=zx_m3, zx_m4=zx_m4,
    )

    date_str = pick_date.strftime("%Y-%m-%d")
    candidates: List[Candidate] = []

    for code in pool_codes:
        df = prepared.get(code)
        if df is None or pick_date not in df.index:
            continue
        try:
            pf = selector.prepare_df(df)
            if selector.vec_picks_from_prepared(pf, start=pick_date, end=pick_date):
                row = pf.loc[pick_date]
                candidates.append(Candidate(
                    code=code,
                    date=date_str,
                    strategy="b1",
                    close=float(row["close"]),
                    turnover_n=float(row["turnover_n"]),
                ))
        except Exception as exc:
            logger.debug("B1 skip %s: %s", code, exc)

    logger.info("B1 选出: %d 只", len(candidates))
    return candidates


# =============================================================================
# 砖型图策略
# =============================================================================

def run_brick(
    prepared: Dict[str, pd.DataFrame],
    pick_date: pd.Timestamp,
    pool_codes: List[str],
    cfg_brick: dict,
) -> List[Candidate]:
    """在流动性池内运行砖型图策略，返回按 brick_growth 降序的 Candidate 列表.

    优化：对每只股票先调用 prepare_df() 预计算 brick/zxdq/wma_bull 等列，
    再用 vec_picks_from_prepared() 直接查表，brick_growth 也直接读预计算列，
    避免重复计算。
    """
    selector = BrickChartSelector(
        daily_return_threshold=float(cfg_brick.get("daily_return_threshold", 0.05)),
        brick_growth_ratio=float(cfg_brick.get("brick_growth_ratio", 1.0)),
        min_prior_green_bars=int(cfg_brick.get("min_prior_green_bars", 2)),
        zxdq_ratio=cfg_brick.get("zxdq_ratio"),
        zxdq_span=int(cfg_brick.get("zxdq_span", 10)),
        require_zxdq_gt_zxdkx=bool(cfg_brick.get("require_zxdq_gt_zxdkx", True)),
        zxdkx_m1=int(cfg_brick.get("zxdkx_m1", 14)),
        zxdkx_m2=int(cfg_brick.get("zxdkx_m2", 28)),
        zxdkx_m3=int(cfg_brick.get("zxdkx_m3", 57)),
        zxdkx_m4=int(cfg_brick.get("zxdkx_m4", 114)),
        require_weekly_ma_bull=bool(cfg_brick.get("require_weekly_ma_bull", True)),
        wma_short=int(cfg_brick.get("wma_short", 20)),
        wma_mid=int(cfg_brick.get("wma_mid", 60)),
        wma_long=int(cfg_brick.get("wma_long", 120)),
        n=int(cfg_brick.get("n", 4)),
        m1=int(cfg_brick.get("m1", 4)),
        m2=int(cfg_brick.get("m2", 6)),
        m3=int(cfg_brick.get("m3", 6)),
        t=float(cfg_brick.get("t", 4.0)),
        shift1=float(cfg_brick.get("shift1", 90.0)),
        shift2=float(cfg_brick.get("shift2", 100.0)),
        sma_w1=int(cfg_brick.get("sma_w1", 1)),
        sma_w2=int(cfg_brick.get("sma_w2", 1)),
        sma_w3=int(cfg_brick.get("sma_w3", 1)),
    )

    date_str = pick_date.strftime("%Y-%m-%d")
    candidates: List[Candidate] = []

    for code in pool_codes:
        df = prepared.get(code)
        if df is None or pick_date not in df.index:
            continue
        try:
            pf = selector.prepare_df(df)
            if selector.vec_picks_from_prepared(pf, start=pick_date, end=pick_date):
                row = pf.loc[pick_date]
                bg = float(row["brick_growth"]) if "brick_growth" in pf.columns else selector.brick_growth_on_date(pf, pick_date)
                candidates.append(Candidate(
                    code=code,
                    date=date_str,
                    strategy="brick",
                    close=float(row["close"]),
                    turnover_n=float(row["turnover_n"]),
                    brick_growth=bg if np.isfinite(bg) else None,
                ))
        except Exception as exc:
            logger.debug("Brick skip %s: %s", code, exc)

    candidates.sort(key=lambda c: c.brick_growth or -999, reverse=True)
    logger.info("Brick 选出: %d 只", len(candidates))
    return candidates


# =============================================================================
# 主入口
# =============================================================================

def run_preselect(
    *,
    config_path: Optional[str] = None,
    data_dir: Optional[str] = None,
    end_date: Optional[str] = None,
    pick_date: Optional[str] = None,
) -> Tuple[pd.Timestamp, List[Candidate]]:
    """
    量化初选主函数，返回 (pick_date_ts, List[Candidate])。
    不写任何文件，由 cli.py 负责落盘。

    参数
    ----
    config_path : rules_preselect.yaml 路径（None = 默认）
    data_dir : CSV 目录（None = 读配置）
    end_date : 数据截断日期（回测用）
    pick_date : 选股基准日期（None = 自动最新）
    """
    cfg = load_config(config_path)
    g = cfg.get("global", {})

    _data_dir = str(_resolve_cfg_path(data_dir or g.get("data_dir", "./data/raw")))
    top_m = int(g.get("top_m", 20))
    n_turnover_days = int(g.get("n_turnover_days", 43))
    min_bars_buffer = int(g.get("min_bars_buffer", 10))

    # 1) 加载原始数据
    raw_data = load_raw_data(_data_dir, end_date=end_date)

    # 2) 计算 warmup_bars
    warmup = _calc_warmup(cfg, min_bars_buffer)

    # 3) 通用数据预处理
    preparer = MarketDataPreparer(
        end_date=pd.to_datetime(end_date) if end_date else None,
        warmup_bars=warmup,
        n_turnover_days=n_turnover_days,
        selector=None,
    )
    prepared = preparer.prepare(raw_data)

    # 4) 确定选股日期
    pick_ts = _resolve_pick_date(prepared, pick_date)
    logger.info("选股日期: %s", pick_ts.date())

    # 5) 构建流动性池
    pool_codes = TopTurnoverPoolBuilder(top_m=top_m).build(prepared).get(pick_ts, [])
    if not pool_codes:
        logger.warning("流动性池为空，pick_date=%s", pick_ts.date())
        return pick_ts, []

    logger.info("流动性池: %d 只", len(pool_codes))

    # 6) 运行各策略
    all_candidates: List[Candidate] = []

    if cfg.get("b1", {}).get("enabled", True):
        all_candidates.extend(run_b1(prepared, pick_ts, pool_codes, cfg["b1"]))

    if cfg.get("brick", {}).get("enabled", True):
        all_candidates.extend(run_brick(prepared, pick_ts, pool_codes, cfg["brick"]))

    # 7) 去重（同一只保留首次命中的策略）
    seen: set = set()
    deduped = [c for c in all_candidates if not (c.code in seen or seen.add(c.code))]  # type: ignore[func-returns-value]

    logger.info("初选完成，候选股票: %d 只", len(deduped))
    return pick_ts, deduped
