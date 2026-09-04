# -*- coding: utf-8 -*-
"""
按年拉取股票截面指标（每年只取指定一天）

存储：raw/stock_data/{sh|sz|bj}/{code}.csv
策略：按年循环，每批 20 只一次请求当天数据。
增量：本地文件已有该截面日则跳过，不重复请求。
北交所（.BJ）不拉取。

用法：
    python3 dataservice/scripts/fetch_stock_data_yearly.py
"""
import json
import os
import sys
import time
from datetime import datetime
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

from iFinDPy import THS_iFinDLogin, THS_iFinDLogout, THS_DS
import pandas as pd


# ======================================================================
# 配置
# ======================================================================
IFIND_USER = os.getenv('IFIND_USER', '')
IFIND_PASS = os.getenv('IFIND_PASS', '')

LIST_FILE = 'zz_all_list_cn.csv'
LISTS_DIR = PROJECT_ROOT / 'data' / 'lists'
DATA_ROOT = WORKSPACE_ROOT / 'raw' / 'stock_data'
FAIL_DIR = PROJECT_ROOT / 'data' / 'ths_ds'

START_YEAR = int(os.getenv('HISTORY_START_YEAR', '2012'))
# 每年截面日（非交易日已换成相邻交易日）
SNAPSHOT_DATES = {
    2012: '2012-06-29',
    2013: '2013-07-01',
    2014: '2014-06-30',
    2015: '2015-06-30',
    2016: '2016-06-30',
    2017: '2017-06-30',
    2018: '2018-06-29',
    2019: '2019-07-01',
    2020: '2020-06-30',
    2021: '2021-06-30',
    2022: '2022-06-30',
    2023: '2023-06-30',
    2024: '2024-07-01',
    2025: '2025-06-30',
    2026: '2026-06-30',
}

INDICATORS = (
    'ths_the_citic_industry_stock;'
    'ths_market_value_stock;'
    'ths_current_mv_stock;'
    'ths_dividend_ps_stock;'
    'ths_dividend_yield_ttm_ex_sd_stock;'
    'ths_np_ttm_stock;'
    'ths_total_shares_stock;'
    'ths_float_ashare_stock;'
    'ths_free_float_shares_stock;'
    'ths_af_stock'
)
PARAMS = '1;;;;;100;;;;'

# 接口英文字段 → 本地中文表头（按此顺序落盘）
HEADER_MAP = [
    ('date', '日期'),
    ('thscode', '股票代码'),
    ('ths_the_citic_industry_stock', '所属中信行业'),
    ('ths_market_value_stock', '总市值'),
    ('ths_current_mv_stock', '流通市值'),
    ('ths_dividend_ps_stock', '每股分红送转'),
    ('ths_dividend_yield_ttm_ex_sd_stock', '股息率TTM（不含特别分红）'),
    ('ths_np_ttm_stock', 'TTM归母净利润'),
    ('ths_total_shares_stock', '总股本'),
    ('ths_float_ashare_stock', '流通A股'),
    ('ths_free_float_shares_stock', '自由流通股本'),
    ('ths_af_stock', '后复权因子'),
]
COLUMNS_CN = [cn for _, cn in HEADER_MAP]

BATCH_SIZE = 20
REQ_INTERVAL = 0.15
MAX_RETRIES = 3
MARKET_DEFAULT = 'cn'
SKIP_SUFFIXES = ('.BJ',)  # 北交所本地已齐全，不再拉取
# ======================================================================


def snapshot_years(now=None):
    """只拉日期表里、且已经到了的年份。"""
    now = now or datetime.now()
    years = []
    for year, day in SNAPSHOT_DATES.items():
        if year < START_YEAR:
            continue
        if datetime.strptime(day, '%Y-%m-%d').date() <= now.date():
            years.append(year)
    return years


def snapshot_date(year):
    return SNAPSHOT_DATES[year]


def load_codes():
    path = LISTS_DIR / LIST_FILE
    if not path.exists():
        print(f"错误：清单文件不存在: {path}")
        sys.exit(1)
    df = pd.read_csv(path)
    col = 'thscode' if 'thscode' in df.columns else df.columns[0]
    codes = df[col].dropna().astype(str).str.strip().tolist()
    skip = tuple(s.upper() for s in SKIP_SUFFIXES)
    kept = [c for c in codes if not c.upper().endswith(skip)]
    skipped = len(codes) - len(kept)
    if skipped:
        print(f"  已跳过北交所 {skipped} 只（本地已齐全）")
    return kept


def guess_market(code):
    suffix = code.split('.')[-1] if '.' in code else ''
    return {'SH': 'sh', 'SZ': 'sz', 'BJ': 'bj'}.get(suffix, MARKET_DEFAULT)


def filepath_for(code):
    return DATA_ROOT / guess_market(code) / f'{code}.csv'


def existing_dates(code):
    """读取本地已有的日期（YYYY-MM-DD），用于增量跳过。"""
    fpath = filepath_for(code)
    if not fpath.exists() or fpath.stat().st_size == 0:
        return set()
    try:
        df = pd.read_csv(fpath)
        col = '日期' if '日期' in df.columns else df.columns[0]
        dates = set()
        for v in df[col].dropna().astype(str):
            day = v.strip()[:10]
            if len(day) == 10:
                dates.add(day)
        return dates
    except Exception as e:
        print(f"  警告：读取 {fpath} 失败: {e}")
        return set()


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def fetch_ds(codes, start, end):
    code_str = ','.join(codes)
    data = None
    for attempt in range(1, MAX_RETRIES + 1):
        data = THS_DS(code_str, INDICATORS, PARAMS, '', start, end)
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


