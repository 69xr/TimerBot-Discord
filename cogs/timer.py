"""
FocusBeast — Timer Cog v2
===========================
Security & features:
  - Rate limit: one /timer attempt per user every 10 seconds
  - Respects guild allowed_role_id (if set, only that role can start timers)
  - Respects blocked_channels (VC timer forbidden in listed channels)
  - Respects max_session_min from guild settings
  - Respects min_vc_members (won't start if not enough people in VC)
  - XP rewards respect bonus_multiplier and xp_blocked user flag
  - Multi-VC: unlimited concurrent sessions, each independent
  - Empty VC auto-shutdown with notification
  - Session history logged on completion
  - Daily streak updated on completion
  - Cooldown between consecutive sessions per user (60s)
  - Log channel posting for session events if configured
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
import logging
from typing import Optional

from core.image_engine import THEMES

log = logging.getLogger("Timer")

# ── Constants ─────────────────────────────────────────────────────────────────
EDIT_EVERY     = 30   # seconds between image refreshes
TICK           = 5    # main loop resolution in seconds
USER_COOLDOWN  = 60   # seconds a user must wait before starting another session

THEME_CHOICES = [
    app_commands.Choice(name=t.label.title(), value=t.name)
    for t in THEMES.values()
]


# ── Stop Button View ──────────────────────────────────────────────────────────
class TimerView(discord.ui.View):
    """Persistent stop button. Survives bot restarts via custom_id."""

    def __init__(self, cog: "TimerCog", vc_id: int, owner_id: int):
        super().__init__(timeout=None)
        self.cog      = cog
        self.vc_id    = vc_id
        self.owner_id = owner_id

    @discord.ui.button(
        label="⏹ Stop Session",
        style=discord.ButtonStyle.danger,
        custom_id="fb:timer_stop",
    )
    async def stop(self, interaction: discord.Interaction, _btn):
        member = interaction.guild.get_member(interaction.user.id)
        in_vc  = (
            member
            and member.voice
            and member.voice.channel
            and member.voice.channel.id == self.vc_id
        )
        is_admin = member and member.guild_permissions.administrator

        if interaction.user.id != self.owner_id and not in_vc and not is_admin:
            return await interaction.response.send_message(
                "Only the session owner, a member in the voice channel, "
                "or an admin can stop this.",
                ephemeral=True,
            )

        self.cog._cancel(self.vc_id)
        embed = discord.Embed(
            title="Session Stopped",
            description=(
                f"**{interaction.user.display_name}** ended the session early.\n"
                "Start a new one any time with `/timer`."
            ),
            color=0xFF4444,
        )
        await interaction.response.edit_message(embed=embed, attachments=[], view=None)


# ── Timer Cog ─────────────────────────────────────────────────────────────────
class TimerCog(commands.Cog):

    def __init__(self, bot: commands.Bot):
        self.bot   = bot
        # vc_id → bool (alive flag per running session)
        self._alive: dict[int, bool] = {}
        # user_id → last session end timestamp (for cooldown)
        self._last_session: dict[int, float] = {}

    def _cancel(self, vc_id: int):
        self._alive[vc_id] = False

    # ── /timer ────────────────────────────────────────────────────────────────
    @app_commands.command(
        name="timer",
        description="Start a focus session for your voice channel",
    )
    @app_commands.describe(
        duration="Session length in minutes (5–720)",
        theme="Visual theme for the timer image",
        break_time="Break length after session (10–55 min)",
    )
    @app_commands.choices(theme=THEME_CHOICES)
    @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)  # 1 per 10s per user
    async def timer(
        self,
        interaction: discord.Interaction,
        duration:   app_commands.Range[int, 5, 720],
        theme:      str,
        break_time: app_commands.Range[int, 5, 55] = 15,
    ):
        db     = self.bot.db
        member = interaction.guild.get_member(interaction.user.id)

        # ── Security: must be in a voice channel ──────────────────────────────
        if not member or not member.voice or not member.voice.channel:
            return await interaction.response.send_message(
                "You must be in a voice channel to start a timer.\n"
                "Join a voice channel, then run `/timer` again.",
                ephemeral=True,
            )

        vc = member.voice.channel
        s  = await db.get_settings(interaction.guild_id)

        # ── Security: allowed_role check ──────────────────────────────────────
        allowed_role_id = s.get("allowed_role_id", 0)
        if allowed_role_id:
            role_ids = {r.id for r in member.roles}
            if allowed_role_id not in role_ids and not member.guild_permissions.administrator:
                role = interaction.guild.get_role(allowed_role_id)
                rname = role.name if role else f"Role {allowed_role_id}"
                return await interaction.response.send_message(
                    f"Only members with the **{rname}** role can start focus sessions.",
                    ephemeral=True,
                )

        # ── Security: blocked channel check ───────────────────────────────────
        if await db.is_blocked(vc.id, interaction.guild_id):
            return await interaction.response.send_message(
                f"**{vc.name}** is blocked from focus sessions.\n"
                "Ask an admin to unblock it with `/admin unblock`.",
                ephemeral=True,
            )

        # ── Security: max session duration ────────────────────────────────────
        max_dur = s.get("max_session_min", 720)
        if duration > max_dur:
            return await interaction.response.send_message(
                f"Maximum session length for this server is **{max_dur} minutes**.",
                ephemeral=True,
            )

        # ── Security: one timer per VC ────────────────────────────────────────
        if vc.id in self._alive or await db.get_timer(vc.id):
            return await interaction.response.send_message(
                f"**{vc.name}** already has a session running.\n"
                "Stop the current one first, or join a different voice channel.",
                ephemeral=True,
            )

        # ── Security: min VC members ──────────────────────────────────────────
        min_members = s.get("min_vc_members", 1)
        vc_humans   = [m for m in vc.members if not m.bot]
        if len(vc_humans) < min_members:
            return await interaction.response.send_message(
                f"At least **{min_members}** member(s) must be in the voice channel "
                "to start a session.",
                ephemeral=True,
            )

        # ── Security: user cooldown (prevents spam-starting) ──────────────────
        last = self._last_session.get(interaction.user.id, 0)
        wait = USER_COOLDOWN - (time.time() - last)
        if wait > 0:
            return await interaction.response.send_message(
                f"Please wait **{int(wait)}s** before starting another session.",
                ephemeral=True,
            )

        # ── Build session ─────────────────────────────────────────────────────
        xp_pm    = s["xp_per_min"]
        coins_pm = s["coins_per_min"]
        now      = time.time()
        total    = duration * 60
        end      = now + total
        names    = [m.display_name for m in vc_humans]

        pet     = await db.get_active_pet(interaction.user.id)
        pet_key = pet["species"] if pet else None
        pet_nm  = pet["name"]    if pet else None

        # Send initial image
        ie    = self.bot.image_engine
        t     = THEMES[theme]
        buf   = ie.render_timer(theme, total, total, break_time,
                                pet_key, pet_nm, names, xp_pm, coins_pm)
        file  = discord.File(buf, filename="timer.png")
        embed = self._make_embed(t, total, duration, break_time,
                                 vc.name, names, xp_pm, coins_pm)
        embed.set_image(url="attachment://timer.png")

        await interaction.response.send_message(embed=embed, file=file)
        msg = await interaction.original_response()
        await msg.edit(view=TimerView(self, vc.id, interaction.user.id))

        # Persist session
        await db.save_timer(
            vc.id, msg.id, interaction.user.id, interaction.guild_id,
            interaction.channel_id, theme, duration, break_time, now, end,
        )
        for m in vc_humans:
            await db.add_timer_member(vc.id, m.id, now)

        self._alive[vc.id] = True

        # Post to log channel if configured
        await self._post_log(
            interaction.guild, s,
            f"Session started in **{vc.name}** by {interaction.user.mention} "
            f"({duration} min, {theme} theme)."
        )

        asyncio.create_task(
            self._run(
                interaction, msg, vc,
                theme, duration, break_time, end,
                pet_key, pet_nm, xp_pm, coins_pm,
                interaction.guild_id,
            )
        )

    # ── Voice state listener ──────────────────────────────────────────────────
    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after:  discord.VoiceState,
    ):
        if member.bot:
            return

        db  = self.bot.db
        now = time.time()

        # Left a VC with a timer
        if before.channel and before.channel.id in self._alive:
            vc          = before.channel
            await db.remove_timer_member(vc.id, member.id)
            live_humans = [m for m in vc.members if not m.bot]
            log.info(f"{member.display_name} left {vc.name} "
                     f"({len(live_humans)} remaining)")

            # Auto-shutdown if VC is empty
            if not live_humans:
                log.info(f"{vc.name} empty — auto-stopping timer")
                self._cancel(vc.id)

        # Joined a VC with a timer
        if after.channel and after.channel.id in self._alive:
            await db.add_timer_member(after.channel.id, member.id, now)
            log.info(f"{member.display_name} joined {after.channel.name} — tracking")

    # ── Main loop ─────────────────────────────────────────────────────────────
    async def _run(
        self,
        interaction: discord.Interaction,
        msg:         discord.Message,
        vc:          discord.VoiceChannel,
        theme:       str,
        duration:    int,
        break_time:  int,
        end:         float,
        pet_key:     Optional[str],
        pet_nm:      Optional[str],
        xp_pm:       int,
        coins_pm:    int,
        guild_id:    int,
    ):
        db        = self.bot.db
        ie        = self.bot.image_engine
        t         = THEMES[theme]
        total     = duration * 60
        last_tick = -1
        last_edit = time.time()

        while self._alive.get(vc.id, False):
            remaining = int(end - time.time())
            if remaining <= 0:
                break

            # Award XP/coins once per elapsed minute
            elapsed = (total - remaining) // 60
            if elapsed > last_tick and elapsed > 0:
                last_tick = elapsed
                tracked   = await db.get_timer_members(vc.id)
                live_ids  = {m.id for m in vc.members if not m.bot}
                eligible  = [r["user_id"] for r in tracked if r["user_id"] in live_ids]
                if eligible:
                    await db.bulk_reward(
                        eligible, xp_pm, coins_pm,
                        guild_id=guild_id,
                        reason=f"voice_minute:{elapsed}",
                    )
                    log.info(
                        f"[{vc.name}] min={elapsed} "
                        f"+{xp_pm}xp +{coins_pm}c → {len(eligible)}"
                    )

            # Refresh image every EDIT_EVERY seconds
            if time.time() - last_edit >= EDIT_EVERY:
                last_edit  = time.time()
                live_names = [m.display_name for m in vc.members if not m.bot]
                try:
                    buf   = ie.render_timer(
                        theme, remaining, total, break_time,
                        pet_key, pet_nm, live_names, xp_pm, coins_pm,
                    )
                    file  = discord.File(buf, filename="timer.png")
                    embed = self._make_embed(
                        t, remaining, duration, break_time,
                        vc.name, live_names, xp_pm, coins_pm,
                    )
                    embed.set_image(url="attachment://timer.png")
                    await msg.edit(
                        embed=embed, attachments=[file],
                        view=TimerView(self, vc.id, interaction.user.id),
                    )
                except (discord.NotFound, discord.HTTPException) as e:
                    log.warning(f"Edit failed: {e}")
                    break

            await asyncio.sleep(TICK)

        # ── Cancelled or empty VC ─────────────────────────────────────────────
        if not self._alive.get(vc.id, False):
            self._alive.pop(vc.id, None)
            await db.delete_timer(vc.id)

            # Notify text channel if VC went empty
            ch   = self.bot.get_channel(interaction.channel_id)
            live = [m for m in vc.members if not m.bot]
            if ch and not live:
                await ch.send(
                    f"Session in **{vc.name}** ended — the voice channel became empty."
                )
            return

        # ── Session complete ───────────────────────────────────────────────────
        self._alive.pop(vc.id, None)

        tracked   = await db.get_timer_members(vc.id)
        live_ids  = {m.id for m in vc.members if not m.bot}
        finishers = [r["user_id"] for r in tracked if r["user_id"] in live_ids]

        # Completion bonus scales with duration
        bonus_xp    = max(10, duration // 5) * 2
        bonus_coins = duration * 3

        if finishers:
            await db.bulk_reward(
                finishers, bonus_xp, bonus_coins,
                guild_id=guild_id,
                reason="session_complete_bonus",
            )
            for uid in finishers:
                await db.add_focus_time(uid, duration)
                await db.update_streak(uid)
                await db.log_session(
                    uid, guild_id, vc.id, theme,
                    duration, bonus_xp, bonus_coins,
                )

        # Record cooldown for session owner
        self._last_session[interaction.user.id] = time.time()

        await db.delete_timer(vc.id)

        # Final image
        live_names = [m.display_name for m in vc.members if not m.bot]
        buf  = ie.render_timer(theme, 0, total, break_time,
                               pet_key, pet_nm, live_names, xp_pm, coins_pm)
        file = discord.File(buf, filename="timer.png")
        embed = discord.Embed(
            title="Session Complete! 🎉",
            description=(
                f"**{duration}-minute** focus session finished!\n\n"
                f"**Completion bonus** for everyone who stayed:\n"
                f"`+{bonus_xp} XP`  ·  `+{bonus_coins} coins`\n\n"
                f"Now take a **{break_time}-minute** break. You earned it."
            ),
            color=0x00E87A,
        )
        embed.set_image(url="attachment://timer.png")
        embed.set_footer(text="Use /profile to see your updated stats · Use /streak for your streak")
        await msg.edit(embed=embed, attachments=[file], view=None)

        # Ping finishers
        ch = self.bot.get_channel(interaction.channel_id)
        if ch and finishers:
            pings = " ".join(f"<@{u}>" for u in finishers)
            await ch.send(
                f"{pings}\nSession complete! Enjoy your **{break_time}-minute** break."
            )

        # Log to guild log channel
        s = await db.get_settings(guild_id)
        await self._post_log(
            interaction.guild, s,
            f"Session in **{vc.name}** completed. "
            f"{len(finishers)} finisher(s). "
            f"+{bonus_xp} XP, +{bonus_coins} coins each."
        )

    # ── /activesessions ───────────────────────────────────────────────────────
    @app_commands.command(
        name="activesessions",
        description="View all currently running focus sessions in this server",
    )
    async def activesessions(self, interaction: discord.Interaction):
        if not self._alive:
            return await interaction.response.send_message(
                "No active focus sessions right now.", ephemeral=True
            )

        lines = []
        for vc_id in list(self._alive.keys()):
            vc  = interaction.guild.get_channel(vc_id)
            row = await self.bot.db.get_timer(vc_id)
            if not vc or not row:
                continue
            remaining = int(row["end_time"] - time.time())
            mins, secs = remaining // 60, remaining % 60
            members   = [m.display_name for m in vc.members if not m.bot]
            lines.append(
                f"**{vc.name}** — `{mins:02d}:{secs:02d}` left\n"
                f"  Members: {', '.join(members) if members else 'Nobody'}"
            )

        embed = discord.Embed(
            title=f"Active Sessions ({len(lines)})",
            description="\n\n".join(lines) or "None",
            color=0x5080FF,
        )
        embed.set_footer(text="Each voice channel runs its own independent timer")
        await interaction.response.send_message(embed=embed)

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _make_embed(self, theme, remaining, duration, break_time,
                    vc_name, names, xp_pm, coins_pm) -> discord.Embed:
        m, s = remaining // 60, remaining % 60
        pct  = int((1 - remaining / max(duration*60, 1)) * 100)
        embed = discord.Embed(
            title=theme.label,
            description=(
                f"**`{m:02d}:{s:02d}`** remaining  ·  {pct}% complete\n"
                f"Voice channel: **{vc_name}**\n\n"
                f"**In session:** "
                f"{'  ·  '.join(names) if names else '*Nobody*'}"
            ),
            color=theme.discord_color,
        )
        embed.set_footer(
            text=f"{duration} min total  ·  "
                 f"+{xp_pm} XP & +{coins_pm} coins per minute in voice"
        )
        return embed

    async def _post_log(self, guild: discord.Guild, settings: dict, text: str):
        """Post a message to the guild's log channel if configured."""
        ch_id = settings.get("log_channel_id", 0)
        if not ch_id:
            return
        ch = guild.get_channel(ch_id)
        if not ch:
            return
        try:
            await ch.send(f"📋 {text}")
        except Exception:
            pass
