import sqlite3
import datetime
from typing import Optional, List, Dict, Any

DbPath = "tickets.db"

def init_db() -> None:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                channel_id INTEGER PRIMARY KEY,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                state TEXT NOT NULL,
                claimed_by INTEGER,
                ticket_num INTEGER NOT NULL,
                created_at TEXT NOT NULL
            )
        """)
        Cursor.execute("""
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        Conn.commit()

def create_ticket(ChannelId: int, UserId: int, Category: str, State: str, TicketNum: int) -> None:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        CreatedAt = datetime.datetime.now().isoformat()
        Cursor.execute("""
            INSERT OR REPLACE INTO tickets (channel_id, user_id, category, state, claimed_by, ticket_num, created_at)
            VALUES (?, ?, ?, ?, NULL, ?, ?)
        """, (ChannelId, UserId, Category, State, TicketNum, CreatedAt))
        Conn.commit()

def get_ticket(ChannelId: int) -> Optional[Dict[str, Any]]:
    with sqlite3.connect(DbPath) as Conn:
        Conn.row_factory = sqlite3.Row
        Cursor = Conn.cursor()
        Cursor.execute("SELECT * FROM tickets WHERE channel_id = ?", (ChannelId,))
        Row = Cursor.fetchone()
        if Row:
            return dict(Row)
        return None

def get_active_user_ticket(UserId: int) -> Optional[Dict[str, Any]]:
    with sqlite3.connect(DbPath) as Conn:
        Conn.row_factory = sqlite3.Row
        Cursor = Conn.cursor()
        Cursor.execute("SELECT * FROM tickets WHERE user_id = ? AND state = 'ACTIVE'", (UserId,))
        Row = Cursor.fetchone()
        if Row:
            return dict(Row)
        return None

def claim_ticket(ChannelId: int, StaffId: int) -> None:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Cursor.execute("UPDATE tickets SET claimed_by = ? WHERE channel_id = ?", (StaffId, ChannelId))
        Conn.commit()

def unclaim_ticket_db(ChannelId: int) -> None:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Cursor.execute("UPDATE tickets SET claimed_by = NULL WHERE channel_id = ?", (ChannelId,))
        Conn.commit()

def close_ticket_db(ChannelId: int) -> None:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Cursor.execute("UPDATE tickets SET state = 'CLOSED' WHERE channel_id = ?", (ChannelId,))
        Conn.commit()

def get_next_ticket_number(Category: str) -> int:
    with sqlite3.connect(DbPath) as Conn:
        Cursor = Conn.cursor()
        Key = f"counter_{Category.lower()}"
        Cursor.execute("SELECT value FROM config WHERE key = ?", (Key,))
        Row = Cursor.fetchone()
        if Row:
            Num = int(Row[0])
        else:
            Num = 1
        NextNum = Num + 1
        Cursor.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (Key, str(NextNum)))
        Conn.commit()
        return Num
