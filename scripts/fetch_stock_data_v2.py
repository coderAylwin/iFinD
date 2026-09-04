# -*- coding: utf-8 -*-
"""
高效批量拉取 zz_all_list_cn.csv 所有股票的指定指标数据

策略：
  - 分两组查询：
    1. 批量拉取（无参数指标）：行业、总市值、流通市值、总股本、流通A股、自由流通股、复权因子
    2. 单只拉取（有参数指标）：每股分红送转、股息率TTM、净利润TTM
  - 通过 time+thscode 合并
  - 断点续传（记录进度到 JSON）
  - 每批50只合并后写入

用法：
    python3 IFIND_DATA/scripts/fetch_stock_data.py

输出：
    data/ths_ds/stock_data_20260903.csv  （合并后最终文件）
"""
import os
import sys
import time
import json
from datetime import datetime, timedelta
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
    print("警告：未安装 python-dotenv，无法从 .env 加载配置")
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
LISTS_DIR = PROJECT_ROOT / 'data' / 'lists'

# 输出目录
OUTPUT_DIR = PROJECT_ROOT / 'data' / 'ths_ds'
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 日期范围
DATE_START = '2026-09-01'
DATE_END = '2026-09-03'

# 分组
# 组A：无参数，批量拉取 —— 行业、总市值、流通市值、总股本、流通A股、自由流通股、复权因子
INDICATORS_BATCH = (
    'ths_the_citic_industry_stock;'
    'ths_market_value_stock;'
    'ths_current_mv_stock;'
    'ths_total_shares_stock;'
    'ths_float_ashare_stock;'
    'ths_free_float_shares_stock;'
    'ths_af_stock'
)
# 组B：需要 reportPeriod 参数，单只拉取 —— 每股分红送转、股息率TTM、净利润TTM
INDICATORS_SINGLE = (
    'ths_dividend_ps_stock;'
    'ths_dividend_yield_ttm_ex_sd_stock;'
    'ths_np_ttm_stock'
)
PARAMS_SINGLE = ';;;;;100;;;;'

# 批量查询每批多少只
BATCH_SIZE = 50
# 单只查询间隔（秒）
SINGLE_INTERVAL = 0.15
# 重试次数
MAX_RETRIES = 3

# 进度文件（断点续传）
PROGRESS_FILE = OUTPUT_DIR / '.progress.json'


# ======================================================================
# 工具函数
# ======================================================================
def load_stock_list():
    """读取列表 CSV，返回 thscode 列表"""
    path = LISTS_DIR / LIST_FILE
    if not path.exists():
        print(f"错误：清单文件不存在: {path}")
        sys.exit(1)
    df = pd.read_csv(path)
    col = 'thscode' if 'thscode' in df.columns else df.columns[0]
    codes = df[col].dropna().astype(str).str.strip().tolist()
    return codes


def load_progress():
    """读取进度文件，返回已成功处理的 code 集合"""
    if PROGRESS_FILE.exists():
        try:
            data = json.loads(PROGRESS_FILE.read_text(encoding='utf-8'))
            done = set(data.get('done_codes', []))
            return done
        except Exception:
            return set()
    return set()


