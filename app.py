"""StockHelper Streamlit 移动端 Web App

手机浏览器即可访问，无需安装任何 App
"""

import sys
from pathlib import Path
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd

from src.collector import DataCollector
from src.industry_chain import IndustryChainResearcher
from src.analyzer.growth_screener import GrowthScreener
from src.analyzer.signal_engine import SignalEngine
from src.reporter.pyecharts_renderer import PyechartsReportGenerator
from src.utils.portfolio import PortfolioManager

# ===================== 页面配置 =====================
st.set_page_config(
    page_title="StockHelper 智能投研",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ===================== 样式 =====================
st.markdown("""
<style>
    /* 移动端适配 */
    .stApp { background-color: #0d1117; }
    .main > div { padding: 1rem 0.5rem; }
    .stButton > button { width: 100%; border-radius: 10px; height: 3em; font-size: 16px; }
    .stTextInput > div > input { font-size: 16px; border-radius: 10px; }
    h1, h2, h3 { color: #e6edf3 !important; }
    .block-container { padding-top: 1rem; padding-bottom: 1rem; }
    /* 卡片样式 */
    .card {
        background: #161b22;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        border: 1px solid #30363d;
    }
    .card-title { color: #8b949e; font-size: 12px; margin-bottom: 4px; }
    .card-value { color: #e6edf3; font-size: 22px; font-weight: bold; }
    .card-detail { color: #8b949e; font-size: 11px; margin-top: 4px; }
    /* 标签 */
    .tag-buy { background: #f85149; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .tag-hold { background: #d29922; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .tag-sell { background: #3fb950; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
    .tag-high { background: #f85149; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; }
    .tag-mid { background: #d29922; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; }
    .tag-low { background: #3fb950; color: white; padding: 2px 6px; border-radius: 4px; font-size: 11px; }
    /* 进度条 */
    .score-bar { height: 6px; border-radius: 3px; background: #30363d; margin-top: 8px; }
    .score-fill { height: 100%; border-radius: 3px; }
</style>
""", unsafe_allow_html=True)


# ===================== 初始化 =====================
@st.cache_resource
def get_collector():
    return DataCollector()

@st.cache_resource
def get_researcher():
    return IndustryChainResearcher()

@st.cache_resource
def get_screener():
    return GrowthScreener()

@st.cache_resource
def get_signal_engine():
    return SignalEngine()

@st.cache_resource
def get_portfolio():
    return PortfolioManager()

collector = get_collector()
researcher = get_researcher()
screener = get_screener()
signal_engine = get_signal_engine()
portfolio = get_portfolio()


# ===================== 页面路由 =====================
st.title("📈 StockHelper")
st.caption("智能股票数据分析助手")

pages = ["🏠 首页", "🔍 产业链调研", "📊 买卖信号", "🔥 业绩扫描", "📋 自选股", "📄 分析报告"]
page = st.radio("", pages, horizontal=True, label_visibility="collapsed")


# ===================== 首页 =====================
if page == pages[0]:
    st.subheader("🔥 热门产业链")

    chains = researcher.get_available_chains()
    col1, col2 = st.columns(2)
    for i, chain in enumerate(chains[:8]):
        with col1 if i % 2 == 0 else col2:
            name = chain["name"]
            node_count = chain["node_count"]
            source = "📦" if chain["source"] == "builtin" else "🔍"
            st.markdown(
                f'<div class="card" style="cursor:pointer;">'
                f'<div style="font-size:16px;font-weight:bold;">{source} {name}</div>'
                f'<div style="color:#8b949e;font-size:12px;">{node_count}个环节</div>'
                f'</div>',
                unsafe_allow_html=True
            )
            if st.button(name, key=f"home_{name}", use_container_width=True):
                st.session_state["chain_name"] = name
                st.session_state["page"] = pages[1]
                st.rerun()

    st.subheader("⚡ 快速操作")
    if st.button("🔥 扫描全市场业绩爆发公司", use_container_width=True):
        st.session_state["page"] = pages[3]
        st.rerun()

    if st.button("📋 查看自选股", use_container_width=True):
        st.session_state["page"] = pages[4]
        st.rerun()


# ===================== 产业链调研 =====================
elif page == pages[1]:
    st.subheader("🔍 产业链调研")

    chain_name = st.text_input("输入产业名称",
                                placeholder="如：低空经济、机器人、固态电池...",
                                value=st.session_state.get("chain_name", ""))

    col1, col2 = st.columns([3, 1])
    with col1:
        btn = st.button("🚀 开始调研", use_container_width=True)
    with col2:
        refresh = st.button("🔄 刷新", use_container_width=True)

    if btn or refresh or st.session_state.get("chain_name"):
        name = chain_name or st.session_state.get("chain_name", "")
        if name:
            with st.spinner(f"正在调研 [{name}] 产业链..."):
                chain_data = researcher.research_chain(name, force=refresh)
                bottlenecks = researcher.analyze_bottlenecks(chain_data)

            source_tag = "📦 基线" if chain_data.source == "builtin" else "🔍 调研"
            st.markdown(f'<div class="card"><b>{name}</b> | {chain_data.description}<br><small>{source_tag}</small></div>', unsafe_allow_html=True)

            # 图谱展示
            for node in chain_data.nodes:
                with st.expander(f"📌 {node.name}", expanded=True):
                    st.caption(node.description)
                    for comp in node.companies[:6]:
                        tag = "🟢" if comp.get("position") == "核心" else "⚪"
                        st.markdown(f"{tag} **{comp['name']}** (`{comp['code']}`)")
                    if len(node.companies) > 6:
                        st.caption(f"...及其他 {len(node.companies) - 6} 家")

            # 瓶颈分析
            st.subheader("🔍 瓶颈分析")
            for b in bottlenecks:
                level_icon = {"🔴 高": "🔴", "🟡 中": "🟡", "🟢 低": "🟢"}.get(b["level"], "⚪")
                st.markdown(
                    f'<div class="card">'
                    f'<b>{b["segment"]}</b> {level_icon} {b["level"]}<br>'
                    f'<small>{b["analysis"][:80]}...</small>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            # 增长标的
            st.subheader("📈 产业链增长标的")
            for node in chain_data.nodes:
                if node.companies:
                    scores = screener.scan_industry_chain(node.companies)
                    top = [s for s in scores if abs(s.revenue_yoy) > 5][:3]
                    if top:
                        for s in top:
                            st.markdown(
                                f'<div class="card">'
                                f'<b>{s.name}</b> ({s.code}) '
                                f'<span class="tag-{"high" if s.tag == "🔥" else "buy" if s.tag == "📈" else "hold"}">{s.tag} {s.tag_label}</span><br>'
                                f'营收 <b>{"{:.1f}".format(s.revenue_yoy)}</b>% | '
                                f'净利 <b>{"{:.1f}".format(s.net_profit_yoy)}</b>% | '
                                f'评分 <b>{s.total_score}</b>'
                                f'</div>',
                                unsafe_allow_html=True
                            )


# ===================== 买卖信号 =====================
elif page == pages[2]:
    st.subheader("📊 买卖信号分析")

    code = st.text_input("输入股票代码", placeholder="如：688017、300124、600519")

    if st.button("🔍 分析信号", use_container_width=True) and code:
        with st.spinner(f"正在分析 {code}..."):
            # 优先使用缓存财务数据
            fin = collector.get_financial_data(code)
            daily = collector.get_stock_daily(code)

            if not daily.empty:
                result = signal_engine.analyze_with_data(code, daily, fin)
            elif "error" not in fin:
                result = signal_engine.analyze(code)
            else:
                st.error("无法获取数据，请检查网络连接")
                st.stop()

        # 信号展示
        name = fin.get("name", code) if "error" not in fin else code
        action = result.action.value
        action_color = "#f85149" if "买入" in action else "#d29922" if "持有" in action else "#3fb950"

        st.markdown(
            f'<div class="card" style="text-align:center;border-color:{action_color};">'
            f'<div style="font-size:14px;color:#8b949e;">{name} ({code})</div>'
            f'<div style="font-size:32px;font-weight:bold;color:{action_color};">{action}</div>'
            f'<div style="font-size:13px;">综合评分 {result.total_score:.0f}/100 | 信心指数 {result.confidence}/100</div>'
            f'</div>',
            unsafe_allow_html=True
        )

        # 维度评分
        cols = st.columns(4)
        dims = [
            ("技术面", result.technical_score, "35%"),
            ("动量", result.momentum_score, "20%"),
            ("基本面", result.fundamental_score, "25%"),
            ("产业", result.chain_score, "20%"),
        ]
        for col, (label, score, weight) in zip(cols, dims):
            with col:
                color = "#f85149" if score >= 60 else "#d29922" if score >= 40 else "#3fb950"
                st.markdown(
                    f'<div class="card" style="text-align:center;">'
                    f'<div class="card-title">{label}</div>'
                    f'<div style="font-size:20px;font-weight:bold;color:{color};">{score:.0f}</div>'
                    f'<div class="card-detail">{weight}</div>'
                    f'<div class="score-bar"><div class="score-fill" style="width:{score}%;background:{color};"></div></div>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        # 分析理由
        if result.reasons:
            st.subheader("📌 分析要点")
            for r in result.reasons:
                st.markdown(f"- {r}")

        # 风险提示
        if result.risks:
            st.subheader("⚠️ 风险提示")
            for r in result.risks:
                st.markdown(f"- {r}")

        # 交易参考
        st.subheader("💰 交易参考")
        ref_cols = st.columns(3)
        ref_cols[0].metric("入场区间", f"{result.entry_low:.2f} - {result.entry_high:.2f}")
        ref_cols[1].metric("止损参考", f"{result.stop_loss:.2f}")
        ref_cols[2].metric("建议仓位", f"{result.risk_pct:.1f}%")


# ===================== 业绩扫描 =====================
elif page == pages[3]:
    st.subheader("🔥 业绩爆发增长扫描")

    if st.button("🚀 开始扫描全市场", use_container_width=True):
        with st.spinner("正在扫描全市场，请稍候（约30秒）..."):
            results = screener.scan_market(top_n=50)

        breakout = [r for r in results if r.tag == "🔥"]
        high = [r for r in results if r.tag == "📈"]

        if breakout:
            st.subheader(f"🔥 业绩爆发 ({len(breakout)}只)")
            for r in breakout[:10]:
                st.markdown(
                    f'<div class="card">'
                    f'<b>{r.name}</b> (`{r.code}`) <span class="tag-high">业绩爆发</span><br>'
                    f'营收 <b style="color:#f85149;">+{r.revenue_yoy:.1f}%</b> | '
                    f'净利 <b style="color:#f85149;">+{r.net_profit_yoy:.1f}%</b> | '
                    f'ROE {r.roe:.1f}% | 评分 <b>{r.total_score:.1f}</b>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        if high:
            st.subheader(f"📈 高增长 ({len(high)}只)")
            for r in high[:10]:
                st.markdown(
                    f'<div class="card">'
                    f'<b>{r.name}</b> (`{r.code}`) <span class="tag-buy">高增长</span><br>'
                    f'营收 <b style="color:#f85149;">+{r.revenue_yoy:.1f}%</b> | '
                    f'净利 <b style="color:#f85149;">+{r.net_profit_yoy:.1f}%</b> | '
                    f'评分 <b>{r.total_score:.1f}</b>'
                    f'</div>',
                    unsafe_allow_html=True
                )

        if not breakout and not high:
            st.info("当前扫描范围未找到符合条件的公司")


# ===================== 自选股 =====================
elif page == pages[4]:
    st.subheader("📋 自选股管理")

    tab1, tab2 = st.tabs(["📋 我的自选", "➕ 添加"])

    with tab1:
        stocks = portfolio.list_stocks()
        if stocks:
            for s in stocks:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{s.get('name', '')}** ({s['code']})  `{s.get('group', '默认')}`")
                with col2:
                    if st.button("分析", key=f"analyze_{s['code']}", use_container_width=True):
                        st.session_state["signal_code"] = s["code"]
                        st.session_state["page"] = pages[2]
                        st.rerun()
        else:
            st.info("还没有添加自选股，在「添加」标签页添加吧")

    with tab2:
        code = st.text_input("股票代码", placeholder="如：688017")
        group = st.selectbox("分组", ["默认", "长期持有", "短线观察", "机器人", "AI"])
        name = st.text_input("名称（可选）")

        if st.button("➕ 添加自选", use_container_width=True) and code:
            if collector.validate_code(code):
                portfolio.add_stock(code, group, name or "")
                st.success(f"已添加 {code} 到「{group}」")
                st.rerun()
            else:
                st.error("无效股票代码")


# ===================== 分析报告 =====================
elif page == pages[5]:
    st.subheader("📄 生成分析报告")

    code = st.text_input("股票代码", placeholder="如：688017、300750")

    if st.button("📊 生成报告", use_container_width=True) and code:
        with st.spinner("正在生成报告..."):
            daily = collector.get_stock_daily(code)
            fin = collector.get_financial_data(code)

            if not daily.empty:
                renderer = PyechartsReportGenerator()
                path = renderer.generate(code, daily, fin)

                st.success(f"报告已生成！")
                st.info(f"文件路径: {path}")

                # 显示报告预览链接
                with open(path, "r", encoding="utf-8") as f:
                    html_content = f.read()
                st.download_button(
                    "📥 下载报告 (HTML)",
                    data=html_content,
                    file_name=f"{code}_report.html",
                    mime="text/html",
                    use_container_width=True
                )
            else:
                st.error("无法获取行情数据，请检查网络")
                if "error" not in fin:
                    st.info("已获取到财务数据，但日线行情不可用")
