"""配置加载模块 —— 读取 config.yaml 并提供全局配置对象"""

import os
from pathlib import Path
from typing import Any, Dict
import yaml


# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
CONFIG_PATH = PROJECT_ROOT / "config" / "config.yaml"


def load_config(path: Path = CONFIG_PATH) -> Dict[str, Any]:
    """加载 YAML 配置文件"""
    if not path.exists():
        raise FileNotFoundError(f"配置文件不存在: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# 全局配置单例
_config_cache: Dict[str, Any] | None = None


def get_config() -> Dict[str, Any]:
    """获取全局配置（带缓存）"""
    global _config_cache
    if _config_cache is None:
        _config_cache = load_config()
    return _config_cache


def get_data_dir() -> Path:
    """获取数据目录"""
    return PROJECT_ROOT / "data"


def get_cache_dir() -> Path:
    """获取缓存目录"""
    return PROJECT_ROOT / get_config()["cache"]["dir"]


def get_chain_cache_dir() -> Path:
    """获取产业链缓存目录"""
    return PROJECT_ROOT / get_config()["industry_chain"]["cache_dir"]


def get_report_dir() -> Path:
    """获取报告输出目录"""
    return PROJECT_ROOT / get_config()["report"]["output_dir"]
