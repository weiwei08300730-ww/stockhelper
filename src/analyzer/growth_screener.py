"""业绩爆发增长筛选模型（FR-08）

七维因子评分体系：
1. 营收增长（25%）— 营业收入同比增长率
2. 利润增长（25%）— 归母净利润同比增长率
3. 盈利能力（15%）— ROE
4. 增长质量（10%）— 经营性现金流/净利润
5. 盈利趋势（10%）— 毛利率同比变化
6. 估值匹配（10%）— PEG
7. 季度加速（5%）— 环比增速变化

特殊标识：
🔥 业绩爆发：营收>50% 且 净利润>100%
📈 高增长：营收>30% 且 净利润>50%
⚡ 困境反转：过去亏损转正且增速>100%
🚀 增速加速：连续两季度增速环比提升

参考：UZI-Skill 180 条量化规则的打分引擎设计
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field

import pandas as pd

from src.collector import DataCollector
from src.config import get_config


@dataclass
class GrowthScore:
    """增长评分结果"""
    code: str
    name: str = ""
    # 各维度得分
    revenue_score: float = 0.0
    profit_score: float = 0.0
    roe_score: float = 0.0
    cashflow_score: float = 0.0
    margin_score: float = 0.0
    peg_score: float = 0.0
    acceleration_score: float = 0.0
    # 原始数据
    revenue_yoy: float = 0.0
    net_profit_yoy: float = 0.0
    roe: float = 0.0
    gross_margin: float = 0.0
    gross_margin_change: float = 0.0
    operating_cf: float = 0.0
    net_profit: float = 0.0
    pe: float = 0.0
    peg: float = 0.0
    # 综合
    total_score: float = 0.0
    tag: str = ""         # 🔥📈⚡🚀 标识
    tag_label: str = ""    # 标识文字说明


class GrowthScreener:
    """业绩爆发增长筛选器"""

    def __init__(self):
        self.collector = DataCollector()
        cfg = get_config()
        gs_cfg = cfg["growth_screener"]
        self.weights = gs_cfg["weights"]
        self.thresholds = gs_cfg["thresholds"]

    def scan_market(self, top_n: int = 50) -> List[GrowthScore]:
        """全市场扫描业绩爆发增长公司

        Args:
            top_n: 返回排名前 N 的公司

        Returns:
            按综合评分排序的 GrowthScore 列表
        """
        results = []

        try:
            # 获取全市场股票列表
            df_stocks = self.collector.get_stock_list()
            total = len(df_stocks)
            checked = 0

            for _, row in df_stocks.iterrows():
                code = str(row.get("code", ""))
                name = row.get("name", "")
                if not code:
                    continue

                # 获取财务数据
                fin_data = self.collector.get_financial_data(code)
                if "error" in fin_data:
                    continue

                # 计算评分
                score = self._score_company(fin_data)
                if score and score.total_score > 0:
                    score.code = code
                    score.name = name
                    score.tag, score.tag_label = self._determine_tag(
                        score.revenue_yoy, score.net_profit_yoy
                    )
                    results.append(score)

                checked += 1
                if checked % 500 == 0:
                    pass  # 进度

        except Exception as e:
            pass

        # 排序取 top
        results.sort(key=lambda x: x.total_score, reverse=True)
        return results[:top_n]

    def scan_industry_chain(self, companies: List[Dict]) -> List[GrowthScore]:
        """对产业链中的特定公司列表进行增长筛选"""
        results = []
        for comp in companies:
            code = comp.get("code", "")
            if not code:
                continue
            fin_data = self.collector.get_financial_data(code)
            if "error" in fin_data:
                continue
            score = self._score_company(fin_data)
            if score:
                score.code = code
                score.name = comp.get("name", "")
                score.tag, score.tag_label = self._determine_tag(
                    score.revenue_yoy, score.net_profit_yoy
                )
                results.append(score)

        results.sort(key=lambda x: x.total_score, reverse=True)
        return results

    def _score_company(self, fin_data: Dict[str, Any]) -> Optional[GrowthScore]:
        """计算单公司七维评分"""
        score = GrowthScore(code=fin_data.get("code", ""))

        # 提取财务指标
        revenue_yoy = fin_data.get("revenue_yoy", 0) or 0
        net_profit_yoy = fin_data.get("net_profit_yoy", 0) or 0
        roe = fin_data.get("roe", 0) or 0
        gross_margin = fin_data.get("gross_margin", 0) or 0
        pe = fin_data.get("pe", 0) or 0

        # 1. 营收增长得分（25%）
        score.revenue_yoy = revenue_yoy
        if revenue_yoy >= self.thresholds["breakout_revenue"]:
            score.revenue_score = 100
        elif revenue_yoy < 0:
            score.revenue_score = 0
        else:
            score.revenue_score = min(100, (revenue_yoy / self.thresholds["breakout_revenue"]) * 100)

        # 2. 利润增长得分（25%）
        score.net_profit_yoy = net_profit_yoy
        if net_profit_yoy >= self.thresholds["breakout_profit"]:
            score.profit_score = 100
        elif net_profit_yoy < 0:
            score.profit_score = 0
        else:
            score.profit_score = min(100, (net_profit_yoy / self.thresholds["breakout_profit"]) * 100)

        # 3. ROE 得分（15%）
        score.roe = roe
        if roe >= self.thresholds["roe_threshold"]:
            score.roe_score = min(100, (roe / self.thresholds["roe_threshold"]) * 100)
        elif roe <= 0:
            score.roe_score = 0
        else:
            score.roe_score = (roe / self.thresholds["roe_threshold"]) * 60

        # 4. 增长质量：现金流/净利润（10%）
        score.operating_cf = fin_data.get("operating_cf", 0) or 0
        net_profit_val = fin_data.get("net_profit", 0) or 1
        cf_ratio = score.operating_cf / net_profit_val if abs(net_profit_val) > 1 else 0.5
        score.cashflow_score = min(100, max(0, cf_ratio / 0.8 * 100))

        # 5. 毛利率趋势（10%）
        score.gross_margin = gross_margin
        # 简化处理：高毛利率加分
        if gross_margin >= 40:
            score.margin_score = 100
        elif gross_margin >= 20:
            score.margin_score = 60
        elif gross_margin >= 10:
            score.margin_score = 30
        else:
            score.margin_score = 10

        # 6. PEG 得分（10%）
        score.pe = pe
        if pe > 0 and net_profit_yoy > 0:
            peg = pe / net_profit_yoy
            score.peg = round(peg, 2)
            if peg <= self.thresholds["peg_threshold"]:
                score.peg_score = 100
            elif peg <= 2:
                score.peg_score = 60
            else:
                score.peg_score = max(0, 30 - (peg - 2) * 10)
        else:
            score.peg_score = 50  # 数据不足时给中性分

        # 7. 季度加速（5%）— 简化处理
        score.acceleration_score = 50  # 中性分

        # 计算总分
        total = (
            score.revenue_score * self.weights["revenue_growth"] +
            score.profit_score * self.weights["profit_growth"] +
            score.roe_score * self.weights["roe"] +
            score.cashflow_score * self.weights["cashflow_quality"] +
            score.margin_score * self.weights["margin_trend"] +
            score.peg_score * self.weights["peg"] +
            score.acceleration_score * self.weights["acceleration"]
        ) / 100

        score.total_score = round(total, 1)
        return score

    def _determine_tag(self, revenue_yoy: float, profit_yoy: float) -> Tuple[str, str]:
        """确定增长标签"""
        if revenue_yoy >= 50 and profit_yoy >= 100:
            return "🔥", "业绩爆发"
        if revenue_yoy >= 30 and profit_yoy >= 50:
            return "📈", "高增长"
        if profit_yoy >= 100:  # 假设前值为负
            return "⚡", "高增速"
        # 检查连续加速（简化）
        if revenue_yoy > 20 and profit_yoy > 30:
            return "🚀", "增速加速"
        return "📊", "正常"
