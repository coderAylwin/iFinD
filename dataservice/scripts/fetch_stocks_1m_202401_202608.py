# -*- coding: utf-8 -*-
"""
批量下载指定标的1分钟K线数据
时间范围：2024-01-01 至 2026-08-01

标的列表（Aylwin 指定）：
  601899, 601600, 600900, 600938, 603993,
  000807, 000933, 002532, 601225,
  000651, 000333, 600690, 605499,
  600066, 000951

用法：
    cd IFIND_DATA && python3 dataservice/scripts/fetch_stocks_1m_202401_202608.py
"""
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---- 项目根目录，并确保能 import 到 iFinDPy（项目内 sdk/ 目录） ----
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'sdk'))

# 项目根目录（dataservice 的上一级，放 raw/ 等）
WORKSPACE_ROOT = PROJECT_ROOT.parent

# ---- 加载 .env 配置 ----
try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / '.env')
except ImportError:
    print("警告：未安装 python-dotenv，无法从 .env 加载配置")
    raise

from iFinDPy import THS_iFinDLogin, THS_iFinDLogout, THS_HF
import pandas as pd


# ======================================================================
# 配置
# ======================================================================
IFIND_USER = os.getenv('IFIND_USER', '')
IFIND_PASS = os.getenv('IFIND_PASS', '')
DATA_ROOT = str(WORKSPACE_ROOT / 'raw/minute')
FILL = os.getenv('FILL', 'Original')
CPS = os.getenv('CPS', 'backward1')

INDICATORS = 'open;high;low;close;volume;amount'

# ---- 各市场配置 ----
MARKET_CFG = {
    'cn': {'cps': 'backward2', 'open': '09:15:00', 'close': '15:00:00'},
    'hk': {'cps': 'backward',  'open': '09:30:00', 'close': '16:00:00'},
}

# ---- 固定参数：时间范围 ----
START_DATE = '2024-01-01'
END_DATE = '2026-08-31'

# ---- 标的列表 (code, market) ----
STOCKS = [
    # A 股
    ('601899.SH', 'cn'), ('601600.SH', 'cn'), ('600900.SH', 'cn'),
    ('600938.SH', 'cn'), ('603993.SH', 'cn'),
    ('000807.SZ', 'cn'), ('000933.SZ', 'cn'), ('002532.SZ', 'cn'),
    ('601225.SH', 'cn'),
    ('000651.SZ', 'cn'), ('000333.SZ', 'cn'), ('600690.SH', 'cn'),
    ('605499.SH', 'cn'),
    ('600066.SH', 'cn'), ('000951.SZ', 'cn'),
    # 港股
    ('0700.HK', 'hk'), ('1171.HK', 'hk'),
]


# ======================================================================
# 工具函数
# ======================================================================
def get_month_end(year, month):
    """获取某年某月的最后一天（返回 '01'~'31' 字符串）"""
    if month == 12:
        return '31'
    return str((datetime(year, month + 1, 1) - timedelta(days=1)).day)


def read_last_timestamp(csv_path):
    """读取 CSV 最后一行的 time 时间戳；文件不存在或为空返回 None"""
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return None
    try:
        df = pd.read_csv(csv_path, usecols=lambda c: True)
        if df.empty:
            return None
        time_col = 'time' if 'time' in df.columns else df.columns[0]
        last = str(df[time_col].iloc[-1]).strip()
        return last if last else None
    except Exception as e:
        print(f"  警告：读取 {csv_path} 最后时间戳失败: {e}")
        return None


def append_by_year(code, df, data_root_market):
    """
    将拉取的 DataFrame 按年份拆分，追加写入对应年份文件。
    """
    if df is None or df.empty:
        return

    df = df.copy()
    df['__year'] = df['time'].astype(str).str[:4]
    for year, group in df.groupby('__year'):
        year_dir = os.path.join(data_root_market, str(year))
        os.makedirs(year_dir, exist_ok=True)
        filepath = os.path.join(year_dir, f'{code}.csv')
        file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
        drop = group.drop(columns=['__year'])
        drop.to_csv(filepath, mode='a', header=not file_exists, index=False)
        print(f"    → 写入 {year} 年文件: {os.path.basename(filepath)} (+{len(drop)} 行)")


