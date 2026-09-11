# -*- coding: utf-8 -*-
"""
自选 A 股 / 港股 1 分钟 K 线（THS_HF）

A股：CPS:backward2, Fill:Original，时段 09:15–15:00
港股：CPS:backward1, Fill:Original，时段 09:30–16:00
区间：2024-01-01 开盘 → 2026-08-31 收盘（写在脚本内）
存储：raw/watchlist_1m/{cn|hk}/{year}/{code}.csv
增量：读当年文件最后时间戳，从下一秒续拉。

用法：
    python3 -u dataservice/scripts/fetch_watchlist_1m.py
"""
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
WORKSPACE_ROOT = PROJECT_ROOT.parent
sys.path.insert(0, str(PROJECT_ROOT / 'sdk'))

try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv(WORKSPACE_ROOT / '.env')
except ImportError:
    raise

from iFinDPy import THS_iFinDLogin, THS_iFinDLogout, THS_HF
import pandas as pd


# ======================================================================
# 配置
# ======================================================================
IFIND_USER = os.getenv('IFIND_USER', '')
IFIND_PASS = os.getenv('IFIND_PASS', '')
DATA_ROOT = WORKSPACE_ROOT / 'raw' / 'watchlist_1m'

STOCKS_CN_RAW = [
    '601899', '601600', '600900', '600938', '603993',
    '000807', '000933', '002532', '601225', '000651',
    '000333', '600690', '605499', '600066', '000951',
]
STOCKS_HK_RAW = ['0700', '1171']

DATE_START = '2024-01-01'
DATE_END = '2026-08-31'

INDICATORS = 'open;high;low;close;avgPrice;volume;amount'
OUT_COLS = ['time', 'code', 'open', 'high', 'low', 'close', 'avgPrice', 'volume', 'amount']

CN_JSONPARAM = 'CPS:backward2,Fill:Original'
HK_JSONPARAM = 'CPS:backward1,Fill:Original'
CN_OPEN, CN_CLOSE = '09:15:00', '15:00:00'
HK_OPEN, HK_CLOSE = '09:30:00', '16:00:00'

REQ_INTERVAL = 0.3
MAX_RETRIES = 3
# ======================================================================


def complete_code(raw, market):
    s = str(raw).strip().upper()
    for suf in ('.SH', '.SZ', '.HK'):
        if s.endswith(suf):
            s = s[: -len(suf)]
    s = ''.join(ch for ch in s if ch.isdigit())
    if market == 'hk':
        return f'{s.zfill(4)}.HK'
    s = s.zfill(6)
    if s.startswith(('000', '001', '002', '003', '300', '301')):
        return f'{s}.SZ'
    return f'{s}.SH'


def stock_list():
    items = []
    for raw in STOCKS_CN_RAW:
        items.append((complete_code(raw, 'cn'), 'cn', CN_JSONPARAM, CN_OPEN, CN_CLOSE))
    for raw in STOCKS_HK_RAW:
        items.append((complete_code(raw, 'hk'), 'hk', HK_JSONPARAM, HK_OPEN, HK_CLOSE))
    return items


def month_iter():
    start = datetime.strptime(DATE_START, '%Y-%m-%d')
    end = datetime.strptime(DATE_END, '%Y-%m-%d')
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def month_end_day(year, month):
    if month == 12:
        return 31
    return (datetime(year, month + 1, 1) - timedelta(days=1)).day


def month_window(year, month, open_t, close_t):
    start_d = datetime(year, month, 1)
    end_d = datetime(year, month, month_end_day(year, month))
    range_start = datetime.strptime(DATE_START, '%Y-%m-%d')
    range_end = datetime.strptime(DATE_END, '%Y-%m-%d')
    if start_d < range_start:
        start_d = range_start
    if end_d > range_end:
        end_d = range_end
    start = f'{start_d.strftime("%Y-%m-%d")} {open_t}'
    end = f'{end_d.strftime("%Y-%m-%d")} {close_t}'
    return start, end


def filepath_for(code, market, year):
    return DATA_ROOT / market / str(year) / f'{code}.csv'


def read_last_timestamp(code, market, year):
    fpath = filepath_for(code, market, year)
    if not fpath.exists() or fpath.stat().st_size == 0:
        return None
    try:
        df = pd.read_csv(fpath)
        if df.empty:
            return None
        col = 'time' if 'time' in df.columns else df.columns[0]
        last = str(df[col].iloc[-1]).strip()
        return last if last else None
    except Exception as e:
        print(f"  警告：读取 {fpath} 最后时间失败: {e}")
        return None


def parse_ts(value):
    s = str(value).strip()
    if len(s) == 16:
        s += ':00'
    return datetime.strptime(s[:19], '%Y-%m-%d %H:%M:%S')


