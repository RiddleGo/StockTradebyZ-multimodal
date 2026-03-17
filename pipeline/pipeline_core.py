# pipeline_core.py
"""
数据管道基础设施层
==================
提供选股流程所需的通用组件，与具体回测策略无关。

导出
----
- Trade — 单笔交易记录
- MarketDataPreparer — 多进程数据清洗 + 特征预计算
- TopTurnoverPoolBuilder — 按滚动成交额构建流动性池
- SelectorPickPrecomputer — 并行预计算选股信号
"""
from __future__ import annotations

from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tqdm import tqdm

from .Selector import AnySelector


# =============================================================================
# Worker 函数（模块级，可被 ProcessPoolExecutor pickle）
# =============================================================================

def _prepare_worker(args: tuple) -> tuple:
    """单只股票的数据清洗 + 特征计算（turnover_n + selector.prepare_df）。"""
    code, df, start, end, warmup_bars, n_turnover_days, selector = args

    df = df.copy()
    df.columns = [c.lower() for c in df.columns]

    if "date" not in df.columns:
        return code, None
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    # warmup slice
    if start is not None:
        dates = df["date"].values
        idx_start = int(np.searchsorted(dates, start.to_datetime64(), side="left"))
        if idx_start >= len(df):
            return code, None
        warmup_start = max(0, idx_start - warmup_bars)
        df = df.iloc[warmup_start:].reset_index(drop=True)

    # end slice
    if end is not None:
        df = df[df["date"] <= end].reset_index(drop=True)

    if df.empty:
        return code, None

    # turnover_n
    for col in ("open", "close", "volume"):
        if col not in df.columns:
            return code, None
    o, c, v = df["open"], df["close"], df["volume"]
    df["signed_turnover"] = (o + c) / 2 * v
    df["turnover_n"] = df["signed_turnover"].rolling(n_turnover_days, min_periods=1).sum()

    # set index
    df = df.set_index("date", drop=False)

    # selector-specific prepare（可选）
    if selector is not None and hasattr(selector, "prepare_df"):
        df = selector.prepare_df(df)

    return code, df


def _selector_worker(
    args: tuple,
):
    code, df, selector, start, end, top_turnover_pool_sets = args

    dates = df.index.tolist() if isinstance(df.index, pd.DatetimeIndex) else df["date"].tolist()
    passed_dates: List[pd.Timestamp] = []

    for d in dates:
        if start is not None and d < start:
            continue
        if end is not None and d > end:
            break

        if top_turnover_pool_sets is not None:
            codes_today = top_turnover_pool_sets.get(d)
            if not codes_today or code not in codes_today:
                continue

        if selector.passes_df_on_date(df, d):
            passed_dates.append(d)

    return code, passed_dates


# =============================================================================
# MarketDataPreparer
# =============================================================================

