"""HTML 分析报告生成器

参考 ZBS-Stock-Screener 的 html_renderer 设计：
- 深色/浅色双主题
- ECharts 交互式图表
- 自包含离线可查看
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from src.config import get_config, get_report_dir, PROJECT_ROOT
from src.analyzer import (
    calculate_ma, calculate_macd, calculate_rsi,
    calculate_kdj
)


class HtmlReportRenderer:
    """HTML 报告渲染器"""

    def __init__(self):
        cfg = get_config()
        report_cfg = cfg["report"]
        self.output_dir = get_report_dir()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.theme = report_cfg.get("theme", "dark")
        self.language = report_cfg.get("language", "zh")

    def generate(self, code: str, daily: pd.DataFrame,
                 fin_data: Dict[str, Any] = None,
                 chain_info: Optional[Dict] = None) -> str:
        """生成个股分析报告"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        stock_name = fin_data.get("name", code) if fin_data else code

        # 计算指标
        charts = self._build_charts(daily)
        financials = self._build_financials(fin_data)

        html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{stock_name}({code}) 分析报告 — StockHelper</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.6.0/dist/echarts.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Noto Sans SC', sans-serif;
       background: {'#0d1117' if self.theme == 'dark' else '#ffffff'};
       color: {'#e6edf3' if self.theme == 'dark' else '#24292f'};
       line-height: 1.6; padding: 20px; }}