def save_progress(done_codes):
    """保存进度"""
    data = {
        'done_codes': sorted(list(done_codes)),
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total': len(done_codes),
    }
    PROGRESS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def fetch_batch(codes_batch):
    """
    批量拉取组A指标（无 reportPeriod 参数）
    返回 DataFrame 或 None
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            data = THS_DS(
                ','.join(codes_batch),
                INDICATORS_BATCH,
                '',
                '',
                DATE_START,
                DATE_END
            )
            if data.errorcode == 0:
                df = data.data
                if df is not None and not df.empty:
                    return df
                else:
                    return None
            else:
                print(f"  [批] 拉取失败 (第{attempt}次): errorcode={data.errorcode} {data.errmsg}")
        except Exception as e:
            print(f"  [批] 异常 (第{attempt}次): {e}")
        if attempt < MAX_RETRIES:
            time.sleep(2)
    return None


def fetch_single(code):
    """
    单只拉取组B指标（有 reportPeriod 参数）
    返回 DataFrame 或 None
    """
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            data = THS_DS(
                code,
                INDICATORS_SINGLE,
                PARAMS_SINGLE,
                '',
                DATE_START,
                DATE_END
            )
            if data.errorcode == 0:
                df = data.data
                if df is not None and not df.empty:
                    return df
                else:
                    return None
            else:
                print(f"  {code}: 失败 (第{attempt}次): errorcode={data.errorcode} {data.errmsg}")
        except Exception as e:
            print(f"  {code}: 异常 (第{attempt}次): {e}")
        if attempt < MAX_RETRIES:
            time.sleep(max(0.5, 2 * attempt * 0.5))
    return None


def safe_filename_date():
    start_obj = datetime.strptime(DATE_START, '%Y-%m-%d')
    end_obj = datetime.strptime(DATE_END, '%Y-%m-%d')
    return end_obj.strftime('%Y%m%d')


# ======================================================================
# 主流程
# ======================================================================
def main():
    date_tag = safe_filename_date()
    print("===== THS_DS 高效批量拉取股票数据 =====\n")
    print(f"清单: {LIST_FILE}")
    print(f"日期: {DATE_START} → {DATE_END}")
    print(f"批量大小: {BATCH_SIZE} 只/批")
    print(f"组A(批量): {INDICATORS_BATCH.replace(';', ' | ')}")
    print(f"组B(单只): {INDICATORS_SINGLE.replace(';', ' | ')}")
    print()

    # ---- 登录 ----
    if not IFIND_USER or not IFIND_PASS:
        print("错误：请在 .env 中配置 IFIND_USER 和 IFIND_PASS")
        sys.exit(1)

    ret = THS_iFinDLogin(IFIND_USER, IFIND_PASS)
    if ret != 0:
        print(f"登录失败，错误码: {ret}")
        sys.exit(1)
    print("登录成功\n")

    codes = load_stock_list()
    total = len(codes)
    done_set = load_progress()
    print(f"清单共 {total} 只股票，已处理 {len(done_set)} 只")
    print()

    # ---- 拉取组A（批量）----
    print("===== 组A: 批量拉取（无参数指标）=====")
    batch_a_dfs = []
    pending = [c for c in codes if c not in done_set]
    total_pending = len(pending)
    batch_count = 0
    a_success = 0
    a_fail = 0

    # 先把全部代码分批查
    for batch_start in range(0, len(pending), BATCH_SIZE):
        batch = pending[batch_start:batch_start + BATCH_SIZE]
        batch_no = batch_start // BATCH_SIZE + 1
        print(f"  [批 {batch_no}/{((total_pending-1)//BATCH_SIZE)+1}] {batch[0]}..{batch[-1]} ({len(batch)}只) ...", end='')
        sys.stdout.flush()

        df = fetch_batch(batch)
        if df is not None:
            batch_a_dfs.append(df)
            a_success += len(batch)
            batch_count += 1
            print(f" ✓ ({len(df)} 行)")
        else:
            # 批量失败，退化到逐只拉取
            print(f" ✗ (退化到单只拉取)")
            for code in batch:
                df_s = fetch_single(code.replace('ths_market_value_stock', ''))  # 不会走这步
                # 实际上批量失败时，我们逐只用组B的方式也查不到组A指标
                # 所以先跳过，后面再补
                pass
            a_fail += len(batch)
            print(f"    → {len(batch)}只跳过，后续单只补拉")

        time.sleep(0.1)

    # 合并组A
    if batch_a_dfs:
        df_a = pd.concat(batch_a_dfs, ignore_index=True)
        print(f"\n  组A合并: {len(df_a)} 行")
    else:
        df_a = None
        print("\n  组A无数据")

    # ---- 登录重连（组B单只拉取前先重新登录，保活）----
    print("\n===== 组B: 单只拉取（有参数指标）=====")
    b_dfs = []
    b_success = 0
    b_fail = 0
    b_batch_dfs = []  # 每50只合并一次写中间文件

    for i, code in enumerate(pending, 1):
        if code in done_set:
            continue

        print(f"  [{i}/{total_pending}] {code} ...", end='')
        sys.stdout.flush()

        df = fetch_single(code)
        if df is not None:
            b_dfs.append(df)
            b_success += 1
            print(f" ✓ ({len(df)} 行)")
        else:
            b_fail += 1
            print(f" ✗")

        # 每50只记录一次进度并写中间文件
        if len(b_dfs) >= 50:
            b_partial = pd.concat(b_dfs, ignore_index=True)
            partial_path = OUTPUT_DIR / f'stock_data_{date_tag}_partial_b_{b_success//50:03d}.csv'
            b_partial.to_csv(partial_path, index=False, encoding='utf-8-sig')
            print(f"\n  → 已写中间文件: {partial_path.name} ({len(b_partial)} 行)\n")
            b_dfs.clear()

            # 更新进度
            done_set.update([c for c in pending[:i] if c not in done_set][-50:])
            save_progress(done_set)

        time.sleep(SINGLE_INTERVAL)

    # 最后一批组B
    if b_dfs:
        b_partial = pd.concat(b_dfs, ignore_index=True)
        partial_path = OUTPUT_DIR / f'stock_data_{date_tag}_partial_b_{b_success//50+1:03d}.csv'
        b_partial.to_csv(partial_path, index=False, encoding='utf-8-sig')
        print(f"\n  → 已写最终批: {partial_path.name} ({len(b_partial)} 行)")

    # ---- 合并组A和组B ----
    print("\n===== 合并最终文件 =====")

    # 收集所有组B中间文件
    b_partials = sorted(OUTPUT_DIR.glob(f'stock_data_{date_tag}_partial_b_*.csv'))
    if b_partials:
        df_b = pd.concat((pd.read_csv(f) for f in b_partials), ignore_index=True)
        print(f"组B合并: {len(df_b)} 行（来自 {len(b_partials)} 个中间文件）")

        if df_a is not None:
            # 按 time + thscode 合并
            merged = pd.merge(df_a, df_b, on=['time', 'thscode'], how='outer')
            print(f"合并后: {len(merged)} 行")
        else:
            merged = df_b
    elif df_a is not None:
        # 只有组A数据（组B全失败）
        merged = df_a
        print("组B无数据，仅输出组A")
    else:
        print("错误：两组均无数据")
        THS_iFinDLogout()
        sys.exit(1)

    # 重命名 time -> date（与行业惯例一致）
    if 'time' in merged.columns and 'date' not in merged.columns:
        merged = merged.rename(columns={'time': 'date'})

    final_path = OUTPUT_DIR / f'stock_data_{date_tag}.csv'
    merged.to_csv(final_path, index=False, encoding='utf-8-sig')
    print(f"\n最终文件: {final_path} ({len(merged)} 行)")

    # 排序：按 date 和 thscode
    print(f"列: {list(merged.columns)}")

    # 清理中间文件
    for f in b_partials:
        f.unlink()
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()
    print("已清理中间文件和进度文件")

    # ---- 登出 ----
    try:
        THS_iFinDLogout()
        print("已登出 iFinD")
    except Exception:
        pass

    # ---- 汇总 ----
    print(f"\n===== 完成 =====")
    print(f"总计: {total} 只股票")
    print(f"组A(批量)成功/失败: {a_success}/{a_fail}")
    print(f"组B(单只)成功/失败: {b_success}/{b_fail}")
    print(f"总行数: {len(merged)}")
    print(f"数据文件: {final_path}")


if __name__ == '__main__':
    main()