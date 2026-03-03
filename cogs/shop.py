"""
Shop Cog — Buy Discord roles with coins earned from focus sessions.
Admins can add/remove roles from the shop.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import logging

log = logging.getLogger("Shop")


# ── Role Shop View ────────────────────────────────────────────────────────────
class RoleShopView(discord.ui.View):
    def __init__(self, cog: "ShopCog", user: discord.Member, roles: list, page: int = 0):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.roles = roles
        self.page = page
        self._update_buttons()

    def _update_buttons(self):
        # Rebuild select menu dynamically
        for item in self.children:
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)

        if self.roles:
            opts = []
            for r in self.roles:
                color_hex = f"#{r['color']:06X}"
                opts.append(discord.SelectOption(
                    label=f"{r['icon']} {r['name']}",
                    description=f"🪙 {r['price']:,} coins — {r['description'][:50] or 'No description'}",
                    value=str(r["role_id"]),
                ))
            select = discord.ui.Select(
                placeholder="🛒 Select a role to buy...",
                options=opts[:25]
            )
            select.callback = self._on_select
            self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.defer()
        role_id = int(interaction.data["values"][0])
        await self.cog._buy_role(interaction, role_id)


# ── Shop Cog ──────────────────────────────────────────────────────────────────
class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /shop ─────────────────────────────────────────────────────────────────
    @app_commands.command(name="shop", description="🛍️ Browse the role shop — spend your focus coins!")
    async def shop(self, interaction: discord.Interaction):
        roles = await self.bot.db.get_shop_roles(interaction.guild_id)
        user_data = await self.bot.db.get_user(interaction.user.id)
        coins = user_data["coins"] if user_data else 0

        if not roles:
            embed = discord.Embed(
                title="🛍️ Role Shop",
                description=(
                    "The shop is empty! No roles have been added yet.\n\n"
                    "**Admins:** Use `/addshoprole` to add roles for sale."
                ),
                color=0xFF6B35,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = self._build_shop_embed(roles, coins, interaction.guild)
        view = RoleShopView(self, interaction.user, roles)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # ── /addshoprole (admin) ──────────────────────────────────────────────────
    @app_commands.command(name="addshoprole", description="⚙️ [Admin] Add a role to the shop")
    @app_commands.describe(
        role="The Discord role to sell",
        price="Price in coins",
        icon="Emoji icon for the role (default: ✨)",
        description="Short description shown in shop",
    )
    @app_commands.default_permissions(administrator=True)
    async def addshoprole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        price: app_commands.Range[int, 1, 1000000],
        icon: str = "✨",
        description: str = "",
    ):
        await self.bot.db.add_shop_role(
            role.id, interaction.guild_id,
            role.name, price, role.color.value,
            icon, description
        )

        embed = discord.Embed(
            title="✅ Role Added to Shop",
            description=(
                f"**{icon} {role.mention}** is now for sale!\n\n"
                f"💰 Price: **{price:,} coins**\n"
                f"📝 Description: {description or 'None'}\n\n"
                f"Users can now buy it with `/shop`."
            ),
            color=0x00FF88,
        )
        await interaction.response.send_message(embed=embed)

    # ── /removeshoprole (admin) ────────────────────────────────────────────────
    @app_commands.command(name="removeshoprole", description="⚙️ [Admin] Remove a role from the shop")
    @app_commands.describe(role="The role to remove from sale")
    @app_commands.default_permissions(administrator=True)
    async def removeshoprole(self, interaction: discord.Interaction, role: discord.Role):
        await self.bot.db.remove_shop_role(role.id)
        embed = discord.Embed(
            title="🗑️ Role Removed",
            description=f"**{role.mention}** has been removed from the shop.",
            color=0xFF4444,
        )
        await interaction.response.send_message(embed=embed)

    # ── /givecoins (admin) ────────────────────────────────────────────────────
    @app_commands.command(name="givecoins", description="⚙️ [Admin] Give coins to a user")
    @app_commands.default_permissions(administrator=True)
    async def givecoins(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 100000],
    ):
        new_balance = await self.bot.db.add_coins(user.id, amount)
        embed = discord.Embed(
            title="🪙 Coins Given",
            description=f"Gave **{amount:,} coins** to {user.mention}\nNew balance: **{new_balance:,} coins**",
            color=0xFFD700,
        )
        await interaction.response.send_message(embed=embed)

    # ── /leaderboard ──────────────────────────────────────────────────────────
    @app_commands.command(name="leaderboard", description="🏆 View the XP leaderboard")
    async def leaderboard(self, interaction: discord.Interaction):
        rows = await self.bot.db.get_leaderboard(10)
        if not rows:
            return await interaction.response.send_message("No data yet!", ephemeral=True)

        guild = interaction.guild
        medals = ["🥇", "🥈", "🥉"]
        lines = []
        for i, row in enumerate(rows):
            member = guild.get_member(row["user_id"]) if guild else None
            name = member.display_name if member else f"User {row['user_id']}"
            medal = medals[i] if i < 3 else f"`#{i+1}`"
            hours = row["total_focus"] // 60
            lines.append(
                f"{medal} **{name}** — ⭐ {row['xp']:,} XP  |  ⏱ {hours}h  |  🪙 {row['coins']:,}"
            )

        embed = discord.Embed(
            title="🏆 Focus Beast Leaderboard",
            description="\n".join(lines),
            color=0xFFD700,
        )
        embed.set_footer(text="Earn XP by being in voice during /timer sessions!")
        await interaction.response.send_message(embed=embed)

    # ── Internal buy ─────────────────────────────────────────────────────────
    async def _buy_role(self, interaction: discord.Interaction, role_id: int):
        db = self.bot.db
        guild = interaction.guild
        user = interaction.user

        # Fetch shop role
        shop_roles = await db.get_shop_roles(guild.id)
        role_data = next((r for r in shop_roles if r["role_id"] == role_id), None)
        if not role_data:
            return await interaction.response.send_message("❌ Role not found in shop.", ephemeral=True)

        # Already owns
        if await db.owns_role(user.id, role_id):
            discord_role = guild.get_role(role_id)
            if discord_role and discord_role not in user.roles:
                await user.add_roles(discord_role)
            return await interaction.response.send_message(
                f"✅ You already own **{role_data['icon']} {role_data['name']}**! Role re-applied.",
                ephemeral=True
            )

        # Spend coins
        spent = await db.spend_coins(user.id, role_data["price"])
        if not spent:
            user_data = await db.get_user(user.id)
            return await interaction.response.send_message(
                f"❌ Not enough coins!\n"
                f"💰 You have: **{user_data['coins']:,}** coins\n"
                f"💸 Need: **{role_data['price']:,}** coins\n\n"
                f"Earn coins by completing focus sessions with `/timer`!",
                ephemeral=True
            )

        # Apply role
        discord_role = guild.get_role(role_id)
        if discord_role:
            try:
                await user.add_roles(discord_role)
            except discord.Forbidden:
                # Refund
                await db.add_coins(user.id, role_data["price"])
                return await interaction.response.send_message(
                    "❌ I don't have permission to assign this role. Coins refunded.",
                    ephemeral=True
                )

        await db.grant_role(user.id, role_id, guild.id)

        color = discord_role.color if discord_role else discord.Color.gold()
        embed = discord.Embed(
            title="🎉 Role Purchased!",
            description=(
                f"You bought **{role_data['icon']} {role_data['name']}**!\n\n"
                f"💸 Spent: **{role_data['price']:,} coins**\n\n"
                f"The role has been applied to your account. Flex it! 💪"
            ),
            color=color,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def _build_shop_embed(self, roles: list, coins: int, guild: discord.Guild) -> discord.Embed:
        embed = discord.Embed(
            title="🛍️ Role Shop",
            description=f"Your balance: 🪙 **{coins:,} coins**\n\nEarn more by completing `/timer` sessions!\n\u200b",
            color=0xFF6B35,
        )
        for r in roles[:15]:
            discord_role = guild.get_role(r["role_id"]) if guild else None
            role_mention = discord_role.mention if discord_role else r["name"]
            embed.add_field(
                name=f"{r['icon']} {r['name']}",
                value=f"{role_mention}\n💰 `{r['price']:,}` coins\n{r['description'] or '—'}",
                inline=True,
            )
        embed.set_footer(text="Select a role from the dropdown to buy it!")
        return embed