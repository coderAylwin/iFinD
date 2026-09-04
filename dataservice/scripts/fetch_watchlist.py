# -*- coding: utf-8 -*-
"""
拉取指定A股+港股标的日线数据（原始价格 + 复权因子）

标的：
  A股: 601899.SH, 601600.SH, 600900.SH, 600938.SH, 603993.SH,
       000807.SZ, 000933.SZ, 002532.SZ, 601225.SH, 000651.SZ,
       000333.SZ, 600690.SH, 605499.SH, 600066.SH, 000951.SZ
  港股: 2899.HK, 2600.HK, 6690.HK, 0700.HK, 3808.HK, 1171.HK

字段：date, code, open, high, low, close, volume, amount, af, af2
存储：raw/daily/{market}/{year}/{code}.csv（按年分文件）
断点续传：每次只拉缺的年份

运行：cd IFIND_DATA && python3 -u dataservice/scripts/fetch_watchlist.py
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
DATA_ROOT = str(WORKSPACE_ROOT / 'raw' / 'daily')

STOCKS_CN = [
    '601899.SH', '601600.SH', '600900.SH', '600938.SH', '603993.SH',
    '000807.SZ', '000933.SZ', '002532.SZ', '601225.SH', '000651.SZ',
    '000333.SZ', '600690.SH', '605499.SH', '600066.SH', '000951.SZ',
]
STOCKS_HK = ['2899.HK', '2600.HK', '6690.HK', '0700.HK', '3808.HK', '1171.HK']

START_DATE = '2012-01-01'
END_DATE = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

INDICATORS = (
    'ths_af_stock;ths_af2_stock;'
    'ths_open_price_stock;ths_high_price_stock;ths_low_stock;'
    'ths_close_price_stock;ths_vol_stock;ths_amt_stock'
)
PARAMS = ';;0;0;0;0;0;0'
OUT_COLS = ['date', 'code', 'open', 'high', 'low', 'close', 'volume', 'amount', 'af', 'af2']
FETCH_INTERVAL = 0.5

def log(msg):
    print(msg, flush=True)

def append_to_csv(code, market, year, df):
    if df is None or df.empty:
        return 0
    year_dir = os.path.join(DATA_ROOT, market, str(year))
    os.makedirs(year_dir, exist_ok=True)
    filepath = os.path.join(year_dir, f'{code}.csv')
    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
    df.to_csv(filepath, mode='a', header=not file_exists, index=False)
    return len(df)

def read_last_date(code, market, year):
    filepath = os.path.join(DATA_ROOT, market, str(year), f'{code}.csv')
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return None
    try:
        df = pd.read_csv(filepath, usecols=['date'])
        return str(df['date'].iloc[-1]).strip()[:10]
    except Exception:
        return None

def fetch_and_save(code, market, start, end):
    start_year = int(start[:4])
    end_year = int(end[:4])
    total = 0
    for year in range(start_year, end_year + 1):
        year_start = f'{year}-01-01'
        year_end = f'{year}-12-31'
        if year == end_year:
            year_end = end

        last_date = read_last_date(code, market, year)
        if last_date:
            try:
                ld = datetime.strptime(last_date, '%Y-%m-%d')
                if ld >= datetime.strptime(year_end, '%Y-%m-%d'):
                    continue
                year_start = (ld + timedelta(days=1)).strftime('%Y-%m-%d')
            except ValueError:
                pass

        if year_start > year_end:
            continue

        for attempt in range(3):
            data = THS_DS(code, INDICATORS, PARAMS, '', year_start, year_end)
            if data.errorcode == 0:
                break
            log(f"  ⚠️ 重试 {attempt+1}: {code} [{year}] {data.errmsg}")
            time.sleep(2 * (attempt + 1))

        if data.errorcode != 0:
            log(f"  ❌ 失败 {code} [{year}]: {data.errmsg}")
            continue

        df = data.data
        if df is None or df.empty:
            log(f"    {year}: 无数据")
            time.sleep(FETCH_INTERVAL)
            continue

        rename = {
            'time': 'date', 'thscode': 'code',
            'ths_af_stock': 'af', 'ths_af2_stock': 'af2',
            'ths_open_price_stock': 'open', 'ths_high_price_stock': 'high',
            'ths_low_stock': 'low', 'ths_close_price_stock': 'close',
            'ths_vol_stock': 'volume', 'ths_amt_stock': 'amount',
        }
        df = df.rename(columns=rename)
        for c in OUT_COLS:
            if c not in df.columns:
                df[c] = None
        df = df[OUT_COLS]

        rows = append_to_csv(code, market, year, df)
        total += rows
        log(f"    {year}: +{rows} 行")
        time.sleep(FETCH_INTERVAL)

    return total

def main():
    log("=" * 60)
    log("iFinD 自选标的日线数据获取")
    log("=" * 60)
    log(f"范围: {START_DATE} → {END_DATE}")
    log(f"A股: {len(STOCKS_CN)} 只")
    log(f"港股: {len(STOCKS_HK)} 只")
    log(f"目录: {DATA_ROOT}")
    log("")

    if not IFIND_USER or not IFIND_PASS:
        log("❌ 请在 dataservice/.env 中配置 IFIND_USER / IFIND_PASS")
        return

    ret = THS_iFinDLogin(IFIND_USER, IFIND_PASS)
    if ret != 0:
        log(f"❌ 登录失败: {ret}")
        return
    log("✅ 登录成功\n")

    total_rows = 0
    try:
        log("--- A股 ---")
        for code in STOCKS_CN:
            log(f"📈 {code}")
            r = fetch_and_save(code, 'cn', START_DATE, END_DATE)
            total_rows += r
            log(f"  → {r} 行\n")

        log("--- 港股 ---")
        for code in STOCKS_HK:
            log(f"📈 {code}")
            r = fetch_and_save(code, 'hk', START_DATE, END_DATE)
            total_rows += r
            log(f"  → {r} 行\n")

        log("=" * 60)
        log(f"✅ 完成！")
        log(f"   总共 {total_rows:,} 行")
        log("=" * 60)
    finally:
        try:
            THS_iFinDLogout()
        except Exception:
            pass

if __name__ == '__main__':
    main()