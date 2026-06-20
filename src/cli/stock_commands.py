"""股票相关 CLI 命令"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box

from src.collector import DataCollector
from src.analyzer import (
    calculate_ma, calculate_macd, calculate_rsi,
    calculate_kdj, calculate_boll, generate_signals
)
from src.utils.portfolio import PortfolioManager

console = Console()


def register_stock_commands(cli_group):
    """注册股票命令到 CLI 组"""

    @cli_group.group()
    def stock():
        """股票相关操作"""

    @stock.command("list")
    def list_stocks():
        """查看自选股列表"""
        pm = PortfolioManager()
        stocks = pm.list_stocks()

        if not stocks:
            console.print("[yellow]⚠ 自选股列表为空[/yellow]")
            console.print("使用 [bold]stock add <code>[/bold] 添加股票")
            return

        table = Table(title="📋 自选股列表", box=box.ROUNDED, header_style="bold cyan")
        table.add_column("序号", justify="right")
        table.add_column("代码", style="bold")
        table.add_column("名称")
        table.add_column("分组")
        table.add_column("添加时间")

        for i, s in enumerate(stocks, 1):
            table.add_row(
                str(i),
                s.get("code", ""),
                s.get("name", ""),
                s.get("group", "默认"),
                s.get("added_at", "")
            )
        console.print(table)

    @stock.command("add")
    @click.argument("code")
    @click.option("--group", "-g", default="默认", help="分组名称")
    def add_stock(code: str, group: str):
        """添加自选股"""
        collector = DataCollector()
        pm = PortfolioManager()

        if not collector.validate_code(code):
            # 尝试搜索
            results = collector.search_stock(code)
            if results:
                console.print(f"找到以下匹配结果:")
                for r in results[:5]:
                    console.print(f"  {r.get('code', '')} - {r.get('name', '')}")
                console.print("[yellow]请使用完整股票代码重试[/yellow]")
            else:
                console.print(f"[red]❌ 无效股票代码: {code}[/red]")
            return

        pm.add_stock(code, group)
        console.print(f"[green]✅ 已添加 {code} 到「{group}」分组[/green]")

    @stock.command("remove")
    @click.argument("code")
    def remove_stock(code: str):
        """删除自选股"""
        pm = PortfolioManager()
        if pm.remove_stock(code):
            console.print(f"[green]✅ 已删除 {code}[/green]")
        else:
            console.print(f"[yellow]⚠ 未找到 {code}[/yellow]")

    @stock.command("detail")
    @click.argument("code")
    def detail_stock(code: str):
        """查看个股详情与技术指标"""
        collector = DataCollector()

        with console.status(f"[bold green]正在获取 {code} 的数据..."):

            # 获取行情
            daily = collector.get_stock_daily(code, end_date="20260619")
            if daily.empty:
                console.print(f"[red]❌ 无法获取 {code} 的行情数据[/red]")
                return

            # 获取财务
            fin = collector.get_financial_data(code)

            # 获取实时行情
            quote = collector.get_realtime_quote(code)

        # 基本信息
        name = fin.get("name", "") or daily.iloc[0].get("名称", code)
        console.print(
            Panel.fit(
                f"[bold]{name} ({code})[/bold]\n"
                f"最新价: {quote.get('price', '—')}   "
                f"涨跌幅: {quote.get('change_pct', '—')}%",
                border_style="blue"
            )
        )

        # 财务摘要
        if "error" not in fin:
            fin_table = Table(title="📊 财务概览", box=box.SIMPLE, header_style="bold cyan")
            fin_table.add_column("指标")
            fin_table.add_column("数值", justify="right")
            fin_table.add_row("营收增速", f"{fin.get('revenue_yoy', 0):+.2f}%")
            fin_table.add_row("净利增速", f"{fin.get('net_profit_yoy', 0):+.2f}%")
            fin_table.add_row("ROE", f"{fin.get('roe', 0):.2f}%")
            fin_table.add_row("毛利率", f"{fin.get('gross_margin', 0):.2f}%")
            fin_table.add_row("PE", f"{fin.get('pe', 0):.2f}")
            fin_table.add_row("PB", f"{fin.get('pb', 0):.2f}")
            console.print(fin_table)

        # 技术指标
        try:
            close = daily["收盘"]
            high = daily["最高"]
            low = daily["最低"]

            if len(close) >= 60:
                ma5 = calculate_ma(close, 5).iloc[-1]
                ma10 = calculate_ma(close, 10).iloc[-1]
                ma20 = calculate_ma(close, 20).iloc[-1]
                ma60 = calculate_ma(close, 60).iloc[-1]
                dif, dea, macd_bar = calculate_macd(close)
                rsi = calculate_rsi(close, 14)
                k, d, j = calculate_kdj(high, low, close)
                upper, mid, lower = calculate_boll(close)
                signal = generate_signals(dif, dea, rsi, k, d)

                tech_table = Table(title="📈 技术指标", box=box.SIMPLE, header_style="bold yellow")
                tech_table.add_column("指标")
                tech_table.add_column("数值", justify="right")
                tech_table.add_row("MA5", f"{ma5:.2f}")
                tech_table.add_row("MA10", f"{ma10:.2f}")
                tech_table.add_row("MA20", f"{ma20:.2f}")
                tech_table.add_row("MA60", f"{ma60:.2f}")
                tech_table.add_row("MACD", f"DIF={dif.iloc[-1]:.3f} DEA={dea.iloc[-1]:.3f}")
                tech_table.add_row("RSI(14)", f"{rsi.iloc[-1]:.1f}")
                tech_table.add_row("KDJ", f"K={k.iloc[-1]:.1f} D={d.iloc[-1]:.1f} J={j.iloc[-1]:.1f}")
                tech_table.add_row("BOLL", f"上={upper.iloc[-1]:.2f} 中={mid.iloc[-1]:.2f} 下={lower.iloc[-1]:.2f}")
                tech_table.add_row("信号", f"[bold]{signal}[/bold]")
                console.print(tech_table)

        except Exception as e:
            console.print(f"[dim]技术指标计算异常: {e}[/dim]")

        # 底部：买卖信号摘要
        try:
            from src.analyzer.signal_engine import SignalEngine

            sig_result = SignalEngine().analyze(code)

            action_icons = {
                "STRONG_BUY": "[bold red]强买入[/bold red]",
                "BUY": "[red]买入[/red]",
                "HOLD": "[yellow]持有[/yellow]",
                "SELL": "[green]卖出[/green]",
                "STRONG_SELL": "[bold green]强卖出[/bold green]",
            }

            sig_str = action_icons.get(sig_result.action.name, "[yellow]待定[/yellow]")
            score_bar = "#" * int(sig_result.total_score / 10) + "-" * (10 - int(sig_result.total_score / 10))

            sig_panel = Panel.fit(
                f"[bold]综合信号: {sig_str}[/bold]  |  评分: {sig_result.total_score:.1f}/100  |  信心: {sig_result.confidence}/100\n"
                f"技术面 {sig_result.technical_score:.0f} / 动量 {sig_result.momentum_score:.0f} / "
                f"基本面 {sig_result.fundamental_score:.0f} / 产业链 {sig_result.chain_score:.0f}\n"
                f"[dim]{score_bar}[/dim]  {sig_result.reasons[0] if sig_result.reasons else ''}",
                border_style="blue",
                title="买卖信号摘要"
            )
            console.print(sig_panel)

        except Exception:
            pass