def split_by_code(df, batch):
    """把批量返回拆成 {code: DataFrame}，每只保留当天一行。"""
    if df is None or df.empty:
        return {}
    code_col = 'thscode' if 'thscode' in df.columns else None
    if code_col is None:
        if len(batch) == 1:
            return {batch[0]: df.tail(1)}
        return {}
    out = {}
    for code, rec in df.groupby(code_col):
        out[str(code).strip()] = rec.tail(1)
    return out


def to_output_row(df):
    """只保留对照表字段，表头改成中文后写入。"""
    row = df.copy()
    row.columns = [str(c).strip() for c in row.columns]
    # THS_DS 时间列名是 time，按对照表统一成 date
    if 'date' not in row.columns and 'time' in row.columns:
        row = row.rename(columns={'time': 'date'})
    lower = {c.lower(): c for c in row.columns}
    out = pd.DataFrame(index=row.index)
    for en, cn in HEADER_MAP:
        src = en if en in row.columns else lower.get(en.lower())
        out[cn] = row[src].values if src else None
    out['日期'] = pd.to_datetime(out['日期'], errors='coerce').dt.strftime('%Y-%m-%d')
    return out[COLUMNS_CN]


def upsert_row(code, row):
    fpath = filepath_for(code)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    if fpath.exists() and fpath.stat().st_size > 0:
        old = pd.read_csv(fpath)
        combined = pd.concat([old, row], ignore_index=True)
        combined['日期'] = combined['日期'].astype(str)
        combined = combined.drop_duplicates(subset=['日期'], keep='last')
        combined = combined.sort_values('日期')
        combined.to_csv(fpath, index=False, encoding='utf-8-sig')
    else:
        row.to_csv(fpath, index=False, encoding='utf-8-sig')


def save_picked(code, picked, saved):
    if picked is None or picked.empty:
        return
    upsert_row(code, to_output_row(picked))
    saved.add(code)


def fetch_year(year, pending, fail_list):
    day = snapshot_date(year)
    saved = set()
    empty = 0

    def save_from_df(df, batch):
        n = 0
        for code, rec in split_by_code(df, batch).items():
            save_picked(code, rec, saved)
            n += 1
        return n

    total_batches = (len(pending) - 1) // BATCH_SIZE + 1
    for batch_i, batch in enumerate(chunks(pending, BATCH_SIZE), 1):
        print(f"  [{day}] 批 {batch_i}/{total_batches} "
              f"{batch[0]}..{batch[-1]} ({len(batch)}只) ...", end='', flush=True)

        df, err = fetch_ds(batch, day, day)
        if err is not None:
            print(" ✗ 批量失败，改单只")
            for code in batch:
                df_one, err_one = fetch_ds([code], day, day)
                if err_one is not None:
                    fail_list[f'{code}:{year}'] = err_one
                    print(f"    {code} ✗ ({err_one})")
                    continue
                if save_from_df(df_one, [code]) == 0:
                    empty += 1
            time.sleep(REQ_INTERVAL)
            continue

        got = save_from_df(df, batch)
        empty += len(batch) - got
        print(f" ✓ 写入 {got} / 无数据 {len(batch) - got}")
        time.sleep(REQ_INTERVAL)

    return len(saved), empty, saved


def main():
    FAIL_DIR.mkdir(parents=True, exist_ok=True)
    years = snapshot_years()
    tag = datetime.now().strftime('%Y%m%d')

    if not years:
        print("错误：没有可拉取的截面日期")
        sys.exit(1)

    print("===== 股票年截面数据下载（每年一天）=====\n")
    print(f"清单: {LIST_FILE}")
    days = [SNAPSHOT_DATES[y] for y in years]
    print(f"截面日: {', '.join(days)}")
    print(f"批量: {BATCH_SIZE} 只/次")
    print(f"年份: {years[0]} - {years[-1]}")
    print(f"输出: {DATA_ROOT}/{{sh|sz|bj}}/{{code}}.csv")
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

    codes = load_codes()
    total = len(codes)
    print(f"清单共 {total} 只\n")

    have_dates = {code: existing_dates(code) for code in codes}
    fail_list = {}
    total_wrote = 0
    total_empty = 0

    try:
        for year in years:
            day = snapshot_date(year)
            pending = [c for c in codes if day not in have_dates[c]]
            if not pending:
                print(f"[{day}] 全部已有，跳过")
                continue
            print(f"[{day}] 待拉取 {len(pending)} / {total} 只")
            wrote, empty, saved = fetch_year(year, pending, fail_list)
            total_wrote += wrote
            total_empty += empty
            for code in saved:
                have_dates[code].add(day)
            print()
    finally:
        try:
            THS_iFinDLogout()
        except Exception:
            pass

    print("===== 完成 =====")
    print(f"本次写入: {total_wrote} 行")
    print(f"无数据（未上市等）: {total_empty} 次")
    print(f"失败: {len(fail_list)}")
    if fail_list:
        for key, err in list(fail_list.items())[:20]:
            print(f"  {key}: {err}")
        fail_path = FAIL_DIR / f'fail_list_yearly_{tag}.json'
        fail_path.write_text(
            json.dumps(fail_list, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        print(f"失败记录: {fail_path}")


if __name__ == '__main__':
    main()
