# iFinD QuantAPI 数据字典

> 完整记录同花顺 iFinD QuantAPI（HTTP版）所有可获取的数据维度。
> 提数据需求前先查此表，确认"能不能拉、用什么接口、指标代码是什么"。
>
> 版本: v1.0 · 2026-08-26

---

## 目录

- [接口一览](#接口一览)
- [A. THS_HQ — 历史行情](#a-ths_hq--历史行情)
- [B. THS_BD — 基础数据（估值/财务/基本面）](#b-ths_bd--基础数据估值财务基本面)
- [C. THS_HF — 高频序列（分钟K线）](#c-ths_hf--高频序列分钟k线)
- [D. THS_RQ — 实时行情](#d-ths_rq--实时行情)
- [E. THS_SS — 日内快照](#e-ths_ss--日内快照)
- [F. THS_DP — 数据池（板块成分/股票池）](#f-ths_dp--数据池板块成分股票池)
- [G. THS_EDB — 宏观经济](#g-ths_edb--宏观经济)
- [H. THS_DS — 日期序列（日间序列）](#h-ths_ds--日期序列日间序列)
- [I. THS_WCQuery — 智能选股（问财）](#i-ths_wcquery--智能选股问财)
- [J. THS_ReportQuery — 公告查询](#j-ths_reportquery--公告查询)
- [K. THS_realTimeValuation — 基金实时估值](#k-ths_realtimevaluation--基金实时估值)
- [附录. 需本地计算的衍生数据](#附录-需本地计算的衍生数据)

---

## 接口一览

| # | 接口 | HTTP URL | 用途 | 数据维度 | HTTP状态 |
|---|------|---------|------|---------|---------|
| 1 | **THS_HQ** | `POST /api/v1/cmd_history_quotation` | 日/周/月/季/年K线行情 | 行情类 | ✅ |
| 2 | **THS_BD** | `POST /api/v1/basic_data_service` | 基本面/估值/财务/股本/行业 | 基本面类 | ✅ |
| 3 | **THS_HF** | `POST /api/v1/high_frequency` | 1/3/5/10/15/30/60分钟K线 | 行情类 | ✅ |
| 4 | **THS_RQ** | `POST /api/v1/real_time_quotation` | 最新一笔实时行情 | 实时类 | ✅ |
| 5 | **THS_SS** | `POST /api/v1/snap_shot` | 日内/历史快照及盘口 | 实时类 | ✅ |
| 6 | **THS_DP** | `POST /api/v1/data_pool` | 板块成分/股票池/基金列表 | 标的类 | ✅ |
| 7 | **THS_EDB** | `POST http://.../api/v1/edb_service` | 宏观/行业/区域经济数据 | 宏观类 | ✅ |
| 8 | **THS_DS** | `POST /api/v1/date_sequence` | 日间序列（行/估/指） | 基本面类 | ✅ |
| 9 | **THS_WCQuery** | `POST /api/v1/smart_stock_picking` | 问财自然语言选股 | 选股类 | ✅ |
| 10 | **THS_ReportQuery** | `POST /api/v1/report_query` | 公告查询（PDF链接） | 公告类 | ✅ |
| 11 | **THS_realTimeValuation** | `POST /api/v1/fund_valuation` | 基金实时估值 | 基金类 | ✅ |
| — | get_access_token | `POST /api/v1/get_access_token` | 获取鉴权token | 基础 | ✅ |
| — | THS_Special_ShapePredict | 暂无HTTP | 形态预测 | — | ❌ |
| — | THS_Special_StockLink | 暂无HTTP | 期股联动 | — | ❌ |
| — | THS_DateQuery | 暂无HTTP | 交易日历 | — | ❌ |
| — | THS_DateOffset | 暂无HTTP | 日期偏移 | — | ❌ |
| — | THS_DataStatistics | 暂无HTTP | 数据量统计 | — | ❌ |

---

## A. THS_HQ — 历史行情

获取日/周/月/季/年K线行情，支持复权和债券报价。

### 接口信息

| 项目 | 内容 |
|------|------|
| HTTP URL | `POST https://quantapi.51ifind.com/api/v1/cmd_history_quotation` |
| 请求头 | `Content-Type: application/json` + `access_token` + `ifindlang: cn` |
| 适用品种 | 股票/基金/指数/债券/期货 |
| 周期 | `D`(日) / `W`(周) / `M`(月) / `Q`(季) / `Y`(年) |

### 请求参数

| 字段 | 必填 | 说明 |
|------|------|------|
| `codes` | ✅ | 标的代码，逗号分隔，如 `"300033.SZ,600030.SH"` |
| `indicators` | ✅ | 指标名，**逗号分隔** |
| `startdate` | ✅ | `YYYY-MM-DD` |
| `enddate` | ✅ | `YYYY-MM-DD` |
| `functionpara.Interval` | ❌ | `D`/`W`/`M`/`Q`/`Y`，默认`D` |
| `functionpara.CPS` | ❌ | 复权方式: `1`(不) / `2`(前,分红再投) / `3`(后,分红再投) / `4`~`7` |
| `functionpara.Fill` | ❌ | `Previous`/`Blank`/`Omit`，默认`Previous` |
| `functionpara.Currency` | ❌ | `MHB`(美元)/`GHB`(港元)/`RMB`(人民币)/`YSHB`(原始货币) |

### 可获取的指标

| 序号 | 指标名 | 含义 | 备注 |
|------|--------|------|------|
| 1 | `open` | 开盘价 | |
| 2 | `high` | 最高价 | |
| 3 | `low` | 最低价 | |
| 4 | `close` | 收盘价 | |
| 5 | `pre_close` | 前收盘价 | |
| 6 | `volume` | 成交量（股） | |
| 7 | `amount` | 成交额（元） | |
| 8 | `changeRatio` | 涨跌幅（%） | |
| 9 | `turnoverRatio` | 换手率（%） | |

> 💡 **推荐用 THS_HQ 而非 THS_BD 拿日线行情**：一次请求拿到全部9个字段，比THS_BD逐个指标请求效率高得多。

---

## B. THS_BD — 基础数据（估值/财务/基本面）

最核心的接口，覆盖估值、财务、股本、行业、PIT等基本面数据。

### 接口信息

| 项目 | 内容 |
|------|------|
| HTTP URL | `POST https://quantapi.51ifind.com/api/v1/basic_data_service` |
| 请求方式 | 指标名通过 `indipara` 数组传入（非逗号拼接） |

### 请求参数

| 字段 | 必填 | 说明 |
|------|------|------|
| `codes` | ✅ | 标的代码，逗号分隔 |
| `indipara` | ✅ | 指标数组，每项 `{ indicator, indiparams? }` |

---

### B1. 日线行情（备选）

> ⚠️ **推荐用 THS_HQ** 拿日线，这里只列 THS_BD 也支持的指标名，供需要混在同一个 THS_BD 请求里使用。

| 序号 | 指标代码 | 含义 | 参数格式 | 频率 | 实测 |
|------|---------|------|---------|------|------|
| 1 | `ths_open_price_stock` | 开盘价 | `[日期, 100, 日期]` | 日 | ✅ |
| 2 | `ths_high_price_stock` | 最高价 | `[日期, 100, 日期]` | 日 | ✅ |
| 3 | `ths_low_price_stock` | 最低价 | `[日期, 100, 日期]` | 日 | ✅ |
| 4 | `ths_close_price_stock` | 收盘价 | `[日期, 100, 日期]` | 日 | ✅ |
| 5 | `ths_pre_close_price_stock` | 前收盘价 | `[日期, 100, 日期]` | 日 | ✅ |
| 6 | `ths_vol_stock` | 成交量 | `[日期, 100, 日期]` | 日 | ✅ |
| 7 | `ths_amt_stock` | 成交额 | `[日期, 100, 日期]` | 日 | ✅ |
| 8 | `ths_chg_ratio_stock` | 涨跌幅(%) | `[日期, 100, 日期]` | 日 | ✅ |
| 9 | `ths_turnover_ratio_stock` | 换手率(%) | `[日期, 100, 日期]` | 日 | ✅ |

> 复权通过 `indiparams[1]` 控制: `100`=不复权, `101`=前复权, `102`=后复权

---

### B2. 估值因子

| 序号 | 指标代码 | 含义 | 参数 | 频率 | 实测 |
|------|---------|------|------|------|------|
| 1 | `ths_pe_stock` | 市盈率(静态) | `[日期, 100, 日期]` | 日 | ✅ |
| 2 | `ths_pe_ttm_stock` | 市盈率(TTM) | `[日期, 100, 日期]` | 日 | ✅ |
| 3 | `ths_pb_stock` | 市净率 | `[日期, 100, 日期]` | 日 | ✅ |
| 4 | `ths_ps_stock` | 市销率 | `[日期, 100, 日期]` | 日 | ✅ |
| 5 | `ths_ps_ttm_stock` | 市销率(TTM) | `[日期, 100, 日期]` | 日 | ✅ |
| 6 | `ths_pcf_stock` | 市现率 | `[日期, 100, 日期]` | 日 | ✅ |
| 7 | `ths_market_value_stock` | 总市值（元） | `[日期, 100, 日期]` | 日 | ✅ |
| 8 | `ths_float_mv_stock` | 流通市值（元） | `[日期, 100, 日期]` | 日 | ✅ |
| 9 | `ths_dividend_yield_stock` | 股息率(%) | `[日期, 100, 日期]` | 日 | ✅ |
| 10 | `ths_dividend_rate_stock` | 股息 | `[日期, 100, 日期]` | 日 | ✅ |

---

### B3. 盈利能力（财务）

| 序号 | 指标代码 | 含义 | 参数 | 频率 | 实测 |
|------|---------|------|------|------|------|
| 1 | `ths_roe_stock` | 净资产收益率(ROE,%) | `[日期, 100, 日期]` | 季 | ✅ |
| 2 | `ths_roa_stock` | 总资产收益率(ROA,%) | `[日期, 100, 日期]` | 季 | ✅ |
| 3 | `ths_gross_profit_margin_stock` | 毛利率(%) | `[日期, 100, 日期]` | 季 | ✅ |
| 4 | `ths_net_profit_margin_stock` | 净利率(%) | `[日期, 100, 日期]` | 季 | ✅ |
| 5 | `ths_eps_stock` | 每股收益(EPS) | `[日期, 100, 日期]` | 季 | ✅ |
| 6 | `ths_np_stock` | 归母净利润（元） | `[日期, 100, 日期]` | 季 | ✅ |

### B4. 成长能力（财务）

| 序号 | 指标代码 | 含义 | 参数 | 频率 | 实测 |
|------|---------|------|------|------|------|
| 1 | `ths_or_yoy_stock` | 营收同比增长(%) | `[日期, 100, 日期]` | 季 | ✅ |
| 2 | `ths_np_yoy_stock` | 净利润同比增长(%) | `[日期, 100, 日期]` | 季 | ✅ |
| 3 | `ths_eps_yoy_stock` | EPS同比增长(%) | `[日期, 100, 日期]` | 季 | ✅ |
| 4 | `ths_yoy_revenue_stock` | 营收同比(原始指标) | `[日期, 100, 日期]` | 季 | ✅ |
| 5 | `ths_yoy_net_profit_stock` | 净利同比(原始指标) | `[日期, 100, 日期]` | 季 | ✅ |

### B5. 偿债能力（财务）

| 序号 | 指标代码 | 含义 | 参数 | 频率 | 实测 |
|------|---------|------|------|------|------|
| 1 | `ths_asset_liability_ratio_stock` | 资产负债率(%) | `[日期, 100, 日期]` | 季 | ✅ |
| 2 | `ths_current_ratio_stock` | 流动比率 | `[日期, 100, 日期]` | 季 | ✅ |
| 3 | `ths_quick_ratio_stock` | 速动比率 | `[日期, 100, 日期]` | 季 | ✅ |

### B6. 运营效率（财务）

| 序号 | 指标代码 | 含义 | 参数 | 频率 | 实测 |
|------|---------|------|------|------|------|
| 1 | `ths_asset_turnover_stock` | 总资产周转率 | `[日期, 100, 日期]` | 季 | ✅ |
| 2 | `ths_inventory_turnover_stock` | 存货周转率 | `[日期, 100, 日期]` | 季 | ✅ |
| 3 | `ths_receivable_turnover_stock` | 应收账款周转率 | `[日期, 100, 日期]` | 季 | ✅ |

### B7. 每股指标

| 序号 | 指标代码 | 含义 | 参数 | 频率 | 实测 |
|------|---------|------|------|------|------|
| 1 | `ths_bps_stock` | 每股净资产(BPS) | `[日期, 100, 日期]` | 季 | ✅ |
| 2 | `ths_ocfps_stock` | 每股经营现金流(OCFPS) | `[日期, 100, 日期]` | 季 | ✅ |
| 3 | `ths_retained_earnings_ps_stock` | 每股未分配利润 | `[日期, 100, 日期]` | 季 | ✅ |

### B8. 股本与股东

| 序号 | 指标代码 | 含义 | 参数 | 频率 | 实测 |
|------|---------|------|------|------|------|
| 1 | `ths_total_shares_stock` | 总股本（股） | `[日期, 100, 日期]` | 不定期 | ✅ |
| 2 | `ths_float_ashare_stock` | 流通A股（股） | `[日期, 100, 日期]` | 不定期 | ✅ |
| 3 | `ths_shareholder_num_stock` | 股东户数 | `[日期, 100, 日期]` | 季 | ✅ |
| 4 | `ths_avg_shares_stock` | 人均持股数 | `[日期, 100, 日期]` | 季 | ✅ |

### B9. 资金面

| 序号 | 指标代码 | 含义 | 参数 | 频率 | 实测 |
|------|---------|------|------|------|------|
| 1 | `ths_margin_trading_stock` | 融资融券余额 | `[日期, 100, 日期]` | 日 | ✅ |

### B10. 行业分类

| 序号 | 指标代码 | 含义 | 参数 | 频率 | 实测 |
|------|---------|------|------|------|------|
| 1 | `ths_the_sw_industry_stock` | 申万一级行业 | 无参数 | 不定期 | ✅ |
| 2 | `ths_the_csrc_industry_stock` | 证监会行业 | 无参数 | 不定期 | ✅ |
| 3 | `ths_stock_short_name_stock` | 股票简称 | 无参数 | — | ✅ |

### B11. PIT（时点数据，防未来数据回测）

> PIT = Point In Time，回测时使用到财报数据时必须用PIT版本，否则会用到"未来才能知道的数据"。
> `indiparams: ["计算日期", "报告期(YYYYMMDD)", "1(累计)/2(单季)"`

| 序号 | 指标代码 | 含义 | 参数示例 | 实测 |
|------|---------|------|---------|------|
| 1 | `ths_np_atoopc_pit_stock` | 归母净利润(PIT) | `["2024-05-15", "20240331", "1"]` | ✅ |
| 2 | `ths_or_pit_stock` | 营业收入(PIT) | 同上 | ✅ |
| 3 | `ths_roe_pit_stock` | ROE(PIT) | 同上 | ✅ |
| 4 | `ths_regular_report_actual_dd_stock` | 财报实际披露日 | 无参数 | ✅ |

---

## C. THS_HF — 高频序列（分钟K线）

获取1/3/5/10/15/30/60分钟K线。

### 接口信息

| 项目 | 内容 |
|------|------|
| HTTP URL | `POST https://quantapi.51ifind.com/api/v1/high_frequency` |
| 时间格式 | `YYYY-MM-DD HH:mm:ss` |

### 主要参数

| 字段 | 必填 | 说明 |
|------|------|------|
| `codes` | ✅ | 标的代码 |
| `indicators` | ✅ | 指标名，逗号分隔 |
| `starttime` | ✅ | 开始时间 |
| `endtime` | ✅ | 结束时间 |
| `functionpara.Interval` | ❌ | `1`/`3`/`5`/`10`/`15`/`30`/`60` 分钟 |
| `functionpara.CPS` | ❌ | `no`(不复权) / `forward1`(前复权) / `backward1`(后复权) |
| `functionpara.Limitstart` | ❌ | 每日数据开始，如 `09:30:00` |
| `functionpara.Limitend` | ❌ | 每日数据截止，如 `15:00:00` |

### 可获取的指标

| 序号 | 指标名 | 含义 | 备注 |
|------|--------|------|------|
| 1 | `open` | 开盘价 | |
| 2 | `high` | 最高价 | |
| 3 | `low` | 最低价 | |
| 4 | `close` | 收盘价 | |
| 5 | `volume` | 成交量 | |
| 6 | `amount` | 成交额 | |

---

## D. THS_RQ — 实时行情

获取最新一笔实时行情。

### 接口信息

| 项目 | 内容 |
|------|------|
| HTTP URL | `POST https://quantapi.51ifind.com/api/v1/real_time_quotation` |

### 可获取的指标（典型）

| 序号 | 指标名 | 含义 | 备注 |
|------|--------|------|------|
| 1 | `open` | 今日开盘价 | |
| 2 | `high` | 今日最高价 | |
| 3 | `low` | 今日最低价 | |
| 4 | `latest` | 最新价 | |
| 5 | `pre_close` | 前收盘价 | |
| 6 | `volume` | 成交量 | |
| 7 | `amount` | 成交额 | |
| 8 | `change` | 涨跌额 | |
| 9 | `changeRatio` | 涨跌幅(%) | |
| 10 | `turnoverRatio` | 换手率 | |
| 11 | `totalShares` | 总股本 | |
| 12 | `floatShares` | 流通股本 | |
| 13 | `marketValue` | 总市值 | |
| 14 | `pe` | 市盈率 | |

> THS_RQ的具体指标名可能比上述更多，建议通过 SuperCommand 查询完整清单。

---

## E. THS_SS — 日内快照

获取日内/历史快照和盘口数据。

### 接口信息

| 项目 | 内容 |
|------|------|
| HTTP URL | `POST https://quantapi.51ifind.com/api/v1/snap_shot` |

### 可获取的指标

| 序号 | 指标名 | 含义 | 备注 |
|------|--------|------|------|
| 1 | `latest` | 最新价 | |
| 2 | `bid1` ~ `bid5` | 买一~买五价 | 盘口 |
| 3 | `ask1` ~ `ask5` | 卖一~卖五价 | 盘口 |
| 4 | `bidsize1` ~ `bidsize5` | 买一~买五量 | 盘口 |
| 5 | `asksize1` ~ `asksize5` | 卖一~卖五量 | 盘口 |

---

## F. THS_DP — 数据池（板块成分/股票池）

获取板块成分股、全A股列表、基金列表等。

### 接口信息

| 项目 | 内容 |
|------|------|
| HTTP URL | `POST https://quantapi.51ifind.com/api/v1/data_pool` |

### 已知板块代码

| 板块 | 代码 | 实测 | 成分数 |
|------|------|------|--------|
| **全A股** | `001005010` | ✅ | ~5,542只 |
| 上证主板 | `001005001` | — | — |
| 深证主板 | `001005002` | — | — |
| 创业板 | `001005003` | ❌(-4001) | — |
| 科创板 | `001005004` | ❌(-4001) | — |
| 北交所 | `001005005` | — | — |
| **上证50** | `001005260` | ✅ | 50只 |
| **沪深300** | `001005290` | ✅ | 300只 |
| **中证500** | `001005270` | ✅ | 500只 |
| 中证1000 | `001005263` | — | — |

> 部分板块代码无法通过HTTP成功调用（返回-4001），可能需使用SDK版THS_DP。

### 已知的reportname

| reportname | 用途 | 说明 |
|-----------|------|------|
| `p03425` | 全A股列表 | 已验证可用 |
| `p03291` | 含代码、名称、行业等 | 常见输出参数前缀 |

---

## G. THS_EDB — 宏观经济

获取宏观/行业/区域经济数据。

### 接口信息

| 项目 | 内容 |
|------|------|
| HTTP URL | `POST http://quantapi.51ifind.com/api/v1/edb_service` |
| ⚠️ | **此接口使用HTTP而非HTTPS** |

### 请求参数

| 字段 | 必填 | 说明 |
|------|------|------|
| `indicators` | ✅ | EDB指标ID，逗号分隔，如 `"M001620253,M002826938"` |
| `startdate` | ✅ | `YYYY-MM-DD` |
| `enddate` | ✅ | `YYYY-MM-DD` |

### 已知EDB指标示例

| EDB指标ID | 含义 | 说明 |
|----------|------|------|
| `M001620253` | GDP:人均 | 宏观 |
| `M002826938` | GDP:同比 | 宏观 |
| `M0000638` | CPI:当月同比 | 通胀 |
| `M0000642` | PPI:全部工业品 | 工业 |

> ⚠️ EDB指标ID需要通过 iFinD 终端 → 经济数据库 → 查询获取。
> 未列出的指标可通过 SuperCommand 的 "工具→EDB指标ID查询" 查找。

---

## H. THS_DS — 日期序列（日间序列）

获取历史日间序列数据，包括行情、基本面、技术指标。

### 接口信息

| 项目 | 内容 |
|------|------|
| HTTP URL | `POST https://quantapi.51ifind.com/api/v1/date_sequence` |

> 支持按时间周期（日/周/月/季/年）返回序列，可设置非交易日处理方式。

---

## I. THS_WCQuery — 智能选股（问财）

通过语义识别进行条件选股。

### 接口信息

| 项目 | 内容 |
|------|------|
| HTTP URL | `POST https://quantapi.51ifind.com/api/v1/smart_stock_picking` |
| 请求 | `{ searchstring: "...", searchtype: "stock" }` |

### 典型使用场景

| searchstring | 用途 | 备注 |
|-------------|------|------|
| `"低市盈率"` | 低PE选股 | 定性结果 |
| `"主力资金净流入"` | 资金流向选股 | 无法直接获取数值 |
| `"超大单净流入"` | 超大单流向 | 同上 |
| `"大单净流入"` | 大单流向 | 同上 |

> ⚠️ THS_WCQuery 返回的是**符合条件的股票列表**，而非数值指标。
> 资金流向等值无法直接通过THS_BD获取数值时，可用问财做近似语义查询。

---

## J. THS_ReportQuery — 公告查询

查询股票公告信息。

### 接口信息

| 项目 | 内容 |
|------|------|
| HTTP URL | `POST https://quantapi.51ifind.com/api/v1/report_query` |

### 输出参数

| 列名 | 含义 |
|------|------|
| `reportDate` | 公告日期 |
| `thscode` | 同花顺代码 |
| `secName` | 证券简称 |
| `ctime` | 发布时间 |
| `reportTitle` | 公告标题 |
| `pdfURL` | 公告PDF链接 |
| `seq` | 唯一标识号 |

---

## K. THS_realTimeValuation — 基金实时估值

获取基金实时估值数据。

### 接口信息

| 项目 | 内容 |
|------|------|
| HTTP URL | `POST https://quantapi.51ifind.com/api/v1/fund_valuation` |

### 输出参数

| 列名 | 含义 |
|------|------|
| `changeRatioValuation` | 估值涨跌幅 |
| `realTimeValuation` | 实时估值 |
| `Deviation30TDays` | 30日偏离度 |

---

## 附录. 需本地计算的衍生数据

以下数据无法直接从 API 获取，但可通过 API 原料本地计算得到。

### 行情衍生

| 数据 | 计算方式 | 所需原料 | 用途 |
|------|---------|---------|------|
| N日收益率 | `close_t / close_{t-N} - 1` | THS_HQ: close | 动量因子 |
| N日波动率(年化) | `std(returns, N) * sqrt(252)` | THS_HQ: close | 风险因子 |
| N日均线(MA) | `mean(close, N)` | THS_HQ: close | 趋势因子 |
| 振幅 | `(high - low) / pre_close` | THS_HQ: high,low,pre_close | 波动因子 |
| 量价背离 | corr(price, volume, N) | THS_HQ: close, volume | 反转因子 |

### 估值衍生

| 数据 | 计算方式 | 所需原料 | 用途 |
|------|---------|---------|------|
| EP (盈利收益率) | `1 / PE` | THS_BD: ths_pe_ttm_stock | 价值因子 |
| BP (账面价值比) | `1 / PB` | THS_BD: ths_pb_stock | 价值因子 |
| SP (销售收益率) | `1 / PS` | THS_BD: ths_ps_stock | 价值因子 |
| 相对PE | `PE / 行业中位数PE` | PE + 行业分类 | 相对估值 |

### 风险衍生

| 数据 | 计算方式 | 所需原料 | 用途 |
|------|---------|---------|------|
| Beta | `cov(stock_ret, mkt_ret) / var(mkt_ret)` | 个股+市场日线 | 系统性风险 |
| 残差波动率 | 回归残差的std | Beta回归残差 | 特质风险 |
| Amihud非流动性 | `abs(return) / volume` | 日线收益率+成交量 | 流动性因子 |
| 平均成交额 | `mean(amount, N)` | amount | 流动性 |
| 平均换手率 | `mean(turnover, N)` | turnoverRatio | 活跃度 |

### Barra CNE5 风格因子映射

| 风格因子 | 构建方式 | 原料来源 |
|---------|---------|---------|
| Size | `log(ths_market_value_stock)` | 估值因子 |
| Beta | 计算 | 日线 |
| Momentum | 过去12个月收益率 | 日线 |
| Volatility | 收益率标准差 | 日线 |
| Value | `1 / ths_pb_stock` | 估值因子 |
| Liquidity | `ths_turnover_ratio_stock` | 日线 |
| Earnings Yield | `1 / ths_pe_ttm_stock` | 估值因子 |
| Growth | `ths_np_yoy_stock` | 财务因子 |
| Leverage | `ths_asset_liability_ratio_stock` | 财务因子 |

---

## 空缺标记

以下维度目前在字典中有空缺，需要后续补齐：

| 空缺 | 原因 | 补全方式 |
|------|------|---------|
| ❌ THS_BD 的更多指标（如技术指标、港股指标、期货指标） | 文档未公开完整列表 | 通过 SuperCommand → 工具 → 指标函数查询导出 |
| ❌ THS_DP 的更多 reportname | 文档未公开 | 通过 SuperCommand → data_pool 命令生成 |
| ❌ THS_RQ 的完整指标清单 | 实际品种间有差异 | 实测补充 |
| ❌ THS_EDB 的完整指标ID | 文档未公开 | 通过 SuperCommand → EDB 指标ID查询 |
| ❌ THS_SS 的完整指标清单 | 文档未公开 | 实测补充 |

---

*文档版本: v1.0 · 更新日期: 2026-08-26*
*文件位置: `IFIND_DATA/docs/12-iFinD数据字典.md`*