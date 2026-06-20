# StockHelper — 智能股票数据分析助手

## 项目简介
基于 Python 的股票数据分析工具，核心能力为**产业链按需调研**和**业绩爆发增长筛选**。
用户输入任意产业名称，系统自动调研构建产业链图谱，并从中挖掘业绩爆发增长标的。

## 自然语言交互

用户可以直接说中文需求，由我（Claude）自动转化为对应的 Python 命令执行。

### 自然语言 → 命令映射

| 用户说 | 我执行 |
|-------|--------|
| "调研/分析下 XXX 产业链" | `python main.py chain research XXX` |
| "对比下 XXX 产业链各环节" | `python main.py chain compare XXX` |
| "XXX 产业链有哪些增长标的" | `python main.py chain growth XXX` |
| "XXX 产业链景气度怎么样" | `python main.py chain boom XXX` |
| "看下 XXX 这只股票" | `python main.py stock detail 代码` |
| "扫描全市场业绩爆发公司" | `python main.py stock screener` |
| "加 XXX 到自选股" | `python main.py stock add 代码` |
| "查看自选股" | `python main.py stock list` |
| "生成 XXX 的分析报告" | `python main.py stock report 代码` |
| "查看综合看板" | `python main.py dashboard` |

### 股票代码识别
- 用户说股票名称（如"贵州茅台""宁德时代"），我需要先用搜索功能找到对应代码
- 然后用正确的代码执行命令

### 快速开始

## 技能文件
StockHelper 作为 Claude Code 技能定义在 `.claude/skills/stockhelper/SKILL.md` 中。
采用渐进式加载架构：SKILL.md（核心）+ references/（按需加载）。

## 设计参考
- 数据采集：参考 **UZI-Skill** 的 22 维数据架构（akshare）
- 产业链瓶颈分析：参考 **Serenity Skill** 的瓶颈评分卡方法论
- 报告渲染：参考 **ZBS-Stock-Screener** 的 HTML 报告模板
- Skill 架构：参考 **Buffett Skills** 的渐进式加载设计模式
- 技术栈：Python + akshare + click + rich + ECharts
