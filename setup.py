from setuptools import setup, find_packages

setup(
    name="stockhelper",
    version="0.1.0",
    description="智能股票数据分析助手 — 产业链调研 + 增长筛选 + 技术分析",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "akshare>=1.14.0",
        "pandas>=2.0.0",
        "numpy>=1.24.0",
        "rich>=13.0.0",
        "click>=8.1.0",
        "requests>=2.31.0",
        "pyyaml>=6.0",
        "jinja2>=3.1.0",
        "loguru>=0.7.0",
    ],
    entry_points={
        "console_scripts": [
            "stock=src.cli.main:cli",
        ],
    },
)
