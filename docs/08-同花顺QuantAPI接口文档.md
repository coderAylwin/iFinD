# 同花顺 QuantAPI — HTTP 接口文档

> 基于同花顺量化接口官方手册整理，仅包含 **HTTP RESTful API** 调用方式。
> 适用于 Python / Node.js / Go / Java 等任何支持 HTTP 的语言。
>
> **所有数据接口均返回 JSON 格式**，字段统一结构见下方「通用返回结构」。

---

## 目录

- [1. 通用约定](#1-通用约定)
- [2. Token 获取与鉴权](#2-token-获取与鉴权)
- [3. 基础数据 — THS_BD](#3-基础数据--ths_bd)
- [4. 日期序列 — THS_DS](#4-日期序列--ths_ds)
- [5. 历史行情 — THS_HQ](#5-历史行情--ths_hq)
- [6. 高频序列 — THS_HF](#6-高频序列--ths_hf)
- [7. 实时行情 — THS_RQ](#7-实时行情--ths_rq)
- [8. 日内快照 — THS_SS](#8-日内快照--ths_ss)
- [9. EDB 宏观经济 — THS_EDB](#9-edb-宏观经济--ths_edb)
- [10. 数据池 — THS_DP (Data Pool)](#10-数据池--ths_dp-data-pool)
- [11. 智能选股 — THS_WCQuery](#11-智能选股--ths_wcquery)
- [12. 公告查询 — THS_ReportQuery](#12-公告查询--ths_reportquery)
- [13. 形态预测 — THS_Special_ShapePredict](#13-形态预测--ths_special_shapepredict)
- [14. 期股联动 — THS_Special_StockLink](#14-期股联动--ths_special_stocklink)
- [15. 基金实时估值 — THS_realTimeValuation](#15-基金实时估值--ths_realtimevaluation)
- [16. 数据量统计 — THS_DataStatistics](#16-数据量统计--ths_datastatistics)
- [17. 日期查询 — THS_DateQuery](#17-日期查询--ths_datequery)
- [18. 日期偏移 — THS_DateOffset](#18-日期偏移--ths_dateoffset)

---

## 1. 通用约定

### 1.1 Base URL

```
https://quantapi.51ifind.com
```

> ⚠️ EDB 接口使用 `http://quantapi.51ifind.com`，其余均为 `https`。

### 1.2 通用请求头

| Header | 值 | 必填 |
|--------|-----|------|
| `Content-Type` | `application/json` | ✅ |
| `access_token` | 通过 `get_access_token` 获取的 token | ✅ |
| `ifindlang` | `cn` (中文) | ✅ |

### 1.3 通用返回结构

所有数据接口返回 JSON，顶层字段统一如下：

| 字段 | 类型 | 描述 |
|------|------|------|
| `errorcode` | int | 错误码。`0` 表示成功，非 0 参考下方异常码 |
| `errmsg` | string | 错误信息（`errorcode != 0` 时有意义） |
| `indicators` | array | 请求的指标列表 |
| `datatype` | string | 数据格式（通常为 `json` / `table`） |
| `perf` | int | 请求处理耗时（ms） |
| `dataVol` | int | 当前请求消耗的数据量 |
| `time` | array | 数据对应的时间列表 |
| `thscode` | array | 标的代码列表 |
| `data` | mixed | 核心数据体（具体结构取决于接口） |

### 1.4 异常码说明

| errorcode | 含义 |
|-----------|------|
| 0 | 成功 |
| -2 | 用户名或密码错误 |
| -201 | 重复登录 |
| 其他 | 参考 `errmsg` 描述 |

### 1.5 证券代码格式

同花顺代码格式：`代码.市场后缀`

| 市场 | 后缀 | 示例 |
|------|------|------|
| 上海 A 股 | `.SH` | `600000.SH` |
| 深圳 A 股 | `.SZ` | `300033.SZ` |
| 香港 | `.HK` | `00700.HK` |
| 美股 | `.O` / `.N` | `AAPL.O` |
| 基金 | `.SH` / `.SZ` | `512880.SH` |

---

## 2. Token 获取与鉴权

### 2.1 获取 access_token

```
POST https://quantapi.51ifind.com/api/v1/get_access_token
```

#### 请求头

| Header | 值 |
|--------|-----|
| `Content-Type` | `application/json` |
| `refresh_token` | 由同花顺提供的 refresh token |

#### 请求体

（无需 body，refresh_token 放在 header 中）

#### 返回结构

```json
{
  "data": {
    "access_token": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
  }
}
```

#### curl 示例

```bash
curl -s -X POST "https://quantapi.51ifind.com/api/v1/get_access_token" \
  -H "Content-Type: application/json" \
  -H "refresh_token: YOUR_REFRESH_TOKEN"
```

### 2.2 关于 refresh_token 的获取

> 需要下载 Windows 版接口包，解压后打开 SuperCommand → 工具 → 刷新 token 查询 获取 refresh_token。

`refresh_token` 是固定的（由同花顺分配），得到后填入配置文件，每次程序启动时调用 `get_access_token` 换取可用的 `access_token` 即可。

### 2.3 日常使用流程

```python
import requests

# 1. 用 refresh_token 获取 access_token
resp = requests.post(
    "https://quantapi.51ifind.com/api/v1/get_access_token",
    headers={"Content-Type": "application/json", "refresh_token": "YOUR_REFRESH_TOKEN"}
)
access_token = resp.json()["data"]["access_token"]

# 2. 构建通用请求头
headers = {
    "Content-Type": "application/json",
    "access_token": access_token,
    "ifindlang": "cn"
}

# 3. 调用数据接口
resp = requests.post(
    "https://quantapi.51ifind.com/api/v1/high_frequency",
    headers=headers,
    json={"codes": "600000.SH", "indicators": "close", ...}
)
```

### 2.4 说明
- 一个 `access_token` 最大支持 20 个 IP 地址
- 超出限制时返回 "Device exceed limit"，刷新 token 可重置绑定
- ⚠️ 同花顺 SDK 的 `THS_iFinDLogin/Logout` **没有 HTTP 接口**，鉴权完全通过此 token 机制

---

## 3. 基础数据 — THS_BD

获取基本面、财务、盈利预测、并购重组等指标数据。

### 2.1 请求

```
POST /api/v1/basic_data_service
```

#### 请求体

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `codes` | string | ✅ | 标的代码，逗号分隔，如 `"300033.SZ,600030.SH"` |
| `indipara` | array | ✅ | 指标数组，每项为 `{ indicator, indiparams }` |

**indipara 每个元素结构：**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `indicator` | string | ✅ | 指标名，如 `"ths_open_price_stock"` |
| `indiparams` | array | ❌ | 该指标的参数数组。有参数时传，无参数时不传或传 `[]` |

#### 完整请求示例

```json
POST https://quantapi.51ifind.com/api/v1/basic_data_service
Content-Type: application/json
access_token: YOUR_TOKEN
ifindlang: cn

{
  "codes": "300033.SZ,600030.SH",
  "indipara": [
    {
      "indicator": "ths_open_price_stock",
      "indiparams": ["20250113", "100", "20250113"]
    },
    {
      "indicator": "ths_stock_short_name_stock"
    },
    {
      "indicator": "ths_close_price_stock",
      "indiparams": ["20250113", "100", "20250113"]
    }
  ]
}
```

### 2.2 返回结构

```json
{
  "errorcode": 0,
  "errmsg": "",
  "indicators": ["ths_open_price_stock", "ths_stock_short_name_stock", "ths_close_price_stock"],
  "datatype": "table",
  "perf": 123,
  "dataVol": 6,
  "time": ["2025-01-13"],
  "thscode": ["300033.SZ", "600030.SH"],
  "data": {
    "300033.SZ": {
      "ths_open_price_stock": [75.0],
      "ths_stock_short_name_stock": ["同花顺"],
      "ths_close_price_stock": [76.5]
    },
    "600030.SH": {
      "ths_open_price_stock": [22.0],
      "ths_stock_short_name_stock": ["中信证券"],
      "ths_close_price_stock": [22.8]
    }
  }
}
```

### 2.3 curl 示例

```bash
curl -s -X POST "https://quantapi.51ifind.com/api/v1/basic_data_service" \
  -H "Content-Type: application/json" \
  -H "access_token: YOUR_TOKEN" \
  -H "ifindlang: cn" \
  -d '{
    "codes": "300033.SZ,600030.SH",
    "indipara": [
      {"indicator": "ths_open_price_stock", "indiparams": ["20250113", "100", "20250113"]},
      {"indicator": "ths_stock_short_name_stock"},
      {"indicator": "ths_close_price_stock", "indiparams": ["20250113", "100", "20250113"]}
    ]
  }'
```

> 💡 `indiparams` 的三个参数通常为 `[日期, 周期, 日期]`，具体语义取决于指标。
> 指标名可通过同花顺 SuperCommand 客户端查询。

---

## 3. 日期序列 — THS_DS

获取历史的日间序列数据，包括行情、基本面、技术指标等。

### 3.1 请求

```
POST /api/v1/date_sequence
```

#### 请求体

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `codes` | string | ✅ | 标的代码，逗号分隔 |
| `startdate` | string | ✅ | 开始日期，格式 `YYYYMMDD` |
| `enddate` | string | ✅ | 结束日期，格式 `YYYYMMDD` |
| `functionpara` | object | ❌ | 输出设置（见下方） |
| `indipara` | array | ✅ | 指标参数数组 |

**functionpara 字段：**

| 字段 | 可选值 | 描述 | 缺省值 |
|------|--------|------|--------|
| `Interval` | `D` / `W` / `M` / `Q` / `S` / `Y` | 时间周期 | `D` |
| `Days` | `Tradedays` / `Alldays` | 交易日还是日历日 | `Tradedays` |
| `Fill` | `Previous` / `Blank` / 具体数值 | 非交易日处理方式 | `Previous` |

**indipara 每个元素：**

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `indicator` | string | ✅ | 指标名 |
| `indiparams` | array | ❌ | 指标参数数组 |

#### 请求示例

```json
POST https://quantapi.51ifind.com/api/v1/date_sequence
Content-Type: application/json
access_token: YOUR_TOKEN
ifindlang: cn

{
  "codes": "AAPL.O",
  "startdate": "20250101",
  "enddate": "20250113",
  "functionpara": {
    "Days": "Alldays",
    "Fill": "-1"
  },
  "indipara": [
    {
      "indicator": "ths_pre_close_uss",
      "indiparams": ["", "100"]
    }
  ]
}
```

### 3.2 返回结构

通用结构（见 1.3），`data` 中按代码和时间组织数据。

### 3.3 curl 示例

```bash
curl -s -X POST "https://quantapi.51ifind.com/api/v1/date_sequence" \
  -H "Content-Type: application/json" \
  -H "access_token: YOUR_TOKEN" \
  -H "ifindlang: cn" \
  -d '{
    "codes": "AAPL.O",
    "startdate": "20250101",
    "enddate": "20250113",
    "functionpara": {
      "Days": "Alldays",
      "Fill": "-1"
    },
    "indipara": [
      {"indicator": "ths_pre_close_uss", "indiparams": ["", "100"]}
    ]
  }'
```

---

## 4. 历史行情 — THS_HQ

获取历史 K 线行情，支持日/周/月/季/年，支持复权、债券报价选项。

### 4.1 请求

```
POST /api/v1/cmd_history_quotation
```

#### 请求体

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `codes` | string | ✅ | 标的代码，逗号分隔 |
| `indicators` | string | ✅ | 指标名，逗号分隔，如 `"open,high,low,close"` |
| `startdate` | string | ✅ | 开始日期，格式 `YYYY-MM-DD` |
| `enddate` | string | ✅ | 结束日期，格式 `YYYY-MM-DD` |
| `functionpara` | object | ❌ | 输出设置（见下方） |

**functionpara 字段：**

| 字段 | 可选值 | 描述 | 缺省值 |
|------|--------|------|--------|
| `Interval` | `D` / `W` / `M` / `Q` / `Y` | 时间周期 | `D` |
| `SampleInterval` | `D` / `W` / `M` / `Q` / `S` / `Y` | 抽样周期 | `D` |
| `Fill` | `Previous` / `Blank` / `Omit` / 具体数值 | 非交易日处理 | `Previous` |
| `CPS` | `1`~`7` | 复权方式（见下表） | `1` |
| `baseDate` | `YYYY-MM-DD` | 复权基点 | `1900-01-01`（上市首日） |
| `PriceType` | `1` / `2` | 债券报价类型（1 全价 / 2 净价） | `1` |
| `Currency` | `MHB` / `GHB` / `RMB` / `YSHB` | 货币类型 | `YSHB` |

**CPS 复权方式对照表：**

| 值 | 含义 |
|----|------|
| `1` | 不复权 |
| `2` | 前复权（分红再投） |
| `3` | 后复权（分红再投） |
| `4` | 全流通前复权（分红再投） |
| `5` | 全流通后复权（分红再投） |
| `6` | 前复权（现金分红） |
| `7` | 后复权（现金分红） |

#### 请求示例

```json
POST https://quantapi.51ifind.com/api/v1/cmd_history_quotation
Content-Type: application/json
access_token: YOUR_TOKEN
ifindlang: cn

{
  "codes": "300033.SZ",
  "indicators": "open,high,low,close",
  "startdate": "2024-01-13",
  "enddate": "2025-01-13",
  "functionpara": {
    "Currency": "MHB",
    "Fill": "Omit"
  }
}
```

### 4.2 返回结构

通用结构（见 1.3）。`Fill: Omit` 时，无交易的日期不返回。

### 4.3 curl 示例

```bash
curl -s -X POST "https://quantapi.51ifind.com/api/v1/cmd_history_quotation" \
  -H "Content-Type: application/json" \
  -H "access_token: YOUR_TOKEN" \
  -H "ifindlang: cn" \
  -d '{
    "codes": "300033.SZ",
    "indicators": "open,high,low,close",
    "startdate": "2024-01-13",
    "enddate": "2025-01-13",
    "functionpara": {
      "Currency": "MHB",
      "Fill": "Omit"
    }
  }'
```

---

## 5. 高频序列 — THS_HF

获取分钟 K 线，支持 1/3/5/10/15/30/60 分钟。

### 5.1 请求

```
POST /api/v1/high_frequency
```

#### 请求体

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `codes` | string | ✅ | 标的代码，逗号分隔 |
| `indicators` | string | ✅ | 指标名，逗号分隔，如 `"open,high,low,close,volume"` |
| `starttime` | string | ✅ | 开始时间，格式 `YYYY-MM-DD HH:mm:ss` |
| `endtime` | string | ✅ | 结束时间，格式 `YYYY-MM-DD HH:mm:ss` |
| `functionpara` | object | ❌ | 输出设置（见下方） |

**functionpara 字段：**

| 字段 | 可选值 | 描述 | 缺省值 |
|------|--------|------|--------|
| `Interval` | `1` / `3` / `5` / `10` / `15` / `30` / `60` | 分钟周期 | `1` |
| `Fill` | `Original` / `Previous` / `Blank` / 具体数值 | 非交易间隔处理 | `Previous` |
| `CPS` | string | 复权方式（见下表） | `no` |
| `baseDate` | `YYYY-MM-DD` | 复权基点 | `1900-01-01` |
| `Timeformat` | `""` / `LocalTime` | 时间戳格式，空=北京时间 | `""` |
| `Limitstart` | `HH:mm:ss` | 每日数据开始时间 | — |
| `Limitend` | `HH:mm:ss` | 每日数据截止时间 | — |

**CPS 复权方式（股票）：**

| 值 | 含义 |
|----|------|
| `no` | 不复权 |
| `forward1` | 前复权（分红方案计算） |
| `backward1` | 后复权（分红方案计算） |
| `forward3` | 前复权（交易所价格计算） |
| `backward3` | 后复权（交易所价格计算） |
| `forward2` | 全流通前复权（分红方案计算） |
| `backward2` | 全流通后复权（分红方案计算） |
| `forward4` | 全流通前复权（交易所价格计算） |
| `backward4` | 全流通后复权（交易所价格计算） |

**CPS 复权方式（其他品种）：**

| 值 | 含义 |
|----|------|
| `no` | 不复权 |
| `forward` | 前复权 |
| `backward` | 后复权 |

#### 请求示例

```json
POST https://quantapi.51ifind.com/api/v1/high_frequency
Content-Type: application/json
access_token: YOUR_TOKEN
ifindlang: cn

{
  "codes": "300033.SZ",
  "indicators": "close",
  "starttime": "2025-01-01 09:15:00",
  "endtime": "2025-01-13 15:15:00",
  "functionpara": {
    "CPS": "forward1",
    "Fill": "Previous",
    "Timeformat": "LocalTime",
    "Limitstart": "09:30:00",
    "Limitend": "09:40:00"
  }
}
```

### 5.2 返回结构

通用结构（见 1.3），`data` 中按标的代码和时间组织分钟数据。

### 5.3 curl 示例（600000.SH 1分钟K线）

```bash
curl -s -X POST "https://quantapi.51ifind.com/api/v1/high_frequency" \
  -H "Content-Type: application/json" \
  -H "access_token: YOUR_TOKEN" \
  -H "ifindlang: cn" \
  -d '{
    "codes": "600000.SH",
    "indicators": "open,high,low,close,volume",
    "starttime": "2026-08-11 09:30:00",
    "endtime": "2026-08-11 15:00:00",
    "functionpara": {
      "Interval": "1",
      "CPS": "forward1",
      "Fill": "Previous",
      "Timeformat": "LocalTime"
    }
  }'
```

---

## 6. 实时行情 — THS_RQ

获取最新一笔实时行情数据。

### 6.1 请求

```
POST /api/v1/real_time_quotation
```

#### 请求体

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `codes` | string | ✅ | 标的代码，逗号分隔 |
| `indicators` | string | ✅ | 指标名，逗号分隔 |

#### 请求示例

```json
POST https://quantapi.51ifind.com/api/v1/real_time_quotation
Content-Type: application/json
access_token: YOUR_TOKEN
ifindlang: cn

{
  "codes": "300033.SZ,600030.SH",
  "indicators": "open,high,low,latest"
}
```

### 6.2 返回结构

通用结构（见 1.3），`data` 中包含最新一笔数据。

### 6.3 curl 示例

```bash
curl -s -X POST "https://quantapi.51ifind.com/api/v1/real_time_quotation" \
  -H "Content-Type: application/json" \
  -H "access_token: YOUR_TOKEN" \
  -H "ifindlang: cn" \
  -d '{
    "codes": "300033.SZ,600030.SH",
    "indicators": "open,high,low,latest"
  }'
```

---

## 7. 日内快照 — THS_SS

获取日内和历史快照及盘口数据。

### 7.1 请求

```
POST /api/v1/snap_shot
```

#### 请求体

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `codes` | string | ✅ | 标的代码，逗号分隔 |
| `indicators` | string | ✅ | 指标名，逗号分隔 |
| `starttime` | string | ✅ | 开始时间，格式 `YYYY-MM-DD HH:mm:ss` |
| `endtime` | string | ✅ | 结束时间，格式 `YYYY-MM-DD HH:mm:ss` |

#### 请求示例

```json
POST https://quantapi.51ifind.com/api/v1/snap_shot
Content-Type: application/json
access_token: YOUR_TOKEN
ifindlang: cn

{
  "codes": "300033.SZ",
  "indicators": "latest",
  "starttime": "2025-01-13 09:15:00",
  "endtime": "2025-01-17 15:15:00"
}
```

### 7.2 返回结构

通用结构（见 1.3）。

### 7.3 curl 示例

```bash
curl -s -X POST "https://quantapi.51ifind.com/api/v1/snap_shot" \
  -H "Content-Type: application/json" \
  -H "access_token: YOUR_TOKEN" \
  -H "ifindlang: cn" \
  -d '{
    "codes": "300033.SZ",
    "indicators": "latest",
    "starttime": "2025-01-13 09:15:00",
    "endtime": "2025-01-17 15:15:00"
  }'
```

---

## 8. EDB 宏观经济 — THS_EDB

获取宏观/行业/区域经济数据。

⚠️ **注意：此接口使用 HTTP 而非 HTTPS**

```
POST http://quantapi.51ifind.com/api/v1/edb_service
```

#### 请求体

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `indicators` | string | ✅ | 宏观指标 ID，逗号分隔，如 `"M001620253,M002826938"` |
| `startdate` | string | ✅ | 开始日期，格式 `YYYY-MM-DD` |
| `enddate` | string | ✅ | 结束日期，格式 `YYYY-MM-DD` |

#### 请求示例

```json
POST http://quantapi.51ifind.com/api/v1/edb_service
Content-Type: application/json
access_token: YOUR_TOKEN
ifindlang: cn

{
  "indicators": "M001620253,M002826938",
  "startdate": "2024-01-18",
  "enddate": "2025-01-18"
}
```

### 8.1 curl 示例

```bash
curl -s -X POST "http://quantapi.51ifind.com/api/v1/edb_service" \
  -H "Content-Type: application/json" \
  -H "access_token: YOUR_TOKEN" \
  -H "ifindlang: cn" \
  -d '{
    "indicators": "M001620253,M002826938",
    "startdate": "2024-01-18",
    "enddate": "2025-01-18"
  }'
```

---

## 10. 数据池 — THS_DP (Data Pool)

获取板块成分股、股票列表等数据。相当于 SDK 中的 `THS_DP` 函数。

### 10.1 请求

```
POST /api/v1/data_pool
```

#### 请求体

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `reportname` | string | ✅ | 报告名称，如 `"p03425"`（全A股列表） |
| `functionpara` | object | ✅ | 参数（日期、板块代码等） |
| `outputpara` | string | ❌ | 输出列控制，逗号分隔 |

**functionpara 字段：**

| 字段 | 必填 | 描述 |
|------|------|------|
| `date` | ✅ | 日期，格式 `YYYYMMDD` |
| `blockname` | ✅ | 板块代码，如 `001005010`（全A股） |
| `iv_type` | ✅ | 类型，如 `"allcontract"` |

#### 板块代码（同 01-因子列表.md）

| 板块 | 代码 |
|------|------|
| 全A股 | `001005010` |
| 上证主板 | `001005001` |
| 深证主板 | `001005002` |
| 创业板 | `001005003` |
| 科创板 | `001005004` |
| 北交所 | `001005005` |
| 上证50 | `001005260` |
| 沪深300 | `001005261` |
| 中证500 | `001005262` |
| 中证1000 | `001005263` |

#### 请求示例

```json
POST https://quantapi.51ifind.com/api/v1/data_pool
Content-Type: application/json
access_token: YOUR_TOKEN
ifindlang: cn

{
  "reportname": "p03425",
  "functionpara": {
    "date": "20260101",
    "blockname": "001005010",
    "iv_type": "allcontract"
  },
  "outputpara": "p03291_f001,p03291_f002,p03291_f003,p03291_f004"
}
```

### 10.2 curl 示例

```bash
curl -s -X POST "https://quantapi.51ifind.com/api/v1/data_pool" \
  -H "Content-Type: application/json" \
  -H "access_token: YOUR_TOKEN" \
  -H "ifindlang: cn" \
  -d '{
    "reportname": "p03425",
    "functionpara": {
      "date": "20260101",
      "blockname": "001005010",
      "iv_type": "allcontract"
    },
    "outputpara": "p03291_f001,p03291_f002,p03291_f003,p03291_f004"
  }'
```

---

## 11. 智能选股 — THS_WCQuery

通过问财语义识别进行条件选股。

### 9.1 请求

```
POST /api/v1/smart_stock_picking
```

#### 请求体

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `searchstring` | string | ✅ | 问财搜索条件，如 `"低市盈率"` |
| `searchtype` | string | ✅ | 搜索范围，如 `"stock"` |

#### 请求示例

```json
POST https://quantapi.51ifind.com/api/v1/smart_stock_picking
Content-Type: application/json
access_token: YOUR_TOKEN
ifindlang: cn

{
  "searchstring": "低市盈率",
  "searchtype": "stock"
}
```

### 9.2 返回结构

通用结构（见 1.3），`data` 包含符合条件的股票列表。

### 9.3 curl 示例

```bash
curl -s -X POST "https://quantapi.51ifind.com/api/v1/smart_stock_picking" \
  -H "Content-Type: application/json" \
  -H "access_token: YOUR_TOKEN" \
  -H "ifindlang: cn" \
  -d '{
    "searchstring": "低市盈率",
    "searchtype": "stock"
  }'
```

---

## 12. 公告查询 — THS_ReportQuery

查询股票公告信息。

### 10.1 请求

```
POST /api/v1/report_query
```

#### 请求体

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `codes` | string | ✅ | 标的代码，逗号分隔 |
| `functionpara` | object | ❌ | 查询参数（见下方） |
| `beginrDate` | string | ❌ | 公告开始日期，格式 `YYYY-MM-DD` |
| `endrDate` | string | ❌ | 公告结束日期，格式 `YYYY-MM-DD` |
| `outputpara` | string | ❌ | 输出列控制，如 `"reportDate:Y,thscode:Y"` |

**functionpara 字段：**

| 字段 | 可选值 | 描述 |
|------|--------|------|
| `mode` | `allAStock` / `allBond` / `allFund` / `allHKStock` | 板块提取模式（不传则按 codes） |
| `begincTime` | `YYYY-MM-DD` | 发布开始时间 |
| `endcTime` | `YYYY-MM-DD` | 发布截止时间 |
| `reportType` | string | 公告类型编号（如 `901`），推荐用 SuperCommand 生成 |
| `keyword` | string | 标题关键词过滤 |

**outputpara 可选列：**

| 列名 | 含义 |
|------|------|
| `reportDate` | 公告日期 |
| `thscode` | 同花顺代码 |
| `secName` | 证券简称 |
| `ctime` | 发布时间 |
| `reportTitle` | 公告标题 |
| `pdfURL` | 公告 PDF 链接 |
| `seq` | 唯一标识号 |

#### 请求示例

```json
POST https://quantapi.51ifind.com/api/v1/report_query
Content-Type: application/json
access_token: YOUR_TOKEN
ifindlang: cn

{
  "codes": "300033.SZ",
  "functionpara": {
    "reportType": "901"
  },
  "beginrDate": "2024-01-18",
  "endrDate": "2025-01-18",
  "outputpara": "reportDate:Y,thscode:Y,secName:Y,ctime:Y,reportTitle:Y,pdfURL:Y,seq:Y"
}
```

### 10.2 返回结构

通用结构（见 1.3）。

### 10.3 curl 示例

```bash
curl -s -X POST "https://quantapi.51ifind.com/api/v1/report_query" \
  -H "Content-Type: application/json" \
  -H "access_token: YOUR_TOKEN" \
  -H "ifindlang: cn" \
  -d '{
    "codes": "300033.SZ",
    "functionpara": {
      "reportType": "901"
    },
    "beginrDate": "2024-01-18",
    "endrDate": "2025-01-18",
    "outputpara": "reportDate:Y,thscode:Y,secName:Y,ctime:Y,reportTitle:Y,pdfURL:Y,seq:Y"
  }'
```

---

## 13. 形态预测 — THS_Special_ShapePredict

通过历史 K 线形态匹配相似股票。

⚠️ **此接口暂无 HTTP 版示例**，仅 Python 示例可参考参数结构。

### Python 原型参考

```python
THS_Special_ShapePredict(
    '600000.SH',
    'range=SHSE_A_stock;SZSE_A_stock;SHSE_B_stock,match_level=90.0,match_period=20,predict_period=35',
    '2019-07-19',
    '2019-12-01'
)
```

### 参数说明

| 参数 | 描述 |
|------|------|
| `range` | 匹配市场范围，分号分隔 |
| `match_level` | 匹配度阈值（0~100） |
| `match_period` | 匹配周期（天数） |
| `predict_period` | 预测周期（天数） |

---

## 14. 期股联动 — THS_Special_StockLink

通过期货品种名查询关联股票。

⚠️ **此接口暂无 HTTP 版示例**，仅 Python 示例可参考。

### Python 原型参考

```python
THS_Special_StockLink('商品焦炭', 'thscode;thsname')
```

| 参数 | 描述 |
|------|------|
| 第一个参数 | 期货品种中文名 |
| 第二个参数 | 需要的字段，分号分隔 |

---

## 15. 基金实时估值 — THS_realTimeValuation

获取基金实时估值数据。

### 13.1 请求

```
POST /api/v1/fund_valuation
```

#### 请求体

| 字段 | 类型 | 必填 | 描述 |
|------|------|------|------|
| `codes` | string | ✅ | 基金代码，逗号分隔 |
| `functionpara` | object | ✅ | 参数（见下方） |
| `outputpara` | string | ❌ | 输出列控制 |

**functionpara 字段：**

| 字段 | 描述 |
|------|------|
| `onlyLastest` | `"0"` 返回全量分钟数据，`"1"` 仅返回最新 |
| `beginTime` | 开始时间，格式 `YYYY-MM-DD HH:mm:ss` |
| `endTime` | 结束时间，格式 `YYYY-MM-DD HH:mm:ss` |

**outputpara 可选列：**

| 列名 | 含义 |
|------|------|
| `changeRatioValuation` | 估值涨跌幅 |
| `realTimeValuation` | 实时估值 |
| `Deviation30TDays` | 30日偏离度 |

#### 请求示例

```json
POST https://quantapi.51ifind.com/api/v1/fund_valuation
Content-Type: application/json
access_token: YOUR_TOKEN
ifindlang: cn

{
  "codes": "512880.SH",
  "functionpara": {
    "onlyLastest": "0",
    "beginTime": "2024-12-06 09:15:00",
    "endTime": "2024-12-06 15:15:00"
  },
  "outputpara": "realTimeValuation:Y"
}
```

### 13.2 返回结构

通用结构（见 1.3）。

### 13.3 curl 示例

```bash
curl -s -X POST "https://quantapi.51ifind.com/api/v1/fund_valuation" \
  -H "Content-Type: application/json" \
  -H "access_token: YOUR_TOKEN" \
  -H "ifindlang: cn" \
  -d '{
    "codes": "512880.SH",
    "functionpara": {
      "onlyLastest": "0",
      "beginTime": "2024-12-06 09:15:00",
      "endTime": "2024-12-06 15:15:00"
    },
    "outputpara": "realTimeValuation:Y"
  }'
```

---

## 16. 数据量统计 — THS_DataStatistics

查询账号的数据量使用统计。

⚠️ **此接口暂未公布 HTTP 版本**，仅提供 Python 命令方式：

```python
THS_DataStatistics()
```

返回高频、基础、EDB 三类数据的使用量。

---

## 17. 日期查询 — THS_DateQuery

按交易所查询交易日历。

⚠️ **此接口暂未公布 HTTP 版本**，仅 Python 调用方式可参考参数结构。

### Python 原型

```python
THS_DateQuery('SSE', 'dateType:0,period:D,dateFormat:0', '2019-06-01', '2019-06-06')
```

**交易所（exchange）枚举：**

| 值 | 交易所 |
|----|--------|
| `SSE` | 上交所 |
| `SZSE` | 深交所 |
| `HKEX` | 港交所 |
| `YJZHQ` | 银行间债券市场 |
| `NYSEARCA` | NYSE Arca |
| `NASDAQ` | 美国 NASDAQ |
| `NYSE` | 纽约证券交易所 |
| `AMEX` | 美国证券交易所 |
| `CZCE` | 郑州商品交易所 |
| `SHFE` | 上海期货交易所 |
| `DCE` | 大连商品交易所 |
| `BMD` | 马来西亚衍生品交易所 |
| `NYBOT` | 纽约期货交易所 |
| `COMEX` | 纽约商品交易所 |
| `NYMEX` | 纽约商品期货交易所 |
| `CBOT` | 芝加哥商品交易所 |
| `ICE` | 洲际交易所 |

**parameters 字段说明：**

| 参数 | 可选值 | 描述 | 缺省值 |
|------|--------|------|--------|
| `dateType` | `0`（交易日） / `1`（日历日） | 日期类型 | `0` |
| `period` | `D` / `W` / `M` / `Q` / `S` / `Y` | 时间周期 | `D` |
| `dateFormat` | `0`（YYYY-MM-DD） / `1`（YYYY/MM/DD） / `2`（YYYYMMDD） | 日期输出格式 | `0` |

---

## 18. 日期偏移 — THS_DateOffset

按偏移量获取指定日期前后的交易日。

⚠️ **此接口暂未公布 HTTP 版本**，仅 Python 调用方式可参考参数结构。

### Python 原型

```python
THS_DateOffset('SSE', 'dateType:0,period:D,offset:-5,dateFormat:0', '2019-06-06')
```

**parameters 中额外字段：**

| 参数 | 描述 | 缺省值 |
|------|------|--------|
| `offset` | 偏移天数，正数=向前，负数=向后 | `1` |

其余字段（`exchange`、`dateType`、`period`、`dateFormat`）与 THS_DateQuery 一致。

---

## 附录：接口速查表

| # | 功能 | URL | HTTP | 备注 |
|---|------|-----|------|------|
| 1 | 获取 Token | `POST /api/v1/get_access_token` | ✅ | 需 refresh_token |
| 2 | 基础数据 | `POST /api/v1/basic_data_service` | ✅ | 估值/财务/基本面 |
| 3 | 日期序列 | `POST /api/v1/date_sequence` | ✅ | 日间序列 |
| 4 | 历史行情 | `POST /api/v1/cmd_history_quotation` | ✅ | OHLCV日线 |
| 5 | 高频序列 | `POST /api/v1/high_frequency` | ✅ | 分钟K线 |
| 6 | 实时行情 | `POST /api/v1/real_time_quotation` | ✅ | 最新行情 |
| 7 | 日内快照 | `POST /api/v1/snap_shot` | ✅ | 盘口数据 |
| 8 | EDB 宏观 | `POST http://.../api/v1/edb_service` | ✅ | 经济数据 |
| 9 | 数据池 | `POST /api/v1/data_pool` | ✅ | 板块成分/股票池 |
| 10 | 智能选股 | `POST /api/v1/smart_stock_picking` | ✅ | 问财语义 |
| 11 | 公告查询 | `POST /api/v1/report_query` | ✅ | 公告PDF |
| 12 | 基金估值 | `POST /api/v1/fund_valuation` | ✅ | ETF实时估值 |
| 13 | 形态预测 | 暂无 HTTP | ❌ | `THS_Special('shape_predict', ...)` |
| 14 | 期股联动 | 暂无 HTTP | ❌ | `THS_Special('stock_link', ...)` |
| 15 | 数据量统计 | 暂无 HTTP | ❌ | — |
| 16 | 日期查询 | 暂无 HTTP | ❌ | — |
| 17 | 日期偏移 | 暂无 HTTP | ❌ | — |

---

*文档版本：v1.0 · 基于同花顺 QuantAPI 官方手册整理*
*文件位置：`IFIND_DATA/docs/08-同花顺QuantAPI接口文档.md`*