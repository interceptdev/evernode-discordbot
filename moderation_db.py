import sqlite3
import datetime
from typing import Optional, List, Dict, Any

DbPath = "moderation.db"

def init_db() -> None:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Cursor.execute("""
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                moderator_id INTEGER NOT NULL,
                reason TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        Cursor.execute("""
            CREATE TABLE IF NOT EXISTS tempbans (
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                unban_at TEXT NOT NULL,
                PRIMARY KEY (user_id, guild_id)
            )
        """)
        Cursor.execute("""
            CREATE TABLE IF NOT EXISTS moderation_actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action_type TEXT NOT NULL,
                guild_id INTEGER NOT NULL,
                moderator_id INTEGER,
                target_id INTEGER,
                reason TEXT,
                details TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        Conn.commit()

def add_warning(UserId: int, GuildId: int, ModeratorId: int, Reason: str) -> int:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Timestamp = datetime.datetime.now().isoformat()
        Cursor.execute("""
            INSERT INTO warnings (user_id, guild_id, moderator_id, reason, timestamp)
            VALUES (?, ?, ?, ?, ?)
        """, (UserId, GuildId, ModeratorId, Reason, Timestamp))
        Conn.commit()
        return Cursor.lastrowid

def get_warnings(UserId: int, GuildId: int) -> List[Dict[str, Any]]:
    with sqlite3.connect(DbPath) as Conn:
        Conn.row_factory = sqlite3.Row
        Cursor = Conn.cursor()
        Cursor.execute("""
            SELECT id, moderator_id, reason, timestamp FROM warnings 
            WHERE user_id = ? AND guild_id = ?
            ORDER BY id DESC
        """, (UserId, GuildId))
        return [dict(Row) for Row in Cursor.fetchall()]

def delete_warning(WarningId: int) -> bool:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Cursor.execute("DELETE FROM warnings WHERE id = ?", (WarningId,))
        Conn.commit()
        return Cursor.rowcount > 0

def clear_warnings(UserId: int, GuildId: int) -> int:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Cursor.execute("DELETE FROM warnings WHERE user_id = ? AND guild_id = ?", (UserId, GuildId))
        Conn.commit()
        return Cursor.rowcount

def add_tempban(UserId: int, GuildId: int, UnbanAt: datetime.datetime) -> None:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Cursor.execute("""
            INSERT OR REPLACE INTO tempbans (user_id, guild_id, unban_at)
            VALUES (?, ?, ?)
        """, (UserId, GuildId, UnbanAt.isoformat()))
        Conn.commit()

def get_expired_tempbans() -> List[Dict[str, Any]]:
    with sqlite3.connect(DbPath) as Conn:
        Conn.row_factory = sqlite3.Row
        Cursor = Conn.cursor()
        NowStr = datetime.datetime.now().isoformat()
        Cursor.execute("SELECT * FROM tempbans WHERE unban_at <= ?", (NowStr,))
        return [dict(Row) for Row in Cursor.fetchall()]

def remove_tempban(UserId: int, GuildId: int) -> None:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Cursor.execute("DELETE FROM tempbans WHERE user_id = ? AND guild_id = ?", (UserId, GuildId))
        Conn.commit()

def log_mod_action(
    ActionType: str,
    GuildId: int,
    ModeratorId: Optional[int],
    TargetId: Optional[int],
    Reason: Optional[str] = None,
    Details: Optional[str] = None
) -> None:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
        Cursor.execute("""
            INSERT INTO moderation_actions (action_type, guild_id, moderator_id, target_id, reason, details, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ActionType, GuildId, ModeratorId, TargetId, Reason, Details, Timestamp))
        Conn.commit()
