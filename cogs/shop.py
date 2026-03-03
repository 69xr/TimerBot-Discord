"""
Shop Cog — Role shop + leaderboard.
Admins configure roles; members spend coins earned from focus sessions.
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging

log = logging.getLogger("Shop")


class RoleShopView(discord.ui.View):
    def __init__(self, cog: "ShopCog", user: discord.Member, roles: list):
        super().__init__(timeout=180)
        self.cog   = cog
        self.user  = user
        self.roles = roles
        self._add_select()

    def _add_select(self):
        if not self.roles:
            return
        opts = [
            discord.SelectOption(
                label=f"{r['icon']} {r['name']}",
                description=f"🪙 {r['price']:,} coins  —  {(r['description'] or 'No description')[:50]}",
                value=str(r["role_id"]),
            )
            for r in self.roles[:25]
        ]
        sel = discord.ui.Select(placeholder="🛒  Choose a role to buy...", options=opts)
        sel.callback = self._on_select
        self.add_item(sel)

    async def _on_select(self, interaction: discord.Interaction):
        if interaction.user.id != self.user.id:
            return await interaction.response.send_message(
                "❌ This isn't your shop session.", ephemeral=True
            )
        role_id = int(interaction.data["values"][0])
        await self.cog._do_buy_role(interaction, role_id)


class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # /shop ────────────────────────────────────────────────────────────────────
    @app_commands.command(name="shop", description="🛍️ Browse roles you can buy with your focus coins")
    async def shop(self, interaction: discord.Interaction):
        roles = await self.bot.db.get_shop_roles(interaction.guild_id)
        udata = await self.bot.db.get_user(interaction.user.id)
        coins = udata["coins"] if udata else 0

        if not roles:
            embed = discord.Embed(
                title="🛍️  Role Shop",
                description=(
                    "**The shop is empty!**\n\n"
                    "No roles are on sale yet.\n"
                    "Admins can add roles with `/addshoprole`."
                ),
                color=0xFF6B35,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed = discord.Embed(
            title="🛍️  Role Shop",
            description=(
                f"💰 **Your balance:** 🪙 `{coins:,}` coins\n"
                f"Earn more by completing `/timer` sessions!\n\u200b"
            ),
            color=0xFF6B35,
        )
        for r in roles[:12]:
            dr = interaction.guild.get_role(r["role_id"]) if interaction.guild else None
            mention = dr.mention if dr else f"**{r['name']}**"
            embed.add_field(
                name=f"{r['icon']}  {r['name']}",
                value=f"{mention}\n🪙 `{r['price']:,}` coins\n_{r['description'] or 'No description'}_",
                inline=True,
            )
        embed.set_footer(text="Select a role from the dropdown below to purchase it.")

        view = RoleShopView(self, interaction.user, roles)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    # /addshoprole ─────────────────────────────────────────────────────────────
    @app_commands.command(name="addshoprole", description="⚙️ [Admin] Add a role to the shop")
    @app_commands.describe(
        role="Discord role to put on sale",
        price="Price in coins",
        icon="Emoji icon (default ✨)",
        description="Short description for the shop listing",
    )
    @app_commands.default_permissions(administrator=True)
    async def addshoprole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        price: app_commands.Range[int, 1, 1_000_000],
        icon: str = "✨",
        description: str = "",
    ):
        await self.bot.db.add_shop_role(
            role.id, interaction.guild_id,
            role.name, price, role.color.value, icon, description
        )
        embed = discord.Embed(
            title="✅  Role Added to Shop",
            description=(
                f"{icon} {role.mention} is now for sale!\n\n"
                f"💰 **Price:** `{price:,}` coins\n"
                f"📝 **Description:** {description or '_None_'}"
            ),
            color=0x00FF88,
        )
        await interaction.response.send_message(embed=embed)

    # /removeshoprole ──────────────────────────────────────────────────────────
    @app_commands.command(name="removeshoprole", description="⚙️ [Admin] Remove a role from the shop")
    @app_commands.default_permissions(administrator=True)
    async def removeshoprole(self, interaction: discord.Interaction, role: discord.Role):
        await self.bot.db.remove_shop_role(role.id)
        await interaction.response.send_message(
            f"🗑️ **{role.mention}** has been removed from the shop.", ephemeral=True
        )

    # /givecoins ───────────────────────────────────────────────────────────────
    @app_commands.command(name="givecoins", description="⚙️ [Admin] Give coins to a member")
    @app_commands.default_permissions(administrator=True)
    async def givecoins(
        self,
        interaction: discord.Interaction,
        user: discord.Member,
        amount: app_commands.Range[int, 1, 100_000],
    ):
        new_bal = await self.bot.db.add_coins(user.id, amount)
        embed = discord.Embed(
            title="🪙  Coins Given",
            description=f"Gave **{amount:,} coins** to {user.mention}\nNew balance: **{new_bal:,} coins**",
            color=0xFFD700,
        )
        await interaction.response.send_message(embed=embed)

    # /leaderboard ─────────────────────────────────────────────────────────────
    @app_commands.command(name="leaderboard", description="🏆 View the server's top focus grinders")
    async def leaderboard(self, interaction: discord.Interaction):
        rows = await self.bot.db.get_leaderboard(10)
        if not rows:
            return await interaction.response.send_message("No data yet — start with `/timer`!", ephemeral=True)

        guild   = interaction.guild
        medals  = ["🥇", "🥈", "🥉"]
        lines   = []
        for i, row in enumerate(rows):
            member = guild.get_member(row["user_id"]) if guild else None
            name   = member.display_name if member else f"User {row['user_id']}"
            medal  = medals[i] if i < 3 else f"`#{i+1}`"
            hrs    = row["total_focus"] // 60
            lines.append(
                f"{medal} **{name}**\n"
                f"  ⭐ `{row['xp']:,} XP`  🪙 `{row['coins']:,}`  ⏱ `{hrs}h`  📚 `{row['sessions']} sessions`"
            )

        embed = discord.Embed(
            title="🏆  Focus Beast Leaderboard",
            description="\n\n".join(lines),
            color=0xFFD700,
        )
        embed.set_footer(text="Earn XP by staying in voice during /timer sessions!")
        await interaction.response.send_message(embed=embed)

    # ── Internal buy ──────────────────────────────────────────────────────────
    async def _do_buy_role(self, interaction: discord.Interaction, role_id: int):
        db    = self.bot.db
        guild = interaction.guild
        user  = interaction.user

        shop_roles = await db.get_shop_roles(guild.id)
        rdata = next((r for r in shop_roles if r["role_id"] == role_id), None)
        if not rdata:
            return await interaction.response.send_message("❌ Role not found in shop.", ephemeral=True)

        if await db.owns_role(user.id, role_id):
            dr = guild.get_role(role_id)
            if dr and dr not in user.roles:
                try:
                    await user.add_roles(dr)
                except discord.Forbidden:
                    pass
            return await interaction.response.send_message(
                f"✅ You already own **{rdata['icon']} {rdata['name']}** — role re-applied!",
                ephemeral=True,
            )

        spent = await db.spend_coins(user.id, rdata["price"])
        if not spent:
            udata = await db.get_user(user.id)
            need  = rdata["price"] - udata["coins"]
            return await interaction.response.send_message(
                f"❌ Not enough coins!\n"
                f"🪙 You have `{udata['coins']:,}` — need `{rdata['price']:,}` (`{need:,}` short)\n"
                f"_Keep doing /timer sessions to earn more!_",
                ephemeral=True,
            )

        dr = guild.get_role(role_id)
        if dr:
            try:
                await user.add_roles(dr)
            except discord.Forbidden:
                await db.add_coins(user.id, rdata["price"])
                return await interaction.response.send_message(
                    "❌ I don't have permission to assign that role. Coins refunded.", ephemeral=True
                )

        await db.grant_role(user.id, role_id, guild.id)
        embed = discord.Embed(
            title="🎉  Role Purchased!",
            description=(
                f"You bought **{rdata['icon']} {rdata['name']}**!\n\n"
                f"💸 Spent: `{rdata['price']:,}` coins\n"
                f"The role has been applied. Flex it! 💪"
            ),
            color=dr.color if dr else discord.Color.gold(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)