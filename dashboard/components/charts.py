"""
dashboard/components/charts.py
K线 / 知行线 / 量能 / 砖型图 — Plotly 图表组件（亮色主题，双周期）
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_ROOT))


# ─────────────────────────────────────────────────────────────────────────────
# rangebreaks 工具
# ─────────────────────────────────────────────────────────────────────────────

def _calc_rangebreaks_daily(trade_dates: pd.DatetimeIndex) -> list:
    """根据实际交易日期动态计算 rangebreaks，彻底去除所有空缺（含节假日）。"""
    if len(trade_dates) == 0:
        return [dict(bounds=["sat", "mon"])]

    min_d = trade_dates.min()
    max_d = trade_dates.max()
    biz_days = pd.bdate_range(min_d, max_d)
    trade_set = set(trade_dates.normalize())
    missing = [d.strftime("%Y-%m-%d") for d in biz_days if d not in trade_set]

    breaks: list = [dict(bounds=["sat", "mon"])]
    if missing:
        breaks.append(dict(values=missing))
    return breaks


def _calc_rangebreaks_weekly(all_daily_dates: pd.DatetimeIndex) -> list:
    """根据完整日线交易日期计算周线 rangebreaks，去除因长节假日产生的空周。"""
    if len(all_daily_dates) == 0:
        return [dict(bounds=["sat", "mon"])]

    min_d = all_daily_dates.min()
    max_d = all_daily_dates.max()
    all_fridays = pd.date_range(min_d, max_d, freq="W-FRI")

    trade_set = set(all_daily_dates.normalize())
    missing_workdays: list = []
    for fri in all_fridays:
        week_workdays = pd.date_range(fri - pd.Timedelta(days=4), fri)
        if not any(d in trade_set for d in week_workdays):
            for wd in week_workdays:
                missing_workdays.append(wd.strftime("%Y-%m-%d"))

    breaks: list = [dict(bounds=["sat", "mon"])]
    if missing_workdays:
        breaks.append(dict(values=missing_workdays))
    return breaks


# ─────────────────────────────────────────────────────────────────────────────
# 指标计算
# ─────────────────────────────────────────────────────────────────────────────

def _calc_ma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=1).mean()


def _calc_kdj(
    df: pd.DataFrame,
    n: int = 9,
    m1: int = 3,
    m2: int = 3,
) -> tuple:
    """KDJ 指标（通达信标准公式）。"""
    high = df["high"].astype(float)
    low = df["low"].astype(float)
    close = df["close"].astype(float)

    llv = low.rolling(n, min_periods=1).min()
    hhv = high.rolling(n, min_periods=1).max()
    denom = hhv - llv
    denom = denom.replace(0, 1e-6)
    rsv = (close - llv) / denom * 100.0

    alpha_k = 1.0 / m1
    alpha_d = 1.0 / m2
    k = rsv.ewm(alpha=alpha_k, adjust=False).mean()
    d = k.ewm(alpha=alpha_d, adjust=False).mean()
    j = 3 * k - 2 * d

    return k, d, j


def _calc_zx_lines(
    df: pd.DataFrame,
    zxdq_span: int = 10,
    m1: int = 14, m2: int = 28, m3: int = 57, m4: int = 114,
) -> tuple:
    """知行短期线 (zxdq) = double-EWM(span)；知行多空线 (zxdkx) = 四均线均值。"""
    close = df["close"].astype(float)
    zxdq = close.ewm(span=zxdq_span, adjust=False).mean().ewm(span=zxdq_span, adjust=False).mean()
    zxdkx = (
        close.rolling(m1, min_periods=m1).mean()
        + close.rolling(m2, min_periods=m2).mean()
        + close.rolling(m3, min_periods=m3).mean()
        + close.rolling(m4, min_periods=m4).mean()
    ) / 4.0
    return zxdq, zxdkx


def _calc_brick(
    df: pd.DataFrame,
    n: int = 4, m1: int = 4, m2: int = 6, m3: int = 6,
    t: float = 4.0, shift1: float = 90.0, shift2: float = 100.0,
    sma_w1: int = 1, sma_w2: int = 1, sma_w3: int = 1,
) -> pd.Series:
    """砖型图 raw 值（通达信 VAR6A）。"""
    high = df["high"].values.astype(float)
    low = df["low"].values.astype(float)
    close = df["close"].values.astype(float)
    length = len(close)

    hhv = pd.Series(high).rolling(n, min_periods=1).max().values
    llv = pd.Series(low).rolling(n, min_periods=1).min().values

    a1 = sma_w1 / m1
    b1 = 1.0 - a1
    var2a = np.empty(length, dtype=float)
    for i in range(length):
        rng = hhv[i] - llv[i]
        if rng == 0.0:
            rng = 0.01
        v1 = (hhv[i] - close[i]) / rng * 100.0 - shift1
        var2a[i] = (v1 + shift2) if i == 0 else (a1 * v1 + b1 * (var2a[i - 1] - shift2) + shift2)

    a2 = sma_w2 / m2
    b2 = 1.0 - a2
    a3 = sma_w3 / m3
    b3 = 1.0 - a3
    var4a = np.empty(length, dtype=float)
    var5a = np.empty(length, dtype=float)
    for i in range(length):
        rng = hhv[i] - llv[i]
        if rng == 0.0:
            rng = 0.01
        v3 = (close[i] - llv[i]) / rng * 100.0
        if i == 0:
            var4a[i] = v3
            var5a[i] = v3 + shift2
        else:
            var4a[i] = a2 * v3 + b2 * var4a[i - 1]
            var5a[i] = a3 * var4a[i] + b3 * (var5a[i - 1] - shift2) + shift2

    raw = np.empty(length, dtype=float)
    for i in range(length):
        diff = var5a[i] - var2a[i]
        raw[i] = diff - t if diff > t else 0.0

    return pd.Series(raw, index=df.index)


def _build_weekly_df(df: pd.DataFrame) -> pd.DataFrame:
    """日线 DataFrame → 周线 OHLCV（W-FRI）。"""
    d = df.copy()
    d["date"] = pd.to_datetime(d["date"])
    d = d.set_index("date").sort_index()
    weekly = d.resample("W-FRI").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna(subset=["open", "close"])
    weekly = weekly.reset_index()
    return weekly


# ─────────────────────────────────────────────────────────────────────────────
# 公共布局参数
# ─────────────────────────────────────────────────────────────────────────────

_LIGHT_LAYOUT = dict(
    template="plotly_white",
    paper_bgcolor="#ffffff",
    plot_bgcolor="#ffffff",
    font=dict(color="#1f2328", size=12),
    margin=dict(l=10, r=10, t=40, b=10),
    legend=dict(
        orientation="h",
        yanchor="bottom", y=1.01,
        xanchor="right", x=1,
        font=dict(size=11),
        bgcolor="rgba(255,255,255,0)",
    ),
    xaxis_rangeslider_visible=False,
    hovermode="x unified",
)

_GRID_COLOR = "rgba(0,0,0,0.07)"


def _apply_axis_style(fig: go.Figure, n_rows: int, rangebreaks: list) -> None:
    """统一设置所有子图的坐标轴样式。"""
    for i in range(1, n_rows + 1):
        xname = "xaxis" if i == 1 else f"xaxis{i}"
        yname = "yaxis" if i == 1 else f"yaxis{i}"
        fig.update_layout(**{xname: dict(
            rangebreaks=rangebreaks,
            showgrid=False,
            linecolor="#d0d7de",
            tickfont=dict(color="#636c76"),
        )})
        fig.update_layout(**{yname: dict(
            showgrid=True,
            gridcolor=_GRID_COLOR,
            zeroline=False,
            linecolor="#d0d7de",
            tickfont=dict(color="#636c76"),
        )})


# ─────────────────────────────────────────────────────────────────────────────
# 日线图：K线 + 知行线 + 量能
# ─────────────────────────────────────────────────────────────────────────────

def make_daily_chart(
    df: pd.DataFrame,
    code: str,
    volume_up_color: str = "rgba(220,53,69,0.7)",
    volume_down_color: str = "rgba(40,167,69,0.7)",
    bars: int = 120,
    height: int = 560,
    zx_params: Optional[dict] = None,
) -> go.Figure:
    """日线图：K线 + 知行短期线 + 知行长期线 + 量能。"""
    zx_params = zx_params or {}

    df = df.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    zxdq, zxdkx = _calc_zx_lines(df, **zx_params)
    df["_zxdq"] = zxdq.values
    df["_zxdkx"] = zxdkx.values

    if bars > 0:
        df = df.tail(bars).reset_index(drop=True)

    x = df["date"]
    up_mask = df["close"] >= df["open"]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.03,
        subplot_titles=[f"{code} 日线", "成交量"],
        specs=[[{"type": "candlestick"}], [{"type": "bar"}]],
    )

    fig.add_trace(go.Candlestick(
        x=x,
        open=df["open"], high=df["high"],
        low=df["low"], close=df["close"],
        increasing_line_color="#dc3545",
        decreasing_line_color="#28a745",
        increasing_fillcolor="#dc3545",
        decreasing_fillcolor="#28a745",
        name="K线",
        showlegend=False,
        line=dict(width=1),
    ), row=1, col=1)

    fig.add_trace(go.Scatter(
        x=x, y=df["_zxdq"],
        mode="lines",
        name="短期均线",
        line=dict(color="#e67e22", width=1.5),
    ), row=1, col=1)
    fig.add_trace(go.Scatter(
        x=x, y=df["_zxdkx"],
        mode="lines",
        name="长期均线",
        line=dict(color="#2980b9", width=1.5, dash="dot"),
    ), row=1, col=1)

    vol_colors = np.where(up_mask, volume_up_color, volume_down_color)
    fig.add_trace(go.Bar(
        x=x, y=df["volume"],
        marker_color=vol_colors.tolist(),
        name="成交量",
        showlegend=False,
    ), row=2, col=1)

    fig.update_layout(height=height, **_LIGHT_LAYOUT)
    _apply_axis_style(fig, 2, _calc_rangebreaks_daily(pd.DatetimeIndex(x)))
    for ann in fig.layout.annotations:
        ann.font = dict(color="#636c76", size=11)

    return fig


# ─────────────────────────────────────────────────────────────────────────────
# 周线图：K线 + 四条 MA + 量能
# ─────────────────────────────────────────────────────────────────────────────

def make_weekly_chart(
    df: pd.DataFrame,
    code: str,
    ma_windows: Optional[List[int]] = None,
    ma_colors: Optional[Dict[int, str]] = None,
    volume_up_color: str = "rgba(220,53,69,0.7)",
    volume_down_color: str = "rgba(40,167,69,0.7)",
    bars: int = 60,
    height: int = 400,
) -> go.Figure:
    """周线图：K线 + 四条 MA 均线 + 量能。"""
    ma_windows = ma_windows or [5, 10, 20, 60]
    ma_colors = ma_colors or {5: "#e67e22", 10: "#27ae60", 20: "#2980b9", 60: "#8e44ad"}

    all_daily_dates = pd.DatetimeIndex(pd.to_datetime(df["date"]))
    weekly_rangebreaks = _calc_rangebreaks_weekly(all_daily_dates)

    wdf = _build_weekly_df(df)

    if bars > 0:
        wdf = wdf.tail(bars).reset_index(drop=True)

    x = wdf["date"]
    up_mask = wdf["close"] >= wdf["open"]

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        row_heights=[0.75, 0.25],
        vertical_spacing=0.04,
        subplot_titles=[f"{code} 周线", "成交量(周)"],
        specs=[[{"type": "candlestick"}], [{"type": "bar"}]],
    )

    fig.add_trace(go.Candlestick(
        x=x,
        open=wdf["open"], high=wdf["high"],
        low=wdf["low"], close=wdf["close"],
        increasing_line_color="#dc3545",
        decreasing_line_color="#28a745",
        increasing_fillcolor="#dc3545",
        decreasing_fillcolor="#28a745",
        name="K线(周)",
        showlegend=False,
        line=dict(width=1),
    ), row=1, col=1)

    for w in ma_windows:
        if len(wdf) >= w:
            ma = _calc_ma(wdf["close"], w)
            fig.add_trace(go.Scatter(
                x=x, y=ma,
                mode="lines",
                name=f"MA{w}(周)",
                line=dict(color=ma_colors.get(w, "#aaa"), width=1.4),
            ), row=1, col=1)

    vol_colors = np.where(up_mask, volume_up_color, volume_down_color)
    fig.add_trace(go.Bar(
        x=x, y=wdf["volume"],
        marker_color=vol_colors.tolist(),
        name="成交量(周)",
        showlegend=False,
    ), row=2, col=1)

    fig.update_layout(height=height, **_LIGHT_LAYOUT)
    _apply_axis_style(fig, 2, weekly_rangebreaks)
    for ann in fig.layout.annotations:
        ann.font = dict(color="#636c76", size=11)

    return fig
