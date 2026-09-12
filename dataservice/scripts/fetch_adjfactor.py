# -*- coding: utf-8 -*-
"""
按年拉取股票后复权因子（THS_DS / ths_af_stock）

年份：.env 的 HISTORY_START_YEAR / HISTORY_END_YEAR
清单：.env 的 STOCK_LISTS_DAILY
存储：raw/adjfactor/{market}/{year}/{code}.csv
增量：读本地该年文件最后日期，从下一天续拉；整年已齐则跳过。
当年只拉到当天。

用法：
    python3 -u dataservice/scripts/fetch_adjfactor.py
"""
import json
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

from iFinDPy import THS_iFinDLogin, THS_iFinDLogout, THS_DS
import pandas as pd


# ======================================================================
# 配置
# ======================================================================
IFIND_USER = os.getenv('IFIND_USER', '')
IFIND_PASS = os.getenv('IFIND_PASS', '')

HISTORY_START_YEAR = int(os.getenv('HISTORY_START_YEAR', str(datetime.now().year - 1)))
HISTORY_END_YEAR = int(os.getenv('HISTORY_END_YEAR', str(datetime.now().year)))
STOCK_LISTS = os.getenv('STOCK_LISTS_DAILY', os.getenv('STOCK_LISTS', 'zz_all_list_cn.csv'))

LISTS_DIR = PROJECT_ROOT / 'data' / 'lists'
DATA_ROOT = WORKSPACE_ROOT / 'raw' / 'adjfactor'
FAIL_DIR = PROJECT_ROOT / 'data' / 'ths_ds'

INDICATORS = 'ths_af_stock'
PARAMS = ''

COLUMNS = ['日期', '股票代码', '后复权因子']
BATCH_SIZE = 20
REQ_INTERVAL = 0.15
MAX_RETRIES = 3
# ======================================================================


def guess_market_from_listname(list_name):
    stem = Path(list_name).stem
    parts = stem.split('_')
    if len(parts) >= 2:
        suffix = parts[-1]
        if len(suffix) <= 6 and suffix.isalpha():
            return suffix.lower()
    return 'cn'


def year_bounds(year, today):
    start = f'{year}-01-01'
    end = f'{year}-12-31'
    today_str = today.strftime('%Y-%m-%d')
    if end > today_str:
        end = today_str
    return start, end


def has_weekday(start, end):
    """区间内是否包含周一到周五（无交易日历时，用来跳过纯周末空请求）。"""
    d = datetime.strptime(start, '%Y-%m-%d')
    e = datetime.strptime(end, '%Y-%m-%d')
    while d <= e:
        if d.weekday() < 5:
            return True
        d += timedelta(days=1)
    return False


def load_stock_lists():
    items = []
    seen = set()
    for name in [x.strip() for x in STOCK_LISTS.split(',') if x.strip()]:
        path = LISTS_DIR / name
        if not path.exists():
            print(f"  警告：清单文件不存在: {path}")
            continue
        try:
            market = guess_market_from_listname(name)
            df = pd.read_csv(path)
            col = 'thscode' if 'thscode' in df.columns else df.columns[0]
            n = 0
            for c in df[col].dropna():
                c = str(c).strip()
                key = (c, market)
                if key not in seen:
                    seen.add(key)
                    items.append(key)
                    n += 1
            print(f"  已加载清单: {name} (市场={market}, {n} 只)")
        except Exception as e:
            print(f"  警告：读取清单 {name} 失败: {e}")
    return items


def filepath_for(code, market, year):
    return DATA_ROOT / market / str(year) / f'{code}.csv'


def read_last_date(code, market, year):
    fpath = filepath_for(code, market, year)
    if not fpath.exists() or fpath.stat().st_size == 0:
        return None
    try:
        df = pd.read_csv(fpath, usecols=lambda c: True)
        if df.empty:
            return None
        col = '日期' if '日期' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
        last = str(df[col].iloc[-1]).strip()[:10]
        return last if len(last) == 10 else None
    except Exception as e:
        print(f"  警告：读取 {fpath} 最后日期失败: {e}")
        return None


