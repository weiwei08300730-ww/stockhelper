"""多维度买卖信号评分引擎

参考 trading-agents-plugin 的多智能体辩论思想，综合多个维度产生 BUY/SELL/HOLD 信号。

评分维度及权重：
1. 技术面趋势 (35%) — MA排列、MACD、RSI、KDJ、BOLL
2. 资金面动量 (20%) — 成交量变化、价格动量
3. 基本面质量 (25%) — 增长评分、盈利能力、估值
4. 产业链位置 (20%) — 瓶颈评分、景气度

输出：综合信号 + 各维度评分 + 入场/止损参考
"""

from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

import pandas as pd
import numpy as np

from src.collector import DataCollector
from src.analyzer import (
    calculate_ma, calculate_macd, calculate_rsi,
    calculate_kdj, calculate_boll
)
from src.config import get_config


class SignalAction(Enum):
    STRONG_BUY = "强买入"
    BUY = "买入"
    HOLD = "持有"
    SELL = "卖出"
    STRONG_SELL = "强卖出"


@dataclass
class SignalResult:
    """买卖信号结果"""
    code: str = ""
    name: str = ""
    action: SignalAction = SignalAction.HOLD
    confidence: int = 0           # 信心指数 0-100
    # 各维度评分
    technical_score: float = 0.0  # 技术面 (0-100)
    momentum_score: float = 0.0   # 资金动量 (0-100)
    fundamental_score: float = 0.0  # 基本面 (0-100)
    chain_score: float = 0.0      # 产业链 (0-100)
    total_score: float = 0.0      # 综合评分 (0-100)
    # 交易参考
    entry_low: float = 0.0        # 入场区间下沿
    entry_high: float = 0.0       # 入场区间上沿
    stop_loss: float = 0.0        # 止损价
    risk_pct: float = 0.0         # 建议仓位风险比例 (%)
    # 分析详情
    reasons: List[str] = field(default_factory=list)  # 买入理由
    risks: List[str] = field(default_factory=list)    # 风险提示
    signals_detail: Dict[str, str] = field(default_factory=dict)  # 各指标信号详情


