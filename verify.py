"""StockHelper 快速验证脚本"""

import sys
import io
from pathlib import Path

# 处理 Windows GBK 编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

def verify():
    """验证核心模块是否正常导入"""
    errors = []

    try:
        import akshare as ak
        print(f"[OK] akshare {ak.__version__}")
    except ImportError as e:
        errors.append(f"akshare 导入失败: {e}")

    try:
        import pandas as pd
        import numpy as np
        print(f"[OK] pandas {pd.__version__}, numpy {np.__version__}")
    except ImportError as e:
        errors.append(f"pandas/numpy 导入失败: {e}")

    try:
        import click
        import rich
        print(f"[OK] click, rich")
    except ImportError as e:
        errors.append(f"click/rich 导入失败: {e}")

    try:
        import yaml
        print(f"[OK] pyyaml")
    except ImportError as e:
        errors.append(f"pyyaml 导入失败: {e}")

    # 验证项目模块
    try:
        from src.config import get_config
        cfg = get_config()
        print(f"[OK] 配置加载成功: {cfg.get('data_source', {}).get('primary')}")
    except Exception as e:
        errors.append(f"配置模块错误: {e}")

    try:
        from src.collector import DataCollector
        collector = DataCollector()
        print(f"[OK] DataCollector 初始化成功")
    except Exception as e:
        errors.append(f"DataCollector 错误: {e}")

    try:
        from src.industry_chain import IndustryChainResearcher
        researcher = IndustryChainResearcher()
        chains = researcher.get_available_chains()
        print(f"[OK] IndustryChainResearcher 初始化成功，基线产业链: {len(chains)} 条")
    except Exception as e:
        errors.append(f"IndustryChainResearcher 错误: {e}")

    try:
        from src.analyzer.growth_screener import GrowthScreener
        screener = GrowthScreener()
        print(f"[OK] GrowthScreener 初始化成功")
    except Exception as e:
        errors.append(f"GrowthScreener 错误: {e}")

    try:
        from src.cli.main import cli
        print(f"[OK] CLI 命令组注册成功")
    except Exception as e:
        errors.append(f"CLI 错误: {e}")

    try:
        from src.utils.portfolio import PortfolioManager
        pm = PortfolioManager()
        print(f"[OK] PortfolioManager 初始化成功")
    except Exception as e:
        errors.append(f"PortfolioManager 错误: {e}")

    print(f"\n{'='*50}")
    if errors:
        print(f"[FAIL] {len(errors)} 个错误:")
        for e in errors:
            print(f"   - {e}")
    else:
        print(f"[PASS] 所有模块验证通过!")
    print(f"{'='*50}")

    return len(errors) == 0


if __name__ == "__main__":
    success = verify()
    sys.exit(0 if success else 1)
