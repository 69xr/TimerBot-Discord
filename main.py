"""
╔══════════════════════════════════════════════════════╗
║           FOCUS BEAST — Discord Timer Bot            ║
║   Timer • XP • Shop • Roles • Pets • Leaderboard     ║
╚══════════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import os
import logging
from pathlib import Path

from core.database import Database
from core.image_engine import ImageEngine
from cogs.timer import TimerCog
from cogs.shop import ShopCog
from cogs.pets import PetsCog
from cogs.profile import ProfileCog

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("FocusBeast")

# ── Bot ────────────────────────────────────────────────────────────────────────
class FocusBeast(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.voice_states = True
        intents.members = True
        super().__init__(command_prefix="!", intents=intents, help_command=None)

        self.db = Database("data/focusbeast.db")
        self.image_engine = ImageEngine()

    async def setup_hook(self):
        Path("data").mkdir(exist_ok=True)
        await self.db.init()

        await self.add_cog(TimerCog(self))
        await self.add_cog(ShopCog(self))
        await self.add_cog(PetsCog(self))
        await self.add_cog(ProfileCog(self))

        # Clear old commands
        self.tree.clear_commands(guild=None)
        await self.tree.sync()
        log.info("🧹 Cleared old global slash commands")
        
        # Set flag for guild sync in on_ready
        self._pending_guild_sync = True

    async def on_ready(self):
        log.info(f"🚀 FocusBeast online as {self.user} ({self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="you grind 🔥"
            )
        )

        if getattr(self, "_pending_guild_sync", False):
            self._pending_guild_sync = False

            # Sync globally (takes ~1hr to propagate)
            await self.tree.sync()
            log.info("✅ Global slash commands synced (up to 1hr to show everywhere)")

            # Sync to all guilds for instant availability
            synced_guilds = 0
            for guild in self.guilds:
                try:
                    # Copy global commands to this guild
                    self.tree.copy_global_to(guild=guild)
                    await self.tree.sync(guild=guild)
                    synced_guilds += 1
                    log.info(f"✅ Synced commands to guild: {guild.name} ({guild.id})")
                except Exception as e:
                    log.warning(f"Could not sync to guild {guild.id}: {e}")

            log.info(f"⚡ Instantly synced to {synced_guilds} guild(s) — commands available NOW")


TOKEN = "MTQyNzY5MDA1MzEyMzE3ODU1OA.Gq55Wg.rlTa0NiFSq_0W1Y_uPVS9U3BbFH4lO4N4nTQuA"

if __name__ == "__main__":
    bot = FocusBeast()
    bot.run(TOKEN, log_handler=None)