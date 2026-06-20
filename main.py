#!/usr/bin/env python3
"""StockHelper — 智能股票数据分析助手

Usage:
    python main.py --help
    python main.py stock list
    python main.py stock detail 600519
    python main.py chain research 低空经济
    python main.py stock screener
"""

import sys
import io
from pathlib import Path

# Windows GBK 编码兼容处理
import os
if sys.stdout.encoding and 'gbk' in sys.stdout.encoding.lower():
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# 确保项目根目录在 sys.path 中
project_root = Path(__file__).parent.resolve()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.cli.main import cli

if __name__ == "__main__":
    cli()