.container {{ max-width: 1200px; margin: 0 auto; }}
.header {{ text-align: center; padding: 30px 0; border-bottom: 1px solid {'#30363d' if self.theme == 'dark' else '#d0d7de'}; margin-bottom: 30px; }}
.header h1 {{ font-size: 28px; margin-bottom: 5px; }}
.header .subtitle {{ color: {'#8b949e' if self.theme == 'dark' else '#656d76'}; font-size: 14px; }}
.section {{ margin-bottom: 30px; }}
.section h2 {{ font-size: 20px; padding-bottom: 10px; border-bottom: 1px solid {'#30363d' if self.theme == 'dark' else '#d0d7de'}; margin-bottom: 15px; }}
.chart-box {{ background: {'#161b22' if self.theme == 'dark' else '#f6f8fa'}; border-radius: 8px; padding: 15px; margin-bottom: 20px; }}
.chart-box .chart {{ width: 100%; height: 450px; }}
.card-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
.card {{ background: {'#161b22' if self.theme == 'dark' else '#f6f8fa'}; border-radius: 8px; padding: 15px; text-align: center; }}
.card .value {{ font-size: 24px; font-weight: bold; margin: 8px 0; }}
.card .label {{ font-size: 12px; color: {'#8b949e' if self.theme == 'dark' else '#656d76'}; }}
.up {{ color: #f85149; }}
.down {{ color: #3fb950; }}
table {{ width: 100%; border-collapse: collapse; margin: 15px 0; }}
th, td {{ padding: 10px 12px; text-align: left; border-bottom: 1px solid {'#30363d' if self.theme == 'dark' else '#d0d7de'}; }}
th {{ background: {'#161b22' if self.theme == 'dark' else '#f6f8fa'}; font-weight: 600; }}
.footer {{ text-align: center; padding: 30px 0; margin-top: 40px; border-top: 1px solid {'#30363d' if self.theme == 'dark' else '#d0d7de'}; color: {'#8b949e' if self.theme == 'dark' else '#656d76'}; font-size: 12px; }}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>{stock_name} <span style="color: #58a6ff;">({code})</span></h1>
        <div class="subtitle">生成时间: {now} | StockHelper 智能分析报告</div>
    </div>

    <div class="section">
        <h2>📊 核心指标</h2>
        {financials}
    </div>

    <div class="section">
        <h2>📈 行情走势</h2>
        {charts}
    </div>

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
            f.write(html)

        return str(file_path)

    def _build_financials(self, fin_data: Optional[Dict]) -> str:
        """构建财务概览 HTML"""
        if not fin_data or "error" in fin_data:
            return '<div class="card"><p>暂无财务数据</p></div>'

        cards = ""
        items = [
            ("营收增速", f"{fin_data.get('revenue_yoy', 0):+.1f}%",
             "up" if fin_data.get('revenue_yoy', 0) > 0 else "down"),
            ("净利增速", f"{fin_data.get('net_profit_yoy', 0):+.1f}%",
             "up" if fin_data.get('net_profit_yoy', 0) > 0 else "down"),
            ("ROE", f"{fin_data.get('roe', 0):.1f}%", ""),
            ("毛利率", f"{fin_data.get('gross_margin', 0):.1f}%", ""),
            ("PE", f"{fin_data.get('pe', 0):.1f}", ""),
            ("PB", f"{fin_data.get('pb', 0):.1f}", ""),
        ]

        for label, value, cls in items:
            cls_str = f' class="{cls}"' if cls else ""
            cards += f"""
            <div class="card">
                <div class="label">{label}</div>
                <div class="value"{cls_str}>{value}</div>
            </div>"""

        return f'<div class="card-grid">{cards}</div>'

    def _build_charts(self, daily: pd.DataFrame) -> str:
        """构建 ECharts 图表的 HTML"""
        if daily.empty:
            return "<p>暂无行情数据</p>"

        try:
            dates = daily["日期"].astype(str).tolist()
            close = daily["收盘"].tolist()
            open_p = daily["开盘"].tolist()
            high = daily["最高"].tolist()
            low = daily["最低"].tolist()
            volume = (daily["成交量"] / 10000).tolist()  # 万手
        except (KeyError, Exception):
            return "<p>数据格式异常，无法绘制图表</p>"

        kline_data = []
        for i in range(len(dates)):
            kline_data.append([open_p[i], close[i], low[i], high[i]])

        chart_id = "kline_chart"

        return f"""
        <div class="chart-box">
            <div id="{chart_id}" class="chart"></div>
        </div>
        <script>
        (function() {{
            var chart = echarts.init(document.getElementById('{chart_id}'));
            var dates = {json.dumps(dates)};
            var klineData = {json.dumps(kline_data)};
            var volumeData = {json.dumps(volume)};

            var option = {{
                tooltip: {{ trigger: 'axis', axisPointer: {{ type: 'cross' }} }},
                legend: {{ data: ['K线', 'MA5', 'MA10', 'MA20', '成交量'],
                         textStyle: {{ color: '{'#e6edf3' if self.theme == 'dark' else '#24292f'}'}} }},
                grid: [
                    {{ left: '10%', right: '10%', top: 60, height: '55%' }},
                    {{ left: '10%', right: '10%', top: '75%', height: '15%' }}
                ],
                xAxis: [
                    {{ type: 'category', data: dates, gridIndex: 0,
                       axisLabel: {{ rotate: 45, fontSize: 10,
                       color: '{'#8b949e' if self.theme == 'dark' else '#656d76'}' }} }},
                    {{ type: 'category', data: dates, gridIndex: 1,
                       axisLabel: {{ show: false }} }}
                ],
                yAxis: [
                    {{ type: 'value', gridIndex: 0, scale: true,
                       splitLine: {{ lineStyle: {{ color: '{'#30363d' if self.theme == 'dark' else '#d0d7de'}' }} }}}},
                    {{ type: 'value', gridIndex: 1, scale: true,
                       splitLine: {{ show: false }} }}
                ],
                dataZoom: [{{ type: 'inside', xAxisIndex: [0,1] }}],
                series: [
                    {{
                        name: 'K线', type: 'candlestick', xAxisIndex: 0, yAxisIndex: 0,
                        itemStyle: {{ color: '#f85149', color0: '#3fb950',
                                     borderColor: '#f85149', borderColor0: '#3fb950' }},
                        data: klineData
                    }},
                    {{
                        name: '成交量', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
                        data: volumeData.map(function(v) {{ return v / 10; }}),
                        itemStyle: {{ color: '#58a6ff' }}
                    }}
                ]
            }};
            chart.setOption(option);
            window.addEventListener('resize', function() {{ chart.resize(); }});
        }})();
        </script>"""