class SignalEngine:
    """多维度买卖信号评分引擎"""

    def __init__(self):
        self.collector = DataCollector()

    def analyze(self, code: str) -> SignalResult:
        """对个股进行完整的买卖信号分析（自动获取数据）"""
        daily = self.collector.get_stock_daily(code)
        fin = self.collector.get_financial_data(code)
        quote = self.collector.get_realtime_quote(code)
        return self._analyze_with_data(code, daily, fin, quote)

    def analyze_with_data(self, code: str, daily: pd.DataFrame,
                          fin_data: Optional[Dict] = None,
                          quote: Optional[Dict] = None) -> SignalResult:
        """用已获取的数据分析买卖信号（避免重复网络请求）"""
        return self._analyze_with_data(code, daily, fin_data or {}, quote or {})

    def _analyze_with_data(self, code: str, daily: pd.DataFrame,
                           fin: Dict, quote: Dict) -> SignalResult:
        """核心分析逻辑"""
        result = SignalResult(code=code)

        if daily.empty:
            result.reasons.append("无法获取行情数据")
            return result

        # 1. 技术面分析 (35%)
        tech_score, tech_details = self._analyze_technical(daily)
        result.technical_score = tech_score
        result.signals_detail.update(tech_details)

        # 2. 资金动量分析 (20%)
        mom_score, mom_details = self._analyze_momentum(daily, quote)
        result.momentum_score = mom_score
        result.signals_detail.update(mom_details)

        # 3. 基本面分析 (25%)
        fund_score, fund_details = self._analyze_fundamental(fin)
        result.fundamental_score = fund_score
        result.signals_detail.update(fund_details)

        # 4. 产业链分析 (20%)
        chain_score = self._analyze_chain_position(code)
        result.chain_score = chain_score

        # 计算综合评分
        result.total_score = (
            tech_score * 0.35 +
            mom_score * 0.20 +
            fund_score * 0.25 +
            chain_score * 0.20
        )

        # 确定买卖信号
        result.action, result.confidence = self._determine_action(result.total_score)

        # 计算交易参考
        if not daily.empty:
            close = daily["收盘"].iloc[-1]
            # 取最近20日均价作为基准
            ma20 = calculate_ma(daily["收盘"], 20).iloc[-1] if len(daily) >= 20 else close
            result.entry_low = round(ma20 * 0.95, 2)
            result.entry_high = round(ma20 * 1.02, 2)
            result.stop_loss = round(ma20 * 0.90, 2)

            # 计算波动率调整仓位
            volatility = daily["收盘"].pct_change().std() * np.sqrt(252)
            if volatility > 0:
                base_risk = min(5.0, 3.0 / volatility * 100)
                if result.action in (SignalAction.STRONG_BUY, SignalAction.BUY):
                    result.risk_pct = round(min(base_risk, 8.0), 1)
                elif result.action in (SignalAction.SELL, SignalAction.STRONG_SELL):
                    result.risk_pct = 0.0
                else:
                    result.risk_pct = round(base_risk * 0.3, 1)

        # 生成分析理由
        result.reasons = self._generate_reasons(result, quote, fin)
        result.risks = self._generate_risks(result, daily)

        # 获取股票名称
        if "error" not in fin and fin.get("name"):
            result.name = fin["name"]
        elif quote.get("name"):
            result.name = quote["name"]

        return result

    def _analyze_technical(self, daily: pd.DataFrame) -> Tuple[float, Dict[str, str]]:
        """技术面分析 (权重35%)"""
        score = 50  # 中性分
        details = {}
        close = daily["收盘"]
        high = daily["最高"]
        low = daily["最低"]

        if len(close) < 20:
            return 50, {"技术面": "数据不足"}

        try:
            # MACD 信号 (-20 ~ +20)
            dif, dea, macd_bar = calculate_macd(close)
            if dif.iloc[-1] > dea.iloc[-1] and macd_bar.iloc[-1] > 0:
                score += 15
                details["MACD"] = "金叉+多头 ✅ (+15)"
            elif dif.iloc[-1] > dea.iloc[-1]:
                score += 8
                details["MACD"] = "金叉 (+8)"
            elif dif.iloc[-1] < dea.iloc[-1] and macd_bar.iloc[-1] < 0:
                score -= 15
                details["MACD"] = "死叉+空头 ❌ (-15)"
            else:
                score -= 8
                details["MACD"] = "死叉 (-8)"

            # RSI 信号 (-10 ~ +10)
            rsi = calculate_rsi(close, 14)
            rsi_val = rsi.iloc[-1]
            if 30 <= rsi_val <= 70:
                if rsi_val > 50:
                    score += 5
                    details["RSI"] = f"偏多 {rsi_val:.0f} (+5)"
                else:
                    score += 2
                    details["RSI"] = f"中性 {rsi_val:.0f} (+2)"
            elif rsi_val < 30:
                score += 10  # 超卖反弹机会
                details["RSI"] = f"超卖 {rsi_val:.0f} (+10)"
            elif rsi_val > 70:
                score -= 5
                details["RSI"] = f"超买 {rsi_val:.0f} (-5)"

            # KDJ 信号 (-10 ~ +10)
            k, d, j = calculate_kdj(high, low, close)
            if k.iloc[-1] > d.iloc[-1] and k.iloc[-2] <= d.iloc[-2]:
                score += 8
                details["KDJ"] = "金叉 (+8)"
            elif k.iloc[-1] < d.iloc[-1] and k.iloc[-2] >= d.iloc[-2]:
                score -= 8
                details["KDJ"] = "死叉 (-8)"
            else:
                score += 2 if k.iloc[-1] > d.iloc[-1] else -2
                details["KDJ"] = f"{'多头' if k.iloc[-1] > d.iloc[-1] else '空头'}排列"

            # MA 排列信号 (-15 ~ +15)
            if len(close) >= 60:
                ma5 = calculate_ma(close, 5).iloc[-1]
                ma10 = calculate_ma(close, 10).iloc[-1]
                ma20 = calculate_ma(close, 20).iloc[-1]
                ma60 = calculate_ma(close, 60).iloc[-1]

                if ma5 > ma10 > ma20 > ma60:
                    score += 15
                    details["均线"] = "多头排列 ✅ (+15)"
                elif ma5 < ma10 < ma20 < ma60:
                    score -= 15
                    details["均线"] = "空头排列 ❌ (-15)"
                elif ma5 > ma10 and ma10 > ma20:
                    score += 5
                    details["均线"] = "短多中 (+5)"

            # BOLL 位置 (-5 ~ +5)
            upper, mid, lower = calculate_boll(close)
            last_close = close.iloc[-1]
            if last_close <= lower.iloc[-1]:
                score += 5
                details["布林"] = "触及下轨 (+5)"
            elif last_close >= upper.iloc[-1]:
                score -= 3
                details["布林"] = "触及上轨 (-3)"
            else:
                details["布林"] = "中轨附近"

        except Exception:
            pass

        return max(0, min(100, score)), details

    def _analyze_momentum(self, daily: pd.DataFrame, quote: Dict) -> Tuple[float, Dict[str, str]]:
        """资金动量分析 (权重20%)"""
        score = 50
        details = {}

        try:
            # 成交量变化 (-10 ~ +10)
            if len(daily) >= 20:
                vol_ma5 = daily["成交量"].tail(5).mean()
                vol_ma20 = daily["成交量"].tail(20).mean()
                if vol_ma20 > 0:
                    vol_ratio = vol_ma5 / vol_ma20
                    if vol_ratio > 1.5:
                        score += 10
                        details["成交量"] = f"放量 {vol_ratio:.1f}x (+10)"
                    elif vol_ratio > 1.2:
                        score += 5
                        details["成交量"] = f"温和放量 {vol_ratio:.1f}x (+5)"
                    elif vol_ratio < 0.7:
                        score -= 5
                        details["成交量"] = f"缩量 {vol_ratio:.1f}x (-5)"
                    else:
                        details["成交量"] = f"正常 {vol_ratio:.1f}x"

            # 价格动量 (-10 ~ +10)
            if len(daily) >= 10:
                price_10d_ago = daily["收盘"].iloc[-10]
                current_close = daily["收盘"].iloc[-1]
                momentum = (current_close - price_10d_ago) / price_10d_ago * 100
                if momentum > 10:
                    score += 10
                    details["动量"] = f"强势 {momentum:+.1f}% (+10)"
                elif momentum > 5:
                    score += 5
                    details["动量"] = f"偏强 {momentum:+.1f}% (+5)"
                elif momentum < -10:
                    score -= 10
                    details["动量"] = f"弱势 {momentum:+.1f}% (-10)"
                elif momentum < -5:
                    score -= 5
                    details["动量"] = f"偏弱 {momentum:+.1f}% (-5)"
                else:
                    details["动量"] = f"平稳 {momentum:+.1f}%"

            # 涨跌幅 (-5 ~ +5)
            change_pct = quote.get("change_pct", 0)
            if abs(change_pct) < 2:
                score += 3
                details["当日涨跌"] = f"{change_pct:+.2f}% (+3)"
            elif change_pct > 5:
                score -= 3
                details["当日涨跌"] = f"大涨{change_pct:+.2f}% 追高风险 (-3)"
            elif change_pct < -5:
                score += 5
                details["当日涨跌"] = f"大跌{change_pct:.2f}% 超卖机会 (+5)"

        except Exception:
            pass

        return max(0, min(100, score)), details

    def _analyze_fundamental(self, fin: Dict) -> Tuple[float, Dict[str, str]]:
        """基本面质量分析 (权重25%)"""
        score = 50
        details = {}

        if "error" in fin or not fin:
            details["基本面"] = "数据不足"
            return 50, details

        try:
            revenue_yoy = fin.get("revenue_yoy", 0) or 0
            profit_yoy = fin.get("net_profit_yoy", 0) or 0
            roe = fin.get("roe", 0) or 0
            gross_margin = fin.get("gross_margin", 0) or 0
            pe = fin.get("pe", 0) or 0

            # 营收增长 (-15 ~ +20)
            if revenue_yoy >= 30:
                score += 20
                details["营收增长"] = f"{revenue_yoy:+.1f}% 高增长 ✅ (+20)"
            elif revenue_yoy >= 10:
                score += 10
                details["营收增长"] = f"{revenue_yoy:+.1f}% 稳增长 (+10)"
            elif revenue_yoy < 0:
                score -= 15
                details["营收增长"] = f"{revenue_yoy:+.1f}% 负增长 ❌ (-15)"
            else:
                details["营收增长"] = f"{revenue_yoy:+.1f}%"

            # 利润增长 (-15 ~ +20)
            if profit_yoy >= 50:
                score += 20
                details["利润增长"] = f"{profit_yoy:+.1f}% 爆发 (+20)"
            elif profit_yoy >= 10:
                score += 10
                details["利润增长"] = f"{profit_yoy:+.1f}% (+10)"
            elif profit_yoy < 0:
                score -= 15
                details["利润增长"] = f"{profit_yoy:+.1f}% 下滑 ❌ (-15)"
            else:
                details["利润增长"] = f"{profit_yoy:+.1f}%"

            # ROE (-10 ~ +10)
            if roe >= 15:
                score += 10
                details["ROE"] = f"{roe:.1f}% 优秀 (+10)"
            elif roe >= 8:
                score += 5
                details["ROE"] = f"{roe:.1f}% 良好 (+5)"
            elif roe < 0:
                score -= 10
                details["ROE"] = f"{roe:.1f}% 负值 (-10)"
            else:
                details["ROE"] = f"{roe:.1f}%"

            # 毛利率 (-5 ~ +5)
            if gross_margin >= 40:
                score += 5
                details["毛利率"] = f"{gross_margin:.1f}% (+5)"
            elif gross_margin < 10:
                score -= 5
                details["毛利率"] = f"{gross_margin:.1f}% 偏低 (-5)"

            # 估值 (-5 ~ +5)
            if 0 < pe <= 15:
                score += 5
                details["估值"] = f"PE={pe:.0f} 低估 (+5)"
            elif pe > 50:
                score -= 5
                details["估值"] = f"PE={pe:.0f} 偏高 (-5)"
            elif pe > 0:
                details["估值"] = f"PE={pe:.0f}"

        except Exception:
            pass

        return max(0, min(100, score)), details

    def _analyze_chain_position(self, code: str) -> float:
        """产业链位置分析 (权重20%)"""
        return 55.0  # 基线分，略偏正面

    def _determine_action(self, total_score: float) -> Tuple[SignalAction, int]:
        """根据综合评分确定买卖信号"""
        if total_score >= 80:
            return SignalAction.STRONG_BUY, int(total_score)
        elif total_score >= 65:
            return SignalAction.BUY, int(total_score)
        elif total_score >= 40:
            return SignalAction.HOLD, int(total_score)
        elif total_score >= 25:
            return SignalAction.SELL, int(total_score)
        else:
            return SignalAction.STRONG_SELL, int(total_score)

    def _generate_reasons(self, result: SignalResult, quote: Dict,
                          fin: Dict) -> List[str]:
        """生成买入/持有理由"""
        reasons = []

        if result.technical_score >= 65:
            reasons.append(f"技术面偏多 ({result.technical_score:.0f}分): MACD/均线呈现多头排列")
        elif result.technical_score <= 35:
            reasons.append(f"技术面偏空 ({result.technical_score:.0f}分): 注意均线压力")

        if result.momentum_score >= 65:
            reasons.append(f"资金动量积极 ({result.momentum_score:.0f}分): 成交量配合")
        elif result.momentum_score <= 35:
            reasons.append(f"资金动量不足 ({result.momentum_score:.0f}分): 关注放量信号")

        rev = fin.get("revenue_yoy", 0) or 0
        profit = fin.get("net_profit_yoy", 0) or 0
        if rev > 20 and profit > 30:
            reasons.append(f"业绩增长强劲: 营收+{rev:.1f}%, 净利+{profit:.1f}%")
        elif rev < 0 and profit < 0:
            reasons.append(f"业绩承压: 营收{rev:+.1f}%, 净利{profit:+.1f}%")

        price = quote.get("price", 0)
        stop = result.stop_loss
        if stop > 0 and price > 0:
            risk_ratio = (price - stop) / price * 100
            if risk_ratio < 5:
                reasons.append(f"止损空间可控 ({risk_ratio:.1f}%), 盈亏比合理")

        if result.chain_score >= 60:
            reasons.append("产业链位置有利，享有一定行业壁垒")

        if not reasons:
            reasons.append("当前无明显偏向信号，建议观望")

        return reasons[:5]

    def _generate_risks(self, result: SignalResult, daily: pd.DataFrame) -> List[str]:
        """生成风险提示"""
        risks = []

        if result.technical_score <= 40:
            risks.append("技术面整体偏弱，反弹可能受限")

        try:
            volatility = daily["收盘"].pct_change().std() * np.sqrt(252)
            if volatility > 0.4:
                risks.append(f"年化波动率 {volatility:.1%}, 属于高波动标的，仓位需控制")
        except Exception:
            pass

        if result.total_score < 40:
            risks.append(f"综合评分偏低 ({result.total_score:.0f}分)，不建议重仓")

        if result.action in (SignalAction.STRONG_BUY, SignalAction.BUY):
            risks.append("本信号基于历史数据，不构成投资建议，请自行判断")

        if not risks:
            risks.append("当前风险可控，但仍需关注大盘系统性风险")

        return risks[:4]

    def batch_analyze(self, codes: List[str]) -> List[SignalResult]:
        """批量分析多个股票"""
        results = []
        for code in codes:
            try:
                result = self.analyze(code)
                results.append(result)
            except Exception:
                pass
        return sorted(results, key=lambda r: r.total_score, reverse=True)
