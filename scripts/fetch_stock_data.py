# -*- coding: utf-8 -*-
"""
批量拉取 zz_all_list_cn.csv 所有股票的指定截面指标数据（THS_DS）

存储方式（仿 fetch_daily.py）：
    raw/stock_profile/{market}/{year}/{code}.csv

策略：
  - 每只股票逐条拉取，追加写入独立文件
  - 支持断点续传（文件已存在则跳过）
  - 失败股票记录到 fail_list.json

用法：
    python3 IFIND_DATA/scripts/fetch_stock_data.py

依赖：同花顺 iFinDPy（dataservice/sdk/），需在 dataservice/.env 配置账号密码。
"""
import os, sys, signal, time, json
from datetime import datetime
from pathlib import Path

# ---- 项目根目录 & SDK 路径 ----
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'sdk'))

# ---- 加载 .env 配置 ----
try:
    from dotenv import load_dotenv
    env_path = PROJECT_ROOT / 'dataservice' / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv(PROJECT_ROOT / '.env')
except ImportError:
    raise

from iFinDPy import THS_iFinDLogin, THS_iFinDLogout, THS_DS
import pandas as pd

# ======================================================================
# 配置
# ======================================================================
IFIND_USER = os.getenv('IFIND_USER', '')
IFIND_PASS = os.getenv('IFIND_PASS', '')

# 清单文件
LIST_FILE = 'zz_all_list_cn.csv'
LISTS_DIR = PROJECT_ROOT / 'dataservice' / 'data' / 'lists'

# 数据根目录（仿 fetch_daily.py: raw/stock_profile/）
DATA_ROOT = PROJECT_ROOT / 'raw' / 'stock_profile'
# 市场目录（清单文件名后缀推断）
MARKET = 'cn'

# 日期范围
DATE_START = '2012-01-01'
DATE_END = '2026-08-31'

# THS_DS 指标（用户原始命令格式）
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

REQ_INTERVAL = 0.15
MAX_RETRIES = 3
TIMEOUT_SEC = 30

# 失败记录文件
FAIL_DIR = PROJECT_ROOT / 'data' / 'ths_ds'
# ======================================================================


def load_codes():
    """读取清单文件，返回 thscode 列表"""
    path = LISTS_DIR / LIST_FILE
    if not path.exists():
        print(f"错误：清单文件不存在: {path}")
        sys.exit(1)
    df = pd.read_csv(path)
    col = 'thscode' if 'thscode' in df.columns else df.columns[0]
    return df[col].dropna().astype(str).str.strip().tolist()


def guess_market(code):
    """从代码后缀推断市场目录（cn / bj / sh / sz）"""
    suffix = code.split('.')[-1] if '.' in code else ''
    suffix_map = {
        'SH': 'sh', 'SZ': 'sz', 'BJ': 'bj',
    }
    return suffix_map.get(suffix, MARKET)


def filepath_for(code, year):
    """生成每只股票某年的独立文件路径"""
    market = guess_market(code)
    year_dir = DATA_ROOT / market / str(year)
    year_dir.mkdir(parents=True, exist_ok=True)
    return year_dir / f'{code}.csv'


def fetch_one(code):
    """带超时控制的单只股票拉取"""
    for attempt in range(1, MAX_RETRIES + 1):
        class TimeoutError(Exception):
            pass

        def _handler(signum, frame):
            raise TimeoutError()

        old_handler = None
        try:
            old_handler = signal.signal(signal.SIGALRM, _handler)
            signal.alarm(TIMEOUT_SEC)
        except Exception:
            pass

        try:
            data = THS_DS(code, INDICATORS, PARAMS, '', DATE_START, DATE_END)
            try:
                signal.alarm(0)
            except:
                pass
            try:
                signal.signal(signal.SIGALRM, old_handler)
            except:
                pass

            if data.errorcode == 0:
                df = data.data
                if df is not None and not df.empty:
                    return df, None
                return None, "empty"
            else:
                err = f"ec={data.errorcode} {data.errmsg}"
                if attempt < MAX_RETRIES:
                    time.sleep(2 * attempt)
                else:
                    return None, err
        except TimeoutError:
            try:
                signal.alarm(0)
            except:
                pass
            try:
                signal.signal(signal.SIGALRM, old_handler)
            except:
                pass
            err = "timeout"
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
            else:
                return None, err
        except Exception as e:
            try:
                signal.alarm(0)
            except:
                pass
            try:
                signal.signal(signal.SIGALRM, old_handler)
            except:
                pass
            err = str(e)
            if attempt < MAX_RETRIES:
                time.sleep(2 * attempt)
            else:
                return None, err
    return None, "retries_exhausted"


def write_stock_file(df, code):
    """按年份拆分，追加写入独立文件（仿 append_by_year）"""
    if df is None or df.empty:
        return 0

    df_out = df.copy()
    if 'time' in df_out.columns:
        df_out = df_out.rename(columns={'time': 'date'})

    # 按年份拆分
    df_out['__year'] = df_out['date'].astype(str).str[:4]
    total_rows = 0
    for year, group in df_out.groupby('__year'):
        fpath = filepath_for(code, int(year))
        file_exists = fpath.exists() and fpath.stat().st_size > 0
        drop = group.drop(columns=['__year'])
        drop.to_csv(fpath, mode='a', header=not file_exists,
                    index=False, encoding='utf-8-sig')
        total_rows += len(drop)
    return total_rows


def main():
    FAIL_DIR.mkdir(parents=True, exist_ok=True)
    tag = datetime.strptime(DATE_END, '%Y-%m-%d').strftime('%Y%m%d')

    print(f"清单: {LIST_FILE}  日期: {DATE_START} → {DATE_END}")
    print(f"数据根目录: {DATA_ROOT}")
    print()

    # ---- 登录 ----
    if not IFIND_USER or not IFIND_PASS:
        print("错误：请在 .env 中配置 IFIND_USER 和 IFIND_PASS")
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
    print("登录成功")

    codes = load_codes()
    total = len(codes)

    # ---- 断点续传：已有文件的跳过 ----
    pending = []
    for code in codes:
        # 检查 2026 年文件是否已存在
        fpath = filepath_for(code, 2026)
        if fpath.exists() and fpath.stat().st_size > 0:
            continue
        pending.append(code)

    success = total - len(pending)
    fail_list = {}

    print(f"共 {total} 只，已存在 {success} 只，待拉取 {len(pending)} 只")
    print()

    # ---- 逐只拉取并写入独立文件 ----
    for i, code in enumerate(pending, 1):
        print(f"  [{i}/{len(pending)}] {code} ...", end='', flush=True)

        df, err = fetch_one(code)

        if df is not None:
            rows = write_stock_file(df, code)
            success += 1
            print(f" ✓ ({rows}行)", flush=True)
        else:
            fail_list[code] = err
            print(f" ✗ ({err})", flush=True)

        time.sleep(REQ_INTERVAL)

    # ---- 登出 ----
    try:
        THS_iFinDLogout()
    except Exception:
        pass

    # ---- 汇总 ----
    print(f"\n总计: {total}  成功: {success}  失败: {len(fail_list)}")
    if fail_list:
        for c, e in list(fail_list.items())[:20]:
            print(f"  {c}: {e}")
        fail_path = FAIL_DIR / f'fail_list_{tag}.json'
        fail_path.write_text(json.dumps(fail_list, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f"失败记录: {fail_path}")


if __name__ == '__main__':
    main()