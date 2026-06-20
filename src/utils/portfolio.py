"""自选股管理 —— 本地持久化存储"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import get_config, PROJECT_ROOT


class PortfolioManager:
    """自选股管理器（JSON 文件持久化）"""

    def __init__(self):
        cfg = get_config()
        portfolio_cfg = cfg["portfolio"]
        self.file_path = PROJECT_ROOT / portfolio_cfg["file"]
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    def _load(self) -> Dict[str, Any]:
        """加载自选股数据"""
        if self.file_path.exists():
            try:
                with open(self.file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError):
                pass
        return {"stocks": [], "groups": ["默认", "长期持有", "短线观察"]}

    def _save(self):
        """保存自选股数据"""
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, ensure_ascii=False, indent=2)

    def list_stocks(self, group: Optional[str] = None) -> List[Dict]:
        """获取自选股列表"""
        stocks = self._data.get("stocks", [])
        if group:
            stocks = [s for s in stocks if s.get("group") == group]
        return stocks

    def add_stock(self, code: str, group: str = "默认", name: str = "") -> bool:
        """添加自选股"""
        stocks = self._data.setdefault("stocks", [])

        # 检查是否已存在
        if any(s["code"] == code for s in stocks):
            return False

        stocks.append({
            "code": code,
            "name": name,
            "group": group,
            "added_at": datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        self._save()
        return True

    def remove_stock(self, code: str) -> bool:
        """删除自选股"""
        stocks = self._data.get("stocks", [])
        new_stocks = [s for s in stocks if s["code"] != code]
        if len(new_stocks) == len(stocks):
            return False
        self._data["stocks"] = new_stocks
        self._save()
        return True

    def update_group(self, code: str, group: str) -> bool:
        """修改自选股分组"""
        for s in self._data.get("stocks", []):
            if s["code"] == code:
                s["group"] = group
                self._save()
                return True
        return False

    def get_groups(self) -> List[str]:
        """获取所有分组"""
        return self._data.get("groups", [])

    def add_group(self, name: str) -> bool:
        """添加分组"""
        if name not in self._data["groups"]:
            self._data["groups"].append(name)
            self._save()
            return True
        return False
