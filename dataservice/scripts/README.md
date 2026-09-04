# iFinD 数据拉取脚本使用说明

所有脚本在 `/home/ubuntu/ifind_workspace/IFIND_DATA/dataservice/scripts/` 下，
统一使用 SDK 登录（账号密码在 `dataservice/.env`）。

**通用用法：**
```bash
cd /home/ubuntu/ifind_workspace/IFIND_DATA/dataservice
python3 scripts/<脚本名>.py <参数>
```

---

## 1. fetch_1m_kline.py — 获取1分钟K线

```bash
python3 scripts/fetch_1m_kline.py <代码> <开始日期> <结束日期> [--adj 复权] [-o 输出文件]
```

**参数：**
- `<代码>`：如 `515080.SH`、`600519.SH`
- `<开始日期>` / `<结束日期>`：`YYYY-MM-DD`
- `--adj`：复权方式
  - `no` 不复权（默认）
  - `backward1` 后复权（分红方案）← **回测推荐**
  - `forward1` 前复权（分红方案）
  - `backward3` / `forward3` 交易所价格计算
- `-o`：输出 CSV 路径（默认 `{代码}_1m_{起}_{止}_{复权}.csv`）

**示例：**
```bash
# 后复权，纳指ETF（有份额折算，必须后复权才连续）
python3 scripts/fetch_1m_kline.py 159941.SZ 2022-07-04 2022-07-05 --adj backward1

# 不复权
python3 scripts/fetch_1m_kline.py 515080.SH 2026-01-02 2026-01-07
```

**输出字段：** `datetime, open, high, low, close, volume, amount`

---

## 2. query_index_members.py — 查询指数成分股及权重

```bash
python3 scripts/query_index_members.py <指数代码> <日期>
```

**参数：**
- `<指数代码>`：如 `000922.CSI`（中证红利）、`000300.SH`（沪深300）、`000001.SH`（上证指数）
- `<日期>`：`YYYY-MM-DD`，任意历史日期

**示例：**
```bash
python3 scripts/query_index_members.py 000922.CSI 2026-01-05
python3 scripts/query_index_members.py 000300.SH 2024-06-01
```

**输出：**
- 控制台打印完整成分股列表（按权重降序，含代码、名称、权重%）
- 自动保存 `{指数代码}_{日期}.csv` 到当前目录

---

## 3. fetch_1m.py — 批量拉取分钟K线（配置文件驱动）

```bash
python3 scripts/fetch_1m.py
```
按 `.env` 中 `STOCK_LISTS_1M` 清单批量拉取，无参数，直接运行。

---

## 4. fetch_daily.py — 批量拉取日线

```bash
python3 scripts/fetch_daily.py
```
按 `.env` 中 `STOCK_LISTS_DAILY` 清单批量拉取，无参数，直接运行。

---

## 5. demo_1m.py — 示例脚本

演示 1分钟K线拉取的最小可运行示例，参考用。

---

## 复权说明

同花顺 SDK 的 `THS_HQ`（日线接口）复权参数不生效（所有 CPS 返回相同价格），
但 `THS_HF`（分钟K线接口）的 `backward1` 是实际生效的。

因此：
- **要后复权数据 → 用 `fetch_1m_kline.py --adj backward1`**
- 同花顺没有公开的"复权因子"指标接口（`ths_adj_factor_stock` 返回 -209）