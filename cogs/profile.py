"""
Profile Cog — /profile command with rendered profile card.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import logging
from core.image_engine import PETS

log = logging.getLogger("Profile")


class ProfileCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="profile", description="👤 View your focus stats and profile card")
    @app_commands.describe(user="View another user's profile (optional)")
    async def profile(self, interaction: discord.Interaction, user: Optional[discord.Member] = None):
        target = user or interaction.user
        db = self.bot.db

        user_data = await db.get_user(target.id)
        active_pet = await db.get_active_pet(target.id)
        pet_dict = dict(active_pet) if active_pet else None

        buf = self.bot.image_engine.render_profile(
            target.display_name,
            user_data["xp"],
            user_data["coins"],
            user_data["total_focus"],
            user_data["sessions"],
            active_pet=pet_dict,
        )
        file = discord.File(buf, filename="profile.png")

        embed = discord.Embed(
            title=f"👤  {target.display_name}'s Profile",
            color=0x5080FF,
        )

        # XP level calculation
        xp = user_data["xp"]
        level = int(xp ** 0.5) // 10 + 1
        embed.add_field(name="⭐ XP", value=f"{xp:,}", inline=True)
        embed.add_field(name="📊 Level", value=str(level), inline=True)
        embed.add_field(name="🪙 Coins", value=f"{user_data['coins']:,}", inline=True)
        embed.add_field(name="⏱ Total Focus", value=f"{user_data['total_focus']:,} min", inline=True)
        embed.add_field(name="📚 Sessions", value=str(user_data["sessions"]), inline=True)

        if active_pet:
            p = PETS.get(active_pet["species"], {})
            embed.add_field(
                name="🐾 Active Pet",
                value=f"{p.get('emoji', '?')} **{active_pet['name']}** (Lv.{active_pet['level']})",
                inline=True,
            )

        embed.set_image(url="attachment://profile.png")
        embed.set_footer(text="Use /timer to earn more XP and coins!")
        await interaction.response.send_message(embed=embed, file=file)