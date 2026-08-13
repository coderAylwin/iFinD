# -*- coding: utf-8 -*-
"""
示例：用 THS_HF 拉取 1 分钟 K 线，保存为 CSV
保存路径：IFIND_DATA/data/market/minute/{market}/{year}/{code}.csv

用法：
    cd IFIND_DATA && python3 scripts/demo_save_csv.py

依赖：同花顺 iFinDPy（本地 SDK），需配置 .env 账号密码
"""
import os
import sys
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'sdk'))

# 项目根目录（dataservice 的上一级，放 raw/ 等）
WORKSPACE_ROOT = PROJECT_ROOT.parent

# 加载 .env 配置
from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / '.env')

from iFinDPy import THS_iFinDLogin, THS_HF
import pandas as pd


# ============ 读取配置 ============
IFIND_USER = os.getenv('IFIND_USER', '')
IFIND_PASS = os.getenv('IFIND_PASS', '')
DATA_ROOT  = str(WORKSPACE_ROOT / 'raw/minute')
CPS        = os.getenv('CPS', 'no')
FILL       = os.getenv('FILL', 'Original')

# 数据参数
CODE = "600000.SH"                              # 标的
INDICATORS = "open;high;low;close;volume;amount" # 指标（分号分隔）
START = "2026-08-13 14:15:00"
END = "2026-08-13 15:15:00"


def get_year_dir(code, start_ts):
    """按 标的/市场/年份 建目录
    minute/{market}/{year}/{code}.csv"""
    market = "cn"          # 按代码后缀判断市场，后续可扩展
    year = start_ts[:4]    # 从开始时间取年份
    dirpath = os.path.join(DATA_ROOT, market, year)
    os.makedirs(dirpath, exist_ok=True)
    return dirpath, os.path.join(dirpath, f"{code}.csv")


def main():
    # 1. 检查配置
    if not IFIND_USER or not IFIND_PASS:
        print("错误：请在 IFIND_DATA/.env 中配置 IFIND_USER 和 IFIND_PASS")
        return

    # 2. 登录
    ret = THS_iFinDLogin(IFIND_USER, IFIND_PASS)
    if ret != 0:
        print(f"登录失败，错误码: {ret}")
        return
    print("登录成功")

    # 3. 拉 1 分钟 K 线（format 默认 dataframe，直接返回 DataFrame）
    # jsonparam 传空字符串或 Fill:Original 即可，其他参数使用默认值
    jsonparam = FILL if FILL else ''
    data = THS_HF(CODE, INDICATORS, jsonparam, START, END)
    if data.errorcode != 0:
        print(f"拉取失败: {data.errmsg}")
        return

    df = data.data
    if df is None or df.empty:
        print("没有数据")
        return

    print("拿到数据，形状:", df.shape)
    print("列名:", list(df.columns))
    print(df.head())

    # 4. 建目录并保存
    dirpath, filepath = get_year_dir(CODE, START)
    file_exists = os.path.exists(filepath)

    # 首次创建时写 header，追加时只写数据行
    df.to_csv(filepath, mode="a", header=not file_exists, index=False)

    print(f"\n已保存: {filepath}")
    print(f"数据根目录: {DATA_ROOT}")


if __name__ == "__main__":
    main()