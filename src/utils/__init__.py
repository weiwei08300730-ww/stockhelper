"""缓存工具模块 —— 本地 JSON 缓存，支持 TTL 过期"""

import json
import time
from pathlib import Path
from typing import Any, Optional


class Cache:
    """简单的本地 JSON 缓存，键值对存储 + TTL"""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe = key.replace("/", "_").replace("\\", "_").replace(" ", "_")
        return self.cache_dir / f"{safe}.json"

    def get(self, key: str, default: Any = None) -> Optional[Any]:
        """获取缓存，过期返回 None"""
        path = self._path(key)
        if not path.exists():
            return default
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            expires_at = data.get("_expires_at", 0)
            if time.time() > expires_at:
                path.unlink(missing_ok=True)
                return default
            return data.get("value")
        except (json.JSONDecodeError, KeyError):
            return default

    def set(self, key: str, value: Any, ttl: int = 86400):
        """写入缓存，ttl 为有效期（秒）"""
        path = self._path(key)
        data = {
            "value": value,
            "_expires_at": time.time() + ttl,
            "_created_at": time.time(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def exists(self, key: str) -> bool:
        """检查缓存是否存在且未过期"""
        return self.get(key, _sentinel := object()) != _sentinel

    def delete(self, key: str):
        """删除缓存"""
        path = self._path(key)
        path.unlink(missing_ok=True)

    def clear_expired(self):
        """清理所有过期缓存"""
        for f in self.cache_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if time.time() > data.get("_expires_at", 0):
                    f.unlink(missing_ok=True)
            except (json.JSONDecodeError, KeyError, OSError):
                f.unlink(missing_ok=True)

    def list_keys(self) -> list[str]:
        """列出所有未过期的缓存键"""
        keys = []
        for f in self.cache_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if time.time() <= data.get("_expires_at", 0):
                    keys.append(f.stem)
            except (json.JSONDecodeError, KeyError):
                continue
        return keys
