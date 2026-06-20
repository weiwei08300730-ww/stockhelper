"""Pyecharts 专业股票图表报告生成器

使用 Pyecharts（Apache ECharts Python 封装）生成：
- K 线图 + MA 均线 + 买卖信号标记
- MACD 柱状图
- RSI / KDJ 指标图
- 成交量柱状图

买卖信号标记在 K 线图上叠加显示 BUY/SELL 箭头。
"""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

from pyecharts.charts import Kline, Bar, Line, Grid, Page, Scatter
from pyecharts import options as opts
from pyecharts.globals import ThemeType

from src.config import get_report_dir
from src.analyzer import (
    calculate_ma, calculate_macd, calculate_rsi,
    calculate_kdj, calculate_boll
)
from src.analyzer.signal_engine import SignalEngine, SignalAction


class PyechartsReportGenerator:
    """Pyecharts 专业图表报告生成器"""

    def __init__(self):
        self.output_dir = get_report_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.signal_engine = SignalEngine()

    def generate(self, code: str, daily: pd.DataFrame,
                 fin_data: Optional[Dict[str, Any]] = None) -> str:
        """生成完整的 Html 报告"""
        stock_name = fin_data.get("name", code) if fin_data and "error" not in fin_data else code
        now = datetime.now().strftime("%Y-%m-%d %H:%M")

        # 计算买卖信号（复用已传入的数据，避免重复网络请求）
        signal = self.signal_engine.analyze_with_data(code, daily, fin_data or {})

        # 分别渲染各图表（不使用 Page 容器，避免远程资源加载）
        chart_kline = self._chart_to_div(self._create_kline_chart(code, daily, signal), "kline")
        chart_vol = self._chart_to_div(self._create_volume_chart(daily), "volume")
        chart_macd = self._chart_to_div(self._create_macd_chart(daily), "macd")
        chart_rsi = self._chart_to_div(self._create_rsi_chart(daily), "rsi")

        charts_html = f"""
        <div class="chart-section" style="margin-bottom:20px;">
            <div style="background:#161b22;border-radius:8px;padding:10px;">{chart_kline}</div>
        </div>
        <div class="chart-section" style="margin-bottom:20px;">
            <div style="background:#161b22;border-radius:8px;padding:10px;">{chart_vol}</div>
        </div>
        <div class="chart-section" style="margin-bottom:20px;">
            <div style="background:#161b22;border-radius:8px;padding:10px;">{chart_macd}</div>
        </div>
        <div class="chart-section" style="margin-bottom:20px;">
            <div style="background:#161b22;border-radius:8px;padding:10px;">{chart_rsi}</div>
        </div>
        """

        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{stock_name}({code}) 分析报告 — StockHelper</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;
       background: #0d1117; color: #e6edf3; padding: 20px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
