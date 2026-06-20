# 数据源参考

按需加载文件 — 只有进行深度分析或产业链调研时才加载。

## akshare 核心接口

| 功能 | 接口函数 | 说明 |
|------|---------|------|
| A股列表 | `stock_info_a_code_name()` | 全量股票代码+名称 |
| A股日线 | `stock_zh_a_hist(symbol, period, start_date, end_date, adjust)` | 支持前复权/后复权 |
| A股实时 | `stock_zh_a_spot_em()` | 全量实时行情快照 |
| A股财务 | `stock_financial_abstract(symbol)` | 财务指标摘要（多期） |
| A股估值 | `stock_a_lg_indicator(symbol)` | PE/PB 等估值指标 |
| 行业板块 | `stock_board_industry_name_em()` | 东方财富行业板块列表 |
| 板块成分 | `stock_board_industry_cons_em(symbol)` | 指定板块成分股 |

## 数据使用规范

1. 优先使用缓存，减少 API 调用频率
2. 日线数据缓存 1 小时，财务数据缓存 1 天
3. 网络异常时自动重试 3 次（2s/5s/10s）
4. 财务数据注意标注报告期（如 2026Q1）
