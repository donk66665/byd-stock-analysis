"""
02_analyze.py — 四项教材任务的计算，输出网页可直接消费的 analysis.json

任务对应：
  (1) 数据形状、前 5 行、定量变量描述性统计
  (2) 相关系数矩阵（价格水平 / 日频变动 双口径）
  (3) 2023 全年收盘价时序 + 2023-2026 全区间时序
  (4) 2023-04 ~ 2023-06 K 线 + 区间画像

用法：python scripts/02_analyze.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "byd_hfq_full.csv"
OUT = ROOT / "data" / "analysis.json"

PRICE = ["开盘", "收盘", "最高", "最低"]
VOL = ["成交量", "成交额"]
RATIO = ["振幅", "涨跌幅", "涨跌额", "换手率"]
NUM = PRICE + VOL + RATIO


def r(x, n=2):
    """安全取整，处理 NaN / inf。"""
    if x is None or (isinstance(x, float) and (np.isnan(x) or np.isinf(x))):
        return None
    return round(float(x), n)


def fmt_date(s: pd.Series) -> list[str]:
    return pd.to_datetime(s).dt.strftime("%Y-%m-%d").tolist()


def describe(df: pd.DataFrame) -> dict:
    out = {}
    for col in NUM:
        s = df[col].astype(float)
        out[col] = {
            "count": int(s.count()),
            "mean": r(s.mean()),
            "std": r(s.std()),
            "min": r(s.min()),
            "q25": r(s.quantile(0.25)),
            "median": r(s.median()),
            "q75": r(s.quantile(0.75)),
            "max": r(s.max()),
            "skew": r(s.skew(), 3),
            "kurt": r(s.kurt(), 3),
            "range": r(s.max() - s.min()),
            "cv": r(s.std() / s.mean(), 4) if s.mean() else None,
        }
    return out


def corr_block(df: pd.DataFrame, cols: list[str]) -> dict:
    m = df[cols].astype(float).corr(method="pearson")
    return {
        "labels": cols,
        "matrix": [[r(m.loc[i, j], 4) for j in cols] for i in cols],
    }


def series_block(df: pd.DataFrame, with_ma: bool = True) -> dict:
    close = df["收盘"].astype(float)
    block = {
        "dates": fmt_date(df["日期"]),
        "close": [r(v) for v in close],
        "vol": [r(v, 0) for v in df["成交量"].astype(float)],
    }
    if with_ma:
        block["ma20"] = [r(v) for v in close.rolling(20).mean()]
        block["ma60"] = [r(v) for v in close.rolling(60).mean()]
    return block


def kpi_block(df: pd.DataFrame) -> dict:
    close = df["收盘"].astype(float)
    ret = close.pct_change().dropna()
    cummax = close.cummax()
    drawdown = (close / cummax - 1.0) * 100
    hi_idx = close.idxmax()
    lo_idx = close.idxmin()
    return {
        "first_date": df["日期"].iloc[0].strftime("%Y-%m-%d"),
        "last_date": df["日期"].iloc[-1].strftime("%Y-%m-%d"),
        "first_close": r(close.iloc[0]),
        "last_close": r(close.iloc[-1]),
        "total_return_pct": r((close.iloc[-1] / close.iloc[0] - 1) * 100),
        "high": {"value": r(close.max()), "date": df["日期"].loc[hi_idx].strftime("%Y-%m-%d")},
        "low": {"value": r(close.min()), "date": df["日期"].loc[lo_idx].strftime("%Y-%m-%d")},
        "ann_vol_pct": r(ret.std() * np.sqrt(252) * 100),
        "max_drawdown_pct": r(drawdown.min()),
        "avg_turnover": r(df["换手率"].astype(float).mean(), 3),
        "up_days": int((ret > 0).sum()),
        "down_days": int((ret < 0).sum()),
        "flat_days": int((ret == 0).sum()),
        "max_gain_pct": r(df["涨跌幅"].astype(float).max()),
        "max_loss_pct": r(df["涨跌幅"].astype(float).min()),
    }


def annual_block(df: pd.DataFrame) -> list[dict]:
    rows = []
    for year, g in df.groupby(df["日期"].dt.year):
        c = g["收盘"].astype(float)
        rows.append({
            "year": int(year),
            "trading_days": int(len(g)),
            "start": r(c.iloc[0]),
            "end": r(c.iloc[-1]),
            "chg_pct": r((c.iloc[-1] / c.iloc[0] - 1) * 100),
            "high": r(c.max()),
            "low": r(c.min()),
            "amp_pct": r((c.max() / c.min() - 1) * 100),
            "ann_vol_pct": r(c.pct_change().std() * np.sqrt(252) * 100),
        })
    return rows


def main() -> int:
    df = pd.read_csv(SRC, parse_dates=["日期"])
    df = df.sort_values("日期").reset_index(drop=True)
    df = df.drop(columns=["序号"], errors="ignore")

    print(f"载入 {len(df)} 行，区间 {df['日期'].min():%Y-%m-%d} ~ {df['日期'].max():%Y-%m-%d}")

    d2023 = df[df["日期"].dt.year == 2023].copy()
    k = df[(df["日期"] >= "2023-04-01") & (df["日期"] <= "2023-06-30")].copy()

    print(f"2023 全年 {len(d2023)} 行 | K线区间 {len(k)} 行 "
          f"({k['日期'].min():%Y-%m-%d} ~ {k['日期'].max():%Y-%m-%d})")

    # 相关系数：剔除换手率为 0 的停牌异常不影响，直接算
    corr_level = corr_block(df, NUM)
    corr_flow = corr_block(df, ["涨跌幅", "振幅", "成交量", "成交额", "换手率"])

    k_high_idx = k["最高"].astype(float).idxmax()
    k_low_idx = k["最低"].astype(float).idxmin()

    payload = {
        "meta": {
            "name": "比亚迪",
            "symbol": "002594",
            "adjust": "hfq",
            "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "start": df["日期"].iloc[0].strftime("%Y-%m-%d"),
            "end": df["日期"].iloc[-1].strftime("%Y-%m-%d"),
            "rows": int(len(df)),
            "cols": int(len(NUM)) + 1,
            "columns": ["日期"] + NUM,
            "raw_rows": int(len(d2023)),
        },
        "kpi": kpi_block(df),
        "annual": annual_block(df),
        "shape": {"rows": int(len(df)), "cols": int(len(NUM)) + 1},
        "head": [
            {"日期": row["日期"].strftime("%Y-%m-%d"),
             **{c: r(row[c]) for c in NUM}}
            for _, row in df.head(5).iterrows()
        ],
        "describe_full": describe(df),
        "describe_2023": describe(d2023),
        "corr": corr_level,
        "corr_flow": corr_flow,
        "series_2023": series_block(d2023),
        "series_full": series_block(df),
        "kline": {
            "dates": fmt_date(k["日期"]),
            # ECharts candlestick 约定：[open, close, low, high]
            "ohlc": [
                [r(o), r(c), r(lo), r(hi)]
                for o, c, lo, hi in zip(k["开盘"], k["收盘"], k["最低"], k["最高"])
            ],
            "vol": [r(v, 0) for v in k["成交量"].astype(float)],
            "chg": [r(v) for v in k["涨跌幅"].astype(float)],
            "ma5": [r(v) for v in k["收盘"].astype(float).rolling(5).mean()],
            "ma10": [r(v) for v in k["收盘"].astype(float).rolling(10).mean()],
            "ma20": [r(v) for v in k["收盘"].astype(float).rolling(20).mean()],
            "high": {
                "value": r(k["最高"].astype(float).max()),
                "date": k["日期"].loc[k_high_idx].strftime("%Y-%m-%d"),
            },
            "low": {
                "value": r(k["最低"].astype(float).min()),
                "date": k["日期"].loc[k_low_idx].strftime("%Y-%m-%d"),
            },
            "start_close": r(k["收盘"].astype(float).iloc[0]),
            "end_close": r(k["收盘"].astype(float).iloc[-1]),
            "chg_pct": r((k["收盘"].astype(float).iloc[-1] /
                           k["收盘"].astype(float).iloc[0] - 1) * 100),
            "avg_vol": r(k["成交量"].astype(float).mean(), 0),
            "up_days": int((k["涨跌幅"].astype(float) > 0).sum()),
            "down_days": int((k["涨跌幅"].astype(float) < 0).sum()),
        },
    }

    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    size_kb = OUT.stat().st_size / 1024
    print(f"已写出 {OUT.relative_to(ROOT)}（{size_kb:.0f} KB）")

    # 控制台摘要，便于人工核对
    kp = payload["kpi"]
    print("\n区间画像：")
    print(f"  {kp['first_date']} 收盘 {kp['first_close']} -> "
          f"{kp['last_date']} 收盘 {kp['last_close']}，累计 {kp['total_return_pct']}%")
    print(f"  最高 {kp['high']['value']}（{kp['high']['date']}）  "
          f"最低 {kp['low']['value']}（{kp['low']['date']}）")
    print(f"  年化波动 {kp['ann_vol_pct']}%  最大回撤 {kp['max_drawdown_pct']}%")
    kl = payload["kline"]
    print(f"\nK线区间 {kl['dates'][0]} ~ {kl['dates'][-1]}（{len(kl['dates'])} 根）")
    print(f"  {kl['start_close']} -> {kl['end_close']}，区间 {kl['chg_pct']}%")
    print(f"  最高 {kl['high']['value']}（{kl['high']['date']}）  "
          f"最低 {kl['low']['value']}（{kl['low']['date']}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
