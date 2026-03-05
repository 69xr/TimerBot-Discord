"""
FocusBeast — Admin Cog
All admin-only tools in one place. Admin = Discord administrator permission.

Commands:
  /admin block    — block a VC from running timers
  /admin unblock  — unblock a VC
  /admin setrole  — set/clear required role for /timer
  /admin setlog   — set/clear session log channel
  /admin xpblock  — block a user from earning XP/coins
  /admin xpunblock— unblock a user
  /admin givexp   — give XP to a user
  /admin takexp   — take XP from a user
  /admin givecoins— give coins to a user
  /admin takecoins— take coins from a user
  /admin resetuser— wipe a user's XP, coins, sessions
  /admin audit    — view a user's recent XP/coin history
  /admin status   — overview of bot status in this server
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging
import time

log = logging.getLogger("Admin")


class AdminCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    admin = app_commands.Group(
        name="admin",
        description="[Admin] FocusBeast administration tools",
        default_permissions=discord.Permissions(administrator=True),
    )

    # ── block / unblock ───────────────────────────────────────────────────────
    @admin.command(name="block", description="Block a channel from running focus timers")
    @app_commands.describe(channel="The voice or text channel to block")
    async def block(self, i: discord.Interaction, channel: discord.abc.GuildChannel):
        await self.bot.db.block_channel(channel.id, i.guild_id)
        await i.response.send_message(
            f"**{channel.name}** is now blocked from focus sessions.", ephemeral=True
        )
        log.info(f"[{i.guild.name}] Blocked channel {channel.name} by {i.user}")

    @admin.command(name="unblock", description="Remove a channel's timer block")
    @app_commands.describe(channel="The channel to unblock")
    async def unblock(self, i: discord.Interaction, channel: discord.abc.GuildChannel):
        await self.bot.db.unblock_channel(channel.id, i.guild_id)
        await i.response.send_message(
            f"**{channel.name}** is now unblocked.", ephemeral=True
        )

    @admin.command(name="blocklist", description="Show all blocked channels")
    async def blocklist(self, i: discord.Interaction):
        rows = await self.bot.db.get_blocked_channels(i.guild_id)
        if not rows:
            return await i.response.send_message(
                "No channels are blocked.", ephemeral=True
            )
        lines = []
        for r in rows:
            ch = i.guild.get_channel(r["channel_id"])
            ch_str = ch.mention if ch else f"ID {r['channel_id']}"
            lines.append(f"• {ch_str}")
        embed = discord.Embed(
            title="Blocked Channels",
            description="\n".join(lines),
            color=0xFF4444,
        )
        await i.response.send_message(embed=embed, ephemeral=True)

    # ── role / log ────────────────────────────────────────────────────────────
    @admin.command(name="setrole",
                   description="Require a role to use /timer (leave blank to remove)")
    @app_commands.describe(role="Role required to start sessions (optional)")
    async def setrole(self, i: discord.Interaction,
                      role: discord.Role = None):
        rid = role.id if role else 0
        await self.bot.db.set_settings(i.guild_id, allowed_role_id=rid)
        if role:
            await i.response.send_message(
                f"Only members with **{role.name}** can now start focus sessions.",
                ephemeral=True,
            )
        else:
            await i.response.send_message(
                "Timer access restriction removed — anyone can start sessions.",
                ephemeral=True,
            )

    @admin.command(name="setlog",
                   description="Set a channel to log session events (leave blank to disable)")
    @app_commands.describe(channel="Text channel for logs (optional)")
    async def setlog(self, i: discord.Interaction,
                     channel: discord.TextChannel = None):
        cid = channel.id if channel else 0
        await self.bot.db.set_settings(i.guild_id, log_channel_id=cid)
        if channel:
            await i.response.send_message(
                f"Session events will be logged in {channel.mention}.", ephemeral=True
            )
        else:
            await i.response.send_message(
                "Session logging disabled.", ephemeral=True
            )

    # ── XP block ──────────────────────────────────────────────────────────────
    @admin.command(name="xpblock",
                   description="Block a user from earning XP or coins")
    @app_commands.describe(user="The member to block", reason="Reason (logged)")
    async def xpblock(self, i: discord.Interaction,
                      user: discord.Member, reason: str = "No reason given"):
        await self.bot.db.set_xp_block(user.id, i.guild_id, True, reason)
        await i.response.send_message(
            f"{user.mention} is now blocked from earning XP and coins.\n"
            f"Reason: *{reason}*",
            ephemeral=True,
        )
        log.warning(f"[{i.guild.name}] XP blocked {user} — {reason} — by {i.user}")

    @admin.command(name="xpunblock",
                   description="Remove XP block from a user")
    @app_commands.describe(user="The member to unblock")
    async def xpunblock(self, i: discord.Interaction, user: discord.Member):
        await self.bot.db.set_xp_block(user.id, i.guild_id, False)
        await i.response.send_message(
            f"{user.mention} can earn XP and coins again.", ephemeral=True
        )

    @admin.command(name="xpblocklist",
                   description="List all users currently blocked from earning XP")
    async def xpblocklist(self, i: discord.Interaction):
        rows = await self.bot.db.get_all_flags(i.guild_id)
        if not rows:
            return await i.response.send_message(
                "No users are currently XP-blocked.", ephemeral=True
            )
        lines = []
        for r in rows:
            m = i.guild.get_member(r["user_id"])
            name = m.mention if m else f"User {r['user_id']}"
            lines.append(f"• {name} — _{r['note'] or 'No reason'}_")
        embed = discord.Embed(
            title="XP-Blocked Users",
            description="\n".join(lines),
            color=0xFF8800,
        )
        await i.response.send_message(embed=embed, ephemeral=True)

    # ── XP management ─────────────────────────────────────────────────────────
    @admin.command(name="givexp", description="Give XP to a member")
    @app_commands.describe(user="Target member", amount="Amount of XP to give")
    async def givexp(self, i: discord.Interaction,
                     user: discord.Member,
                     amount: app_commands.Range[int, 1, 1_000_000]):
        await self.bot.db.add_xp(
            user.id, amount, i.guild_id, f"admin_give by {i.user.id}"
        )
        u = await self.bot.db.get_user(user.id)
        await i.response.send_message(
            f"Gave **{amount:,} XP** to {user.mention}. "
            f"New total: **{u['xp']:,} XP**.",
            ephemeral=True,
        )

    @admin.command(name="takexp", description="Remove XP from a member")
    @app_commands.describe(user="Target member", amount="Amount to remove")
    async def takexp(self, i: discord.Interaction,
                     user: discord.Member,
                     amount: app_commands.Range[int, 1, 1_000_000]):
        u = await self.bot.db.get_user(user.id)
        actual = min(amount, u["xp"])
        await self.bot.db.add_xp(
            user.id, -actual, i.guild_id, f"admin_take by {i.user.id}"
        )
        await i.response.send_message(
            f"Removed **{actual:,} XP** from {user.mention}.", ephemeral=True
        )

    # ── Coin management ───────────────────────────────────────────────────────
    @admin.command(name="givecoins", description="Give coins to a member")
    @app_commands.describe(user="Target member", amount="Amount to give")
    async def givecoins(self, i: discord.Interaction,
                        user: discord.Member,
                        amount: app_commands.Range[int, 1, 10_000_000]):
        bal = await self.bot.db.add_coins(
            user.id, amount, i.guild_id, f"admin_give by {i.user.id}"
        )
        await i.response.send_message(
            f"Gave **{amount:,} coins** to {user.mention}. "
            f"New balance: **{bal:,}**.",
            ephemeral=True,
        )

    @admin.command(name="takecoins", description="Remove coins from a member")
    @app_commands.describe(user="Target member", amount="Amount to remove")
    async def takecoins(self, i: discord.Interaction,
                        user: discord.Member,
                        amount: app_commands.Range[int, 1, 10_000_000]):
        u = await self.bot.db.get_user(user.id)
        actual = min(amount, u["coins"])
        await self.bot.db.spend_coins(user.id, actual)
        await i.response.send_message(
            f"Removed **{actual:,} coins** from {user.mention}.", ephemeral=True
        )

    # ── User reset ────────────────────────────────────────────────────────────
    @admin.command(name="resetuser",
                   description="Wipe a user's XP, coins and session count")
    @app_commands.describe(user="The member to reset",
                           confirm="Type CONFIRM to proceed")
    async def resetuser(self, i: discord.Interaction,
                        user: discord.Member, confirm: str):
        if confirm.upper() != "CONFIRM":
            return await i.response.send_message(
                "Pass `confirm:CONFIRM` to confirm this destructive action.",
                ephemeral=True,
            )
        await self.bot.db._ex(
            "UPDATE users SET xp=0, coins=100, total_focus=0, sessions=0"
            " WHERE user_id=?",
            (user.id,)
        )
        await self.bot.db._ex(
            "DELETE FROM user_streaks WHERE user_id=?", (user.id,)
        )
        await self.bot.db._audit(
            user.id, i.guild_id, 0, 0, f"full_reset by {i.user.id}"
        )
        await i.response.send_message(
            f"{user.mention} has been reset to default stats.", ephemeral=True
        )
        log.warning(f"[{i.guild.name}] Reset {user} by {i.user}")

    # ── Audit log ─────────────────────────────────────────────────────────────
    @admin.command(name="audit",
                   description="View recent XP/coin transactions for a user")
    @app_commands.describe(user="Member to audit", limit="Number of entries (max 20)")
    async def audit(self, i: discord.Interaction,
                    user: discord.Member,
                    limit: app_commands.Range[int, 1, 20] = 10):
        rows = await self.bot.db.get_audit_log(user.id, i.guild_id, limit)
        if not rows:
            return await i.response.send_message(
                f"No audit records for {user.mention}.", ephemeral=True
            )

        lines = []
        for r in rows:
            ts    = f"<t:{int(r['ts'])}:R>"
            parts = []
            if r["xp_delta"]:
                sign = "+" if r["xp_delta"] > 0 else ""
                parts.append(f"{sign}{r['xp_delta']} XP")
            if r["coin_delta"]:
                sign = "+" if r["coin_delta"] > 0 else ""
                parts.append(f"{sign}{r['coin_delta']} coins")
            lines.append(f"{ts} `{', '.join(parts)}` — {r['reason']}")

        embed = discord.Embed(
            title=f"Audit Log — {user.display_name}",
            description="\n".join(lines),
            color=0x888888,
        )
        embed.set_footer(text=f"Showing {len(rows)} most recent entries")
        await i.response.send_message(embed=embed, ephemeral=True)

    # ── Server status ─────────────────────────────────────────────────────────
    @admin.command(name="status",
                   description="Overview of FocusBeast in this server")
    async def status(self, i: discord.Interaction):
        db = self.bot.db
        s  = await db.get_settings(i.guild_id)

        # Active sessions in this guild
        timer_cog    = self.bot.cogs.get("TimerCog")
        active_in_guild = []
        if timer_cog:
            for vc_id, alive in timer_cog._alive.items():
                if not alive:
                    continue
                vc = i.guild.get_channel(vc_id)
                if vc:
                    row = await db.get_timer(vc_id)
                    if row:
                        rem = int(row["end_time"] - time.time())
                        active_in_guild.append(
                            f"**{vc.name}** — {rem//60}m {rem%60:02d}s left"
                        )

        blocked = await db.get_blocked_channels(i.guild_id)
        blocked_names = []
        for r in blocked:
            ch = i.guild.get_channel(r["channel_id"])
            blocked_names.append(ch.mention if ch else str(r["channel_id"]))

        allowed_rid = s.get("allowed_role_id", 0)
        log_cid     = s.get("log_channel_id", 0)

        embed = discord.Embed(
            title=f"FocusBeast Status — {i.guild.name}",
            color=0x5080FF,
        )
        embed.add_field(
            name="Active Sessions",
            value="\n".join(active_in_guild) or "None",
            inline=False,
        )
        embed.add_field(
            name="Rewards",
            value=(
                f"XP/min: **{s['xp_per_min']}** × **{s.get('bonus_multiplier',1)}**\n"
                f"Coins/min: **{s['coins_per_min']}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Session Limits",
            value=(
                f"Max duration: **{s.get('max_session_min',720)} min**\n"
                f"Min VC members: **{s.get('min_vc_members',1)}**"
            ),
            inline=True,
        )
        embed.add_field(
            name="Access",
            value=(
                f"Required role: {f'<@&{allowed_rid}>' if allowed_rid else 'Anyone'}\n"
                f"Log channel: {f'<#{log_cid}>' if log_cid else 'Disabled'}"
            ),
            inline=True,
        )
        embed.add_field(
            name="Blocked Channels",
            value=", ".join(blocked_names) or "None",
            inline=False,
        )
        embed.set_footer(text="Use /settings to change configuration")
        await i.response.send_message(embed=embed, ephemeral=True)
