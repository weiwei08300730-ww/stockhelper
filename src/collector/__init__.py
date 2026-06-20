"""数据采集模块 —— 行情、财务、产业链数据统一采集层

参考 UZI-Skill 的 22 维数据架构，抽象数据源访问层，
支持多数据源切换和自动重试。
"""

import time
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from pathlib import Path

import pandas as pd

from src.config import get_config, get_cache_dir
from src.utils import Cache


# ===================== 数据模型 =====================

@dataclass
class StockDaily:
    """日线行情数据模型"""
    code: str
    name: str = ""
    date: str = ""
    open: float = 0.0
    close: float = 0.0
    high: float = 0.0
    low: float = 0.0
    volume: int = 0          # 成交量（手）
    amount: float = 0.0      # 成交额（元）
    change_pct: float = 0.0  # 涨跌幅（%）
    change_amt: float = 0.0  # 涨跌额


@dataclass
class FinancialMetrics:
    """财务指标数据模型"""
    code: str
    name: str = ""
    report_date: str = ""
    revenue: float = 0.0           # 营业收入
    revenue_yoy: float = 0.0       # 营收同比增长(%)
    net_profit: float = 0.0        # 归母净利润
    net_profit_yoy: float = 0.0    # 净利润同比增长(%)
    roe: float = 0.0               # 净资产收益率(%)
    gross_margin: float = 0.0      # 毛利率(%)
    net_margin: float = 0.0        # 净利率(%)
    operating_cf: float = 0.0      # 经营性现金流
    pe: float = 0.0                # 市盈率
    pb: float = 0.0                # 市净率


@dataclass
class ChainNode:
    """产业链节点"""
    name: str                      # 环节名称
    description: str = ""          # 环节描述
    companies: List[Dict] = field(default_factory=list)  # 该环节公司列表


@dataclass
class IndustryChain:
    """产业链模型"""
    name: str                      # 产业链名称
    description: str = ""          # 描述
    nodes: List[ChainNode] = field(default_factory=list)  # 环节列表
    source: str = "research"       # 来源：research / cache / manual
    researched_at: str = ""        # 调研时间


# ===================== 数据采集器 =====================