def fetch_month(code, year, month, start, end, last_ts, stats, hf_jsonparam, data_root_market):
    """
    拉取单个 code 某个月的1分钟K线（[start, end] 在一个月内），
    结合断点续传：若 last_ts 已覆盖 start，则从 last_ts 之后续拉。
    """
    if last_ts is not None:
        try:
            if len(last_ts) == 16:
                last_ts += ':00'
            lt = datetime.strptime(last_ts, '%Y-%m-%d %H:%M:%S')
            s = datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
            if lt >= s:
                start = (lt + timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')
        except ValueError:
            pass

    try:
        s = start if len(start) == 19 else start + ':00'
        e = end if len(end) == 19 else end + ':00'
        if datetime.strptime(s, '%Y-%m-%d %H:%M:%S') >= datetime.strptime(e, '%Y-%m-%d %H:%M:%S'):
            print(f"  {code} [{year}-{month:02d}] 已有完整数据 → 跳过")
            return
    except ValueError:
        pass

    # 调用 THS_HF 拉取（带重试）
    data = None
    retries = 3
    for attempt in range(1, retries + 1):
        data = THS_HF(code, INDICATORS, hf_jsonparam, start, end)
        if data.errorcode == 0:
            break
        print(f"  {code} [{year}-{month:02d}] 拉取失败(第{attempt}次): {data.errmsg}，重试中...")
        time.sleep(2 * attempt)

    if data is None or data.errorcode != 0:
        print(f"  错误：{code} {year}-{month:02d} 重试{retries}次仍失败: {data.errmsg if data else '未知'}")
        stats['errors'] += 1
        return

    vol = getattr(data, 'dataVol', 0)
    stats['used_vol'] += vol
    stats['requests'] += 1

    df = data.data
    if df is not None and not df.empty:
        rows = len(df)
        print(f"  {code} [{year}-{month:02d}] 拉取 {start} → {end}，{rows} 行，本次格数 {vol}")
        append_by_year(code, df, data_root_market)
        stats['rows'] += rows
        stats['codes_updated'] += 1
    else:
        print(f"  {code} [{year}-{month:02d}] 无新数据（{start} → {end}）")
        stats['empty_responses'] += 1


def main():
    # ---- 1. 检查配置 ----
    if not IFIND_USER or not IFIND_PASS:
        print('错误：请在 IFIND_DATA/.env 中配置 IFIND_USER 和 IFIND_PASS')
        return

    hf_params = {
        m: f'Fill:{FILL},CPS:{cfg["cps"]}'
        for m, cfg in MARKET_CFG.items()
    }
    market_open_close = {
        m: (cfg['open'], cfg['close'])
        for m, cfg in MARKET_CFG.items()
    }

    # ---- 2. 初始化统计 ----
    stats = {
        'codes_total': len(STOCKS),
        'codes_processed': 0,
        'codes_updated': 0,
        'requests': 0,
        'rows': 0,
        'errors': 0,
        'empty_responses': 0,
        'used_vol': 0,
    }

    market_dirs = {m: f'{DATA_ROOT}/{m}' for m in MARKET_CFG}

    print(f"===== 指定股票1分钟K线下载 =====\n")
    print(f"时间范围: {START_DATE} → {END_DATE}")
    print(f"数据目录: cn 下 A股, hk 下港股")
    print(f"标的数量: {len(STOCKS)} 只")
    print(f"请求配置: A股 CPS=backward2, 港股 CPS=backward, Fill={FILL}")
    for m in MARKET_CFG:
        codes_group = [c for c, mk in STOCKS if mk == m]
        print(f"  {m}: {', '.join(codes_group)}")
    print()

    # ---- 3. 解析时间范围，生成月份列表 ----
    start_dt = datetime.strptime(START_DATE, '%Y-%m-%d')
    end_dt = datetime.strptime(END_DATE, '%Y-%m-%d')

    months = []
    y, m = start_dt.year, start_dt.month
    while (y, m) <= (end_dt.year, end_dt.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1

    # ---- 4. 登录 iFinD ----
    ret = THS_iFinDLogin(IFIND_USER, IFIND_PASS)
    if ret != 0:
        print(f"登录失败，错误码: {ret}")
        return
    print("登录成功\n")

    try:
        for i, (code, market) in enumerate(STOCKS, 1):
            stats['codes_processed'] += 1
            data_root_market = market_dirs[market]
            hf_jsonparam = hf_params[market]
            open_time, close_time = market_open_close[market]
            print(f"[{i}/{len(STOCKS)}] 处理 {code} (市场={market}, 开盘{open_time}收盘{close_time})")

            for year, month in months:
                start = f'{year}-{month:02d}-01 {open_time}'
                month_end = get_month_end(year, month)

                if year == end_dt.year and month == end_dt.month:
                    end = f'{year}-{month:02d}-{end_dt.day} {close_time}'
                else:
                    end = f'{year}-{month:02d}-{month_end} {close_time}'

                # 读断点续传时间戳
                year_dir = os.path.join(data_root_market, str(year))
                filepath = os.path.join(year_dir, f'{code}.csv')
                last_ts = read_last_timestamp(filepath)

                fetch_month(code, year, month, start, end, last_ts, stats, hf_jsonparam, data_root_market)

            print(f"  [{code}] 已完成所有月份")
            print()

        # ---- 汇总 ----
        print("===== 任务完成汇总 =====")
        print(f"标的: {stats['codes_processed']}/{stats['codes_total']} 只")
        print(f"时间范围: {START_DATE} → {END_DATE}")
        print(f"请求次数: {stats['requests']}")
        print(f"新增行数: {stats['rows']:,}")
        print(f"消耗格数: {stats['used_vol']:,}")
        print(f"错误: {stats['errors']} 次 | 空响应: {stats['empty_responses']} 次")

    finally:
        try:
            THS_iFinDLogout()
            print("已登出 iFinD")
        except Exception:
            pass


if __name__ == '__main__':
    main()