.header {{ text-align: center; padding: 25px 0; border-bottom: 1px solid #30363d; margin-bottom: 20px; }}
.header h1 {{ font-size: 26px; margin-bottom: 5px; color: #e6edf3; }}
.header .subtitle {{ color: #8b949e; font-size: 13px; }}
.signal-box {{ display: flex; gap: 15px; margin: 20px 0; flex-wrap: wrap; }}
.signal-card {{ flex: 1; min-width: 160px; background: #161b22; border-radius: 8px; padding: 15px; text-align: center; }}
.signal-card .label {{ font-size: 11px; color: #8b949e; margin-bottom: 5px; }}
.signal-card .value {{ font-size: 22px; font-weight: bold; }}
.signal-card .detail {{ font-size: 12px; color: #8b949e; margin-top: 5px; }}
.score-bar {{ height: 6px; border-radius: 3px; margin-top: 8px; background: #30363d; }}
.score-fill {{ height: 100%; border-radius: 3px; }}
.reasons {{ background: #161b22; border-radius: 8px; padding: 15px; margin: 15px 0; }}
.reasons h3 {{ font-size: 14px; margin-bottom: 10px; color: #e6edf3; }}
.reasons ul {{ list-style: none; }}
.reasons li {{ padding: 4px 0; font-size: 13px; color: #e6edf3; }}
.reasons li::before {{ content: '\\2022 '; color: #58a6ff; }}
.footer {{ text-align: center; padding: 20px 0; margin-top: 30px; border-top: 1px solid #30363d; color: #8b949e; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>{stock_name} <span style="color: #58a6ff;">({code})</span></h1>
        <div class="subtitle">生成时间: {now} | StockHelper 智能分析报告</div>
    </div>
    <div class="signal-box">
        {self._render_signal_cards(signal)}
    </div>
    <div class="reasons">
        <h3>{'[买入理由]' if signal.action in (SignalAction.BUY, SignalAction.STRONG_BUY) else '[分析要点]'}</h3>
        <ul>
            {''.join(f'<li>{r}</li>' for r in (signal.reasons[:5] if signal.reasons else ['暂无显著信号']))}
        </ul>
    </div>
    <div class="reasons">
        <h3>[风险提示]</h3>
        <ul>
            {''.join(f'<li>{r}</li>' for r in (signal.risks[:4] if signal.risks else ['投资有风险，入市需谨慎']))}
        </ul>
    </div>
    <div class="reasons" style="margin-top:15px; text-align:center; background:transparent; border:1px solid #30363d;">
        <p style="font-size:13px; color:#8b949e;">
        信号: {signal.action.value} | 信心指数: {signal.confidence}/100 |
        入场: {signal.entry_low:.2f}-{signal.entry_high:.2f} |
        止损: {signal.stop_loss:.2f} |
        仓位建议: {signal.risk_pct:.1f}%
        </p>
    </div>
    {charts_html}
    <div class="footer">
        <p>StockHelper v0.1.0 | 本报告仅供参考，不构成投资建议</p>
    </div>
</div>
</body>
</html>"""

        # 保存文件
        file_name = f"{code}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
        file_path = self.output_dir / file_name
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_html)

        return str(file_path)

    def _chart_to_div(self, chart, chart_id: str) -> str:
        """将 Pyecharts 图表转为嵌入的 HTML div 字符串"""
        try:
            return chart.render_embed()
        except Exception as e:
            return '<div style="width:100%;height:400px;"></div>'

    def _render_signal_cards(self, signal) -> str:
        """渲染信号卡片"""
        action = signal.action
        if action in (SignalAction.STRONG_BUY, SignalAction.BUY):
            action_color = "#f85149"
            action_text = action.value
        elif action == SignalAction.HOLD:
            action_color = "#d29922"
            action_text = action.value
        else:
            action_color = "#3fb950"
            action_text = action.value

        return f"""
        <div class="signal-card">
            <div class="label">综合信号</div>
            <div class="value" style="color:{action_color}">{action_text}</div>
            <div class="detail">评分 {signal.total_score:.0f}/100</div>
        </div>
        <div class="signal-card">
            <div class="label">技术面</div>
            <div class="value">{signal.technical_score:.0f}</div>
            <div class="detail">权重35%</div>
            <div class="score-bar" style="background:#30363d;"><div class="score-fill" style="width:{signal.technical_score}%;background:linear-gradient(90deg,#3fb950,#f85149);"></div></div>
        </div>
        <div class="signal-card">
            <div class="label">资金动量</div>
            <div class="value">{signal.momentum_score:.0f}</div>
            <div class="detail">权重20%</div>
            <div class="score-bar" style="background:#30363d;"><div class="score-fill" style="width:{signal.momentum_score}%;background:linear-gradient(90deg,#3fb950,#d29922);"></div></div>
        </div>
        <div class="signal-card">
            <div class="label">基本面</div>
            <div class="value">{signal.fundamental_score:.0f}</div>
            <div class="detail">权重25%</div>
            <div class="score-bar" style="background:#30363d;"><div class="score-fill" style="width:{signal.fundamental_score}%;background:linear-gradient(90deg,#3fb950,#58a6ff);"></div></div>
        </div>
        <div class="signal-card">
            <div class="label">综合评分</div>
            <div class="value">{signal.total_score:.0f}</div>
            <div class="detail">{'偏多' if signal.total_score >= 50 else '偏空'}</div>
            <div class="score-bar" style="background:#30363d;"><div class="score-fill" style="width:{signal.total_score}%;background:linear-gradient(90deg,#3fb950,#f85149);"></div></div>
        </div>
        """

    def _create_kline_chart(self, code: str, daily: pd.DataFrame,
                             signal) -> Kline:
        """创建 K 线图 + MA 均线 + 买卖信号"""
        dates = daily["日期"].astype(str).tolist()
        close = daily["收盘"].tolist()
        ohlc = [
            [row["开盘"], row["收盘"], row["最低"], row["最高"]]
            for _, row in daily.iterrows()
        ]

        # 计算 MA
        ma5 = calculate_ma(daily["收盘"], 5).tolist() if len(daily) >= 5 else []
        ma10 = calculate_ma(daily["收盘"], 10).tolist() if len(daily) >= 10 else []
        ma20 = calculate_ma(daily["收盘"], 20).tolist() if len(daily) >= 20 else []
        ma60 = calculate_ma(daily["收盘"], 60).tolist() if len(daily) >= 60 else []

        kline = (
            Kline(init_opts=opts.InitOpts(
                theme=ThemeType.DARK,
                width="100%",
                height="480px",
                bg_color="#0d1117"
            ))
            .add_xaxis(dates)
            .add_yaxis("K线", ohlc,
                       itemstyle_opts=opts.ItemStyleOpts(
                           color="#f85149", color0="#3fb950",
                           border_color="#f85149", border_color0="#3fb950"
                       ))
            .set_global_opts(
                title_opts=opts.TitleOpts(title=f"{code} K线走势",
                                         title_textstyle_opts=opts.TextStyleOpts(color="#e6edf3")),
                tooltip_opts=opts.TooltipOpts(trigger="axis", axis_pointer_type="cross"),
                legend_opts=opts.LegendOpts(is_show=True, textstyle_opts=opts.TextStyleOpts(color="#e6edf3")),
                datazoom_opts=[opts.DataZoomOpts(type_="inside")],
                xaxis_opts=opts.AxisOpts(
                    type_="category",
                    axislabel_opts=opts.LabelOpts(rotate=45, color="#8b949e", font_size=10),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                ),
                yaxis_opts=opts.AxisOpts(
                    type_="value",
                    splitline_opts=opts.SplitLineOpts(
                        is_show=True,
                        linestyle_opts=opts.LineStyleOpts(color="#30363d", width=0.5)
                    ),
                    axislabel_opts=opts.LabelOpts(color="#8b949e"),
                ),
            )
        )

        # 添加 MA 均线（作为 Line 图表叠加）
        line_ma = Line(init_opts=opts.InitOpts(bg_color="#0d1117"))
        line_ma.add_xaxis(dates)

        if ma5:
            ma5_filled = [None] * (len(dates) - len(ma5)) + [
                v if not (v is None or pd.isna(v)) else None for v in ma5
            ]
            line_ma.add_yaxis("MA5", ma5_filled,
                             linestyle_opts=opts.LineStyleOpts(color="#ff7f50", width=1),
                             label_opts=opts.LabelOpts(is_show=False),
                             is_connect_nones=True)
        if ma10:
            ma10_filled = [None] * (len(dates) - len(ma10)) + [
                v if not (v is None or pd.isna(v)) else None for v in ma10
            ]
            line_ma.add_yaxis("MA10", ma10_filled,
                             linestyle_opts=opts.LineStyleOpts(color="#f0e68c", width=1),
                             label_opts=opts.LabelOpts(is_show=False),
                             is_connect_nones=True)
        if ma20:
            ma20_filled = [None] * (len(dates) - len(ma20)) + [
                v if not (v is None or pd.isna(v)) else None for v in ma20
            ]
            line_ma.add_yaxis("MA20", ma20_filled,
                             linestyle_opts=opts.LineStyleOpts(color="#87ceeb", width=1),
                             label_opts=opts.LabelOpts(is_show=False),
                             is_connect_nones=True)

        kline = kline.overlap(line_ma)
        return kline

    def _create_volume_chart(self, daily: pd.DataFrame) -> Bar:
        """创建成交量柱状图"""
        dates = daily["日期"].astype(str).tolist()
        volume = (daily["成交量"] / 10000).tolist()  # 万手
        close = daily["收盘"].tolist()

        # 红绿柱：收盘价>=开盘价=红
        colors = ["#f85149" if close[i] >= daily["开盘"].iloc[i] else "#3fb950" for i in range(len(daily))]

        bar = (
            Bar(init_opts=opts.InitOpts(theme=ThemeType.DARK, width="100%", height="200px", bg_color="#0d1117"))
            .add_xaxis(dates)
            .add_yaxis("成交量(万手)", volume,
                       itemstyle_opts=opts.ItemStyleOpts(color=colors),
                       label_opts=opts.LabelOpts(is_show=False))
            .set_global_opts(
                title_opts=opts.TitleOpts(title="成交量",
                                         title_textstyle_opts=opts.TextStyleOpts(color="#e6edf3")),
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=45, color="#8b949e", font_size=9),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                ),
                yaxis_opts=opts.AxisOpts(
                    splitline_opts=opts.SplitLineOpts(
                        is_show=True,
                        linestyle_opts=opts.LineStyleOpts(color="#30363d", width=0.5)
                    ),
                    axislabel_opts=opts.LabelOpts(color="#8b949e"),
                ),
                datazoom_opts=[opts.DataZoomOpts(type_="inside")],
            )
        )
        return bar

    def _create_macd_chart(self, daily: pd.DataFrame) -> Bar:
        """创建 MACD 柱状图"""
        dates = daily["日期"].astype(str).tolist()
        dif, dea, macd_bar = calculate_macd(daily["收盘"])
        macd_values = [v if not (v is None or pd.isna(v) or v != v) else 0 for v in macd_bar.tolist()]

        macd_colors = ["#f85149" if v >= 0 else "#3fb950" for v in macd_values]

        bar = (
            Bar(init_opts=opts.InitOpts(theme=ThemeType.DARK, width="100%", height="200px", bg_color="#0d1117"))
            .add_xaxis(dates)
            .add_yaxis("MACD", macd_values,
                       itemstyle_opts=opts.ItemStyleOpts(color=macd_colors),
                       label_opts=opts.LabelOpts(is_show=False))
            .set_global_opts(
                title_opts=opts.TitleOpts(title="MACD",
                                         title_textstyle_opts=opts.TextStyleOpts(color="#e6edf3")),
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                xaxis_opts=opts.AxisOpts(
                    axislabel_opts=opts.LabelOpts(rotate=45, color="#8b949e", font_size=9),
                    splitline_opts=opts.SplitLineOpts(is_show=False),
                ),
                yaxis_opts=opts.AxisOpts(
                    splitline_opts=opts.SplitLineOpts(
                        is_show=True,
                        linestyle_opts=opts.LineStyleOpts(color="#30363d", width=0.5)
                    ),
                    axislabel_opts=opts.LabelOpts(color="#8b949e"),
                ),
                datazoom_opts=[opts.DataZoomOpts(type_="inside")],
            )
        )

        # 添加 DIF/DEA 线
        dif_values = [v if not (v is None or pd.isna(v) or v != v) else None for v in dif.tolist()]
        dea_values = [v if not (v is None or pd.isna(v) or v != v) else None for v in dea.tolist()]

        line_dif = (
            Line()
            .add_xaxis(dates)
            .add_yaxis("DIF", dif_values,
                       linestyle_opts=opts.LineStyleOpts(color="#58a6ff", width=1),
                       label_opts=opts.LabelOpts(is_show=False),
                       is_connect_nones=True)
        )
        line_dea = (
            Line()
            .add_xaxis(dates)
            .add_yaxis("DEA", dea_values,
                       linestyle_opts=opts.LineStyleOpts(color="#ff7f50", width=1),
                       label_opts=opts.LabelOpts(is_show=False),
                       is_connect_nones=True)
        )
        bar = bar.overlap(line_dif).overlap(line_dea)
        return bar

    def _create_rsi_chart(self, daily: pd.DataFrame) -> Line:
        """创建 RSI 指标图"""
        dates = daily["日期"].astype(str).tolist()
        rsi6 = calculate_rsi(daily["收盘"], 6).tolist()
        rsi12 = calculate_rsi(daily["收盘"], 12).tolist()
        rsi24 = calculate_rsi(daily["收盘"], 24).tolist()

        line = (
            Line(init_opts=opts.InitOpts(theme=ThemeType.DARK, width="100%", height="200px", bg_color="#0d1117"))
            .add_xaxis(dates)
            .add_yaxis("RSI(6)", rsi6,
                       linestyle_opts=opts.LineStyleOpts(color="#f85149", width=1),
                       label_opts=opts.LabelOpts(is_show=False),
                       is_connect_nones=True)
            .add_yaxis("RSI(12)", rsi12,
                       linestyle_opts=opts.LineStyleOpts(color="#58a6ff", width=1),
                       label_opts=opts.LabelOpts(is_show=False),
                       is_connect_nones=True)
            .add_yaxis("RSI(24)", rsi24,
                       linestyle_opts=opts.LineStyleOpts(color="#3fb950", width=1),
                       label_opts=opts.LabelOpts(is_show=False),
                       is_connect_nones=True)
            .set_global_opts(
                title_opts=opts.TitleOpts(title="RSI 相对强弱指标（超买>70, 超卖<30）",
                                         title_textstyle_opts=opts.TextStyleOpts(color="#e6edf3")),
                tooltip_opts=opts.TooltipOpts(trigger="axis"),
                xaxis_opts=opts.AxisOpts(axislabel_opts=opts.LabelOpts(rotate=45, color="#8b949e", font_size=9)),
                yaxis_opts=opts.AxisOpts(
                    min_=0, max_=100,
                    splitline_opts=opts.SplitLineOpts(
                        is_show=True,
                        linestyle_opts=opts.LineStyleOpts(color="#30363d", width=0.5)
                    ),
                    axislabel_opts=opts.LabelOpts(color="#8b949e"),
                ),
                datazoom_opts=[opts.DataZoomOpts(type_="inside")],
            )
        )
        return line
