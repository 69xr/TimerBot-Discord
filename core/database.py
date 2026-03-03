"""
Async SQLite database layer for FocusBeast.
All data access goes through here — no JSON files.
"""

import aiosqlite
import json
from typing import Optional
import logging

log = logging.getLogger("DB")


class Database:
    def __init__(self, path: str):
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None

    async def init(self):
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()
        await self._conn.commit()
        log.info("✅ Database initialized")

    async def _create_tables(self):
        await self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            xp          INTEGER DEFAULT 0,
            coins       INTEGER DEFAULT 100,
            total_focus INTEGER DEFAULT 0,
            sessions    INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS pets (
            pet_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            species     TEXT NOT NULL,
            name        TEXT NOT NULL,
            rarity      TEXT NOT NULL,
            level       INTEGER DEFAULT 1,
            xp          INTEGER DEFAULT 0,
            happiness   INTEGER DEFAULT 100,
            active      INTEGER DEFAULT 0,
            acquired_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );

        CREATE TABLE IF NOT EXISTS owned_roles (
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            PRIMARY KEY(user_id, role_id)
        );

        CREATE TABLE IF NOT EXISTS shop_roles (
            role_id  INTEGER PRIMARY KEY,
            guild_id INTEGER NOT NULL,
            name     TEXT NOT NULL,
            price    INTEGER NOT NULL,
            color    INTEGER NOT NULL,
            icon     TEXT DEFAULT '✨',
            description TEXT DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS active_timers (
            message_id  INTEGER PRIMARY KEY,
            user_id     INTEGER NOT NULL,
            guild_id    INTEGER NOT NULL,
            channel_id  INTEGER NOT NULL,
            theme       TEXT NOT NULL,
            duration    INTEGER NOT NULL,
            break_time  INTEGER NOT NULL,
            end_time    REAL NOT NULL,
            cancelled   INTEGER DEFAULT 0
        );
        """)

    # ── Generic helpers ───────────────────────────────────────────────────────
    async def fetchone(self, sql: str, params=()) -> Optional[aiosqlite.Row]:
        async with self._conn.execute(sql, params) as cur:
            return await cur.fetchone()

    async def fetchall(self, sql: str, params=()) -> list:
        async with self._conn.execute(sql, params) as cur:
            return await cur.fetchall()

    async def execute(self, sql: str, params=()):
        await self._conn.execute(sql, params)
        await self._conn.commit()

    # ── User ─────────────────────────────────────────────────────────────────
    async def ensure_user(self, user_id: int):
        await self.execute(
            "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
        )

    async def get_user(self, user_id: int) -> Optional[aiosqlite.Row]:
        await self.ensure_user(user_id)
        return await self.fetchone("SELECT * FROM users WHERE user_id=?", (user_id,))

    async def add_xp(self, user_id: int, amount: int) -> int:
        await self.ensure_user(user_id)
        await self.execute(
            "UPDATE users SET xp=xp+? WHERE user_id=?", (amount, user_id)
        )
        row = await self.get_user(user_id)
        # Also level up active pet
        await self._pet_gain_xp(user_id, amount // 2)
        return row["xp"]

    async def add_coins(self, user_id: int, amount: int) -> int:
        await self.ensure_user(user_id)
        await self.execute(
            "UPDATE users SET coins=coins+? WHERE user_id=?", (amount, user_id)
        )
        row = await self.get_user(user_id)
        return row["coins"]

    async def spend_coins(self, user_id: int, amount: int) -> bool:
        row = await self.get_user(user_id)
        if row["coins"] < amount:
            return False
        await self.execute(
            "UPDATE users SET coins=coins-? WHERE user_id=?", (amount, user_id)
        )
        return True

    async def add_focus_time(self, user_id: int, minutes: int):
        await self.execute(
            "UPDATE users SET total_focus=total_focus+?, sessions=sessions+1 WHERE user_id=?",
            (minutes, user_id)
        )

    async def get_leaderboard(self, limit=10) -> list:
        return await self.fetchall(
            "SELECT user_id, xp, coins, total_focus, sessions FROM users ORDER BY xp DESC LIMIT ?",
            (limit,)
        )

    # ── Pets ─────────────────────────────────────────────────────────────────
    async def add_pet(self, user_id: int, species: str, name: str, rarity: str) -> int:
        await self.ensure_user(user_id)
        async with self._conn.execute(
            "INSERT INTO pets (user_id, species, name, rarity) VALUES (?,?,?,?)",
            (user_id, species, name, rarity)
        ) as cur:
            pet_id = cur.lastrowid
        await self._conn.commit()
        return pet_id

    async def get_pets(self, user_id: int) -> list:
        return await self.fetchall(
            "SELECT * FROM pets WHERE user_id=? ORDER BY active DESC, level DESC",
            (user_id,)
        )

    async def get_active_pet(self, user_id: int) -> Optional[aiosqlite.Row]:
        return await self.fetchone(
            "SELECT * FROM pets WHERE user_id=? AND active=1", (user_id,)
        )

    async def set_active_pet(self, user_id: int, pet_id: int):
        await self.execute("UPDATE pets SET active=0 WHERE user_id=?", (user_id,))
        await self.execute("UPDATE pets SET active=1 WHERE pet_id=? AND user_id=?", (pet_id, user_id))

    async def rename_pet(self, pet_id: int, user_id: int, new_name: str):
        await self.execute(
            "UPDATE pets SET name=? WHERE pet_id=? AND user_id=?",
            (new_name, pet_id, user_id)
        )

    async def _pet_gain_xp(self, user_id: int, amount: int):
        pet = await self.get_active_pet(user_id)
        if not pet:
            return
        new_xp = pet["xp"] + amount
        new_level = pet["level"]
        xp_needed = new_level * 100
        while new_xp >= xp_needed:
            new_xp -= xp_needed
            new_level += 1
            xp_needed = new_level * 100
        await self.execute(
            "UPDATE pets SET xp=?, level=? WHERE pet_id=?",
            (new_xp, new_level, pet["pet_id"])
        )

    async def get_pet(self, pet_id: int) -> Optional[aiosqlite.Row]:
        return await self.fetchone("SELECT * FROM pets WHERE pet_id=?", (pet_id,))

    # ── Roles ─────────────────────────────────────────────────────────────────
    async def add_shop_role(self, role_id: int, guild_id: int, name: str, price: int, color: int, icon: str, desc: str):
        await self.execute(
            "INSERT OR REPLACE INTO shop_roles VALUES (?,?,?,?,?,?,?)",
            (role_id, guild_id, name, price, color, icon, desc)
        )

    async def get_shop_roles(self, guild_id: int) -> list:
        return await self.fetchall(
            "SELECT * FROM shop_roles WHERE guild_id=?", (guild_id,)
        )

    async def remove_shop_role(self, role_id: int):
        await self.execute("DELETE FROM shop_roles WHERE role_id=?", (role_id,))

    async def owns_role(self, user_id: int, role_id: int) -> bool:
        row = await self.fetchone(
            "SELECT 1 FROM owned_roles WHERE user_id=? AND role_id=?", (user_id, role_id)
        )
        return row is not None

    async def grant_role(self, user_id: int, role_id: int, guild_id: int):
        await self.execute(
            "INSERT OR IGNORE INTO owned_roles VALUES (?,?,?)",
            (user_id, role_id, guild_id)
        )

    # ── Active Timers ─────────────────────────────────────────────────────────
    async def save_timer(self, message_id, user_id, guild_id, channel_id, theme, duration, break_time, end_time):
        await self.execute(
            "INSERT OR REPLACE INTO active_timers VALUES (?,?,?,?,?,?,?,?,0)",
            (message_id, user_id, guild_id, channel_id, theme, duration, break_time, end_time)
        )

    async def cancel_timer(self, message_id: int):
        await self.execute("DELETE FROM active_timers WHERE message_id=?", (message_id,))

    async def timer_exists(self, message_id: int) -> bool:
        row = await self.fetchone("SELECT 1 FROM active_timers WHERE message_id=?", (message_id,))
        return row is not None