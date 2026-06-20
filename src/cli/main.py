"""StockHelper 主 CLI 入口"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).parent.parent.parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.columns import Columns

from src.cli.stock_commands import register_stock_commands
from src.cli.chain_commands import register_chain_commands
from src.cli.signal_commands import register_signal_commands


console = Console()


@click.group()
@click.version_option(version="0.1.0", prog_name="StockHelper")
def cli():
    """StockHelper - 智能股票数据分析助手

    面向个人投资者的轻量级智能股票数据分析工具。
    支持产业链按需调研、业绩爆发增长筛选、技术分析等核心功能。
    """


# 注册子命令
register_stock_commands(cli)
register_chain_commands(cli)
register_signal_commands(cli)


@cli.command()
def dashboard():
    """查看综合看板"""
    from src.collector import DataCollector

    collector = DataCollector()

    console.print(Panel.fit(
        "[bold]📊 StockHelper 综合看板[/bold]\n"
        "加载中...",
        border_style="blue"
    ))

    # 加载自选股列表
    from src.utils.portfolio import PortfolioManager
    pm = PortfolioManager()
    stocks = pm.list_stocks()

    if not stocks:
        console.print("[yellow]⚠ 暂无自选股，请先用 [bold]stock add <code>[/bold] 添加[/yellow]")
        return

    # 获取实时行情
    table = Table(
        title="📊 自选股看板",
        box=box.ROUNDED,
        header_style="bold cyan"
    )
    table.add_column("股票", style="bold")
    table.add_column("最新价", justify="right")
    table.add_column("涨跌幅", justify="right")
    table.add_column("涨跌额", justify="right")
    table.add_column("成交量", justify="right")
    table.add_column("信号", style="bold")

    for stock in stocks[:20]:
        code = stock.get("code", "")
        quote = collector.get_realtime_quote(code)
        if "error" in quote:
            continue

        change = quote.get("change_pct", 0)
        change_str = f"[green]+{change:.2f}%[/green]" if change >= 0 else f"[red]{change:.2f}%[/red]"

        volume = quote.get("volume", 0)
        if volume > 1e8:
            vol_str = f"{volume / 1e8:.2f}亿"
        elif volume > 1e4:
            vol_str = f"{volume / 1e4:.2f}万"
        else:
            vol_str = str(int(volume))

        table.add_row(
            f"{stock.get('name', code)}",
            f"{quote.get('price', 0):.2f}",
            change_str,
            f"{quote.get('change_amt', 0):+.2f}",
            vol_str,
            "—"
        )

    console.print(table)


@cli.command()
def screener():
    """选股筛选器 — 业绩爆发增长扫描"""
    from src.analyzer.growth_screener import GrowthScreener

    console.print(Panel.fit(
        "[bold]🔍 全市场业绩爆发增长扫描[/bold]\n"
        "正在扫描全市场，请稍候...",
        border_style="green"
    ))

    screener = GrowthScreener()
    results = screener.scan_market(top_n=30)

    if not results:
        console.print("[yellow]⚠ 未找到符合条件的公司[/yellow]")
        return

    # 按标签分组展示
    breakout = [r for r in results if r.tag == "🔥"]
    high = [r for r in results if r.tag == "📈"]
    others = [r for r in results if r.tag not in ("🔥", "📈")][:10]

    if breakout:
        table = Table(
            title="🔥 业绩爆发（营收>50% 且 净利润>100%）",
            box=box.ROUNDED,
            header_style="bold red",
            show_lines=True
        )
        table.add_column("股票", style="bold")
        table.add_column("营收增速", justify="right")
        table.add_column("净利增速", justify="right")
        table.add_column("ROE", justify="right")
        table.add_column("毛利率", justify="right")
        table.add_column("PEG", justify="right")
        table.add_column("总分", justify="right")

        for r in breakout[:10]:
            table.add_row(
                f"{r.name}({r.code})",
                f"[green]+{r.revenue_yoy:.1f}%[/green]",
                f"[green]+{r.net_profit_yoy:.1f}%[/green]",
                f"{r.roe:.1f}%",
                f"{r.gross_margin:.1f}%",
                f"{r.peg:.2f}" if r.peg > 0 else "—",
                f"[bold]{r.total_score:.1f}[/bold]"
            )
        console.print(table)

    if high:
        table2 = Table(
            title="📈 高增长（营收>30% 且 净利润>50%）",
            box=box.ROUNDED,
            header_style="bold yellow"
        )
        table2.add_column("股票", style="bold")
        table2.add_column("营收增速", justify="right")
        table2.add_column("净利增速", justify="right")
        table2.add_column("ROE", justify="right")
        table2.add_column("总分", justify="right")

        for r in high[:10]:
            table2.add_row(
                f"{r.name}({r.code})",
                f"[green]+{r.revenue_yoy:.1f}%[/green]",
                f"[green]+{r.net_profit_yoy:.1f}%[/green]",
                f"{r.roe:.1f}%",
                f"[bold]{r.total_score:.1f}[/bold]"
            )
        console.print(table2)

    if others:
        console.print(f"\n[dim]...以及其他 {len(others)} 家公司[/dim]")


@cli.command()
@click.argument("code")
def report(code: str):
    """生成个股分析报告（含买卖信号+Pyecharts图表）"""
    from src.reporter.pyecharts_renderer import PyechartsReportGenerator
    from src.collector import DataCollector

    collector = DataCollector()

    with console.status(f"[bold green]正在生成 {code} 的分析报告...") as status:
        # 获取数据
        status.update("获取行情数据...")
        daily = collector.get_stock_daily(code)

        status.update("获取财务数据...")
        fin = collector.get_financial_data(code)

        status.update("生成专业图表报告...")
        renderer = PyechartsReportGenerator()
        report_path = renderer.generate(code, daily, fin)

    console.print(f"[green]✅ 报告已生成: {report_path}[/green]")
    console.print("[dim]提示: 用浏览器打开 HTML 文件即可查看交互式图表[/dim]")


def main():
    """CLI 入口函数"""
    cli()


if __name__ == "__main__":
    main()
