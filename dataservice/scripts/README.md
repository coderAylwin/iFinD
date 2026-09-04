# dataservice/scripts/ — 数据获取脚本

## 通用说明

### 运行环境
- Python 3.8+
- 依赖：`iFinDPy`（位于 `dataservice/sdk/`）
- 所有脚本均由 `IFIND_DATA/` 根目录执行，例如：
  ```bash
  cd IFIND_DATA && python3 dataservice/scripts/fetch_daily.py
  ```

### 外部配置依赖
- **`.env` 账号配置**：所有脚本均从 `IFIND_DATA/.env` 加载同花顺账号密码（`IFIND_USER` / `IFIND_PASS`）
- **SDK 路径**：`dataservice/sdk/` 需包含 iFinD Python SDK（未纳入版本控制，另行部署）
- **用户配置**：`dataservice/sdk/users/Passport/` 下的 passport 文件对应 SDK 配置需求

### 数据输出约定
数据文件（原始数据）统一输出到 `IFIND_DATA/raw/` 目录，不纳入版本控制。

---

## 脚本列表

### 1. `fetch_daily.py` — 全A股日线批量拉取
拉取 `zz_all_list_cn.csv` 中所有 A 股的历史日线 K 线数据，按 `raw/market/{code}.csv` 存储。

```bash
python3 dataservice/scripts/fetch_daily.py
```
- **依赖**: `.env` 账号 + `data/lists/zz_all_list_cn.csv`（股票清单）
- **输出**: `raw/daily/{market}/{code}.csv`

---

### 2. `fetch_1m.py` — ETF 1分钟K线批量拉取
批量下载 ETF 的 1 分钟 K 线数据。

```bash
python3 dataservice/scripts/fetch_1m.py
```
- **依赖**: `.env` 账号 + `zz_all_list_cn.csv`
- **输出**: `raw/market/minute/{market}/{year}/{code}.csv`

---

### 3. `fetch_1m_kline.py` — 单标的1分钟K线（命令行调用）
支持指定代码、日期范围、复权选项。

```bash
python3 dataservice/scripts/fetch_1m_kline.py 515080.SH 2026-01-02 2026-01-07
python3 dataservice/scripts/fetch_1m_kline.py 600519.SH 2026-01-05 2026-01-05 --adj forward1
python3 dataservice/scripts/fetch_1m_kline.py 159941.SZ 2022-07-04 2022-07-05 --adj backward1
```
- **复权选项**：`--adj forward1`（前复权）/ `--adj backward1`（后复权）/ 不传（原始价格）
- **无需 `.env`**（直接命令行参数，仍需要 SDK 登录）

---

### 4. `fetch_daily_supplement.py` — 流通股本 + 股息率（日频补量）
获取流通股本 + 近 12 月股息率，日频序列。不区分 A 股/港股。

```bash
python3 dataservice/scripts/fetch_daily_supplement.py
```
- **依赖**: `.env` 账号
- **输出**: `raw/supplement/{market}/{code}.csv`

---

### 5. `fetch_exchange_rate.py` — 人民币/港币汇率日线
拉取人民币/港币汇率日线数据（THS_EDB 指标 M002842090）。

```bash
python3 dataservice/scripts/fetch_exchange_rate.py
```
- **依赖**: `.env` 账号
- **输出**: `raw/exchange_rate.csv`

---

### 6. `fetch_shares.py` — 股本数据（自由流通股本 / 总股本 / 流通A股）
批量下载 A 股股本数据，对应日间序列。

```bash
python3 dataservice/scripts/fetch_shares.py
```
- **依赖**: `.env` 账号 + `zz_all_list_cn.csv`
- **输出**: `raw/shares/{market}/{code}.csv`

---

### 7. `fetch_financial.py` — 季度财务数据（A股 + 港股）
拉取 A 股 + 港股季报/中报/年报财务数据（THS_DS）。

```bash
python3 dataservice/scripts/fetch_financial.py
```
- **依赖**: `.env` 账号
- **输出**: `raw/financial/{market}/{code}.csv`

---

### 8. `fetch_financial_wc.py` — 问财补充财务数据
对 A 股缺失的季度财务数据，通过问财逐季度补充。

```bash
python3 dataservice/scripts/fetch_financial_wc.py
```
- **依赖**: `.env` 账号
- **输出**: 合并到 `raw/financial/` 目录

---

### 9. `fetch_stock_data.py` — 股票截面指标拉取
批量拉取 `zz_all_list_cn.csv` 中所有股票的指定截面指标数据。

```bash
python3 dataservice/scripts/fetch_stock_data.py
```
- **依赖**: `.env` 账号 + `zz_all_list_cn.csv`
- **输出**: `raw/cross_section/` 目录

---

### 10. `fetch_watchlist.py` — 盯盘列表日线数据
拉取指定 A 股 + 港股标的日线数据（原始价格 + 复权因子）。

```bash
python3 dataservice/scripts/fetch_watchlist.py
```
- **依赖**: `.env` 账号 + 脚本内标的清单
- **输出**: `raw/watchlist/` 目录

---

### 11. `query_index_members.py` — 指数成分股查询
查询指定指数在指定日期的成分股及权重。

```bash
python3 dataservice/scripts/query_index_members.py 000922.CSI 2026-01-05
python3 dataservice/scripts/query_index_members.py 000300.SH 2024-06-01
```
- **支持指数代码后缀**: `.CSI`（中证）、`.SH`（上证）、`.SZ`（深证）
- **无需 `.env`**（直接命令行参数，需要 SDK 登录）

---

### 12. `demo_1m.py` — 1分钟K线示例
演示用 `THS_HF` 拉取 1 分钟 K 线并保存为 CSV 的完整流程。

```bash
python3 dataservice/scripts/demo_1m.py
```
- **依赖**: `.env` 账号
- **输出**: 示例保存到 `data/market/minute/`（可自行修改路径）

---

## 维护说明

- 所有脚本共享 `dataservice/sdk/` 和 `IFIND_DATA/.env` 配置
- `raw/` 目录为数据输出目录，已写入 `.gitignore`
- 如新增脚本，请同步更新本 README