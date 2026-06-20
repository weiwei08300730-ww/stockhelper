"""买卖信号 CLI 命令"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich import box
from rich.columns import Columns

from src.collector import DataCollector
from src.analyzer.signal_engine import SignalEngine, SignalAction

console = Console()


def register_signal_commands(cli_group):
    """注册买卖信号命令到 CLI 组"""

    @cli_group.group()
    def signal():
        """买卖信号分析"""

    @signal.command("analyze")
    @click.argument("code")
    def analyze_signal(code: str):
        """分析个股买卖信号"""
        collector = DataCollector()

        with console.status(f"[bold yellow]正在分析 {code} 买卖信号...") as status:

            status.update("获取行情数据...")
            daily = collector.get_stock_daily(code)
            if daily.empty:
                console.print(f"[red]无法获取 {code} 的行情数据[/red]")
                console.print("[yellow]提示: 当前网络环境可能限制了数据接口访问。[/yellow]")
                console.print("[yellow]可尝试: 1. 检查网络连接 2. 使用代理 3. 稍后重试[/yellow]")
                return

            status.update("获取财务数据...")
            fin = collector.get_financial_data(code)

            status.update("计算多维度信号...")
            engine = SignalEngine()
            result = engine.analyze(code)

        name = result.name or fin.get("name", code)

        # 信号主标题
        action_colors = {
            SignalAction.STRONG_BUY: "bold red",
            SignalAction.BUY: "red",
            SignalAction.HOLD: "yellow",
            SignalAction.SELL: "green",
            SignalAction.STRONG_SELL: "bold green",
        }
        action_icons = {
            SignalAction.STRONG_BUY: "🟢🟢",
            SignalAction.BUY: "🟢",
            SignalAction.HOLD: "🟡",
            SignalAction.SELL: "🔴",
            SignalAction.STRONG_SELL: "🔴🔴",
        }

        color = action_colors.get(result.action, "white")
        icon = action_icons.get(result.action, "⚪")

        console.print(
            Panel.fit(
                f"[bold]{name} ({code})[/bold]\n"
                f"[{color}]{icon} {result.action.value} | 信心指数: {result.confidence}/100 | 综合评分: {result.total_score:.1f}[/{color}]",
                border_style=color
            )
        )

        # 维度评分表
        dim_table = Table(box=box.SIMPLE, header_style="bold cyan")
        dim_table.add_column("维度")
        dim_table.add_column("评分", justify="right")
        dim_table.add_column("权重")
        dim_table.add_column("状态")

        tech_status = "✅ 偏多" if result.technical_score >= 60 else ("⚠️ 中性" if result.technical_score >= 40 else "❌ 偏空")
        mom_status = "✅ 积极" if result.momentum_score >= 60 else ("⚠️ 中性" if result.momentum_score >= 40 else "❌ 不足")
        fund_status = "✅ 良好" if result.fundamental_score >= 60 else ("⚠️ 一般" if result.fundamental_score >= 40 else "❌ 较差")
        chain_status = "✅ 有利" if result.chain_score >= 60 else ("⚠️ 中性" if result.chain_score >= 40 else "❌ 不利")

        dim_table.add_row("[bold]技术面[/bold]", f"{result.technical_score:.0f}", "35%", tech_status)
        dim_table.add_row("[bold]资金动量[/bold]", f"{result.momentum_score:.0f}", "20%", mom_status)
        dim_table.add_row("[bold]基本面[/bold]", f"{result.fundamental_score:.0f}", "25%", fund_status)
        dim_table.add_row("[bold]产业链[/bold]", f"{result.chain_score:.0f}", "20%", chain_status)
        dim_table.add_row("[bold]综合[/bold]", f"[bold]{result.total_score:.1f}[/bold]", "100%",
                          f"{'偏多' if result.total_score >= 50 else '偏空'}")
        console.print(dim_table)

        # 技术指标详情
        if result.signals_detail:
            sig_table = Table(title="📊 技术指标信号详情", box=box.SIMPLE, header_style="bold yellow")
            sig_table.add_column("指标")
            sig_table.add_column("信号")
            for key, val in result.signals_detail.items():
                sig_table.add_row(key, val)
            console.print(sig_table)

        # 买入理由
        if result.reasons:
            console.print(f"\n[bold green]📌 {'买入理由' if result.action in (SignalAction.BUY, SignalAction.STRONG_BUY) else '分析要点'}[/bold green]")
            for r in result.reasons:
                console.print(f"  • {r}")

        # 风险提示
        if result.risks:
            console.print(f"\n[bold red]⚠️ 风险提示[/bold red]")
            for r in result.risks:
                console.print(f"  • {r}")

        # 交易参考
        console.print(f"\n[bold cyan]💰 交易参考[/bold cyan]")
        ref_table = Table(box=box.SIMPLE, header_style="bold cyan")
        ref_table.add_column("项目")
        ref_table.add_column("参考值", justify="right")
        ref_table.add_row("入场区间", f"{result.entry_low:.2f} - {result.entry_high:.2f}")
        ref_table.add_row("止损参考", f"{result.stop_loss:.2f}")
        ref_table.add_row("建议仓位", f"{result.risk_pct:.1f}%")
        if result.entry_low > 0:
            risk_ratio = (result.entry_low - result.stop_loss) / result.entry_low * 100
            ref_table.add_row("最大回撤", f"{risk_ratio:.1f}%")
        console.print(ref_table)

        console.print("\n[dim]⚠️ 本信号基于历史数据，不构成投资建议[/dim]")

    @signal.command("scan")
    @click.argument("codes", nargs=-1, required=False)
    @click.option("--top", "-t", default=20, help="扫描全市场前N只股票")
    def signal_scan(codes, top):
        """批量扫描信号（可指定股票代码列表，或扫描全市场热门股）"""
        engine = SignalEngine()
        collector = DataCollector()

        if codes:
            # 指定代码列表
            stock_list = list(codes)
        else:
            # 从自选股获取
            from src.utils.portfolio import PortfolioManager
            pm = PortfolioManager()
            stocks = pm.list_stocks()
            if stocks:
                stock_list = [s["code"] for s in stocks]
            else:
                # 从全市场取前N只
                try:
                    df = collector.get_stock_list()
                    stock_list = df["code"].head(top).tolist()
                except Exception:
                    console.print("[yellow]⚠ 请先添加自选股或指定股票代码[/yellow]")
                    return

        with console.status(f"[bold green]正在扫描 {len(stock_list)} 只股票的信号...") as status:
            results = engine.batch_analyze(stock_list)

        # 按信号分类
        strong_buy = [r for r in results if r.action == SignalAction.STRONG_BUY]
        buy = [r for r in results if r.action == SignalAction.BUY]
        hold = [r for r in results if r.action == SignalAction.HOLD]
        sell = [r for r in results if r.action in (SignalAction.SELL, SignalAction.STRONG_SELL)]

        # 展示结果
        if strong_buy:
            sb_table = Table(
                title=f"🟢🟢 强买入信号 ({len(strong_buy)}只)",
                box=box.ROUNDED,
                header_style="bold red"
            )
            sb_table.add_column("股票")
            sb_table.add_column("评分", justify="right")
            sb_table.add_column("技术", justify="right")
            sb_table.add_column("动量", justify="right")
            sb_table.add_column("基本面", justify="right")
            sb_table.add_column("入场区间")
            sb_table.add_column("止损", justify="right")
            for r in strong_buy[:10]:
                sb_table.add_row(
                    f"{r.name}({r.code})",
                    f"[bold]{r.total_score:.0f}[/bold]",
                    f"{r.technical_score:.0f}",
                    f"{r.momentum_score:.0f}",
                    f"{r.fundamental_score:.0f}",
                    f"{r.entry_low:.2f}-{r.entry_high:.2f}",
                    f"{r.stop_loss:.2f}"
                )
            console.print(sb_table)

        if buy:
            b_table = Table(
                title=f"🟢 买入信号 ({len(buy)}只)",
                box=box.ROUNDED,
                header_style="bold yellow"
            )
            b_table.add_column("股票")
            b_table.add_column("评分", justify="right")
            b_table.add_column("入场区间")
            b_table.add_column("止损", justify="right")
            for r in buy[:10]:
                b_table.add_row(
                    f"{r.name}({r.code})",
                    f"{r.total_score:.0f}",
                    f"{r.entry_low:.2f}-{r.entry_high:.2f}",
                    f"{r.stop_loss:.2f}"
                )
            console.print(b_table)

        if sell:
            console.print(f"\n[bold red]🔴 卖出/观望信号: {len(sell)}只[/bold red]")
            console.print(", ".join(f"{r.name}({r.code})" for r in sell[:10]))

        console.print(f"\n[dim]共扫描 {len(results)}只 | 🟢🟢强买{len(strong_buy)} 🟢买入{len(buy)} 🟡持有{len(hold)} 🔴卖出{len(sell)}[/dim]")
