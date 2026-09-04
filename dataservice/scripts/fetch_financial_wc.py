# -*- coding: utf-8 -*-
"""
用问财补充A股缺失的季度财务数据

逐季度查，只补 THS_DS 没取到的数据。
问财格式：
  紫金矿业(601899.SH) 2011一季的营业收入、营业成本、净利润、资产总计、负债合计、股东权益合计

存储：raw/financial/cn/{code}.csv（追加）

运行：cd IFIND_DATA && python3 -u dataservice/scripts/fetch_financial_wc.py
"""
import os
import sys
import time
import json
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'sdk'))
WORKSPACE_ROOT = PROJECT_ROOT.parent

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / '.env')
except ImportError:
    pass

from iFinDPy import THS_iFinDLogin, THS_iFinDLogout, THS_WCQuery
import pandas as pd

# ===== 配置 =====
IFIND_USER = os.getenv('IFIND_USER', '')
IFIND_PASS = os.getenv('IFIND_PASS', '')
DATA_ROOT = str(WORKSPACE_ROOT / 'raw' / 'financial')

STOCKS_CN = [
    ('601899.SH', '紫金矿业'), ('601600.SH', '中国铝业'),
    ('600900.SH', '长江电力'), ('600938.SH', '中国海油'),
    ('603993.SH', '洛阳钼业'), ('000807.SZ', '云铝股份'),
    ('000933.SZ', '神火股份'), ('002532.SZ', '天山铝业'),
    ('601225.SH', '陕西煤业'), ('000651.SZ', '格力电器'),
    ('000333.SZ', '美的集团'), ('600690.SH', '海尔智家'),
    ('605499.SH', '东鹏饮料'), ('600066.SH', '宇通客车'),
    ('000951.SZ', '中国重汽'),
]

START_YEAR = 2011
END_DATE = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

FIN_INDICATORS = '营业收入、营业成本、净利润、资产总计、负债合计、股东权益合计'
OUT_COLS = ['date', 'code', 'period', '营业收入', '营业成本', '净利润', '资产总计', '负债合计', '股东权益合计']

REPORT_PERIODS = [
    ('一季', '0331', '03-31'),
    ('中报', '0630', '06-30'),
    ('三季', '0930', '09-30'),
    ('年报', '1231', '12-31'),
]

FETCH_INTERVAL = 0.5

def log(msg):
    print(msg, flush=True)

def get_empty_periods(code, market):
    """读本地文件，返回数据全为空的 period 集合"""
    filepath = os.path.join(DATA_ROOT, market, f'{code}.csv')
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return set()  # 不存在=全部缺失
    try:
        df = pd.read_csv(filepath)
        fin_cols = ['营业收入', '营业成本', '净利润', '资产总计', '负债合计', '股东权益合计']
        # 找出所有财务指标都为空的行
        empty_rows = df[df[fin_cols].isna().all(axis=1)]
        return set(empty_rows['period'].dropna().astype(str).str.strip())
    except Exception:
        return set()

def get_all_periods(code, market):
    """读本地文件已存的 period 集合"""
    filepath = os.path.join(DATA_ROOT, market, f'{code}.csv')
    if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
        return set()
    try:
        df = pd.read_csv(filepath, usecols=['period'])
        return set(df['period'].dropna().astype(str).str.strip())
    except Exception:
        return set()

def fetch_missing():
    """检查所有标的缺失或数据为空的季度，用问财补"""
    for code, name in STOCKS_CN:
        all_periods = get_all_periods(code, 'cn')
        empty_periods = get_empty_periods(code, 'cn')
        log(f"📈 {code} {name} (已有{len(all_periods)}个季度, 空{len(empty_periods)}个)")

        total = 0
        for p_label, p_suffix, p_date in REPORT_PERIODS:
            for year in range(START_YEAR, datetime.now().year + 1):
                period_str = f'{year}{p_suffix}'
                pm = int(p_suffix[:2])

                now = datetime.now()
                if year > now.year or (year == now.year and pm > now.month):
                    continue

                # 已存在且有数据 -> 跳过
                if period_str in all_periods and period_str not in empty_periods:
                    continue

                query = f'{name}({code}) {year}{p_label}的{FIN_INDICATORS}'
                log(f"  📋 命令: {query}")

                for attempt in range(3):
                    data = THS_WCQuery(query, 'stock')
                    if data.errorcode == 0:
                        break
                    log(f"    ⚠️ 重试 {attempt+1}: {data.errmsg[:60]}")
                    time.sleep(3 * (attempt + 1))

                if data.errorcode != 0:
                    log(f"    ❌ 问财失败")
                    time.sleep(FETCH_INTERVAL)
                    continue

                df = data.data
                if df is None or (hasattr(df, 'empty') and df.empty):
                    log(f"    → 无数据")
                    time.sleep(FETCH_INTERVAL)
                    continue

                # 只处理目标标的的行
                found = False
                for _, row in df.iterrows():
                    c = str(row.get('股票代码', '')).strip()
                    if c != code:
                        continue
                    found = True

                    record = {'date': f'{year}-{p_date}', 'code': code, 'period': period_str}
                    for col in df.columns:
                        if col not in ('股票代码', '股票简称'):
                            clean = col.split('[')[0] if '[' in col else col
                            record[clean] = row[col]

                    out_dir = os.path.join(DATA_ROOT, 'cn')
                    os.makedirs(out_dir, exist_ok=True)
                    filepath = os.path.join(out_dir, f'{code}.csv')
                    file_exists = os.path.exists(filepath) and os.path.getsize(filepath) > 0
                    pd.DataFrame([record]).to_csv(filepath, mode='a', header=not file_exists, index=False)
                    total += 1
                    log(f"    ✅ +1 行")
                    break

                if not found:
                    log(f"    → 未匹配")

                time.sleep(FETCH_INTERVAL)

        log(f"  → 本次补 {total} 行\n")

def main():
    log("=" * 60)
    log("问财补充A股季度财务数据")
    log("=" * 60)
    log(f"标的: {len(STOCKS_CN)} 只")
    log(f"年份: {START_YEAR} - 至今")
    log("")

    if not IFIND_USER or not IFIND_PASS:
        log("❌ 请在 dataservice/.env 中配置 IFIND_USER / IFIND_PASS")
        return

    ret = THS_iFinDLogin(IFIND_USER, IFIND_PASS)
    if ret != 0:
        log(f"❌ 登录失败: {ret}")
        return
    log("✅ 登录成功\n")

    try:
        fetch_missing()
        log("=" * 60)
        log("✅ 完成！")
        log("=" * 60)
    finally:
        try:
            THS_iFinDLogout()
        except Exception:
            pass

if __name__ == '__main__':
    main()