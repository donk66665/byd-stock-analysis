"""
01_collect.py — 比亚迪(002594)后复权日线采集与对齐

职责：
  1. 读取教材原始 xlsx（2023 全年 242 个交易日）
  2. 从东方财富（akshare）拉取 2023-01-01 至最新交易日的后复权日线
  3. 在 2023 年重叠区间逐列校验，确认复权基准一致后才拼接
  4. 输出合并数据集 + 采集报告

用法：python scripts/01_collect.py
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

import akshare as ak
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW_XLSX = ROOT / "data" / "raw" / "比亚迪后复权历史行情数据.xlsx"
OUT_CSV = ROOT / "data" / "byd_hfq_full.csv"
REPORT = ROOT / "data" / "collect_report.txt"

SYMBOL = "002594"
PRICE_COLS = ["开盘", "收盘", "最高", "最低", "涨跌额"]
VOLUME_COLS = ["成交量", "成交额"]
PCT_COLS = ["振幅", "涨跌幅", "换手率"]
NUM_COLS = PRICE_COLS + VOLUME_COLS + PCT_COLS

TOLERANCE = 0.01  # 元，价格容差
lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


def load_raw() -> pd.DataFrame:
    """读教材 xlsx，兼容「日期为 Excel 序列号」的存储方式。"""
    df = pd.read_excel(RAW_XLSX)
    df.columns = [str(c).strip() for c in df.columns]

    if pd.api.types.is_numeric_dtype(df["日期"]):
        df["日期"] = pd.to_datetime(
            df["日期"].astype("int64"), unit="D", origin="1899-12-30"
        )
    else:
        df["日期"] = pd.to_datetime(df["日期"])
    return df.sort_values("日期").reset_index(drop=True)


def fetch(start: str, end: str, retries: int = 3) -> pd.DataFrame:
    """拉取后复权日线，带重试。"""
    last_err: Exception | None = None
    for i in range(retries):
        try:
            df = ak.stock_zh_a_hist(
                symbol=SYMBOL,
                period="daily",
                start_date=start,
                end_date=end,
                adjust="hfq",
            )
            if df is None or df.empty:
                raise RuntimeError("接口返回空数据")
            df = df.drop(columns=["股票代码"], errors="ignore")
            df["日期"] = pd.to_datetime(df["日期"])
            return df.sort_values("日期").reset_index(drop=True)
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            log(f"  第 {i + 1} 次请求失败：{type(exc).__name__}: {exc}")
    raise RuntimeError(f"数据拉取失败：{last_err}")


def main() -> int:
    today = dt.date.today()
    log("=" * 62)
    log("比亚迪(002594) 后复权日线采集报告")
    log(f"执行时间：{today.isoformat()}")
    log("=" * 62)

    # ---------- 1. 原始数据 ----------
    raw = load_raw()
    log("\n[1] 教材原始 xlsx")
    log(f"  形状：{raw.shape[0]} 行 × {raw.shape[1]} 列")
    log(f"  区间：{raw['日期'].min():%Y-%m-%d} ~ {raw['日期'].max():%Y-%m-%d}")
    log(f"  列名：{', '.join(raw.columns)}")

    # ---------- 2. 远程数据 ----------
    start = raw["日期"].min().strftime("%Y%m%d")
    end = today.strftime("%Y%m%d")
    log(f"\n[2] 远程拉取 {start} ~ {end}（adjust=hfq）")
    remote = fetch(start, end)
    log(f"  形状：{remote.shape[0]} 行 × {remote.shape[1]} 列")
    log(f"  区间：{remote['日期'].min():%Y-%m-%d} ~ {remote['日期'].max():%Y-%m-%d}")

    # ---------- 3. 重叠区校验 ----------
    log("\n[3] 重叠区间校验（2023 年）")
    merged_check = raw.merge(
        remote, on="日期", suffixes=("_raw", "_api"), how="inner"
    )
    log(f"  可比对交易日：{len(merged_check)} / {len(raw)}")
    if len(merged_check) != len(raw):
        log("  [警告] 存在无法匹配的交易日，需人工核查")

    ok = True
    for col in NUM_COLS:
        a = merged_check[f"{col}_raw"].astype(float)
        b = merged_check[f"{col}_api"].astype(float)
        diff = (a - b).abs()
        max_diff = float(np.nanmax(diff.values)) if len(diff) else float("nan")
        bad = int((diff > TOLERANCE).sum())
        flag = "OK " if bad == 0 else "FAIL"
        if col in PRICE_COLS and bad:
            ok = False
        log(f"  {flag} {col:<5} 最大绝对偏差 {max_diff:.6f}  超差 {bad} 条")

    if not ok:
        log("\n  [中止] 价格列偏差超容差，复权基准可能不一致，禁止直接拼接。")
        REPORT.write_text("\n".join(lines), encoding="utf-8")
        return 1
    log("  => 复权基准一致，可安全拼接")

    # ---------- 4. 合并 ----------
    # 以教材原始数据为准（2023），远程数据补 2024 年起
    tail = remote[remote["日期"] > raw["日期"].max()].copy()
    full = pd.concat([raw, tail], ignore_index=True)
    full = full.drop_duplicates(subset="日期", keep="first").sort_values("日期")
    full = full.reset_index(drop=True)

    log("\n[4] 合并结果")
    log(f"  总行数：{len(full)}（原始 {len(raw)} + 新增 {len(tail)}）")
    log(f"  区间：{full['日期'].min():%Y-%m-%d} ~ {full['日期'].max():%Y-%m-%d}")
    gaps = full["日期"].diff().dt.days
    log(f"  最大自然日间隔：{int(gaps.max())} 天（含长假属正常）")

    full.insert(0, "序号", range(1, len(full) + 1))
    full.to_csv(OUT_CSV, index=False, encoding="utf-8")
    log(f"  已写出：{OUT_CSV.relative_to(ROOT)}")

    log("\n[5] 年度分布")
    for year, g in full.groupby(full["日期"].dt.year):
        log(f"  {year}: {len(g):>3} 个交易日  "
            f"收盘 {g['收盘'].iloc[0]:.2f} -> {g['收盘'].iloc[-1]:.2f}")

    REPORT.write_text("\n".join(lines), encoding="utf-8")
    log(f"\n报告已保存：{REPORT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