def to_output(df, code):
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    if 'time' not in out.columns:
        if 'date' in out.columns:
            out['time'] = out['date'].astype(str)
        else:
            raise ValueError('返回结果无 time/date 列')
    out['time'] = out['time'].astype(str)
    if 'thscode' in out.columns:
        out['code'] = out['thscode']
    elif 'code' not in out.columns:
        out['code'] = code
    for col in OUT_COLS:
        if col not in out.columns:
            out[col] = None
    return out[OUT_COLS]


def append_rows(code, market, df):
    if df is None or df.empty:
        return 0
    out = df.copy()
    out['__year'] = out['time'].astype(str).str[:4]
    total = 0
    for year, group in out.groupby('__year'):
        fpath = filepath_for(code, market, int(year))
        fpath.parent.mkdir(parents=True, exist_ok=True)
        drop = group.drop(columns=['__year'])
        exists = fpath.exists() and fpath.stat().st_size > 0
        drop.to_csv(fpath, mode='a', header=not exists, index=False, encoding='utf-8-sig')
        total += len(drop)
    return total


def fetch_month(code, market, jsonparam, start, end):
    data = None
    for attempt in range(1, MAX_RETRIES + 1):
        data = THS_HF(code, INDICATORS, jsonparam, start, end)
        if data.errorcode == 0:
            df = data.data
            if df is None or (hasattr(df, 'empty') and df.empty):
                return pd.DataFrame(), None
            return df, None
        err = f"ec={data.errorcode} {data.errmsg}"
        if attempt < MAX_RETRIES:
            print(f"    重试 {attempt}: {err}")
            time.sleep(2 * attempt)
        else:
            return None, err
    return None, "retries_exhausted"


def fetch_code(code, market, jsonparam, open_t, close_t):
    rows = 0
    empty = 0
    errors = 0
    for year, month in month_iter():
        start, end = month_window(year, month, open_t, close_t)
        last_ts = read_last_timestamp(code, market, year)
        if last_ts:
            try:
                lt = parse_ts(last_ts)
                st = parse_ts(start)
                if lt >= st:
                    start = (lt + timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')
            except ValueError:
                pass
        try:
            if parse_ts(start) >= parse_ts(end):
                continue
        except ValueError:
            pass

        print(f"  {code} [{year}-{month:02d}] {start} → {end} ...", end='', flush=True)
        df, err = fetch_month(code, market, jsonparam, start, end)
        if err is not None:
            errors += 1
            print(f" ✗ ({err})")
            time.sleep(REQ_INTERVAL)
            continue
        if df is None or df.empty:
            empty += 1
            print(" 无数据")
            time.sleep(REQ_INTERVAL)
            continue
        n = append_rows(code, market, to_output(df, code))
        rows += n
        print(f" ✓ +{n} 行")
        time.sleep(REQ_INTERVAL)
    return rows, empty, errors


def main():
    items = stock_list()
    print("===== 自选标的 1 分钟 K 线 =====\n")
    print(f"区间: {DATE_START} 开盘 → {DATE_END} 收盘")
    print("A股: " + ', '.join(c for c, m, *_ in items if m == 'cn'))
    print("港股: " + ', '.join(c for c, m, *_ in items if m == 'hk'))
    print(f"A股参数: {CN_JSONPARAM}  {CN_OPEN}–{CN_CLOSE}")
    print(f"港股参数: {HK_JSONPARAM}  {HK_OPEN}–{HK_CLOSE}")
    print(f"输出: {DATA_ROOT}/{{cn|hk}}/{{year}}/{{code}}.csv")
    print()

    if not IFIND_USER or not IFIND_PASS:
        print("错误：请在 dataservice/.env 中配置 IFIND_USER 和 IFIND_PASS")
        sys.exit(1)

    for _ in range(3):
        ret = THS_iFinDLogin(IFIND_USER, IFIND_PASS)
        if ret == 0:
            break
        print(f"登录失败 (ret={ret}) 重试...")
        time.sleep(3)
    else:
        print("登录失败")
        sys.exit(1)
    print("登录成功\n")

    total_rows = 0
    total_empty = 0
    total_errors = 0
    try:
        for i, (code, market, jsonparam, open_t, close_t) in enumerate(items, 1):
            print(f"[{i}/{len(items)}] {code} ({market})")
            rows, empty, errors = fetch_code(code, market, jsonparam, open_t, close_t)
            total_rows += rows
            total_empty += empty
            total_errors += errors
            print()
    finally:
        try:
            THS_iFinDLogout()
        except Exception:
            pass

    print("===== 完成 =====")
    print(f"新增行数: {total_rows}")
    print(f"无数据: {total_empty} 次")
    print(f"失败: {total_errors} 次")


if __name__ == '__main__':
    main()
