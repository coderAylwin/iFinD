#!/usr/bin/env python3
"""
获取 iFinD 1分钟 K线数据（支持复权选项）

用法：
    python3 fetch_1m_kline.py 515080.SH 2026-01-02 2026-01-07
    python3 fetch_1m_kline.py 159941.SZ 2022-07-04 2022-07-05 --adj backward1
    python3 fetch_1m_kline.py 600519.SH 2026-01-05 2026-01-05 --adj forward1

复权选项（--adj）：
  no         不复权（默认）
  forward1   前复权（分红方案计算）
  backward1  后复权（分红方案计算）
  forward3   前复权（交易所价格计算）
  backward3  后复权（交易所价格计算）

注意：部分 ETF（如纳指ETF 159941）有份额折算导致价格跳变，
      必须用后复权才能保持价格连续，适合回测使用。
"""

import sys
import argparse
sys.path.insert(0, '/home/ubuntu/ifind_workspace/IFIND_DATA/dataservice/sdk')
from iFinDPy import *

USERNAME = "hzwcxx001"
PASSWORD = "5PdGc0Dk"

# 复权方式参数
ADJ_MAP = {
    'no': 'no',
    'forward1': 'forward1',
    'backward1': 'backward1',
    'forward3': 'forward3',
    'backward3': 'backward3',
    'forward2': 'forward2',
    'backward2': 'backward2',
    'forward4': 'forward4',
    'backward4': 'backward4',
}


def fetch_1m_kline(code, start_date, end_date, adj='no', output_csv=None):
    """
    获取1分钟K线
    """
    ret = THS_iFinDLogin(USERNAME, PASSWORD)
    if ret != 0:
        print(f"[错误] iFinD 登录失败: {ret}")
        return None

    indicator = 'date,time,open,high,low,close,volume,amount'
    jsonparam = f'Interval:1,CPS:{adj}'

    start = f"{start_date} 09:00:00"
    end = f"{end_date} 15:00:00"

    r = THS_HF(code, indicator, jsonparam, start, end)

    THS_iFinDLogout()

    if r.errorcode != 0:
        print(f"[错误] 查询失败: errorcode={r.errorcode}, errmsg={r.errmsg}")
        return None

    df = r.data
    if df is None or len(df) == 0:
        print(f"[提示] 未查到数据")
        return None

    # 处理时间列
    time_col = 'time'
    date_col = None
    for c in df.columns:
        if 'date' in c.lower():
            date_col = c
            break

    if date_col:
        df['datetime'] = df[date_col].astype(str) + ' ' + df[time_col].astype(str)
        df = df.sort_values([date_col, time_col]).reset_index(drop=True)
        cols = ['datetime'] + [c for c in ['open','high','low','close','volume','amount'] if c in df.columns]
        df = df[cols]

    if output_csv:
        df.to_csv(output_csv, index=False, encoding='utf-8-sig')
        print(f"[已保存] {output_csv}")

    return df


def main():
    parser = argparse.ArgumentParser(description='获取iFinD 1分钟K线')
    parser.add_argument('code', help='标的代码，如 515080.SH')
    parser.add_argument('start', help='开始日期，如 2026-01-02')
    parser.add_argument('end', help='结束日期，如 2026-01-07')
    parser.add_argument('--adj', choices=ADJ_MAP.keys(), default='no',
                        help='复权方式（默认不复权）')
    parser.add_argument('-o', '--output', help='输出文件路径')

    args = parser.parse_args()

    out = args.output or f"{args.code.replace('.', '_')}_1m_{args.start}_{args.end}_{args.adj}.csv"

    adj_label = args.adj
    df = fetch_1m_kline(args.code, args.start, args.end, adj=args.adj, output_csv=out)
    if df is None:
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"{args.code} 1分钟K线 | {args.start} ~ {args.end} | 复权: {adj_label}")
    print(f"共 {len(df)} 条记录")
    print(f"{'='*60}")
    print(df.head(5).to_string(index=False))
    print(f"...")
    print(df.tail(3).to_string(index=False))


if __name__ == '__main__':
    main()