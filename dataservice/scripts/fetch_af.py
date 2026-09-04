# -*- coding: utf-8 -*-
"""
拉取中证全指后复权因子（日频 ths_af_stock）

区间：2012-01-01 ~ 2026-09-03（写在脚本内，不读 HISTORY_START_YEAR）
清单：zz_all_list_cn.csv
存储：raw/af/{sh|sz|bj}/{year}/{code}.csv
增量：读本地该年文件最后日期，从下一天续拉；整年已齐则跳过。
北交所（.BJ）不拉取。

用法：
    python3 -u dataservice/scripts/fetch_af.py
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
# 配置（日期和清单以脚本为准）
# ======================================================================
IFIND_USER = os.getenv('IFIND_USER', '')
IFIND_PASS = os.getenv('IFIND_PASS', '')

LIST_FILE = 'zz_all_list_cn.csv'
LISTS_DIR = PROJECT_ROOT / 'data' / 'lists'
DATA_ROOT = WORKSPACE_ROOT / 'raw' / 'af'
FAIL_DIR = PROJECT_ROOT / 'data' / 'ths_ds'

DATE_START = '2012-01-01'
DATE_END = '2026-09-03'

INDICATORS = 'ths_af_stock'
PARAMS = ''

COLUMNS = ['日期', '股票代码', '后复权因子']
BATCH_SIZE = 20
REQ_INTERVAL = 0.15
MAX_RETRIES = 3
SKIP_SUFFIXES = ('.BJ',)  # 北交所本地已齐全，不再拉取
# ======================================================================


def year_range():
    return list(range(int(DATE_START[:4]), int(DATE_END[:4]) + 1))


def year_bounds(year):
    start = f'{year}-01-01'
    end = f'{year}-12-31'
    if start < DATE_START:
        start = DATE_START
    if end > DATE_END:
        end = DATE_END
    return start, end


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
        print(f"  已跳过北交所 {skipped} 只（不请求后复权因子）")
    return kept


def guess_market(code):
    suffix = code.split('.')[-1] if '.' in code else ''
    return {'SH': 'sh', 'SZ': 'sz', 'BJ': 'bj'}.get(suffix, 'cn')


def filepath_for(code, year):
    return DATA_ROOT / guess_market(code) / str(year) / f'{code}.csv'


def read_last_date(code, year):
    fpath = filepath_for(code, year)
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


def append_rows(code, year, row):
    if row is None or row.empty:
        return 0
    fpath = filepath_for(code, year)
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


def save_df(df, batch, year):
    n_codes = 0
    n_rows = 0
    for code, rec in split_by_code(df, batch).items():
        out = to_output(rec, fallback_code=code)
        n_rows += append_rows(code, year, out)
        n_codes += 1
    return n_codes, n_rows


def fetch_one_range(code, year, start, end, fail_list):
    df, err = fetch_ds([code], start, end)
    if err is not None:
        fail_list[f'{code}:{year}'] = err
        print(f"    {code} ✗ ({err})")
        return 0, 0
    if df is None or df.empty:
        return 0, 0
    return save_df(df, [code], year)


def fetch_year(year, codes, fail_list):
    year_start, year_end = year_bounds(year)
    full_year = []
    resume = []

    for code in codes:
        last = read_last_date(code, year)
        if last is None:
            full_year.append(code)
            continue
        try:
            ld = datetime.strptime(last, '%Y-%m-%d')
            ye = datetime.strptime(year_end, '%Y-%m-%d')
            if ld >= ye:
                continue
            start = (ld + timedelta(days=1)).strftime('%Y-%m-%d')
        except ValueError:
            full_year.append(code)
            continue
        if start > year_end:
            continue
        if start == year_start:
            full_year.append(code)
        else:
            resume.append((code, start))

    wrote_codes = 0
    wrote_rows = 0
    empty = 0

    total_batches = (len(full_year) - 1) // BATCH_SIZE + 1 if full_year else 0
    for batch_i, batch in enumerate(chunks(full_year, BATCH_SIZE), 1):
        print(f"  [{year}] 批 {batch_i}/{total_batches} "
              f"{batch[0]}..{batch[-1]} ({len(batch)}只) {year_start}→{year_end} ...",
              end='', flush=True)
        df, err = fetch_ds(batch, year_start, year_end)
        if err is not None:
            print(" ✗ 批量失败，改单只")
            for code in batch:
                n_c, n_r = fetch_one_range(code, year, year_start, year_end, fail_list)
                if n_c == 0:
                    empty += 1
                else:
                    wrote_codes += n_c
                    wrote_rows += n_r
            time.sleep(REQ_INTERVAL)
            continue
        n_c, n_r = save_df(df, batch, year)
        empty += len(batch) - n_c
        wrote_codes += n_c
        wrote_rows += n_r
        print(f" ✓ 写入 {n_c} 只 / {n_r} 行 / 无数据 {len(batch) - n_c}")
        time.sleep(REQ_INTERVAL)

    if resume:
        print(f"  [{year}] 断点续传 {len(resume)} 只")
        for i, (code, start) in enumerate(resume, 1):
            print(f"    [{i}/{len(resume)}] {code} {start}→{year_end} ...", end='', flush=True)
            n_c, n_r = fetch_one_range(code, year, start, year_end, fail_list)
            if n_c == 0:
                empty += 1
                print(" 无数据")
            else:
                wrote_codes += n_c
                wrote_rows += n_r
                print(f" ✓ +{n_r} 行")
            time.sleep(REQ_INTERVAL)

    skipped = len(codes) - len(full_year) - len(resume)
    print(f"  [{year}] 完成：新增 {wrote_codes} 只 / {wrote_rows} 行，"
          f"已齐跳过 {skipped} 只，无数据 {empty} 只")
    return wrote_rows, empty


def main():
    FAIL_DIR.mkdir(parents=True, exist_ok=True)
    years = year_range()
    tag = datetime.now().strftime('%Y%m%d')

    print("===== 后复权因子日频下载（ths_af_stock）=====\n")
    print(f"清单: {LIST_FILE}")
    print(f"区间: {DATE_START} → {DATE_END}")
    print(f"批量: {BATCH_SIZE} 只/次（整年）")
    print(f"输出: {DATA_ROOT}/{{sh|sz|bj}}/{{year}}/{{code}}.csv")
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

    fail_list = {}
    total_rows = 0
    total_empty = 0

    try:
        for year in years:
            start, end = year_bounds(year)
            print(f"[{year}] {start} → {end}")
            rows, empty = fetch_year(year, codes, fail_list)
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
        fail_path = FAIL_DIR / f'fail_list_af_{tag}.json'
        fail_path.write_text(
            json.dumps(fail_list, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        print(f"失败记录: {fail_path}")


if __name__ == '__main__':
    main()