def chunks(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def fetch_ds(codes, start, end):
    code_str = ','.join(codes) if isinstance(codes, (list, tuple)) else codes
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


def to_output(df, fallback_code=None):
    row = df.copy()
    row.columns = [str(c).strip() for c in row.columns]
    if 'date' not in row.columns and 'time' in row.columns:
        row = row.rename(columns={'time': 'date'})
    lower = {c.lower(): c for c in row.columns}
    out = pd.DataFrame(index=row.index)
    date_src = 'date' if 'date' in row.columns else lower.get('date')
    code_src = 'thscode' if 'thscode' in row.columns else lower.get('thscode')
    af_src = 'ths_af_stock' if 'ths_af_stock' in row.columns else lower.get('ths_af_stock')
    out['日期'] = row[date_src].values if date_src else None
    if code_src:
        out['股票代码'] = row[code_src].values
    elif fallback_code:
        out['股票代码'] = fallback_code
    else:
        out['股票代码'] = None
    out['后复权因子'] = row[af_src].values if af_src else None
    out['日期'] = pd.to_datetime(out['日期'], errors='coerce').dt.strftime('%Y-%m-%d')
    return out[COLUMNS]


def append_rows(code, market, year, row):
    if row is None or row.empty:
        return 0
    fpath = filepath_for(code, market, year)
    fpath.parent.mkdir(parents=True, exist_ok=True)
    file_exists = fpath.exists() and fpath.stat().st_size > 0
    row.to_csv(fpath, mode='a', header=not file_exists, index=False, encoding='utf-8-sig')
    return len(row)


def split_by_code(df, batch):
    if df is None or df.empty:
        return {}
    code_col = 'thscode' if 'thscode' in df.columns else None
    if code_col is None:
        if len(batch) == 1:
            return {batch[0]: df}
        return {}
    out = {}
    for code, rec in df.groupby(code_col):
        out[str(code).strip()] = rec
    return out


def save_df(df, batch, market, year):
    n_codes = 0
    n_rows = 0
    for code, rec in split_by_code(df, batch).items():
        out = to_output(rec, fallback_code=code)
        n_rows += append_rows(code, market, year, out)
        n_codes += 1
    return n_codes, n_rows


def fetch_one_range(code, market, year, start, end, fail_list):
    df, err = fetch_ds([code], start, end)
    if err is not None:
        fail_list[f'{code}:{year}'] = err
        print(f"    {code} ✗ ({err})")
        return 0, 0
    if df is None or df.empty:
        return 0, 0
    return save_df(df, [code], market, year)


def fetch_year(year, items, fail_list, today):
    year_start, year_end = year_bounds(year, today)
    if year_start > year_end:
        print(f"  [{year}] 尚未开始，跳过")
        return 0, 0

    full_year = []
    resume = []

    for code, market in items:
        last = read_last_date(code, market, year)
        if last is None:
            full_year.append((code, market))
            continue
        try:
            ld = datetime.strptime(last, '%Y-%m-%d')
            ye = datetime.strptime(year_end, '%Y-%m-%d')
            if ld >= ye:
                continue
            start = (ld + timedelta(days=1)).strftime('%Y-%m-%d')
        except ValueError:
            full_year.append((code, market))
            continue
        if start > year_end:
            continue
        if not has_weekday(start, year_end):
            continue
        if start == year_start:
            full_year.append((code, market))
        else:
            resume.append((code, market, start))

    wrote_codes = 0
    wrote_rows = 0
    empty = 0

    # 同一市场一批，避免混市场批量请求
    by_market = {}
    for code, market in full_year:
        by_market.setdefault(market, []).append(code)

    for market, codes in by_market.items():
        total_batches = (len(codes) - 1) // BATCH_SIZE + 1 if codes else 0
        for batch_i, batch in enumerate(chunks(codes, BATCH_SIZE), 1):
            print(f"  [{year}/{market}] 批 {batch_i}/{total_batches} "
                  f"{batch[0]}..{batch[-1]} ({len(batch)}只) {year_start}→{year_end} ...",
                  end='', flush=True)
            df, err = fetch_ds(batch, year_start, year_end)
            if err is not None:
                print(" ✗ 批量失败，改单只")
                for code in batch:
                    n_c, n_r = fetch_one_range(code, market, year, year_start, year_end, fail_list)
                    if n_c == 0:
                        empty += 1
                    else:
                        wrote_codes += n_c
                        wrote_rows += n_r
                time.sleep(REQ_INTERVAL)
                continue
            n_c, n_r = save_df(df, batch, market, year)
            empty += len(batch) - n_c
            wrote_codes += n_c
            wrote_rows += n_r
            print(f" ✓ 写入 {n_c} 只 / {n_r} 行 / 无数据 {len(batch) - n_c}")
            time.sleep(REQ_INTERVAL)

    if resume:
        print(f"  [{year}] 断点续传 {len(resume)} 只")
        groups = {}
        for code, market, start in resume:
            groups.setdefault((market, start), []).append(code)
        for (market, start), codes in groups.items():
            total_batches = (len(codes) - 1) // BATCH_SIZE + 1
            for batch_i, batch in enumerate(chunks(codes, BATCH_SIZE), 1):
                print(f"  [{year}/{market}] 续传批 {batch_i}/{total_batches} "
                      f"{batch[0]}..{batch[-1]} ({len(batch)}只) {start}→{year_end} ...",
                      end='', flush=True)
                df, err = fetch_ds(batch, start, year_end)
                if err is not None:
                    print(" ✗ 批量失败，改单只")
                    for code in batch:
                        n_c, n_r = fetch_one_range(code, market, year, start, year_end, fail_list)
                        if n_c == 0:
                            empty += 1
                        else:
                            wrote_codes += n_c
                            wrote_rows += n_r
                    time.sleep(REQ_INTERVAL)
                    continue
                n_c, n_r = save_df(df, batch, market, year)
                empty += len(batch) - n_c
                wrote_codes += n_c
                wrote_rows += n_r
                print(f" ✓ 写入 {n_c} 只 / {n_r} 行 / 无数据 {len(batch) - n_c}")
                time.sleep(REQ_INTERVAL)

    skipped = len(items) - len(full_year) - len(resume)
    print(f"  [{year}] 完成：新增 {wrote_codes} 只 / {wrote_rows} 行，"
          f"已齐跳过 {skipped} 只，无数据 {empty} 只")
    return wrote_rows, empty


def main():
    FAIL_DIR.mkdir(parents=True, exist_ok=True)
    today = datetime.now()
    years = list(range(HISTORY_START_YEAR, HISTORY_END_YEAR + 1))
    tag = today.strftime('%Y%m%d')

    print("===== 后复权因子日频下载（ths_af_stock）=====\n")
    print(f"清单: {STOCK_LISTS}")
    print(f"年份: {HISTORY_START_YEAR} → {HISTORY_END_YEAR}")
    print(f"批量: {BATCH_SIZE} 只/次（整年）")
    print(f"输出: {DATA_ROOT}/{{market}}/{{year}}/{{code}}.csv")
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

    items = load_stock_lists()
    if not items:
        print("错误：未从清单文件读取到任何标的，请检查 STOCK_LISTS_DAILY 配置")
        THS_iFinDLogout()
        sys.exit(1)
    print(f"清单共 {len(items)} 只\n")

    fail_list = {}
    total_rows = 0
    total_empty = 0

    try:
        for year in years:
            start, end = year_bounds(year, today)
            print(f"[{year}] {start} → {end}")
            rows, empty = fetch_year(year, items, fail_list, today)
            total_rows += rows
            total_empty += empty
            print()
    finally:
        try:
            THS_iFinDLogout()
        except Exception:
            pass

    print("===== 完成 =====")
    print(f"本次新增行数: {total_rows}")
    print(f"无数据: {total_empty} 次")
    print(f"失败: {len(fail_list)}")
    if fail_list:
        for key, err in list(fail_list.items())[:20]:
            print(f"  {key}: {err}")
        fail_path = FAIL_DIR / f'fail_list_adjfactor_{tag}.json'
        fail_path.write_text(
            json.dumps(fail_list, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        print(f"失败记录: {fail_path}")


if __name__ == '__main__':
    main()
