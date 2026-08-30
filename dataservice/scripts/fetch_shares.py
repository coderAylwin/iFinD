# -*- coding: utf-8 -*-
"""
批量下载 A 股股本数据（自由流通股本、总股本、流通A股）

接口：THS_DS（日间序列）
指标：ths_free_float_shares_stock / ths_total_shares_stock / ths_float_ashare_stock

存储：
  {DATA_ROOT}/shares/{market}/{year}/{code}.csv

逻辑与 fetch_daily.py 一致：
- 按年拉取，一次请求搞定全年
- 断点续传：读本地最后日期，从下一天续拉
- 每周预算控制

用法：
    cd IFIND_DATA && python3 dataservice/scripts/fetch_shares.py

依赖：同花顺 iFinDPy（dataservice/sdk/），需在 dataservice/.env 配置账号密码。
"""
import os
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

# ---- 项目路径 ----
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'sdk'))

WORKSPACE_ROOT = PROJECT_ROOT.parent

# ---- 加载 .env ----
try:
    from dotenv import load_dotenv
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
DATA_ROOT = str(WORKSPACE_ROOT / 'raw/shares')
WEEKLY_BUDGET = int(os.getenv('WEEKLY_BUDGET', '150000000'))

HISTORY_START_YEAR = int(os.getenv('HISTORY_START_YEAR', '2020'))
HISTORY_END_YEAR = int(os.getenv('HISTORY_END_YEAR', str(datetime.now().year)))
STOCK_LISTS = os.getenv('STOCK_LISTS_DAILY', 'zz_all_list_cn.csv')

# THS_DS 股本指标
INDICATORS = 'ths_free_float_shares_stock;ths_total_shares_stock;ths_float_ashare_stock'
# THS_DS 第三个参数是 reportType，股本类为空字符串即可
REPORT_TYPE = ';;'

# 本周用量记录文件（和日线共用预算）
USAGE_FILE = PROJECT_ROOT / 'data' / 'usage_shares.json'


# ======================================================================
# 工具函数（与 fetch_daily.py 保持一致）
# ======================================================================
def load_weekly_usage():
    now = datetime.now()
    monday = (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    monday_str = monday.strftime('%Y-%m-%d')
    if not USAGE_FILE.exists():
        return monday_str, 0
    try:
        import json
        data = json.loads(USAGE_FILE.read_text(encoding='utf-8'))
        if data.get('week_start') == monday_str:
            return monday_str, data.get('used_vol', 0)
        else:
            return monday_str, 0
    except Exception:
        return monday_str, 0


def save_weekly_usage(week_start, used_vol):
    import json
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps({
        'week_start': week_start,
        'used_vol': used_vol,
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }, ensure_ascii=False, indent=2), encoding='utf-8')


def guess_market_from_listname(list_name):
    stem = Path(list_name).stem
    parts = stem.split('_')
    if len(parts) >= 2:
        suffix = parts[-1]
        if len(suffix) <= 6 and suffix.isalpha():
            return suffix.lower()
    return 'cn'


def load_stock_lists():
    lists_dir = PROJECT_ROOT / 'data' / 'lists'
    items = []
    seen = set()
    for name in [x.strip() for x in STOCK_LISTS.split(',') if x.strip()]:
        path = lists_dir / name
        if not path.exists():
            print(f"  警告：清单文件不存在: {path}")
            continue
        try:
            market = guess_market_from_listname(name)
            df = pd.read_csv(path)
            col = 'thscode' if 'thscode' in df.columns else df.columns[0]
            for c in df[col].dropna():
                c = str(c).strip()
                key = (c, market)
                if key not in seen:
                    seen.add(key)
                    items.append(key)
            print(f"  已加载清单: {name} (市场={market}, {len(df)} 只)")
        except Exception as e:
            print(f"  警告：读取清单 {name} 失败: {e}")
    return items


