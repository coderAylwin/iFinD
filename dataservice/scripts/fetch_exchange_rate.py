# -*- coding: utf-8 -*-
"""
拉取人民币/港币汇率日线数据（THS_EDB）

指标ID：M002842090（人民币/港币）
存储：raw/exchange_rate/CNH_HKD.csv（单文件，增量追加）
断点续传：读文件最后日期，从下一天续拉

运行：cd IFIND_DATA && python3 -u dataservice/scripts/fetch_exchange_rate.py
"""
import os
import sys
import time
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

from iFinDPy import THS_iFinDLogin, THS_iFinDLogout, THS_EDB
import pandas as pd

# ===== 配置 =====
IFIND_USER = os.getenv('IFIND_USER', '')
IFIND_PASS = os.getenv('IFIND_PASS', '')
INDICATOR = 'M002842090'  # 人民币/港币
OUT_DIR = str(WORKSPACE_ROOT / 'raw' / 'exchange_rate')
OUT_FILE = os.path.join(OUT_DIR, 'CNH_HKD.csv')

START_DATE = '2012-01-01'
END_DATE = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')

def log(msg):
    print(msg, flush=True)

def read_last_date():
    if not os.path.exists(OUT_FILE) or os.path.getsize(OUT_FILE) == 0:
        return None
    try:
        df = pd.read_csv(OUT_FILE)
        # 尝试常见的日期列名
        for col in df.columns:
            if 'date' in col.lower() or 'time' in col.lower():
                return str(df[col].iloc[-1]).strip()[:10]
        return None
    except Exception:
        return None

def main():
    log("=" * 60)
    log("iFinD 汇率获取: 人民币/港币")
    log(f"指标: {INDICATOR}")
    log(f"范围: {START_DATE} → {END_DATE}")
    log(f"输出: {OUT_FILE}")
    log("")

    if not IFIND_USER or not IFIND_PASS:
        log("❌ 请在 dataservice/.env 中配置 IFIND_USER / IFIND_PASS")
        return

    ret = THS_iFinDLogin(IFIND_USER, IFIND_PASS)
    if ret != 0:
        log(f"❌ 登录失败: {ret}")
        return
    log("✅ 登录成功")

    try:
        # 断点续传
        last_date = read_last_date()
        start = START_DATE
        if last_date:
            try:
                ld = datetime.strptime(last_date, '%Y-%m-%d')
                next_day = (ld + timedelta(days=1)).strftime('%Y-%m-%d')
                if next_day > END_DATE:
                    log(f"已是最新，无需更新（最后日期: {last_date}）")
                    return
                start = next_day
                log(f"断点续传: 从 {start} 开始")
            except ValueError:
                pass

        for attempt in range(3):
            data = THS_EDB(INDICATOR, '', start, END_DATE)
            if data.errorcode == 0:
                break
            log(f"⚠️ 重试 {attempt+1}: {data.errmsg}")
            time.sleep(2 * (attempt + 1))

        if data.errorcode != 0:
            log(f"❌ 拉取失败: {data.errmsg if hasattr(data,'errmsg') else '未知'}")
            return

        df = data.data
        if df is None or (hasattr(df, 'empty') and df.empty):
            log("→ 无新数据")
            return

        os.makedirs(OUT_DIR, exist_ok=True)
        file_exists = os.path.exists(OUT_FILE) and os.path.getsize(OUT_FILE) > 0
        df.to_csv(OUT_FILE, mode='a', header=not file_exists, index=False)
        log(f"✅ 写入 {len(df)} 行 → {OUT_FILE}")

    finally:
        try:
            THS_iFinDLogout()
        except Exception:
            pass

if __name__ == '__main__':
    main()