class MarketDataPreparer:
    """市场数据通用预处理 + 可选 selector 特征计算。"""

    def __init__(
        self,
        *,
        start_date=None,
        end_date=None,
        warmup_bars: int = 250,
        n_turnover_days: int = 20,
        selector: Optional[AnySelector] = None,
        n_jobs: Optional[int] = None,
    ) -> None:
        self.start_date = start_date
        self.end_date = end_date
        self.warmup_bars = int(warmup_bars)
        self.n_turnover_days = int(n_turnover_days)
        self.selector = selector
        self.n_jobs = n_jobs

    def prepare(self, data: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
        """完整预处理：turnover_n + selector.prepare_df()，多进程并行。"""
        tasks = [
            (code, df, self.start_date, self.end_date,
             self.warmup_bars, self.n_turnover_days, self.selector)
            for code, df in data.items()
        ]
        prepared: Dict[str, pd.DataFrame] = {}
        with ProcessPoolExecutor(max_workers=self.n_jobs) as ex:
            futures = {ex.submit(_prepare_worker, args): args[0] for args in tasks}
            for fut in tqdm(as_completed(futures), total=len(futures),
                           desc="准备数据 (mp)", ncols=80):
                code, df_out = fut.result()
                if df_out is not None:
                    prepared[code] = df_out
        return prepared

    def prepare_base_only(
        self, data: Dict[str, pd.DataFrame]
    ) -> Dict[str, pd.DataFrame]:
        """
        仅做通用预处理（切片、turnover_n、set_index），跳过 selector.prepare_df()。
        结果可在多个 trial 间共享；每个 trial 再单独调 apply_selector_features()。
        """
        tasks = [
            (code, df, self.start_date, self.end_date,
             self.warmup_bars, self.n_turnover_days, None)
            for code, df in data.items()
        ]
        prepared: Dict[str, pd.DataFrame] = {}
        with ProcessPoolExecutor(max_workers=self.n_jobs) as ex:
            futures = {ex.submit(_prepare_worker, args): args[0] for args in tasks}
            for fut in tqdm(as_completed(futures), total=len(futures),
                           desc="基础数据准备 (mp)", ncols=80):
                code, df_out = fut.result()
                if df_out is not None:
                    prepared[code] = df_out
        return prepared

    def apply_selector_features(
        self,
        base_prepared: Dict[str, pd.DataFrame],
        selector,
        n_jobs: Optional[int] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        在 prepare_base_only() 结果上叠加 selector.prepare_df()。
        使用线程池：pandas/numpy 计算会释放 GIL，避免 Windows spawn 开销。
        """
        if not hasattr(selector, "prepare_df"):
            return {code: df.copy() for code, df in base_prepared.items()}

        def _apply_one(item):
            code, df = item
            return code, selector.prepare_df(df)

        prepared: Dict[str, pd.DataFrame] = {}
        with ThreadPoolExecutor(max_workers=n_jobs or self.n_jobs) as ex:
            futures = {ex.submit(_apply_one, item): item[0]
                       for item in base_prepared.items()}
            for fut in as_completed(futures):
                code, df_out = fut.result()
                if df_out is not None:
                    prepared[code] = df_out
        return prepared

    def apply_zx_wma_features(
        self,
        base_prepared: Dict[str, pd.DataFrame],
        selector,
        n_jobs: Optional[int] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        仅叠加 zxdq / zxdkx / wma_bull 列（这些列不随砖型图超参变化，
        可在 trial 间复用，只需计算一次）。
        """
        from .Selector import compute_zx_lines, compute_weekly_ma_bull

        def _apply_one(item):
            code, df = item
            df = df.copy()
            zxdq_ser, zxdkx_ser = compute_zx_lines(
                df, selector.zxdkx_m1, selector.zxdkx_m2,
                selector.zxdkx_m3, selector.zxdkx_m4,
                zxdq_span=selector.zxdq_span,
            )
            df["zxdq"] = zxdq_ser
            df["zxdkx"] = zxdkx_ser
            df["wma_bull"] = compute_weekly_ma_bull(
                df, ma_periods=(selector.wma_short, selector.wma_mid, selector.wma_long)
            ).values
            return code, df

        prepared: Dict[str, pd.DataFrame] = {}
        with ThreadPoolExecutor(max_workers=n_jobs or self.n_jobs) as ex:
            futures = {ex.submit(_apply_one, item): item[0]
                       for item in base_prepared.items()}
            for fut in as_completed(futures):
                code, df_out = fut.result()
                if df_out is not None:
                    prepared[code] = df_out
        return prepared

    def apply_brick_features_only(
        self,
        zx_prepared: Dict[str, pd.DataFrame],
        selector,
        n_jobs: Optional[int] = None,
    ) -> Dict[str, pd.DataFrame]:
        """
        在已含 zxdq / zxdkx / wma_bull 的数据上，仅重新计算 brick 相关列。
        就地写入（不 copy），超参搜索内层循环专用，速度快 3-5×。
        """
        if not hasattr(selector, "prepare_df_brick_only"):
            return self.apply_selector_features(zx_prepared, selector, n_jobs)

        def _apply_one(item):
            code, df = item
            return code, selector.prepare_df_brick_only(df)

        with ThreadPoolExecutor(max_workers=n_jobs or self.n_jobs) as ex:
            futures = {ex.submit(_apply_one, item): item[0]
                       for item in zx_prepared.items()}
            for fut in as_completed(futures):
                pass  # 就地写入，无需收集返回值
        return zx_prepared

    @staticmethod
    def build_all_dates(prepared: Dict[str, pd.DataFrame]) -> List[pd.Timestamp]:
        all_dates: set = set()
        for df in prepared.values():
            all_dates.update(df.index)
        return sorted(all_dates)


# =============================================================================
# TopTurnoverPoolBuilder
# =============================================================================

class TopTurnoverPoolBuilder:
    """按每日 turnover_n 跨市场排名，构建流动性池。"""

    def __init__(self, top_m: int) -> None:
        self.top_m = int(top_m)

    def build(self, prepared: Dict[str, pd.DataFrame]) -> Dict[pd.Timestamp, List[str]]:
        if self.top_m <= 0:
            return {}

        pool: Dict[pd.Timestamp, List[Tuple[float, str]]] = defaultdict(list)
        for code, df in prepared.items():
            for dt, val in df["turnover_n"].items():
                pool[dt].append((float(val), code))

        top_codes_by_date: Dict[pd.Timestamp, List[str]] = {}
        for dt, lst in pool.items():
            if not lst:
                continue
            lst_sorted = sorted(lst, key=lambda x: x[0], reverse=True)[: self.top_m]
            top_codes_by_date[dt] = [code for _, code in lst_sorted]
        return top_codes_by_date


# =============================================================================
# SelectorPickPrecomputer
# =============================================================================

class SelectorPickPrecomputer:
    """并行预计算任意 selector 的逐日选股结果。"""

    def __init__(
        self,
        *,
        selector: AnySelector,
        start_date=None,
        end_date=None,
        n_jobs: Optional[int] = None,
    ) -> None:
        self.selector = selector
        self.start_date = start_date
        self.end_date = end_date
        self.n_jobs = n_jobs

    def precompute(
        self,
        prepared: Dict[str, pd.DataFrame],
        top_turnover_pool: Optional[Dict[pd.Timestamp, List[str]]] = None,
        use_threads: bool = False,
    ) -> Dict[pd.Timestamp, List[str]]:
        """
        use_threads=True → ThreadPoolExecutor（超参搜索内层循环推荐）
        use_threads=False → ProcessPoolExecutor（独立运行默认）

        若 df 含 _vec_pick 列，走向量化快速路径，跳过逐日 passes_df_on_date。
        """
        picks: Dict[pd.Timestamp, List[str]] = defaultdict(list)
        codes = list(prepared.keys())

        # ── 向量化快速路径 ──────────────────────────────────────────────
        has_vec = (
            hasattr(self.selector, "vec_picks_from_prepared")
            and codes
            and "_vec_pick" in prepared[codes[0]].columns
        )
        if has_vec:
            pool_sets: Optional[Dict[pd.Timestamp, set]] = (
                {dt: set(lst) for dt, lst in top_turnover_pool.items()}
                if top_turnover_pool is not None else None
            )
            for code in codes:
                df = prepared[code]
                for d in self.selector.vec_picks_from_prepared(
                    df, start=self.start_date, end=self.end_date
                ):
                    if pool_sets is not None:
                        today = pool_sets.get(d)
                        if not today or code not in today:
                            continue
                    picks[d].append(code)
            return picks

        # ── 逐日并行路径 ────────────────────────────────────────────────
        pool_sets2: Optional[Dict[pd.Timestamp, set]] = (
            {dt: set(lst) for dt, lst in top_turnover_pool.items()}
            if top_turnover_pool is not None else None
        )
        tasks = [
            (code, prepared[code], self.selector,
             self.start_date, self.end_date, pool_sets2)
            for code in codes
        ]
        Executor = ThreadPoolExecutor if use_threads else ProcessPoolExecutor
        with Executor(max_workers=self.n_jobs) as ex:
            futures = {ex.submit(_selector_worker, args): args[0] for args in tasks}
            for fut in as_completed(futures):
                code, passed_dates = fut.result()
                for d in passed_dates:
                    picks[d].append(code)
        return picks
