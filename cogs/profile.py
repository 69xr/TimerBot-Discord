"""
Profile Cog — /profile, /xp, /leaderboard
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import logging

from core.image_engine import PIXEL_PETS, RARITY_LABELS

log = logging.getLogger("Profile")


class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # /profile ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="profile", description="👤 View your full focus stats and profile card")
    @app_commands.describe(user="View another member's profile (optional)")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target    = user or interaction.user
        db        = self.bot.db
        udata     = await db.get_user(target.id)
        active    = await db.get_active_pet(target.id)
        pet_dict  = dict(active) if active else None

        buf  = self.bot.image_engine.render_profile(
            target.display_name,
            udata["xp"], udata["coins"],
            udata["total_focus"], udata["sessions"],
            active_pet=pet_dict,
        )
        file  = discord.File(buf, filename="profile.png")
        level = max(1, int(udata["xp"] ** 0.45) // 5)

        embed = discord.Embed(
            title=f"📊  {target.display_name}'s Focus Profile",
            color=0x5080FF,
        )
        embed.add_field(name="⭐ XP",        value=f"`{udata['xp']:,}`",             inline=True)
        embed.add_field(name="📊 Level",      value=f"`{level}`",                     inline=True)
        embed.add_field(name="🪙 Coins",      value=f"`{udata['coins']:,}`",          inline=True)
        embed.add_field(name="⏱ Focus Time", value=f"`{udata['total_focus']:,} min`", inline=True)
        embed.add_field(name="📚 Sessions",   value=f"`{udata['sessions']}`",          inline=True)

        if active:
            p = PIXEL_PETS.get(active["species"], {})
            embed.add_field(
                name="🐾 Active Pet",
                value=f"**{active['name']}** — {RARITY_LABELS.get(active['rarity'], active['rarity'])} Lv.{active['level']}",
                inline=True,
            )

        embed.set_image(url="attachment://profile.png")
        embed.set_footer(text="Use /timer to earn XP & coins  •  /petshop to adopt companions")
        await interaction.response.send_message(embed=embed, file=file)

    # /xp ──────────────────────────────────────────────────────────────────────
    @app_commands.command(name="xp", description="⭐ Check your XP and level")
    async def xp(self, interaction: discord.Interaction):
        udata = await self.bot.db.get_user(interaction.user.id)
        level = max(1, int(udata["xp"] ** 0.45) // 5)
        xp_next = int(((level + 1) * 5) ** (1 / 0.45))
        embed = discord.Embed(
            title=f"⭐  {interaction.user.display_name}'s XP",
            description=(
                f"**Level:** `{level}`\n"
                f"**XP:** `{udata['xp']:,}` / `{xp_next:,}` to next level\n"
                f"**Coins:** 🪙 `{udata['coins']:,}`\n\n"
                f"*Earn XP by staying in voice during /timer sessions!*"
            ),
            color=0xFFD700,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)