"""
資料庫模組 — SQLite 通知儲存
表格: messages(id, to_machine, from_who, text, created_at, acked)
"""
import sqlite3
import os
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "notifications.db")


def get_connection() -> sqlite3.Connection:
    """取得資料庫連線（自動建立資料表）"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _init_db(conn)
    return conn


def _init_db(conn: sqlite3.Connection):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            to_machine  TEXT    NOT NULL,
            from_who    TEXT    NOT NULL,
            text        TEXT    NOT NULL,
            created_at  TEXT    NOT NULL,
            acked       INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_unacked
        ON messages(to_machine, acked, id)
    """)
    conn.commit()


def send_notification(to_machine: str, from_who: str, text: str) -> dict:
    """存入一筆新通知，回傳該筆紀錄"""
    now = datetime.now(timezone.utc).isoformat()
    conn = get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO messages (to_machine, from_who, text, created_at) VALUES (?, ?, ?, ?)",
            (to_machine, from_who, text, now),
        )
        msg_id = cur.lastrowid
        conn.commit()
        return {
            "id": msg_id,
            "to_machine": to_machine,
            "from_who": from_who,
            "text": text,
            "created_at": now,
            "acked": False,
        }
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def poll_messages(machine_name: str) -> list[dict]:
    """回傳該機器的所有未讀通知"""
    conn = get_connection()
    try:
        rows = conn.execute(
            "SELECT id, to_machine, from_who, text, created_at, acked "
            "FROM messages WHERE to_machine = ? AND acked = 0 "
            "ORDER BY id ASC",
            (machine_name,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def ack_message(msg_id: int) -> bool:
    """將指定通知標記為已讀，回傳是否成功"""
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE messages SET acked = 1 WHERE id = ? AND acked = 0",
            (msg_id,),
        )
        conn.commit()
        return cur.rowcount > 0
    except Exception:
        conn.rollback()
        return False
    finally:
        conn.close()
