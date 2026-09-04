#!/usr/bin/env python3
"""
查询 iFinD 指数在指定日期的成分股及权重

用法：
    python3 query_index_members.py 000922.CSI 2026-01-05
    python3 query_index_members.py 000300.SH 2024-06-01
    python3 query_index_members.py 000001.SH 2024-12-31  # 上证指数
"""

import sys
sys.path.insert(0, '/home/ubuntu/ifind_workspace/IFIND_DATA/dataservice/sdk')
from iFinDPy import *
import os

USERNAME = "hzwcxx001"
PASSWORD = "5PdGc0Dk"


def query_index_members(index_code, date_str):
    """
    查指定指数在指定日期的成分股和权重
    """
    ret = THS_iFinDLogin(USERNAME, PASSWORD)
    if ret != 0:
        print(f"[错误] iFinD 登录失败: {ret}")
        return None

    # 指定显示的列
    columns = 'date:Y,thscode:Y,security_name:Y,weight:Y'

    data = THS_DP('index', f'{date_str};{index_code}', columns)

    if data.errorcode != 0:
        print(f"[错误] 查询失败: errorcode={data.errorcode}, errmsg={data.errmsg}")
        THS_iFinDLogout()
        return None

    df = data.data
    if df is None or len(df) == 0:
        print(f"[提示] 未查到数据，可能指数代码不正确或该日期非交易日")
        THS_iFinDLogout()
        return None

    # 排序：按 weight 降序
    if 'WEIGHT' in df.columns:
        df['WEIGHT'] = df['WEIGHT'].astype(float)
        df = df.sort_values('WEIGHT', ascending=False).reset_index(drop=True)

    return df


def main():
    if len(sys.argv) < 3:
        print("用法: python3 query_index_members.py <指数代码> <日期 YYYY-MM-DD>")
        print("示例:")
        print("  python3 query_index_members.py 000922.CSI 2026-01-05")
        print("  python3 query_index_members.py 000300.SH 2026-06-15")
        sys.exit(1)

    index_code = sys.argv[1]
    date_str = sys.argv[2]

    df = query_index_members(index_code, date_str)
    if df is None:
        sys.exit(1)

    # 打印汇总
    print(f"\n{'='*70}")
    print(f"指数: {index_code}  |  日期: {date_str}")
    print(f"成分股数量: {len(df)}")
    print(f"{'='*70}")
    print(f"{'代码':12} {'名称':12} {'权重(%)':>8}")
    print(f"{'-'*12} {'-'*12} {'-'*8}")

    for _, row in df.iterrows():
        code = row['THSCODE']
        name = row['SECURITY_NAME']
        weight = row.get('WEIGHT', 0)
        print(f"{code:12} {name:12} {weight:>8.3f}")

    print(f"{'='*70}")
    print(f"权重合计: {df['WEIGHT'].sum():.2f}%")

    # 可选：保存到 CSV
    csv_path = f"{index_code.replace('.', '_')}_{date_str}.csv"
    df.to_csv(csv_path, index=False, encoding='utf-8-sig')
    print(f"\n[已保存] {csv_path}")

    THS_iFinDLogout()


if __name__ == '__main__':
    main()