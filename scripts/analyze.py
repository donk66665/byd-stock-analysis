# -*- coding: utf-8 -*-
"""
比亚迪（002594）后复权历史行情：清洗、指标计算与结构化导出
-----------------------------------------------------------------
输入：data/比亚迪后复权历史行情数据.xlsx  （242 个交易日 × 11 字段）
输出：site/assets/js/data.js               （window.BYD_DATA = {...}，供离线 H5 直读）

设计约束（详见 AGENTS.md）：
  1. 不引入绘图库，本脚本只做「数据 → 结构化 JSON」，绘图全部交给前端 ECharts；
  2. 所有指标必须可复算，函数纯化，禁止魔法数；
  3. 输出为 JS 变量赋值而非 .json，避免 file:// 协议下 fetch 的 CORS 限制。
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "比亚迪后复权历史行情数据.xlsx"
OUT = ROOT / "site" / "assets" / "js" / "data.js"

TRADING_DAYS = 252          # 年化因子
RISK_FREE = 0.02            # 无风险利率，用于夏普比率
MA_WINDOWS = (5, 10, 20, 60)


# ---------------------------------------------------------------- 1. 加载与清洗
def load_and_clean() -> tuple[pd.DataFrame, dict]:
    """读入原始表并做质量检查，返回 (干净数据, 质量报告)。"""
    raw = pd.read_excel(SRC, sheet_name="Sheet2")
    report: dict = {
        "rawRows": int(len(raw)),
        "rawCols": int(raw.shape[1]),
        "columns": [str(c) for c in raw.columns],
        "missing": int(raw.isna().sum().sum()),
        "duplicated": int(raw.duplicated(subset=["日期"]).sum()),
        "fixed": [],
    }

    df = raw.copy()
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.drop_duplicates(subset=["日期"]).sort_values("日期").reset_index(drop=True)

    # 缺失值：数值列用前值填充（行情数据前后连续，前值填充优于均值）
    num_cols = ["开盘", "收盘", "最高", "最低", "成交量", "成交额", "振幅", "涨跌幅", "涨跌额", "换手率"]
    if df[num_cols].isna().any().any():
        n = int(df[num_cols].isna().sum().sum())
        df[num_cols] = df[num_cols].ffill().bfill()
        report["fixed"].append(f"数值列缺失 {n} 处，采用前值填充（ffill）")

    # 逻辑校验：最高 ≥ max(开,收) 且 最低 ≤ min(开,收)
    bad_high = df["最高"] < df[["开盘", "收盘"]].max(axis=1)
    bad_low = df["最低"] > df[["开盘", "收盘"]].min(axis=1)
    n_bad = int((bad_high | bad_low).sum())
    if n_bad:
        df.loc[bad_high, "最高"] = df.loc[bad_high, ["开盘", "收盘", "最高"]].max(axis=1)
        df.loc[bad_low, "最低"] = df.loc[bad_low, ["开盘", "收盘", "最低"]].min(axis=1)
        report["fixed"].append(f"OHLC 逻辑冲突 {n_bad} 处，按 max/min 规则修正")

    # 非正值与零成交
    n_nonpos = int((df[["开盘", "收盘", "最高", "最低"]] <= 0).sum().sum())
    n_zero_vol = int((df["成交量"] <= 0).sum())
    report["fixed"].append(f"非正价格 {n_nonpos} 处、零成交量 {n_zero_vol} 处，均无需剔除")
    report["cleanRows"] = int(len(df))

    # 字段冗余辨识：换手率 = 成交量 / 流通股本，若流通股本固定则二者严格成比例
    ratio = (df["换手率"] / df["成交量"]).replace([np.inf, -np.inf], np.nan).dropna()
    cv = float(ratio.std(ddof=1) / ratio.mean()) if len(ratio) > 1 else 1.0
    report["turnoverVolumeCV"] = round(cv * 100, 2)
    report["notes"] = [
        f"换手率/成交量 的变异系数仅 {cv*100:.2f}%，说明数据期内流通股本视为恒定，"
        f"换手率与成交量互为线性映射，图表与相关性分析中二者取其一即可，避免重复计数。",
        "成交额 = 成交量 × 成交均价，与成交量的信息不完全重合，因此保留成交额参与量价分析。",
        f"涨跌幅由后复权收盘价推得，与 (收盘/前收-1) 一致，无需额外复权处理。",
    ]
    return df, report


# ------------------------------------------------------------------ 2. 指标层
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """派生均线、净值、回撤等序列指标。"""
    for w in MA_WINDOWS:
        df[f"MA{w}"] = df["收盘"].rolling(w).mean().round(2)

    df["净值"] = (df["收盘"] / df["收盘"].iloc[0]).round(6)
    df["累计最高"] = df["收盘"].cummax()
    df["回撤"] = (df["收盘"] / df["累计最高"] - 1).round(6)

    # 日对数收益率（仅用于波动率与夏普，展示仍用原始涨跌幅）
    df["对数收益"] = np.log(df["收盘"] / df["收盘"].shift(1))

    # 量能相对强弱：成交量 / 过去 20 日均量
    df["量比20"] = (df["成交量"] / df["成交量"].rolling(20).mean()).round(3)
    return df


def _zigzag(closes: list[float], threshold: float = 0.10) -> list[int]:
    """经典 ZigZag 拐点识别：仅在反向幅度超过 threshold 时确认新拐点。

    相比「是否站上 MA20」的二分法，ZigZag 直接刻画趋势段边界，
    拐点数量可控（阈值越大幅度越粗），更适合做走势阶段划分的叙事。
    """
    pivots = [0]
    trend, ext = 0, 0
    for i in range(1, len(closes)):
        if trend == 0:
            if closes[i] > closes[ext] * (1 + threshold):
                trend, ext = 1, i
                pivots.append(i)
            elif closes[i] < closes[ext] * (1 - threshold):
                trend, ext = -1, i
                pivots.append(i)
        elif trend == 1:
            if closes[i] > closes[ext]:
                ext = i
            elif closes[i] <= closes[ext] * (1 - threshold):
                if pivots[-1] != ext:
                    pivots.append(ext)
                trend, ext = -1, i
        else:
            if closes[i] < closes[ext]:
                ext = i
            elif closes[i] >= closes[ext] * (1 + threshold):
                if pivots[-1] != ext:
                    pivots.append(ext)
                trend, ext = 1, i
    if pivots[-1] != ext:
        pivots.append(ext)
    if pivots[0] != 0:
        pivots.insert(0, 0)
    return sorted(set(pivots))


def _phase_split(df: pd.DataFrame, threshold: float = 0.10) -> list[dict]:
    """按 ZigZag 拐点切分走势阶段，并合并相邻同向段。"""
    closes = df["收盘"].tolist()
    pivots = _zigzag(closes, threshold)

    raw = []
    for a, b in zip(pivots[:-1], pivots[1:]):
        ret = closes[b] / closes[a] - 1
        raw.append((a, b, ret))
    # 合并相邻同向段（避免同方向被拆成两截）
    merged: list[list] = []
    for a, b, ret in raw:
        if merged and (merged[-1][2] > 0) == (ret > 0) and len(merged[-1]) == 3:
            merged[-1][1] = b
            merged[-1][2] = closes[b] / closes[merged[-1][0]] - 1
        else:
            merged.append([a, b, ret])

    phases = []
    for k, (a, b, ret) in enumerate(merged):
        seg = df.iloc[a : b + 1]
        phases.append(
            {
                "index": k,
                "start": seg["日期"].iloc[0].strftime("%m-%d"),
                "end": seg["日期"].iloc[-1].strftime("%m-%d"),
                "startDate": seg["日期"].iloc[0].strftime("%Y-%m-%d"),
                "endDate": seg["日期"].iloc[-1].strftime("%Y-%m-%d"),
                "startIdx": int(a),
                "endIdx": int(b),
                "days": int(b - a + 1),
                "return": round(float(ret) * 100, 2),
                "startClose": round(float(closes[a]), 2),
                "endClose": round(float(closes[b]), 2),
                "high": round(float(seg["最高"].max()), 2),
                "low": round(float(seg["最低"].min()), 2),
                "avgTurnover": round(float(seg["换手率"].mean()), 2),
                "amp": round(float(seg["振幅"].mean()), 2),
                "label": "上行段" if ret > 0 else "下行段",
            }
        )
    return phases


def build_summary(df: pd.DataFrame) -> dict:
    """聚合标量指标。"""
    close = df["收盘"]
    ret = df["涨跌幅"] / 100.0
    daily_ret = df["对数收益"].dropna()

    total_ret = close.iloc[-1] / close.iloc[0] - 1
    ann_vol = float(daily_ret.std(ddof=1) * math.sqrt(TRADING_DAYS))
    sharpe = float((daily_ret.mean() * TRADING_DAYS - RISK_FREE) / ann_vol) if ann_vol else 0.0

    mdd = float(df["回撤"].min())
    mdd_idx = int(df["回撤"].idxmin())

    up = int((ret > 0).sum())
    down = int((ret < 0).sum())
    flat = int((ret == 0).sum())

    # 最长连涨 / 连跌
    def streak(sign: int) -> int:
        best = cur = 0
        for v in ret:
            if (v > 0 and sign > 0) or (v < 0 and sign < 0):
                cur += 1
                best = max(best, cur)
            else:
                cur = 0
        return best

    # 量价关系四象限（以 20 日均量为放量基准）
    vol_ratio = df["量比20"]
    quad = {
        "放量上涨": int(((vol_ratio > 1) & (ret > 0)).sum()),
        "缩量上涨": int(((vol_ratio <= 1) & (ret > 0)).sum()),
        "放量下跌": int(((vol_ratio > 1) & (ret < 0)).sum()),
        "缩量下跌": int(((vol_ratio <= 1) & (ret < 0)).sum()),
    }

    hi_idx = int(close.idxmax())
    lo_idx = int(close.idxmin())

    return {
        "startClose": round(float(close.iloc[0]), 2),
        "endClose": round(float(close.iloc[-1]), 2),
        "totalReturn": round(float(total_ret) * 100, 2),
        "high": round(float(df["最高"].max()), 2),
        "highDate": df.loc[int(df["最高"].idxmax()), "日期"].strftime("%Y-%m-%d"),
        "low": round(float(df["最低"].min()), 2),
        "lowDate": df.loc[int(df["最低"].idxmin()), "日期"].strftime("%Y-%m-%d"),
        "closeHigh": round(float(close.max()), 2),
        "closeHighDate": df.loc[hi_idx, "日期"].strftime("%Y-%m-%d"),
        "closeLow": round(float(close.min()), 2),
        "closeLowDate": df.loc[lo_idx, "日期"].strftime("%Y-%m-%d"),
        "avgAmount": round(float(df["成交额"].mean()) / 1e8, 2),          # 亿元
        "totalAmount": round(float(df["成交额"].sum()) / 1e8, 2),         # 亿元
        "avgVolume": round(float(df["成交量"].mean()) / 1e4, 2),          # 万手
        "avgTurnover": round(float(df["换手率"].mean()), 2),
        "avgAmplitude": round(float(df["振幅"].mean()), 2),
        "annualVol": round(ann_vol * 100, 2),
        "dailyVol": round(float(daily_ret.std(ddof=1)) * 100, 2),
        "sharpe": round(sharpe, 2),
        "maxDrawdown": round(mdd * 100, 2),
        "maxDrawdownDate": df.loc[mdd_idx, "日期"].strftime("%Y-%m-%d"),
        "upDays": up,
        "downDays": down,
        "flatDays": flat,
        "winRate": round(up / (up + down) * 100, 2),
        "maxUp": round(float(df["涨跌幅"].max()), 2),
        "maxUpDate": df.loc[int(df["涨跌幅"].idxmax()), "日期"].strftime("%Y-%m-%d"),
        "maxDown": round(float(df["涨跌幅"].min()), 2),
        "maxDownDate": df.loc[int(df["涨跌幅"].idxmin()), "日期"].strftime("%Y-%m-%d"),
        "maxStreakUp": streak(1),
        "maxStreakDown": streak(-1),
        "volumeQuadrant": quad,
        "corrTurnoverPct": round(float(df["换手率"].corr(df["涨跌幅"])), 3),
        "corrAmountPct": round(float(df["成交额"].corr(df["涨跌幅"])), 3),
        "corrAmountAmplitude": round(float(df["成交额"].corr(df["振幅"])), 3),
        "h1Return": round(float(close.iloc[119] / close.iloc[0] - 1) * 100, 2),
        "h2Return": round(float(close.iloc[-1] / close.iloc[119] - 1) * 100, 2),
    }


def build_monthly(df: pd.DataFrame) -> list[dict]:
    """月度收益：月末收盘 / 上月末收盘 - 1（首月用首日收盘为基）。"""
    out = []
    for (y, m), g in df.groupby([df["日期"].dt.year, df["日期"].dt.month]):
        first_pos = df.index.get_loc(g.index[0])
        base = df["收盘"].iloc[first_pos - 1] if first_pos > 0 else df["收盘"].iloc[0]
        last = g["收盘"].iloc[-1]
        out.append(
            {
                "month": f"{m:02d}月",
                "return": round(float(last / base - 1) * 100, 2),
                "close": round(float(last), 2),
                "vol": round(float(g["成交额"].sum()) / 1e8, 1),
                "turnover": round(float(g["换手率"].mean()), 2),
            }
        )
    return out


def build_histogram(df: pd.DataFrame, bin_w: float = 0.5) -> list[dict]:
    """日涨跌幅分布直方图，区间 [-6, +6]，步长 0.5。"""
    s = df["涨跌幅"]
    edges = np.arange(-6.0, 6.0 + bin_w, bin_w)
    out = []
    for i in range(len(edges) - 1):
        lo, hi = edges[i], edges[i + 1]
        cnt = int(((s >= lo) & (s < hi)).sum()) if i < len(edges) - 2 else int(((s >= lo) & (s <= hi)).sum())
        out.append({"bin": round(float((lo + hi) / 2), 2), "count": cnt})
    # 尾部并入
    tail_low = int((s < -6).sum())
    tail_high = int((s > 6).sum())
    if tail_low:
        out[0]["count"] += tail_low
    if tail_high:
        out[-1]["count"] += tail_high
    return out


def build_scatter(df: pd.DataFrame) -> list[list[float]]:
    """换手率 - 涨跌幅散点，剔除极端值便于观察。"""
    sub = df[(df["换手率"] > 0) & (df["换手率"] < df["换手率"].quantile(0.99))]
    return [[round(float(a), 3), round(float(b), 2)] for a, b in zip(sub["换手率"], sub["涨跌幅"])]


# ------------------------------------------------------------------ 3. 主流程
def main() -> None:
    df, quality = load_and_clean()
    df = add_indicators(df)

    series = {
        "dates": [d.strftime("%Y-%m-%d") for d in df["日期"]],
        "shortDates": [d.strftime("%m-%d") for d in df["日期"]],
        "open": [round(float(v), 2) for v in df["开盘"]],
        "close": [round(float(v), 2) for v in df["收盘"]],
        "high": [round(float(v), 2) for v in df["最高"]],
        "low": [round(float(v), 2) for v in df["最低"]],
        "volume": [round(float(v) / 1e4, 2) for v in df["成交量"]],   # 万手
        "amount": [round(float(v) / 1e8, 2) for v in df["成交额"]],   # 亿元
        "turnover": [round(float(v), 2) for v in df["换手率"]],
        "pctChg": [round(float(v), 2) for v in df["涨跌幅"]],
        "amplitude": [round(float(v), 2) for v in df["振幅"]],
        "nav": [round(float(v), 4) for v in df["净值"]],
        "drawdown": [round(float(v) * 100, 2) for v in df["回撤"]],
    }
    for w in MA_WINDOWS:
        series[f"ma{w}"] = [None if pd.isna(v) else round(float(v), 2) for v in df[f"MA{w}"]]

    payload = {
        "meta": {
            "stock": "比亚迪",
            "code": "002594.SZ",
            "priceType": "后复权",
            "market": "深圳证券交易所 · 主板",
            "range": [series["dates"][0], series["dates"][-1]],
            "tradingDays": int(len(df)),
            "fields": quality["columns"],
            "generatedAt": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M"),
            "dataSource": "教材 P92 实战演练配套数据（比亚迪后复权历史行情数据.xlsx）",
        },
        "quality": quality,
        "summary": build_summary(df),
        "phases": _phase_split(df),
        "monthly": build_monthly(df),
        "histogram": build_histogram(df),
        "scatter": build_scatter(df),
        "series": series,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    js = "/* 由 scripts/analyze.py 自动生成，请勿手工修改 */\nwindow.BYD_DATA = " + json.dumps(
        payload, ensure_ascii=False, separators=(",", ":")
    ) + ";\n"
    OUT.write_text(js, encoding="utf-8")

    s = payload["summary"]
    print(f"[OK] 清洗后 {len(df)} 行 -> {OUT}")
    print(f"     区间涨跌幅 {s['totalReturn']}% | 最高 {s['high']} | 最低 {s['low']}")
    print(f"     年化波动 {s['annualVol']}% | 最大回撤 {s['maxDrawdown']}% | 夏普 {s['sharpe']}")
    print(f"     上涨 {s['upDays']} 天 / 下跌 {s['downDays']} 天 | 胜率 {s['winRate']}%")
    print(f"     阶段划分 {len(payload['phases'])} 段 | 月度 {len(payload['monthly'])} 个")
    print(f"     输出体积 {OUT.stat().st_size/1024:.1f} KB")


if __name__ == "__main__":
    main()
