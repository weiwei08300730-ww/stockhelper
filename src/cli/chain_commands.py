"""产业链相关 CLI 命令（核心差异功能）"""

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.tree import Tree
from rich import box
from rich.columns import Columns
from rich.text import Text

from src.industry_chain import IndustryChainResearcher
from src.analyzer.growth_screener import GrowthScreener

console = Console()


def register_chain_commands(cli_group):
    """注册产业链命令到 CLI 组"""

    @cli_group.group()
    def chain():
        """产业链分析（核心功能）"""

    @chain.command("research")
    @click.argument("industry")
    @click.option("--force", "-f", is_flag=True, help="强制重新调研")
    def research_chain(industry: str, force: bool):
        """调研指定产业链并生成全景图谱（核心功能）

        INDUSTRY: 产业名称，如"低空经济""固态电池""人形机器人"
        """
        researcher = IndustryChainResearcher()

        with console.status(f"[bold green]正在调研 [{industry}] 产业链...") as status:

            status.update("搜索产业信息...")
            chain_data = researcher.research_chain(industry, force=force)

            status.update("构建产业链图谱...")
            bottlenecks = researcher.analyze_bottlenecks(chain_data)

            status.update("获取增长数据...")

        # 展示结果
        # 标题
        source_tag = "📦 基线" if chain_data.source == "builtin" else "🔍 调研"
        console.print(
            Panel.fit(
                f"[bold cyan]{'='*50}[/bold cyan]\n"
                f"[bold]{industry}产业链全景图[/bold]\n"
                f"{chain_data.description}\n"
                f"[dim]来源: {source_tag} | 调研时间: {chain_data.researched_at or '—'}[/dim]\n"
                f"[bold cyan]{'='*50}[/bold cyan]",
                border_style="cyan"
            )
        )

        # 图谱展示
        tree = Tree(f"[bold]{industry}产业链[/bold]")
        for node in chain_data.nodes:
            sub = tree.add(f"[yellow]{node.name}[/yellow]")
            sub.add(f"[dim]{node.description}[/dim]")
            companies = node.companies[:5]
            if companies:
                comp_str = "  ".join(
                    f"{c.get('name', '')}({c.get('code', '')})"
                    for c in companies
                )
                sub.add(f"[green]{comp_str}[/green]")
            if len(node.companies) > 5:
                sub.add(f"[dim]...及其他 {len(node.companies) - 5} 家[/dim]")

        console.print(tree)

        # 瓶颈分析
        b_table = Table(
            title="🔍 产业链瓶颈分析（参考 Serenity 方法论）",
            box=box.ROUNDED,
            header_style="bold magenta"
        )
        b_table.add_column("环节", style="bold")
        b_table.add_column("公司数", justify="right")
        b_table.add_column("瓶颈评分", justify="right")
        b_table.add_column("分析")
        for b in bottlenecks:
            b_table.add_row(
                b["segment"],
                str(b["company_count"]),
                f"{b['bottleneck_score']}/10 {b['level']}",
                b["analysis"]
            )
        console.print(b_table)

        # 增长筛选
        console.print("\n[bold]📈 产业链内业绩增长标的筛选:[/bold]")
        for node in chain_data.nodes:
            if node.companies:
                screener = GrowthScreener()
                scores = screener.scan_industry_chain(node.companies)
                top_growth = [s for s in scores if s.tag in ("🔥", "📈")][:3]
                if top_growth:
                    g_table = Table(
                        title=f"{node.name} 增长标的",
                        box=box.SIMPLE,
                        header_style="bold green",
                        show_header=True
                    )
                    g_table.add_column("股票")
                    g_table.add_column("标签")
                    g_table.add_column("营收增速", justify="right")
                    g_table.add_column("净利增速", justify="right")
                    g_table.add_column("评分", justify="right")

                    for s in top_growth:
                        g_table.add_row(
                            f"{s.name}({s.code})",
                            f"{s.tag}{s.tag_label}",
                            f"[green]+{s.revenue_yoy:.1f}%[/green]",
                            f"[green]+{s.net_profit_yoy:.1f}%[/green]",
                            f"[bold]{s.total_score:.1f}[/bold]"
                        )
                    console.print(g_table)

    @chain.command("view")
    @click.argument("industry")
    def view_chain(industry: str):
        """查看已缓存的产业链详情"""
        researcher = IndustryChainResearcher()
        chain_data = researcher.get_chain(industry)

        if chain_data is None:
            console.print(
                f"[yellow]⚠ 未找到 [{industry}] 的缓存数据[/yellow]\n"
                f"请先使用 [bold]chain research {industry}[/bold] 进行调研"
            )
            return

        console.print(
            Panel.fit(
                f"[bold]{industry}产业链[/bold] ({chain_data.source})\n"
                f"{chain_data.description}",
                border_style="cyan"
            )
        )

        for node in chain_data.nodes:
            console.print(f"\n[yellow]▶ {node.name}[/yellow]")
            console.print(f"  {node.description}")
            for comp in node.companies[:8]:
                console.print(f"  • {comp.get('name', '')} ({comp.get('code', '')})")
            if len(node.companies) > 8:
                console.print(f"  [dim]...及其他 {len(node.companies) - 8} 家[/dim]")

    @chain.command("list")
    def list_chains():
        """查看已调研过的产业链列表"""
        researcher = IndustryChainResearcher()
        chains = researcher.get_available_chains()

        if not chains:
            console.print("[yellow]⚠ 暂无产业链数据[/yellow]")
            return

        table = Table(
            title="📋 可用产业链列表",
            box=box.ROUNDED,
            header_style="bold cyan"
        )
        table.add_column("产业链名称", style="bold")
        table.add_column("环节数", justify="right")
        table.add_column("来源")
        table.add_column("描述")

        for c in chains:
            source_str = "📦 内置" if c["source"] == "builtin" else "🔍 调研"
            table.add_row(
                c["name"],
                str(c["node_count"]),
                source_str,
                c.get("description", "")[:60]
            )
        console.print(table)

    @chain.command("refresh")
    @click.argument("industry")
    def refresh_chain(industry: str):
        """重新调研更新产业链数据"""
        researcher = IndustryChainResearcher()

        with console.status(f"[bold green]正在重新调研 [{industry}] 产业链..."):
            chain_data = researcher.refresh_chain(industry)

        console.print(f"[green]✅ 已更新 [{industry}] 产业链数据[/green]")
        console.print(f"共 {len(chain_data.nodes)} 个环节，{sum(len(n.companies) for n in chain_data.nodes)} 家公司")

    @chain.command("compare")
    @click.argument("industry")
    @click.option("--segment", "-s", default=None, help="指定环节名称")
    def compare_companies(industry: str, segment: str):
        """对比产业链各环节公司财务数据"""
        researcher = IndustryChainResearcher()
        chain_data = researcher.get_chain(industry)

        if chain_data is None:
            console.print(f"[yellow]⚠ 请先使用 [bold]chain research {industry}[/bold] 调研该产业链[/yellow]")
            return

        from src.collector import DataCollector
        collector = DataCollector()

        nodes_to_show = [n for n in chain_data.nodes
                        if segment is None or segment in n.name]

        for node in nodes_to_show:
            if not node.companies:
                continue

            table = Table(
                title=f"📊 {node.name} — 财务对比",
                box=box.ROUNDED,
                header_style="bold cyan"
            )
            table.add_column("公司", style="bold")
            table.add_column("营收增速", justify="right")
            table.add_column("净利增速", justify="right")
            table.add_column("ROE", justify="right")
            table.add_column("毛利率", justify="right")
            table.add_column("PE", justify="right")

            for comp in node.companies[:8]:
                fin = collector.get_financial_data(comp.get("code", ""))
                if "error" not in fin:
                    table.add_row(
                        f"{comp.get('name', '')}",
                        f"{fin.get('revenue_yoy', 0):+.1f}%",
                        f"{fin.get('net_profit_yoy', 0):+.1f}%",
                        f"{fin.get('roe', 0):.1f}%",
                        f"{fin.get('gross_margin', 0):.1f}%",
                        f"{fin.get('pe', 0):.1f}"
                    )

            console.print(table)

    @chain.command("growth")
    @click.argument("industry")
    def chain_growth(industry: str):
        """产业链内业绩爆发增长筛选"""
        researcher = IndustryChainResearcher()
        chain_data = researcher.get_chain(industry)

        if chain_data is None:
            console.print(f"[yellow]⚠ 请先使用 [bold]chain research {industry}[/bold] 调研该产业链[/yellow]")
            return

        console.print(f"[bold]📈 正在扫描 [{industry}] 产业链内增长标的...[/bold]")

        screener = GrowthScreener()
        all_scores = []

        for node in chain_data.nodes:
            if node.companies:
                scores = screener.scan_industry_chain(node.companies)
                for s in scores:
                    s.metadata = {"segment": node.name}
                all_scores.extend(scores)

        all_scores.sort(key=lambda x: x.total_score, reverse=True)

        if not all_scores:
            console.print("[yellow]⚠ 未找到增长标的[/yellow]")
            return

        # 展示
        breakout = [s for s in all_scores if s.tag == "🔥"][:5]
        high = [s for s in all_scores if s.tag == "📈"][:5]

        if breakout:
            b_table = Table(
                title=f"🔥 {industry} 业绩爆发标的",
                box=box.ROUNDED,
                header_style="bold red"
            )
            b_table.add_column("股票")
            b_table.add_column("环节")
            b_table.add_column("营收增速", justify="right")
            b_table.add_column("净利增速", justify="right")
            b_table.add_column("ROE", justify="right")
            b_table.add_column("总分", justify="right")

            for s in breakout:
                b_table.add_row(
                    f"{s.name}({s.code})",
                    s.metadata.get("segment", ""),
                    f"[green]+{s.revenue_yoy:.1f}%[/green]",
                    f"[green]+{s.net_profit_yoy:.1f}%[/green]",
                    f"{s.roe:.1f}%",
                    f"[bold]{s.total_score:.1f}[/bold]"
                )
            console.print(b_table)

        if high:
            h_table = Table(
                title=f"📈 {industry} 高增长标的",
                box=box.ROUNDED,
                header_style="bold yellow"
            )
            h_table.add_column("股票")
            h_table.add_column("环节")
            h_table.add_column("营收增速", justify="right")
            h_table.add_column("净利增速", justify="right")
            h_table.add_column("总分", justify="right")

            for s in high:
                h_table.add_row(
                    f"{s.name}({s.code})",
                    s.metadata.get("segment", ""),
                    f"[green]+{s.revenue_yoy:.1f}%[/green]",
                    f"[green]+{s.net_profit_yoy:.1f}%[/green]",
                    f"[bold]{s.total_score:.1f}[/bold]"
                )
            console.print(h_table)

    @chain.command("boom")
    @click.argument("industry")
    def chain_boom(industry: str):
        """产业链景气度热力图"""
        researcher = IndustryChainResearcher()
        chain_data = researcher.get_chain(industry)

        if chain_data is None:
            console.print(f"[yellow]⚠ 请先使用 [bold]chain research {industry}[/bold] 调研该产业链[/yellow]")
            return

        bottlenecks = researcher.analyze_bottlenecks(chain_data)

        table = Table(
            title=f"🌡️ {industry} 产业链景气度热力图",
            box=box.ROUNDED,
            header_style="bold cyan"
        )
        table.add_column("环节")
        table.add_column("景气度")
        table.add_column("公司数", justify="right")
        table.add_column("瓶颈评分", justify="right")

        for b in bottlenecks:
            boom_level = b["level"]
            table.add_row(
                b["segment"],
                boom_level,
                str(b["company_count"]),
                f"{b['bottleneck_score']}/10"
            )
        console.print(table)
        console.print("\n[dim]🟢 低瓶颈 = 竞争充分  🟡 中瓶颈 = 关注变化  🔴 高瓶颈 = 稀缺环节[/dim]")
