# -*- coding: utf-8 -*-
"""
获取季报/中报/年报财务数据

A股 + 港股 统一使用 THS_DS 按季度拉

指标：
  total_oi(营业收入), operating_cost(营业成本), ni(净利润),
  total_assets(资产总计), total_liab(负债合计), total_equity(股东权益合计)

存储：raw/financial/{market}/{code}.csv
字段：date, code, period, 营业收入, 营业成本, 净利润, 资产总计, 负债合计, 股东权益合计

增量逻辑：读本地文件最后一条 period，从下一天起拉 Interval:Q

运行：cd IFIND_DATA && python3 -u dataservice/scripts/fetch_financial.py
"""
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'sdk'))
WORKSPACE_ROOT = PROJECT_ROOT.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / '.env')
except ImportError:
    pass

from iFinDPy import THS_iFinDLogin, THS_iFinDLogout, THS_DS
import pandas as pd

# ===== 配置 =====
IFIND_USER = os.getenv('IFIND_USER', '')
IFIND_PASS = os.getenv('IFIND_PASS', '')
DATA_ROOT = str(WORKSPACE_ROOT / 'raw' / 'financial')

STOCKS_CN = [
    '601899.SH', '601600.SH', '600900.SH', '600938.SH', '603993.SH',
    '000807.SZ', '000933.SZ', '002532.SZ', '601225.SH', '000651.SZ',
    '000333.SZ', '600690.SH', '605499.SH', '600066.SH', '000951.SZ',
]
STOCKS_HK = ['2899.HK', '2600.HK', '6690.HK', '0700.HK', '3808.HK', '1171.HK']

START_YEAR = 2011
END_DATE = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

INDICATORS = 'total_oi;operating_cost;ni;total_assets;total_liab;total_equity'
PARAMS = '1,BB;1,BB;1,BB;1,BB;1,BB;1,BB'
OUT_COLS = ['date', 'code', 'period', '营业收入', '营业成本', '净利润', '资产总计', '负债合计', '股东权益合计']

FETCH_INTERVAL = 0.5

def log(msg):
    print(msg, flush=True)

def get_last_period(code, market):
    """读取本地文件最后一条 period"""
    filepath = os.path.join(DATA_ROOT, market, f'{code}.csv')
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return None
    try:
        df = pd.read_csv(filepath, usecols=['period'])
        return str(df['period'].iloc[-1]).strip()
    except Exception:
        return None

def fetch_stock(code, market):
    """拉取一只标的的季度财务数据（增量）"""
    last_period = get_last_period(code, market)

    start = f'{START_YEAR}-01-01'
    end = END_DATE

    if last_period:
        y, m, d = int(last_period[:4]), int(last_period[4:6]), int(last_period[6:])
        next_start = (datetime(y, m, d) + timedelta(days=1)).strftime('%Y-%m-%d')
        if next_start > end:
            log(f"  [跳过] 已是最新")
            return 0
        start = next_start
        log(f"  增量: {start} → {end}")

    for attempt in range(3):
        data = THS_DS(code, INDICATORS, PARAMS, 'Interval:Q', start, end)
        if data.errorcode == 0:
            break
        log(f"  ⚠️ 重试 {attempt+1}: {code} {data.errmsg[:60]}")
        time.sleep(3 * (attempt + 1))

    if data.errorcode != 0:
        log(f"  ❌ 失败 {code}")
        return 0

    df = data.data
    if df is None or (hasattr(df, 'empty') and df.empty):
        log(f"  → 无新数据")
        return 0

    rename = {
        'time': 'date', 'thscode': 'code',
        'total_oi': '营业收入', 'operating_cost': '营业成本',
        'ni': '净利润', 'total_assets': '资产总计',
        'total_liab': '负债合计', 'total_equity': '股东权益合计',
    }
    df = df.rename(columns=rename)
    df['period'] = df['date'].str.replace('-', '')
    for c in OUT_COLS:
        if c not in df.columns:
            df[c] = None
    df = df[OUT_COLS]

    # 过滤：至少有一个财务指标有数据
    fin_cols = ['营业收入', '营业成本', '净利润', '资产总计', '负债合计', '股东权益合计']
    before = len(df)
    df = df.dropna(subset=fin_cols, how='all')
    after = len(df)

    out_dir = os.path.join(DATA_ROOT, market)
    os.makedirs(out_dir, exist_ok=True)
    filepath = os.path.join(out_dir, f'{code}.csv')
    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    df.to_csv(filepath, mode='a', header=not file_exists, index=False)

    rows = len(df)
    log(f"  → +{rows} 行 (原始{before}行, 过滤{a-before}行全空)" if before != after else f"  → +{rows} 行")
    time.sleep(FETCH_INTERVAL)
    return rows

def main():
    log("=" * 60)
    log("iFinD 季度财务数据获取")
    log("=" * 60)
    log(f"A股: {len(STOCKS_CN)} 只")
    log(f"港股: {len(STOCKS_HK)} 只")
    log(f"起始年份: {START_YEAR}")
    log(f"输出: {DATA_ROOT}")
    log("")

    if not IFIND_USER or not IFIND_PASS:
        log("❌ 请在 dataservice/.env 中配置 IFIND_USER / IFIND_PASS")
        return

    ret = THS_iFinDLogin(IFIND_USER, IFIND_PASS)
    if ret != 0:
        log(f"❌ 登录失败: {ret}")
        return
    log("✅ 登录成功\n")

    total = 0
    try:
        log("--- A股 ---")
        for code in STOCKS_CN:
            log(f"📈 {code}")
            r = fetch_stock(code, 'cn')
            total += r
            log(f"  → 本批 {r} 行\n")

        log("--- 港股 ---")
        for code in STOCKS_HK:
            log(f"📈 {code}")
            r = fetch_stock(code, 'hk')
            total += r
            log(f"  → 本批 {r} 行\n")

        log("=" * 60)
        log(f"✅ 完成！本次总行数: {total:,}")
        log("=" * 60)

    finally:
        try:
            THS_iFinDLogout()
        except Exception:
            pass

if __name__ == '__main__':
    main()