def read_last_timestamp(csv_path):
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return None
    try:
        df = pd.read_csv(csv_path)
        if df.empty:
            return None
        time_col = 'date' if 'date' in df.columns else df.columns[0]
        last = str(df[time_col].iloc[-1]).strip()
        return last if last else None
    except Exception as e:
        print(f"  警告：读取 {csv_path} 最后时间戳失败: {e}")
        return None


def append_by_year(code, market, df, stats):
    if df is None or df.empty:
        stats['empty_responses'] += 1
        return

    df = df.copy()
    # THS_DS 返回 time 列
    time_col = 'time' if 'time' in df.columns else 'date'
    df['__year'] = df[time_col].astype(str).str[:4]
    for year, group in df.groupby('__year'):
        year_dir = os.path.join(DATA_ROOT, market, str(year))
        os.makedirs(year_dir, exist_ok=True)
        filepath = os.path.join(year_dir, f'{code}.csv')
        file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
        drop = group.drop(columns=['__year'])
        if 'time' in drop.columns:
            drop = drop.rename(columns={'time': 'date'})
        drop.to_csv(filepath, mode='a', header=not file_exists, index=False)
        stats['rows'] += len(drop)
        print(f"    → 写入 {year} 年文件: {os.path.basename(filepath)} (+{len(drop)} 行)")
    stats['codes_updated'] += 1


def fetch_year(code, market, year, last_date, used_vol, week_start, week_start_used, stats, now):
    """拉取单个 code 某整年股本数据"""
    start = f'{year}-01-01'
    end = f'{year}-12-31'

    # 当年只拉到昨日
    if year == now.year:
        end = (now - timedelta(days=1)).strftime('%Y-%m-%d')

    # 断点续传
    if last_date is not None:
        try:
            ld = datetime.strptime(str(last_date)[:10], '%Y-%m-%d')
            if ld >= datetime.strptime(start, '%Y-%m-%d'):
                start = (ld + timedelta(days=1)).strftime('%Y-%m-%d')
        except ValueError:
            pass

    try:
        s = datetime.strptime(start[:10], '%Y-%m-%d')
        e = datetime.strptime(end[:10], '%Y-%m-%d')
        if s > e:
            return used_vol
    except ValueError:
        pass

    # THS_DS 参数：codes, indicators, reportType, 空(qryParam), startdate, enddate
    data = None
    retries = 3
    for attempt in range(1, retries + 1):
        data = THS_DS(code, INDICATORS, REPORT_TYPE, '', start, end)
        if data.errorcode == 0:
            break
        print(f"  {code} [{year}] 拉取失败(第{attempt}次): {data.errmsg}，重试中...")
        time.sleep(2 * attempt)

    if data is None or data.errorcode != 0:
        print(f"  错误：{code} {year} 重试{retries}次仍失败: {data.errmsg if data else '未知'}")
        stats['errors'] += 1
        return used_vol

    vol = getattr(data, 'dataVol', 0)
    used_vol += vol
    stats['used_vol'] = used_vol
    stats['week_used'] = week_start_used + used_vol
    stats['requests'] += 1
    save_weekly_usage(week_start, stats['week_used'])

    df = data.data
    if df is not None and not df.empty:
        rows = len(df)
        print(f"  {code} [{year}] 拉取 {start} → {end}，{rows} 行，本次格数 {vol}")
        append_by_year(code, market, df, stats)
    else:
        print(f"  {code} [{year}] 无新数据（{start} → {end}）")

    return used_vol


