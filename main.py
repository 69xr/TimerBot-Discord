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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger("FocusBeast")


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

        # Load cogs — registers all slash commands into the tree
        await self.add_cog(TimerCog(self))
        await self.add_cog(ShopCog(self))
        await self.add_cog(PetsCog(self))
        await self.add_cog(ProfileCog(self))

        # Verify commands loaded
        cmds = [c.name for c in self.tree.get_commands()]
        log.info(f"📋 Commands in tree: {cmds}")

    async def on_ready(self):
        log.info(f"🚀 FocusBeast online as {self.user} ({self.user.id})")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="you grind 🔥"
            )
        )

        # Guild-scoped sync = instant registration, no 1hr wait
        for guild in self.guilds:
            try:
                self.tree.copy_global_to(guild=guild)
                synced = await self.tree.sync(guild=guild)
                log.info(f"✅ Synced {len(synced)} commands to: {guild.name} ({guild.id})")
                for cmd in synced:
                    log.info(f"   /{cmd.name}")
            except Exception as e:
                log.error(f"❌ Failed guild sync {guild.name}: {e}")


TOKEN = ""
if __name__ == "__main__":
    bot = FocusBeast()
    bot.run(TOKEN, log_handler=None)