"""
去重模块 - 基于 SQLite 本地存储，避免重复处理同一条内容
"""
import sqlite3
import logging
from datetime import datetime
from pathlib import Path

from config import DATABASE_PATH

logger = logging.getLogger(__name__)


class DedupManager:
    """去重管理器 - 本地 SQLite 版本，不依赖博客服务器"""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_table()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_table(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS processed_items (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    title TEXT,
                    published_date TEXT,
                    processed_at TEXT DEFAULT (datetime('now', 'localtime')),
                    UNIQUE(source, item_id)
                )
            """)
            conn.commit()

    def is_processed(self, source: str, item_id: str) -> bool:
        """检查是否已处理"""
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT 1 FROM processed_items WHERE source = ? AND item_id = ?",
                (source, item_id),
            ).fetchone()
            return row is not None

    def mark_processed(
        self,
        source: str,
        item_id: str,
        title: str = "",
        published_date: str = "",
    ) -> bool:
        """标记为已处理"""
        with self._get_conn() as conn:
            try:
                conn.execute(
                    "INSERT OR IGNORE INTO processed_items (source, item_id, title, published_date) "
                    "VALUES (?, ?, ?, ?)",
                    (source, item_id, title, published_date),
                )
                conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"标记已处理失败: {e}")
                return False

    def filter_unprocessed(self, items: list, source: str, id_key: str) -> list:
        """过滤出未处理的项目"""
        unprocessed = []
        for item in items:
            item_id = item.get(id_key, "")
            if item_id and not self.is_processed(source, item_id):
                unprocessed.append(item)
        logger.info(f"Dedup: {len(items)} 条中 {len(unprocessed)} 条未处理")
        return unprocessed

    def get_stats(self) -> dict:
        """获取统计信息"""
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM processed_items").fetchone()[0]
            by_source = conn.execute(
                "SELECT source, COUNT(*) as cnt FROM processed_items GROUP BY source"
            ).fetchall()
            return {
                "total": total,
                "by_source": {r["source"]: r["cnt"] for r in by_source},
            }

    def cleanup_old(self, days: int = 90):
        """清理 N 天前的记录"""
        cutoff = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM processed_items WHERE processed_at < datetime(?, ?)",
                (cutoff, f"-{days} days"),
            )
            conn.commit()
