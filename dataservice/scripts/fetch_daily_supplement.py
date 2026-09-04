# -*- coding: utf-8 -*-
"""
获取流通股本 + 近12月股息率（日频）

使用 THS_DS 批量获取日频序列，不区分 A股/港股。
指标：floating_shares（流通股）, dividend_rate_12m（近12月股息率）

存储：raw/supplement/{market}/{code}.csv
字段：date, code, floating_shares, dividend_rate_12m
断点续传：读文件最后日期续拉

运行：cd IFIND_DATA && python3 -u dataservice/scripts/fetch_daily_supplement.py
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
DATA_ROOT = str(WORKSPACE_ROOT / 'raw' / 'supplement')

STOCKS_ALL = [
    # A股
    '601899.SH', '601600.SH', '600900.SH', '600938.SH', '603993.SH',
    '000807.SZ', '000933.SZ', '002532.SZ', '601225.SH', '000651.SZ',
    '000333.SZ', '600690.SH', '605499.SH', '600066.SH', '000951.SZ',
    # 港股
    '2899.HK', '2600.HK', '6690.HK', '0700.HK', '3808.HK', '1171.HK',
]

START_DATE = '2012-01-01'
HISTORY_END = '2026-08-31'
FETCH_INTERVAL = 0.5

INDICATORS = 'floating_shares;dividend_rate_12m'
PARAMS = ';'
OUT_COLS = ['date', 'code', 'floating_shares', 'dividend_rate_12m']

def log(msg):
    print(msg, flush=True)

def market_of(code):
    """根据代码后缀判断市场目录"""
    if code.endswith('.HK'):
        return 'hk'
    return 'cn'

def fetch_one(code):
    """拉取一只标的的流通股+股息率（按年分文件）"""
    market = market_of(code)
    out_root = os.path.join(DATA_ROOT, market)

    start_year = int(START_DATE[:4])
    end_year = int(HISTORY_END[:4])
    total = 0

    for year in range(start_year, end_year + 1):
        year_start = f'{year}-01-01'
        year_end = f'{year}-12-31'
        if year == end_year:
            year_end = HISTORY_END

        # 按年分文件：raw/supplement/{market}/{year}/{code}.csv
        out_dir = os.path.join(out_root, str(year))
        os.makedirs(out_dir, exist_ok=True)
        filepath = os.path.join(out_dir, f'{code}.csv')

        # 断点续传
        last_date = None
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            try:
                ldf = pd.read_csv(filepath, usecols=['date'])
                last_date = str(ldf['date'].iloc[-1]).strip()[:10]
            except:
                pass

        if last_date:
            try:
                ld = datetime.strptime(last_date, '%Y-%m-%d')
                if ld >= datetime.strptime(year_end, '%Y-%m-%d'):
                    continue
                year_start = (ld + timedelta(days=1)).strftime('%Y-%m-%d')
            except:
                pass

        if year_start > year_end:
            continue

        for attempt in range(3):
            data = THS_DS(code, INDICATORS, PARAMS, '', year_start, year_end)
            if data.errorcode == 0:
                break
            log(f"  ⚠️ 重试 {attempt+1}: {code} [{year}] {data.errmsg[:60]}")
            time.sleep(2 * (attempt + 1))

        if data.errorcode != 0:
            log(f"  ❌ 失败 {code} [{year}]")
            continue

        df = data.data
        if df is None or df.empty:
            log(f"    {year}: 无数据")
            time.sleep(FETCH_INTERVAL)
            continue

        df = df.rename(columns={'time': 'date', 'thscode': 'code'})
        for c in OUT_COLS:
            if c not in df.columns:
                df[c] = None
        df = df[OUT_COLS]

        file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
        df.to_csv(filepath, mode='a', header=not file_exists, index=False)
        total += len(df)
        log(f"    {year}: +{len(df)} 行")
        time.sleep(FETCH_INTERVAL)

    return total

def main():
    log("=" * 60)
    log("iFinD 流通股本 + 股息率 日频数据获取")
    log("=" * 60)
    log(f"标的: {len(STOCKS_ALL)} 只（A股+港股统一用 floating_shares）")
    log(f"指标: {INDICATORS}")
    log(f"输出: {DATA_ROOT}/{{market}}/{{code}}.csv")
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
        for code in STOCKS_ALL:
            log(f"📈 {code}")
            r = fetch_one(code)
            total += r
            log(f"  → {r} 行\n")

        log("=" * 60)
        log(f"✅ 完成！总行数: {total:,}")
        log("=" * 60)

    finally:
        try:
            THS_iFinDLogout()
        except Exception:
            pass

if __name__ == '__main__':
    main()