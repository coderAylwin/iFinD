# -*- coding: utf-8 -*-
"""
批量下载 A 股日线 K 线数据（fetch_daily）

核心策略：
- 使用 THS_HD 接口（日线历史行情）替代 THS_HF（分钟线）
- 拉取：按年/月分段，确保单次请求周期不会跨年
- 存储：按年分文件
      {DATA_ROOT}/daily/{market}/{year}/{code}.csv
- 增量：读文件最后时间戳，从下一天续拉
- 频率：每日或每周均可，幂等

用法：
    cd IFIND_DATA && python3 dataservice/scripts/fetch_daily.py

依赖：同花顺 iFinDPy（dataservice/sdk/），需在 dataservice/.env 配置账号密码。
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

from iFinDPy import THS_iFinDLogin, THS_iFinDLogout, THS_HD
import pandas as pd


# ======================================================================
# 配置
# ======================================================================
IFIND_USER = os.getenv('IFIND_USER', '')
IFIND_PASS = os.getenv('IFIND_PASS', '')
DATA_ROOT = str(WORKSPACE_ROOT / 'raw/daily')
WEEKLY_BUDGET = int(os.getenv('WEEKLY_BUDGET', '150000000'))

# 年份范围
HISTORY_START_YEAR = int(os.getenv('HISTORY_START_YEAR', str(datetime.now().year - 1)))
HISTORY_END_YEAR = int(os.getenv('HISTORY_END_YEAR', str(datetime.now().year)))

# 清单文件（逗号分隔，放在 data/lists/ 目录下）
STOCK_LISTS = os.getenv('STOCK_LISTS_DAILY', os.getenv('STOCK_LISTS', 'hs300_list.csv'))

# THS_HD 指标（分号分隔）
INDICATORS = 'open;high;low;close;volume;amount;preClose;turn'

# 本周用量记录文件
USAGE_FILE = PROJECT_ROOT / 'data' / 'usage_daily.json'

# 推送工具（dataservice/src/tools/push.py）
sys.path.insert(0, str(PROJECT_ROOT / 'src'))
from tools.push import push_message


# ======================================================================
# 工具函数
# ======================================================================
def load_weekly_usage():
    """读本周已用格数；跨周则重置为0，返回 (week_start, week_used)"""
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
            return monday_str, 0  # 跨周，重置
    except Exception:
        return monday_str, 0


def save_weekly_usage(week_start, used_vol):
    """持久化本周已用格数"""
    import json
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    USAGE_FILE.write_text(json.dumps({
        'week_start': week_start,
        'used_vol': used_vol,
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }, ensure_ascii=False, indent=2), encoding='utf-8')


def guess_market_from_listname(list_name):
    """从清单文件名后缀推断市场目录

    规则：取文件名最后一个 _ 后的后缀作为市场名
    例如：hs300_list_cn.csv → cn, etf_list_etf.csv → etf, us_list_us.csv → us
    无后缀时默认 cn。
    """
    stem = Path(list_name).stem  # 去掉 .csv
    parts = stem.split('_')
    if len(parts) >= 2:
        suffix = parts[-1]
        # 避免把真正的列表名（如 hs300_list）当成市场
        if len(suffix) <= 6 and suffix.isalpha():
            return suffix.lower()
    return 'cn'


def load_stock_lists():
    """从 data/lists/ 目录读取 STOCK_LISTS 配置的清单文件，返回 (code, market) 列表（去重、保序）

    市场目录由清单文件名后缀决定：
      hs300_list_cn.csv   → market='cn'
      etf_list_etf.csv    → market='etf'
      us_list_us.csv      → market='us'
      hs300_list.csv（无后缀）→ market='cn'
    """
    lists_dir = PROJECT_ROOT / 'data' / 'lists'
    items = []  # [(code, market), ...]
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


def get_month_end(year, month):
    """获取某年某月的最后一天（返回 '01'~'31' 字符串）"""
    if month == 12:
        return '31'
    return str((datetime(year, month + 1, 1) - timedelta(days=1)).day)


def read_last_timestamp(csv_path):
    """读取 CSV 最后一行的 date 时间戳；文件不存在或为空返回 None"""
    if not os.path.exists(csv_path) or os.path.getsize(csv_path) == 0:
        return None
    try:
        df = pd.read_csv(csv_path, usecols=lambda c: True)
        if df.empty:
            return None
        time_col = 'date' if 'date' in df.columns else df.columns[0]
        last = str(df[time_col].iloc[-1]).strip()
        return last if last else None
    except Exception as e:
        print(f"  警告：读取 {csv_path} 最后时间戳失败: {e}")
        return None


def append_by_year(code, market, df, stats):
    """
    将拉取的 DataFrame 按年份拆分，追加写入对应年份文件。
    """
    if df is None or df.empty:
        stats['empty_responses'] += 1
        return

    # 按年份分组（date 列前4位为年份）
    df = df.copy()
    df['__year'] = df['date'].astype(str).str[:4]
    for year, group in df.groupby('__year'):
        year_dir = os.path.join(DATA_ROOT, market, str(year))
        os.makedirs(year_dir, exist_ok=True)
        filepath = os.path.join(year_dir, f'{code}.csv')
        file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
        drop = group.drop(columns=['__year'])
        drop.to_csv(filepath, mode='a', header=not file_exists, index=False)
        stats['rows'] += len(drop)
        print(f"    → 写入 {year} 年文件: {os.path.basename(filepath)} (+{len(drop)} 行)")

    stats['codes_updated'] += 1


def fetch_month(code, market, year, month, start, end, last_date, used_vol, week_start, week_start_used, stats):
    """
    拉取单个 code 某个月的日线（[start, end]），
    结合断点续传：若 last_date 已覆盖 start，则从 last_date 之后续拉。
    """
    # 断点续传
    if last_date is not None:
        try:
            ld = datetime.strptime(str(last_date)[:10], '%Y-%m-%d')
            s = datetime.strptime(str(start)[:10], '%Y-%m-%d')
            if ld >= s:
                # 从本地最后日期 +1 天开始
                start = (ld + timedelta(days=1)).strftime('%Y-%m-%d')
        except ValueError:
            pass

    # 若开始时间已超过 end，跳过
    try:
        s = datetime.strptime(str(start)[:10], '%Y-%m-%d')
        e = datetime.strptime(str(end)[:10], '%Y-%m-%d')
        if s > e:
            return used_vol
    except ValueError:
        pass

    # 调用 THS_HD 拉取日线（带重试）
    data = None
    retries = 3
    for attempt in range(1, retries + 1):
        data = THS_HD(code, INDICATORS, '', start, end)
        if data.errorcode == 0:
            break
        print(f"  {code} [{year}-{month:02d}] 拉取失败(第{attempt}次): {data.errmsg}，重试中...")
        time.sleep(2 * attempt)

    if data is None or data.errorcode != 0:
        print(f"  错误：{code} {year}-{month:02d} 重试{retries}次仍失败: {data.errmsg if data else '未知'}")
        stats['errors'] += 1
        return used_vol

    vol = getattr(data, 'dataVol', 0)
    used_vol += vol
    stats['used_vol'] = used_vol
    stats['week_used'] = week_start_used + used_vol
    stats['requests'] += 1

    # 立即持久化本周用量
    save_weekly_usage(week_start, stats['week_used'])

    df = data.data
    if df is not None and not df.empty:
        rows = len(df)
        print(f"  {code} [{year}-{month:02d}] 拉取 {start} → {end}，{rows} 行，本次格数 {vol}")
        append_by_year(code, market, df, stats)
    else:
        print(f"  {code} [{year}-{month:02d}] 无新数据（{start} → {end}）")
        stats['empty_responses'] += 1

    return used_vol


def main():
    # ---- 1. 检查配置 ----
    if not IFIND_USER or not IFIND_PASS:
        print('错误：请在 IFIND_DATA/.env 中配置 IFIND_USER 和 IFIND_PASS')
        return

    now = datetime.now()
    yesterday = now - timedelta(days=1)
    yesterday_str = yesterday.strftime('%Y-%m-%d')

    # ---- 2. 本周用量 ----
    week_start, week_used = load_weekly_usage()

    # ---- 3. 初始化统计 ----
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

    print(f"===== A股日线数据增量下载（THS_HD）=====\n")
    print(f"数据目录: {DATA_ROOT}")
    print(f"年份范围: {HISTORY_START_YEAR} - {HISTORY_END_YEAR}")
    print(f"每周预算: {WEEKLY_BUDGET:,} 格数")
    print(f"本周起算: {week_start} 已用 {week_used:,} 格")
    print()

    # ---- 4. 登录 ----
    ret = THS_iFinDLogin(IFIND_USER, IFIND_PASS)
    if ret != 0:
        print(f"登录失败，错误码: {ret}")
        return
    print("登录成功")

    try:
        # ---- 5. 加载标的 ----
        codes = load_stock_lists()
        if not codes:
            print('错误：未从清单文件读取到任何标的，请检查 STOCK_LISTS 配置')
            return
        stats['codes_total'] = len(codes)
        # 统计各市场数量
        market_counts = {}
        for _, m in codes:
            market_counts[m] = market_counts.get(m, 0) + 1
        market_info = ', '.join(f'{m}={n}只' for m, n in sorted(market_counts.items()))
        print(f"读取到标的: {len(codes)} 只（清单: {STOCK_LISTS}）→ {market_info}\n")

        # ---- 6. 逐标的逐月拉取 ----
        years = list(range(HISTORY_START_YEAR, HISTORY_END_YEAR + 1))
        stats['years'] = years
        budget_exceeded = False
        current_month = now.month

        for i, (code, market) in enumerate(codes, 1):
            if budget_exceeded:
                break

            stats['codes_processed'] += 1
            print(f"[{i}/{len(codes)}] 处理 {code} (市场={market})")

            for year in years:
                if budget_exceeded:
                    break

                # 读当年文件最后日期（用于断点续传）
                year_dir = os.path.join(DATA_ROOT, market, str(year))
                filepath = os.path.join(year_dir, f'{code}.csv')
                last_date = read_last_timestamp(filepath)

                for month in range(1, 13):
                    if budget_exceeded:
                        break

                    # 未来月份不拉
                    if year == now.year and month > current_month:
                        break

                    start = f'{year}-{month:02d}-01'
                    month_end = get_month_end(year, month)

                    if year == now.year and month == current_month:
                        # 当前月：拉到昨日
                        end = yesterday_str
                    else:
                        # 历史月份：拉满当月
                        end = f'{year}-{month:02d}-{month_end}'

                    stats['used_vol'] = fetch_month(
                        code, market, year, month, start, end, last_date,
                        stats['used_vol'], week_start, week_used, stats
                    )

                    stats['week_used'] = week_used + stats['used_vol']

                    # ---- 预算控制 ----
                    if stats['week_used'] >= WEEKLY_BUDGET:
                        print(f"\n⚠️ 预算超限：本周已用 {stats['week_used']:,} 格数 / 上限 {WEEKLY_BUDGET:,}，停止本次任务")
                        stats['budget_hit'] = True
                        budget_exceeded = True
                        break

        # 保存本周用量
        save_weekly_usage(week_start, stats['week_used'])

        # ---- 汇总 ----
        remaining = max(0, WEEKLY_BUDGET - stats['week_used'])
        print("\n===== 任务完成汇总 =====")
        print(f"标的: {stats['codes_processed']}/{stats['codes_total']} 只")
        print(f"年份: {stats['years'][0]}-{stats['years'][-1]}" if stats['years'] else "年份: -")
        print(f"请求次数: {stats['requests']}")
        print(f"本次新增行数: {stats['rows']:,}")
        print(f"本次消耗格数: {stats['used_vol']:,}")
        print(f"本周累计格数: {stats['week_used']:,} / {WEEKLY_BUDGET:,}")
        print(f"本周剩余格数: {remaining:,}")
        print(f"错误: {stats['errors']} 次 | 空响应: {stats['empty_responses']} 次")
        if stats['budget_hit']:
            print(f"\n⚠️ 已触发预算上限，任务提前终止")

        # ---- 推送 ----
        title = "📊 A股日线数据下载完成"
        lines = [
            f"标的: {stats['codes_processed']}/{stats['codes_total']} 只",
            f"年份: {stats['years'][0]}-{stats['years'][-1]}" if stats['years'] else "年份: -",
            f"本次新增: {stats['rows']:,} 行 / 消耗 {stats['used_vol']:,} 格",
            f"本周累计: {stats['week_used']:,} / {WEEKLY_BUDGET:,} 格（剩余 {remaining:,}）",
            f"错误: {stats['errors']} 次 | 空响应: {stats['empty_responses']} 次",
        ]
        if stats['budget_hit']:
            lines.append("⚠️ 已触发预算上限，任务提前终止")
        push_message(title, lines)

        # ---- 登出 ----
        try:
            THS_iFinDLogout()
            print("已登出 iFinD")
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