"""
FocusBeast — Shop Cog
Persistent role shop. The shop message stays forever and works after bot restarts.

Commands:
  /setupshop      — post the shop embed in this channel  [admin]
  /addshoprole    — add a role to the shop               [admin]
  /removeshoprole — remove a role                        [admin]
  /leaderboard    — top 10 XP earners
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging

log = logging.getLogger("Shop")


class BuySelect(discord.ui.Select):
    def __init__(self, cog: "ShopCog", roles: list):
        self.cog = cog
        opts = [
            discord.SelectOption(
                label=f"{r['name']}",
                description=f"{r['price']:,} coins  •  {(r['description'] or 'No description')[:60]}",
                value=str(r["role_id"]),
                emoji="🏷️",
            )
            for r in roles[:25]
        ]
        super().__init__(
            placeholder="Choose a role to purchase…",
            options=opts,
            custom_id="fb:shop_buy",
            row=0,
        )

    async def callback(self, interaction: discord.Interaction):
        await self.cog._buy(interaction, int(self.values[0]))


class ShopView(discord.ui.View):
    def __init__(self, cog: "ShopCog", roles: list):
        super().__init__(timeout=None)
        self.cog = cog
        if roles:
            self.add_item(BuySelect(cog, roles))

    @discord.ui.button(
        label="My Balance", style=discord.ButtonStyle.secondary,
        custom_id="fb:shop_balance", row=1, emoji="💰",
    )
    async def balance(self, i: discord.Interaction, _):
        u = await self.cog.bot.db.get_user(i.user.id)
        streak = await self.cog.bot.db.get_streak(i.user.id)
        embed  = discord.Embed(
            title="Your Balance",
            description=(
                f"**Coins:** {u['coins']:,}\n"
                f"**Total XP:** {u['xp']:,}\n"
                f"**Focus streak:** {streak['current']} day(s) "
                f"(best: {streak['longest']})\n\n"
                "Earn more coins by staying in voice during `/timer` sessions."
            ),
            color=0xFFD700,
        )
        await i.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(
        label="My Roles", style=discord.ButtonStyle.secondary,
        custom_id="fb:shop_myroles", row=1, emoji="🎭",
    )
    async def my_roles(self, i: discord.Interaction, _):
        shop  = await self.cog.bot.db.get_shop_roles(i.guild_id)
        ids   = {r["role_id"] for r in shop}
        owned = [r for r in i.user.roles if r.id in ids]
        if not owned:
            return await i.response.send_message(
                "You don't own any shop roles yet.\n"
                "Use the dropdown above to purchase one!",
                ephemeral=True,
            )
        embed = discord.Embed(
            title="Your Shop Roles",
            description="\n".join(f"• {r.mention}" for r in owned),
            color=0x8080FF,
        )
        await i.response.send_message(embed=embed, ephemeral=True)


class ShopCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        # Re-attach persistent view so buttons survive bot restarts
        self.bot.add_view(ShopView(self, []))

    # ── /setupshop ────────────────────────────────────────────────────────────
    @app_commands.command(
        name="setupshop",
        description="[Admin] Post the permanent role shop in this channel",
    )
    @app_commands.default_permissions(administrator=True)
    async def setupshop(self, i: discord.Interaction):
        await i.response.defer(ephemeral=True)
        roles = await self.bot.db.get_shop_roles(i.guild_id)
        embed = self._shop_embed(roles, i.guild)
        view  = ShopView(self, roles)
        msg   = await i.channel.send(embed=embed, view=view)
        await self.bot.db.set_shop_message(i.guild_id, i.channel_id, msg.id)
        await i.followup.send(
            f"Shop posted in {i.channel.mention}.\n"
            "Add roles with `/addshoprole` — the shop updates automatically.",
            ephemeral=True,
        )

    # ── /addshoprole ──────────────────────────────────────────────────────────
    @app_commands.command(
        name="addshoprole",
        description="[Admin] Add a role to the shop",
    )
    @app_commands.describe(
        role="Discord role to sell",
        price="Price in coins (1 – 1,000,000)",
        description="Short description shown in the shop (optional)",
    )
    @app_commands.default_permissions(administrator=True)
    async def addshoprole(
        self,
        i: discord.Interaction,
        role: discord.Role,
        price: app_commands.Range[int, 1, 1_000_000],
        description: str = "",
    ):
        # Safety: don't allow selling @everyone or managed roles
        if role.is_default() or role.managed:
            return await i.response.send_message(
                "Cannot add that role to the shop (it's managed or @everyone).",
                ephemeral=True,
            )
        await self.bot.db.add_shop_role(
            role.id, i.guild_id, role.name, price, role.color.value, description
        )
        await i.response.send_message(
            f"{role.mention} added to shop for **{price:,} coins**.", ephemeral=True
        )
        await self._refresh(i.guild)

    # ── /removeshoprole ───────────────────────────────────────────────────────
    @app_commands.command(
        name="removeshoprole",
        description="[Admin] Remove a role from the shop",
    )
    @app_commands.default_permissions(administrator=True)
    async def removeshoprole(self, i: discord.Interaction, role: discord.Role):
        await self.bot.db.remove_shop_role(role.id)
        await i.response.send_message(
            f"**{role.name}** removed from the shop.", ephemeral=True
        )
        await self._refresh(i.guild)

    # ── /leaderboard ──────────────────────────────────────────────────────────
    @app_commands.command(
        name="leaderboard",
        description="View the top 10 focus grinders in this server",
    )
    async def leaderboard(self, i: discord.Interaction):
        rows = await self.bot.db.get_leaderboard(10)
        if not rows:
            return await i.response.send_message(
                "No data yet. Use `/timer` in a voice channel to get started!",
                ephemeral=True,
            )
        MEDALS = ["🥇", "🥈", "🥉"]
        lines  = []
        for idx, r in enumerate(rows):
            member = i.guild.get_member(r["user_id"])
            name   = member.display_name if member else f"User {r['user_id']}"
            rank   = MEDALS[idx] if idx < 3 else f"`#{idx+1}`"
            hours  = r["total_focus"] // 60
            mins   = r["total_focus"] % 60
            lines.append(
                f"{rank} **{name}**\n"
                f"  {r['xp']:,} XP  ·  {r['coins']:,} coins  ·  "
                f"{hours}h {mins}m  ·  {r['sessions']} sessions"
            )
        embed = discord.Embed(
            title="🏆  Focus Leaderboard",
            description="\n\n".join(lines),
            color=0xFFD700,
        )
        embed.set_footer(text="Earn XP by staying in voice during /timer sessions")
        await i.response.send_message(embed=embed)

    # ── Buy logic ─────────────────────────────────────────────────────────────
    async def _buy(self, i: discord.Interaction, role_id: int):
        db    = self.bot.db
        guild = i.guild
        user  = i.user

        # Validate role exists in shop
        roles = await db.get_shop_roles(guild.id)
        rd    = next((r for r in roles if r["role_id"] == role_id), None)
        if not rd:
            return await i.response.send_message(
                "That role is no longer available in the shop.",
                ephemeral=True,
            )

        # Already owns it — just re-apply
        if await db.owns_role(user.id, role_id):
            dr = guild.get_role(role_id)
            if dr and dr not in user.roles:
                try:
                    await user.add_roles(dr, reason="FocusBeast shop re-apply")
                except discord.Forbidden:
                    pass
            return await i.response.send_message(
                f"You already own **{rd['name']}** — role re-applied to your account.",
                ephemeral=True,
            )

        # Check balance
        u = await db.get_user(user.id)
        if u["coins"] < rd["price"]:
            shortage = rd["price"] - u["coins"]
            return await i.response.send_message(
                f"Not enough coins.\n"
                f"You have **{u['coins']:,}** — need **{rd['price']:,}** "
                f"(short by **{shortage:,}**).\n\n"
                "Keep focusing in voice channels to earn more!",
                ephemeral=True,
            )

        # Spend coins
        if not await db.spend_coins(user.id, rd["price"]):
            return await i.response.send_message(
                "Transaction failed — please try again.", ephemeral=True
            )

        # Assign Discord role
        dr = guild.get_role(role_id)
        if dr:
            try:
                await user.add_roles(dr, reason="FocusBeast shop purchase")
            except discord.Forbidden:
                # Refund — bot can't assign the role
                await db.add_coins(user.id, rd["price"],
                                   reason="shop_refund_no_permission")
                return await i.response.send_message(
                    "I don't have permission to assign that role.\n"
                    "Your coins have been refunded. Tell an admin to fix my role position.",
                    ephemeral=True,
                )
        else:
            # Role was deleted — refund
            await db.add_coins(user.id, rd["price"], reason="shop_refund_deleted_role")
            await db.remove_shop_role(role_id)
            await self._refresh(guild)
            return await i.response.send_message(
                "That role no longer exists in this server. Coins refunded.",
                ephemeral=True,
            )

        await db.grant_role(user.id, role_id, guild.id)
        await db._audit(user.id, guild.id, 0, -rd["price"], f"shop_buy:{rd['name']}")

        new_bal = (await db.get_user(user.id))["coins"]
        embed   = discord.Embed(
            title="Purchase Successful!",
            description=(
                f"You now have **{rd['name']}**!\n\n"
                f"Spent: **{rd['price']:,} coins**\n"
                f"New balance: **{new_bal:,} coins**"
            ),
            color=dr.color.value if dr else 0x00CC66,
        )
        await i.response.send_message(embed=embed, ephemeral=True)

    # ── Shop refresh ──────────────────────────────────────────────────────────
    async def _refresh(self, guild: discord.Guild):
        row = await self.bot.db.get_shop_message(guild.id)
        if not row:
            return
        try:
            ch    = guild.get_channel(row["channel_id"])
            msg   = await ch.fetch_message(row["message_id"])
            roles = await self.bot.db.get_shop_roles(guild.id)
            await msg.edit(
                embed=self._shop_embed(roles, guild),
                view=ShopView(self, roles),
            )
        except Exception as e:
            log.warning(f"Shop refresh failed for {guild.name}: {e}")

    def _shop_embed(self, roles: list, guild: discord.Guild) -> discord.Embed:
        embed = discord.Embed(
            title="🛍️  Role Shop",
            description=(
                "Spend coins earned from focus sessions to unlock exclusive roles.\n"
                "Pick a role from the dropdown below.\u200b"
            ),
            color=0x1A1A2E,
        )
        if not roles:
            embed.add_field(
                name="No roles available yet",
                value="Check back later — an admin will add roles soon.",
                inline=False,
            )
        else:
            for r in roles:
                dr  = guild.get_role(r["role_id"])
                val = (
                    f"{dr.mention if dr else r['name']}\n"
                    f"**{r['price']:,} coins**\n"
                    f"_{r['description'] or 'No description'}_"
                )
                embed.add_field(name=r["name"], value=val, inline=True)
        embed.set_footer(text="Earn coins by staying in voice during /timer sessions")
        return embed
