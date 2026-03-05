"""
FocusBeast — Database Layer v2
================================
aiosqlite · WAL mode · Foreign keys · Parameterised queries only

Tables:
  users           — XP, coins, focus time, session count
  user_streaks    — daily streak tracking per user
  user_flags      — per-guild admin flags (xp_blocked, note)
  pets            — companion collection
  owned_roles     — purchased shop roles
  shop_roles      — role catalogue per guild
  shop_messages   — persistent shop message location
  guild_settings  — all per-guild config (rewards, limits, roles, channels)
  blocked_channels— channels where /timer is forbidden
  active_timers   — currently running sessions (one per VC)
  timer_members   — who is currently tracked in each session
  session_history — completed session log per user
  audit_log       — every XP/coin delta with reason
"""

import aiosqlite
import logging
import time
import datetime
from typing import Optional

log = logging.getLogger("DB")

_DEFAULTS = {
    "xp_per_min":       10,
    "coins_per_min":    5,
    "max_session_min":  720,
    "min_vc_members":   1,
    "bonus_multiplier": 1.0,
    "allowed_role_id":  0,
    "log_channel_id":   0,
}


class Database:
    def __init__(self, path: str):
        self.path  = path
        self._conn: Optional[aiosqlite.Connection] = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────
    async def init(self):
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA cache_size=-8000")
        await self._create_tables()
        await self._conn.commit()
        log.info("Database ready")

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None

    async def _create_tables(self):
        await self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            xp          INTEGER DEFAULT 0,
            coins       INTEGER DEFAULT 100,
            total_focus INTEGER DEFAULT 0,
            sessions    INTEGER DEFAULT 0,
            created_at  TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS user_streaks (
            user_id      INTEGER PRIMARY KEY,
            current      INTEGER DEFAULT 0,
            longest      INTEGER DEFAULT 0,
            last_session TEXT    DEFAULT '',
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        CREATE TABLE IF NOT EXISTS user_flags (
            user_id    INTEGER NOT NULL,
            guild_id   INTEGER NOT NULL,
            xp_blocked INTEGER DEFAULT 0,
            note       TEXT    DEFAULT '',
            PRIMARY KEY(user_id, guild_id)
        );
        CREATE TABLE IF NOT EXISTS pets (
            pet_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            species     TEXT    NOT NULL,
            name        TEXT    NOT NULL,
            rarity      TEXT    NOT NULL,
            level       INTEGER DEFAULT 1,
            xp          INTEGER DEFAULT 0,
            happiness   INTEGER DEFAULT 100,
            active      INTEGER DEFAULT 0,
            acquired_at TEXT    DEFAULT (datetime('now')),
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        );
        CREATE TABLE IF NOT EXISTS owned_roles (
            user_id  INTEGER NOT NULL,
            role_id  INTEGER NOT NULL,
            guild_id INTEGER NOT NULL,
            PRIMARY KEY(user_id, role_id)
        );
        CREATE TABLE IF NOT EXISTS shop_roles (
            role_id     INTEGER PRIMARY KEY,
            guild_id    INTEGER NOT NULL,
            name        TEXT    NOT NULL,
            price       INTEGER NOT NULL,
            color       INTEGER NOT NULL DEFAULT 0,
            description TEXT    DEFAULT ''
        );
        CREATE TABLE IF NOT EXISTS shop_messages (
            guild_id   INTEGER PRIMARY KEY,
            channel_id INTEGER NOT NULL,
            message_id INTEGER NOT NULL
        );
        CREATE TABLE IF NOT EXISTS guild_settings (
            guild_id          INTEGER PRIMARY KEY,
            xp_per_min        INTEGER DEFAULT 10,
            coins_per_min     INTEGER DEFAULT 5,
            max_session_min   INTEGER DEFAULT 720,
            min_vc_members    INTEGER DEFAULT 1,
            bonus_multiplier  REAL    DEFAULT 1.0,
            allowed_role_id   INTEGER DEFAULT 0,
            log_channel_id    INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS blocked_channels (
            channel_id INTEGER NOT NULL,
            guild_id   INTEGER NOT NULL,
            PRIMARY KEY(channel_id, guild_id)
        );
        CREATE TABLE IF NOT EXISTS active_timers (
            vc_id           INTEGER PRIMARY KEY,
            message_id      INTEGER NOT NULL,
            owner_id        INTEGER NOT NULL,
            guild_id        INTEGER NOT NULL,
            text_channel_id INTEGER NOT NULL,
            theme           TEXT    NOT NULL,
            duration        INTEGER NOT NULL,
            break_time      INTEGER NOT NULL,
            start_time      REAL    NOT NULL,
            end_time        REAL    NOT NULL
        );
        CREATE TABLE IF NOT EXISTS timer_members (
            vc_id     INTEGER NOT NULL,
            user_id   INTEGER NOT NULL,
            joined_at REAL    NOT NULL,
            PRIMARY KEY(vc_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS session_history (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            guild_id     INTEGER NOT NULL,
            vc_id        INTEGER NOT NULL,
            theme        TEXT    NOT NULL,
            duration     INTEGER NOT NULL,
            xp_earned    INTEGER NOT NULL,
            coins_earned INTEGER NOT NULL,
            completed_at TEXT    DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS audit_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id    INTEGER NOT NULL,
            guild_id   INTEGER NOT NULL,
            xp_delta   INTEGER DEFAULT 0,
            coin_delta INTEGER DEFAULT 0,
            reason     TEXT    NOT NULL,
            ts         REAL    DEFAULT (unixepoch())
        );
        """)

    # ── Low-level helpers ─────────────────────────────────────────────────────
    async def _q1(self, sql: str, params=()):
        async with self._conn.execute(sql, params) as c:
            return await c.fetchone()

    async def _qa(self, sql: str, params=()):
        async with self._conn.execute(sql, params) as c:
            return await c.fetchall()

    async def _ex(self, sql: str, params=()):
        await self._conn.execute(sql, params)
        await self._conn.commit()

    async def _audit(self, uid: int, guild_id: int, xp: int, coins: int, reason: str):
        await self._conn.execute(
            "INSERT INTO audit_log(user_id,guild_id,xp_delta,coin_delta,reason)"
            " VALUES(?,?,?,?,?)",
            (uid, guild_id, xp, coins, reason)
        )
        await self._conn.commit()

    # ── Users ─────────────────────────────────────────────────────────────────
    async def ensure_user(self, uid: int):
        await self._ex("INSERT OR IGNORE INTO users(user_id) VALUES(?)", (uid,))

    async def get_user(self, uid: int):
        await self.ensure_user(uid)
        return await self._q1("SELECT * FROM users WHERE user_id=?", (uid,))

    async def add_xp(self, uid: int, amount: int, guild_id: int = 0, reason: str = ""):
        await self.ensure_user(uid)
        await self._ex("UPDATE users SET xp=xp+? WHERE user_id=?", (amount, uid))
        await self._pet_xp(uid, amount // 2)
        if reason:
            await self._audit(uid, guild_id, amount, 0, reason)

    async def add_coins(self, uid: int, amount: int, guild_id: int = 0,
                        reason: str = "") -> int:
        await self.ensure_user(uid)
        await self._ex("UPDATE users SET coins=coins+? WHERE user_id=?", (amount, uid))
        if reason:
            await self._audit(uid, guild_id, 0, amount, reason)
        return (await self.get_user(uid))["coins"]

    async def spend_coins(self, uid: int, amount: int) -> bool:
        row = await self.get_user(uid)
        if row["coins"] < amount:
            return False
        await self._ex("UPDATE users SET coins=coins-? WHERE user_id=?", (amount, uid))
        return True

    async def add_focus_time(self, uid: int, minutes: int):
        await self._ex(
            "UPDATE users SET total_focus=total_focus+?,"
            " sessions=sessions+1 WHERE user_id=?",
            (minutes, uid)
        )

    async def bulk_reward(self, user_ids: list, xp: int, coins: int,
                          guild_id: int = 0, reason: str = "voice_minute"):
        """Award XP+coins atomically. Skips xp_blocked users. Applies bonus_multiplier."""
        if not user_ids:
            return
        # Apply guild bonus multiplier
        s   = await self.get_settings(guild_id)
        mul = s.get("bonus_multiplier", 1.0)
        xp_actual    = max(1, round(xp * mul))
        coins_actual = max(1, round(coins * mul))

        for uid in user_ids:
            flag = await self._q1(
                "SELECT xp_blocked FROM user_flags WHERE user_id=? AND guild_id=?",
                (uid, guild_id)
            )
            if flag and flag["xp_blocked"]:
                continue
            await self.ensure_user(uid)
            await self._conn.execute(
                "UPDATE users SET xp=xp+?, coins=coins+? WHERE user_id=?",
                (xp_actual, coins_actual, uid)
            )
            await self._pet_xp(uid, xp_actual // 2)

        await self._conn.commit()

        if reason:
            for uid in user_ids:
                await self._conn.execute(
                    "INSERT INTO audit_log(user_id,guild_id,xp_delta,coin_delta,reason)"
                    " VALUES(?,?,?,?,?)",
                    (uid, guild_id, xp_actual, coins_actual, reason)
                )
            await self._conn.commit()

    async def get_leaderboard(self, limit: int = 10):
        return await self._qa(
            "SELECT * FROM users ORDER BY xp DESC LIMIT ?", (limit,)
        )

    # ── Streaks ───────────────────────────────────────────────────────────────
    async def update_streak(self, uid: int):
        today     = datetime.date.today().isoformat()
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()
        row = await self._q1("SELECT * FROM user_streaks WHERE user_id=?", (uid,))
        if not row:
            await self._ex(
                "INSERT INTO user_streaks(user_id,current,longest,last_session)"
                " VALUES(?,1,1,?)", (uid, today)
            )
            return
        if row["last_session"] == today:
            return  # already counted
        cur = (row["current"] + 1) if row["last_session"] == yesterday else 1
        lng = max(row["longest"], cur)
        await self._ex(
            "UPDATE user_streaks SET current=?,longest=?,last_session=?"
            " WHERE user_id=?",
            (cur, lng, today, uid)
        )

    async def get_streak(self, uid: int) -> dict:
        row = await self._q1("SELECT * FROM user_streaks WHERE user_id=?", (uid,))
        return dict(row) if row else {"current": 0, "longest": 0, "last_session": ""}

    # ── User flags ────────────────────────────────────────────────────────────
    async def set_xp_block(self, uid: int, guild_id: int,
                            blocked: bool, note: str = ""):
        await self._ex(
            "INSERT OR REPLACE INTO user_flags(user_id,guild_id,xp_blocked,note)"
            " VALUES(?,?,?,?)",
            (uid, guild_id, int(blocked), note[:200])
        )

    async def get_flag(self, uid: int, guild_id: int):
        return await self._q1(
            "SELECT * FROM user_flags WHERE user_id=? AND guild_id=?",
            (uid, guild_id)
        )

    async def get_all_flags(self, guild_id: int):
        return await self._qa(
            "SELECT * FROM user_flags WHERE guild_id=? AND xp_blocked=1", (guild_id,)
        )

    # ── Pets ──────────────────────────────────────────────────────────────────
    async def add_pet(self, uid: int, species: str, name: str, rarity: str) -> int:
        await self.ensure_user(uid)
        async with self._conn.execute(
            "INSERT INTO pets(user_id,species,name,rarity) VALUES(?,?,?,?)",
            (uid, species, name, rarity)
        ) as c:
            pid = c.lastrowid
        await self._conn.commit()
        return pid

    async def get_pets(self, uid: int):
        return await self._qa(
            "SELECT * FROM pets WHERE user_id=? ORDER BY active DESC, level DESC",
            (uid,)
        )

    async def get_pet(self, pid: int):
        return await self._q1("SELECT * FROM pets WHERE pet_id=?", (pid,))

    async def get_active_pet(self, uid: int):
        return await self._q1(
            "SELECT * FROM pets WHERE user_id=? AND active=1", (uid,)
        )

    async def set_active_pet(self, uid: int, pid: int):
        await self._ex("UPDATE pets SET active=0 WHERE user_id=?", (uid,))
        await self._ex(
            "UPDATE pets SET active=1 WHERE pet_id=? AND user_id=?", (pid, uid)
        )

    async def rename_pet(self, pid: int, uid: int, name: str):
        name = name.strip()[:32]
        await self._ex(
            "UPDATE pets SET name=? WHERE pet_id=? AND user_id=?", (name, pid, uid)
        )

    async def _pet_xp(self, uid: int, amount: int):
        if amount <= 0:
            return
        pet = await self.get_active_pet(uid)
        if not pet:
            return
        xp, lv = pet["xp"] + amount, pet["level"]
        while xp >= lv * 100:
            xp -= lv * 100
            lv += 1
        await self._conn.execute(
            "UPDATE pets SET xp=?, level=? WHERE pet_id=?",
            (xp, lv, pet["pet_id"])
        )

    # ── Shop ─────────────────────────────────────────────────────────────────
    async def add_shop_role(self, role_id: int, guild_id: int, name: str,
                             price: int, color: int, desc: str):
        price = max(1, min(price, 10_000_000))
        await self._ex(
            "INSERT OR REPLACE INTO shop_roles VALUES(?,?,?,?,?,?)",
            (role_id, guild_id, name[:64], price, color, desc[:200])
        )

    async def get_shop_roles(self, guild_id: int):
        return await self._qa(
            "SELECT * FROM shop_roles WHERE guild_id=? ORDER BY price", (guild_id,)
        )

    async def remove_shop_role(self, role_id: int):
        await self._ex("DELETE FROM shop_roles WHERE role_id=?", (role_id,))

    async def owns_role(self, uid: int, role_id: int) -> bool:
        return bool(await self._q1(
            "SELECT 1 FROM owned_roles WHERE user_id=? AND role_id=?",
            (uid, role_id)
        ))

    async def grant_role(self, uid: int, role_id: int, guild_id: int):
        await self._ex(
            "INSERT OR IGNORE INTO owned_roles VALUES(?,?,?)",
            (uid, role_id, guild_id)
        )

    async def set_shop_message(self, guild_id: int, channel_id: int, message_id: int):
        await self._ex(
            "INSERT OR REPLACE INTO shop_messages VALUES(?,?,?)",
            (guild_id, channel_id, message_id)
        )

    async def get_shop_message(self, guild_id: int):
        return await self._q1(
            "SELECT * FROM shop_messages WHERE guild_id=?", (guild_id,)
        )

    # ── Guild settings ────────────────────────────────────────────────────────
    async def get_settings(self, guild_id: int) -> dict:
        row = await self._q1(
            "SELECT * FROM guild_settings WHERE guild_id=?", (guild_id,)
        )
        if row:
            return dict(row)
        return {"guild_id": guild_id, **_DEFAULTS}

    async def set_settings(self, guild_id: int, **kwargs):
        cur = await self.get_settings(guild_id)
        cur.update(kwargs)
        await self._ex(
            "INSERT OR REPLACE INTO guild_settings VALUES(?,?,?,?,?,?,?,?)",
            (
                guild_id,
                cur["xp_per_min"],
                cur["coins_per_min"],
                cur["max_session_min"],
                cur["min_vc_members"],
                cur["bonus_multiplier"],
                cur["allowed_role_id"],
                cur["log_channel_id"],
            )
        )

    # ── Blocked channels ──────────────────────────────────────────────────────
    async def block_channel(self, channel_id: int, guild_id: int):
        await self._ex(
            "INSERT OR IGNORE INTO blocked_channels VALUES(?,?)",
            (channel_id, guild_id)
        )

    async def unblock_channel(self, channel_id: int, guild_id: int):
        await self._ex(
            "DELETE FROM blocked_channels WHERE channel_id=? AND guild_id=?",
            (channel_id, guild_id)
        )

    async def is_blocked(self, channel_id: int, guild_id: int) -> bool:
        return bool(await self._q1(
            "SELECT 1 FROM blocked_channels WHERE channel_id=? AND guild_id=?",
            (channel_id, guild_id)
        ))

    async def get_blocked_channels(self, guild_id: int):
        return await self._qa(
            "SELECT channel_id FROM blocked_channels WHERE guild_id=?", (guild_id,)
        )

    # ── Timers ────────────────────────────────────────────────────────────────
    async def get_timer(self, vc_id: int):
        return await self._q1(
            "SELECT * FROM active_timers WHERE vc_id=?", (vc_id,)
        )

    async def get_all_timers(self):
        return await self._qa("SELECT * FROM active_timers")

    async def save_timer(self, vc_id: int, message_id: int, owner_id: int,
                          guild_id: int, text_ch_id: int, theme: str,
                          duration: int, break_time: int, start: float, end: float):
        await self._ex(
            "INSERT OR REPLACE INTO active_timers VALUES(?,?,?,?,?,?,?,?,?,?)",
            (vc_id, message_id, owner_id, guild_id,
             text_ch_id, theme, duration, break_time, start, end)
        )

    async def delete_timer(self, vc_id: int):
        await self._ex("DELETE FROM active_timers WHERE vc_id=?", (vc_id,))
        await self._ex("DELETE FROM timer_members WHERE vc_id=?", (vc_id,))

    # ── Timer members ─────────────────────────────────────────────────────────
    async def add_timer_member(self, vc_id: int, uid: int, joined_at: float):
        await self.ensure_user(uid)
        await self._ex(
            "INSERT OR IGNORE INTO timer_members(vc_id,user_id,joined_at)"
            " VALUES(?,?,?)",
            (vc_id, uid, joined_at)
        )

    async def remove_timer_member(self, vc_id: int, uid: int):
        await self._ex(
            "DELETE FROM timer_members WHERE vc_id=? AND user_id=?",
            (vc_id, uid)
        )

    async def get_timer_members(self, vc_id: int):
        return await self._qa(
            "SELECT * FROM timer_members WHERE vc_id=?", (vc_id,)
        )

    # ── Session history ───────────────────────────────────────────────────────
    async def log_session(self, uid: int, guild_id: int, vc_id: int,
                           theme: str, duration: int, xp: int, coins: int):
        await self._ex(
            "INSERT INTO session_history"
            "(user_id,guild_id,vc_id,theme,duration,xp_earned,coins_earned)"
            " VALUES(?,?,?,?,?,?,?)",
            (uid, guild_id, vc_id, theme, duration, xp, coins)
        )

    async def get_session_history(self, uid: int, limit: int = 5):
        return await self._qa(
            "SELECT * FROM session_history WHERE user_id=?"
            " ORDER BY id DESC LIMIT ?",
            (uid, limit)
        )

    async def get_audit_log(self, uid: int, guild_id: int, limit: int = 20):
        return await self._qa(
            "SELECT * FROM audit_log WHERE user_id=? AND guild_id=?"
            " ORDER BY id DESC LIMIT ?",
            (uid, guild_id, limit)
        )