class DataCollector:
    """统一数据采集器 —— 封装 akshare 及其它数据源"""

    def __init__(self):
        cfg = get_config()
        self.timeout = cfg["data_source"]["timeout"]
        self.retry_times = cfg["data_source"]["retry_times"]
        self.retry_delays = cfg["data_source"]["retry_delays"]
        self.cache = Cache(get_cache_dir())
        self._akshare = None  # 延迟导入

    @property
    def ak(self):
        """延迟导入 akshare，避免未安装时直接报错"""
        if self._akshare is None:
            import akshare as ak
            self._akshare = ak
        return self._akshare

    def _retry(self, func, *args, **kwargs):
        """带重试的执行包装"""
        last_error = None
        for attempt in range(self.retry_times + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.retry_times:
                    delay = self.retry_delays[min(attempt, len(self.retry_delays) - 1)]
                    time.sleep(delay)
        raise last_error

    # ==================== 行情数据 ====================

    def get_stock_list(self) -> pd.DataFrame:
        """获取 A 股全量股票列表"""
        cache_key = "stock_list"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        df = self._retry(self.ak.stock_info_a_code_name)
        self.cache.set(cache_key, df.to_dict("records"), ttl=86400)
        return df

    def get_stock_daily(self, code: str, start_date: str = "", end_date: str = "") -> pd.DataFrame:
        """获取个股日线行情

        Args:
            code: 股票代码，如 "600519"
            start_date: 开始日期 "YYYYMMDD"
            end_date: 结束日期 "YYYYMMDD"
        """
        # 调整代码格式
        if "." not in code:
            if code.startswith("6") or code.startswith("9"):
                code_fmt = f"{code}"
            else:
                code_fmt = f"{code}"
        else:
            code_fmt = code.split(".")[0]

        cache_key = f"daily_{code_fmt}_{start_date}_{end_date}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return pd.DataFrame(cached)

        try:
            df = self._retry(
                self.ak.stock_zh_a_hist,
                symbol=code_fmt,
                period="daily",
                start_date=start_date or "19000101",
                end_date=end_date or "20500101",
                adjust="qfq"  # 前复权
            )
            if not df.empty:
                self.cache.set(cache_key, df.to_dict("records"), ttl=3600)
            return df
        except Exception as e:
            return pd.DataFrame()

    def get_realtime_quote(self, code: str) -> Dict[str, Any]:
        """获取个股实时行情"""
        try:
            df = self._retry(self.ak.stock_zh_a_spot_em)
            if code.isdigit():
                match = df[df["代码"] == code]
            else:
                match = df[df["代码"] == code]
            if not match.empty:
                row = match.iloc[0]
                return {
                    "code": row.get("代码", code),
                    "name": row.get("名称", ""),
                    "price": float(row.get("最新价", 0)),
                    "change_pct": float(row.get("涨跌幅", 0)),
                    "change_amt": float(row.get("涨跌额", 0)),
                    "volume": float(row.get("成交量", 0)),
                    "amount": float(row.get("成交额", 0)),
                    "high": float(row.get("最高", 0)),
                    "low": float(row.get("最低", 0)),
                    "open": float(row.get("开盘", 0)),
                    "pre_close": float(row.get("昨收", 0)),
                }
            return {"code": code, "error": "未找到该股票"}
        except Exception as e:
            return {"code": code, "error": str(e)}

    # ==================== 财务数据 ====================

    def get_financial_data(self, code: str) -> Dict[str, Any]:
        """获取个股核心财务指标"""
        cache_key = f"financial_{code}"
        cached = self.cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            symbol = code.split(".")[0] if "." in code else code

            # 获取财务指标（akshare 返回格式：列=日期，行=指标名）
            df = self._retry(self.ak.stock_financial_abstract, symbol=symbol)
            if df.empty:
                return {"code": code, "error": "暂无财务数据"}

            # 解析：df 的列是 ['选项','指标','20260331','20251231',...]
            # 行是具体指标数据
            date_cols = [c for c in df.columns if c not in ('选项', '指标')]
            latest_date = date_cols[0] if date_cols else ''

            def _get_val(indicator: str) -> float:
                """从指标行中提取最新一期数值"""
                rows = df[df['指标'] == indicator]
                if not rows.empty and latest_date in rows.columns:
                    val = rows.iloc[0][latest_date]
                    try:
                        return float(val) if pd.notna(val) else 0.0
                    except (ValueError, TypeError):
                        return 0.0
                return 0.0

            def _calc_yoy(indicator: str) -> float:
                """计算同比增速（%）：date_cols[0]=最新, [4]=同季度去年"""
                rows = df[df['指标'] == indicator]
                if rows.empty:
                    return 0.0
                try:
                    cur = float(rows.iloc[0][date_cols[0]]) if pd.notna(rows.iloc[0].get(date_cols[0])) else None
                    prev = float(rows.iloc[0][date_cols[4]]) if len(date_cols) > 4 and pd.notna(rows.iloc[0].get(date_cols[4])) else None
                    if cur is not None and prev is not None and prev != 0:
                        return round((cur - prev) / abs(prev) * 100, 2)
                except (ValueError, TypeError, IndexError):
                    pass
                return 0.0

            # 常用指标行名（akshare 中文）
            net_profit = _get_val('归母净利润')
            revenue = _get_val('营业总收入')

            result = {
                "code": code,
                "report_date": latest_date[:4] + "-" + latest_date[4:6] if len(latest_date) >= 6 else "",
                "revenue": revenue,
                "revenue_yoy": _calc_yoy('营业总收入'),
                "net_profit": net_profit,
                "net_profit_yoy": _calc_yoy('归母净利润'),
                "roe": _get_val('净资产收益率'),
                "gross_margin": _get_val('毛利率'),
                "net_margin": _get_val('销售净利率'),
            }

            # 尝试获取估值数据（独立接口）
            try:
                df_v = self._retry(self.ak.stock_a_lg_indicator, symbol=symbol)
                if not df_v.empty:
                    result["pe"] = float(df_v.iloc[0].get("pe", 0))
                    result["pb"] = float(df_v.iloc[0].get("pb", 0))
                else:
                    result["pe"] = 0.0
                    result["pb"] = 0.0
            except Exception:
                result["pe"] = 0.0
                result["pb"] = 0.0

            self.cache.set(cache_key, result, ttl=86400)
            return result

        except Exception as e:
            return {"code": code, "error": str(e)}

    def get_financial_data_by_quarter(self, code: str) -> pd.DataFrame:
        """获取多期财务数据用于增长趋势分析"""
        try:
            symbol = code.split(".")[0] if "." in code else code
            df = self._retry(self.ak.stock_financial_abstract, symbol=symbol)
            return df
        except Exception:
            return pd.DataFrame()

    # ==================== 行业/板块数据 ====================

    def get_sector_list(self) -> pd.DataFrame:
        """获取行业板块列表"""
        try:
            return self._retry(self.ak.stock_board_industry_name_em)
        except Exception:
            return pd.DataFrame()

    def get_sector_stocks(self, sector_name: str) -> pd.DataFrame:
        """获取指定行业板块的成分股"""
        try:
            return self._retry(
                self.ak.stock_board_industry_cons_em,
                symbol=sector_name
            )
        except Exception:
            return pd.DataFrame()

    # ==================== 数据验证 ====================

    def validate_code(self, code: str) -> bool:
        """验证股票代码是否存在"""
        try:
            df = self.get_stock_list()
            code_clean = code.split(".")[0] if "." in code else code
            return code_clean in df["code"].values or code_clean in df["代码"].values
        except Exception:
            return False

    def search_stock(self, keyword: str) -> List[Dict]:
        """搜索股票（代码或名称模糊匹配）"""
        try:
            df = self.get_stock_list()
            matches = df[
                df["code"].astype(str).str.contains(keyword, na=False) |
                df["name"].str.contains(keyword, na=False)
            ]
            return matches.head(20).to_dict("records")
        except Exception:
            return []
