"""
FocusBeast — Discord Focus Timer Bot
=====================================
Run: python main.py
Set token via environment variable: DISCORD_TOKEN=your_token_here python main.py
Or place token directly in TOKEN below (not recommended for production).
"""

import discord
from discord.ext import commands, tasks
import os
import logging
import asyncio
import sys
from pathlib import Path

from core.database     import Database
from core.image_engine import ImageEngine
from cogs.timer        import TimerCog
from cogs.shop         import ShopCog
from cogs.pets         import PetsCog
from cogs.profile      import ProfileCog
from cogs.settings     import SettingsCog
from cogs.admin        import AdminCog

# ── Logging ───────────────────────────────────────────────────────────────────
Path("logs").mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("logs/focusbeast.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("FocusBeast")

# ── Token ─────────────────────────────────────────────────────────────────────
TOKEN = os.getenv("DISCORD_TOKEN", "Bot Token")
if TOKEN == "YOUR_BOT_TOKEN_HERE":
    log.error("No token set. Put your token in DISCORD_TOKEN env var or edit main.py")
    sys.exit(1)

# ── Status messages rotation ──────────────────────────────────────────────────
_STATUSES = [
    ("watching",   "you grind"),
    ("playing",    "FocusBeast"),
    ("watching",   "focus sessions"),
    ("listening",  "/timer"),
    ("watching",   "the leaderboard"),
]


class FocusBeast(commands.Bot):
    def __init__(self):
        intents              = discord.Intents.default()
        intents.voice_states = True
        intents.members      = True
        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
            # Security: only respond to slash commands, disable prefix help
        )
        self.db           = Database("data/focusbeast.db")
        self.image_engine = ImageEngine()
        self._status_idx  = 0

    # ── Setup ─────────────────────────────────────────────────────────────────
    async def setup_hook(self):
        Path("data").mkdir(exist_ok=True)
        await self.db.init()

        cogs = [TimerCog, ShopCog, PetsCog, ProfileCog, SettingsCog, AdminCog]
        for Cog in cogs:
            try:
                await self.add_cog(Cog(self))
                log.info(f"Loaded cog: {Cog.__name__}")
            except Exception as e:
                log.error(f"Failed to load {Cog.__name__}: {e}")

        self._rotate_status.start()

    # ── Ready ─────────────────────────────────────────────────────────────────
    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info(f"Connected to {len(self.guilds)} guild(s)")

        # Sync slash commands per-guild for instant availability
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                log.info(f"Synced {len(synced)} commands → {guild.name}")
            except Exception as e:
                log.error(f"Sync failed for {guild.name}: {e}")

    # ── Status rotation ───────────────────────────────────────────────────────
    @tasks.loop(minutes=5)
    async def _rotate_status(self):
        kind, text = _STATUSES[self._status_idx % len(_STATUSES)]
        self._status_idx += 1
        act_type = {
            "watching":  discord.ActivityType.watching,
            "playing":   discord.ActivityType.playing,
            "listening": discord.ActivityType.listening,
        }[kind]
        await self.change_presence(
            activity=discord.Activity(type=act_type, name=text)
        )

    @_rotate_status.before_loop
    async def _before_rotate(self):
        await self.wait_until_ready()

    # ── Global error handler ──────────────────────────────────────────────────
    async def on_app_command_error(self, interaction: discord.Interaction,
                                   error: discord.app_commands.AppCommandError):
        msg = "Something went wrong. Please try again."
        if isinstance(error, discord.app_commands.MissingPermissions):
            msg = "You don't have permission to use this command."
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            msg = f"This command is on cooldown. Try again in {error.retry_after:.1f}s."
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            msg = "I'm missing permissions to do that. Check my role settings."
        else:
            log.error(f"Unhandled command error in /{interaction.command.name}: {error}")

        try:
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
        except Exception:
            pass

    # ── Guild join: auto-sync ─────────────────────────────────────────────────
    async def on_guild_join(self, guild: discord.Guild):
        log.info(f"Joined guild: {guild.name} ({guild.id})")
        try:
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
        except Exception as e:
            log.error(f"Failed to sync commands for {guild.name}: {e}")

    # ── Graceful shutdown ─────────────────────────────────────────────────────
    async def close(self):
        log.info("Shutting down gracefully…")
        self._rotate_status.cancel()
        await self.db.close()
        await super().close()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    bot = FocusBeast()
    try:
        bot.run(TOKEN, log_handler=None)
    except discord.LoginFailure:
        log.error("Invalid token. Check your DISCORD_TOKEN.")
    except KeyboardInterrupt:
        log.info("Interrupted by user.")