def main():
    if not IFIND_USER or not IFIND_PASS:
        print('错误：请在 IFIND_DATA/.env 中配置 IFIND_USER 和 IFIND_PASS')
        return

    now = datetime.now()
    week_start, week_used = load_weekly_usage()

    stats = {
        'codes_total': 0,
        'codes_processed': 0,
        'codes_updated': 0,
        'years': [],
        'requests': 0,
        'rows': 0,
        'errors': 0,
        'empty_responses': 0,
        'used_vol': 0,
        'week_used': week_used,
        'budget_hit': False,
    }

    print(f"===== A股股本数据下载（THS_DS）=====\n")
    print(f"数据目录: {DATA_ROOT}")
    print(f"年份范围: {HISTORY_START_YEAR} - {HISTORY_END_YEAR}")
    print(f"每周预算: {WEEKLY_BUDGET:,} 格数")
    print(f"本周起算: {week_start} 已用 {week_used:,} 格")
    print()

    ret = THS_iFinDLogin(IFIND_USER, IFIND_PASS)
    if ret != 0:
        print(f"登录失败，错误码: {ret}")
        return
    print("登录成功")

    try:
        codes = load_stock_lists()
        if not codes:
            print('错误：未从清单文件读取到任何标的')
            return
        stats['codes_total'] = len(codes)
        market_counts = {}
        for _, m in codes:
            market_counts[m] = market_counts.get(m, 0) + 1
        market_info = ', '.join(f'{m}={n}只' for m, n in sorted(market_counts.items()))
        print(f"读取到标的: {len(codes)} 只（清单: {STOCK_LISTS}）→ {market_info}\n")

        years = list(range(HISTORY_START_YEAR, HISTORY_END_YEAR + 1))
        stats['years'] = years
        budget_exceeded = False

        for i, (code, market) in enumerate(codes, 1):
            if budget_exceeded:
                break

            stats['codes_processed'] += 1
            print(f"[{i}/{len(codes)}] 处理 {code} (市场={market})")

            for year in years:
                if budget_exceeded:
                    break

                year_dir = os.path.join(DATA_ROOT, market, str(year))
                filepath = os.path.join(year_dir, f'{code}.csv')
                last_date = read_last_timestamp(filepath)

                stats['used_vol'] = fetch_year(
                    code, market, year, last_date,
                    stats['used_vol'], week_start, week_used, stats, now
                )

                stats['week_used'] = week_used + stats['used_vol']

                if stats['week_used'] >= WEEKLY_BUDGET:
                    print(f"\n⚠️ 预算超限：本周已用 {stats['week_used']:,} 格数 / 上限 {WEEKLY_BUDGET:,}，停止本次任务")
                    stats['budget_hit'] = True
                    budget_exceeded = True
                    break

        save_weekly_usage(week_start, stats['week_used'])

        remaining = max(0, WEEKLY_BUDGET - stats['week_used'])
        print("\n===== 任务完成汇总 =====")
        print(f"标的: {stats['codes_processed']}/{stats['codes_total']} 只")
        print(f"年份: {'-'.join(map(str, stats['years']))}" if stats['years'] else "年份: -")
        print(f"请求次数: {stats['requests']}")
        print(f"本次新增行数: {stats['rows']:,}")
        print(f"本次消耗格数: {stats['used_vol']:,}")
        print(f"本周累计格数: {stats['week_used']:,} / {WEEKLY_BUDGET:,}")
        print(f"本周剩余格数: {remaining:,}")
        print(f"错误: {stats['errors']} 次 | 空响应: {stats['empty_responses']} 次")
        if stats['budget_hit']:
            print(f"\n⚠️ 已触发预算上限，任务提前终止")

        # 推送（复用 push.py）
        try:
            sys.path.insert(0, str(PROJECT_ROOT / 'src'))
            from tools.push import push_message
            title = "📊 A股股本数据下载完成"
            lines = [
                f"标的: {stats['codes_processed']}/{stats['codes_total']} 只",
                f"年份: {'-'.join(map(str, stats['years']))}" if stats['years'] else "年份: -",
                f"本次新增: {stats['rows']:,} 行 / 消耗 {stats['used_vol']:,} 格",
                f"本周累计: {stats['week_used']:,} / {WEEKLY_BUDGET:,} 格（剩余 {remaining:,}）",
                f"错误: {stats['errors']} 次 | 空响应: {stats['empty_responses']} 次",
            ]
            if stats['budget_hit']:
                lines.append("⚠️ 已触发预算上限，任务提前终止")
            push_message(title, lines)
        except Exception:
            pass

        sys.exit(1 if stats['budget_hit'] else 0)

    finally:
        try:
            THS_iFinDLogout()
        except Exception:
            pass


if __name__ == '__main__':
    main()