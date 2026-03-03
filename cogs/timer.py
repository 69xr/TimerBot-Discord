"""
Timer Cog — /timer command with live image updates, XP, voice tracking.
XP and coins are only awarded to members ACTIVELY in a voice channel.
"""

import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
import logging
from core.image_engine import THEMES

log = logging.getLogger("Timer")

THEME_CHOICES = [
    app_commands.Choice(name=t.label.title(), value=t.name)
    for t in THEMES.values()
]


class FinishButton(discord.ui.View):
    def __init__(self, cog: "TimerCog", message_id: int, user_id: int):
        super().__init__(timeout=None)
        self.cog       = cog
        self.message_id = message_id
        self.user_id   = user_id

    @discord.ui.button(label="  Finish Session", emoji="⏹️",
                       style=discord.ButtonStyle.danger, custom_id="finish_timer")
    async def finish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "❌ Only the session owner can stop this timer.", ephemeral=True
            )
        self.cog.cancel_timer(self.message_id)
        embed = discord.Embed(
            title="⏹️ Session Stopped",
            description=(
                f"**{interaction.user.display_name}** ended their focus session early.\n\n"
                "Even partial sessions count — keep grinding! 💪"
            ),
            color=0xFF4444,
        )
        embed.set_footer(text="Start a new session with /timer")
        await interaction.response.edit_message(embed=embed, attachments=[], view=None)


class TimerCog(commands.Cog):
    def __init__(self, bot):
        self.bot     = bot
        self._active: dict[int, bool] = {}  # message_id -> alive

    def cancel_timer(self, message_id: int):
        self._active[message_id] = False

    @app_commands.command(name="timer", description="🎯 Start a focus session with live countdown and XP rewards")
    @app_commands.describe(
        duration="Session length in minutes (5–720)",
        theme="Visual theme for your timer",
        break_time="Break time after session (10–55 min)",
    )
    @app_commands.choices(theme=THEME_CHOICES)
    async def timer(
        self,
        interaction: discord.Interaction,
        duration:   app_commands.Range[int, 5, 720],
        theme:      str,
        break_time: app_commands.Range[int, 10, 55] = 15,
    ):
        db = self.bot.db
        ie = self.bot.image_engine
        t  = THEMES[theme]

        # Resolve active pet
        pet_row  = await db.get_active_pet(interaction.user.id)
        pet_key  = pet_row["species"] if pet_row else None
        pet_name = pet_row["name"]    if pet_row else None

        total = duration * 60
        buf   = ie.render_timer(theme, total, total, break_time, pet_key, pet_name)
        file  = discord.File(buf, filename="timer.png")

        embed = self._build_embed(t, total, duration, break_time, pet_name)
        embed.set_image(url="attachment://timer.png")

        await interaction.response.send_message(embed=embed, file=file)
        message = await interaction.original_response()

        view = FinishButton(self, message.id, interaction.user.id)
        await message.edit(view=view)

        end_time = time.time() + total
        await db.save_timer(
            message.id, interaction.user.id, interaction.guild_id,
            interaction.channel_id, theme, duration, break_time, end_time
        )

        self._active[message.id] = True
        asyncio.create_task(
            self._run_timer(interaction, message, theme, duration, break_time, end_time)
        )

    # ── Timer loop ─────────────────────────────────────────────────────────────
    async def _run_timer(
        self,
        interaction: discord.Interaction,
        message:     discord.Message,
        theme:       str,
        duration:    int,
        break_time:  int,
        end_time:    float,
    ):
        db       = self.bot.db
        ie       = self.bot.image_engine
        t        = THEMES[theme]
        total    = duration * 60
        msg_id   = message.id
        user_id  = interaction.user.id

        last_xp_tick = -1
        last_edit    = time.time()

        # Cache pet once
        pet_row  = await db.get_active_pet(user_id)
        pet_key  = pet_row["species"] if pet_row else None
        pet_name = pet_row["name"]    if pet_row else None

        while self._active.get(msg_id, False):
            remaining = int(end_time - time.time())
            if remaining <= 0:
                break

            # ── XP + coins only if user IS in voice ──────────────────────────
            elapsed_mins = (total - remaining) // 60
            if elapsed_mins > last_xp_tick and elapsed_mins > 0:
                last_xp_tick = elapsed_mins
                guild  = self.bot.get_guild(interaction.guild_id)
                member = guild.get_member(user_id) if guild else None

                if member and member.voice and member.voice.channel:
                    # User is confirmed in a voice channel right now
                    await db.add_xp(user_id, 10)
                    await db.add_coins(user_id, 5)
                    log.info(
                        f"🎯 XP tick: {member.display_name} in "
                        f"#{member.voice.channel.name} — +10XP +5🪙"
                    )
                else:
                    log.info(
                        f"⏭ Skipped XP for {user_id} — not in voice at minute {elapsed_mins}"
                    )

            # ── Edit embed every 30 seconds ───────────────────────────────────
            now = time.time()
            if now - last_edit >= 30:
                last_edit = now
                try:
                    buf   = ie.render_timer(theme, remaining, total, break_time, pet_key, pet_name)
                    file  = discord.File(buf, filename="timer.png")
                    embed = self._build_embed(t, remaining, duration, break_time, pet_name)
                    embed.set_image(url="attachment://timer.png")
                    view  = FinishButton(self, msg_id, user_id)
                    await message.edit(embed=embed, attachments=[file], view=view)
                except (discord.NotFound, discord.HTTPException) as e:
                    log.warning(f"Timer edit failed: {e}")
                    break

            await asyncio.sleep(5)

        if not self._active.get(msg_id, False):
            # Manually cancelled
            self._active.pop(msg_id, None)
            await db.cancel_timer(msg_id)
            return

        # ── Session complete ──────────────────────────────────────────────────
        self._active.pop(msg_id, None)
        await db.cancel_timer(msg_id)
        await db.add_focus_time(user_id, duration)

        bonus_xp    = max(10, duration // 5)
        bonus_coins = duration * 2
        await db.add_xp(user_id, bonus_xp)
        await db.add_coins(user_id, bonus_coins)

        buf  = ie.render_timer(theme, 0, total, break_time, pet_key, pet_name)
        file = discord.File(buf, filename="timer.png")

        embed = discord.Embed(
            title="✅  Session Complete!",
            description=(
                f"**{duration} minute** focus session finished!\n\n"
                f"🎁 **Rewards earned:**\n"
                f"• `+{bonus_xp} XP` completion bonus\n"
                f"• `+{bonus_coins} 🪙` coins\n"
                f"• `+10 XP / +5 🪙` per minute spent in voice\n\n"
                f"☕ Take a **{break_time} minute** break — you earned it!"
            ),
            color=0x00FF88,
        )
        embed.set_image(url="attachment://timer.png")
        embed.set_footer(text="Use /profile to see your stats • /shop to spend coins")
        await message.edit(embed=embed, attachments=[file], view=None)

        channel = self.bot.get_channel(interaction.channel_id)
        if channel:
            await channel.send(
                f"<@{user_id}> ⏰ Focus session done! "
                f"Take a **{break_time} min** break! 🎉"
            )

    def _build_embed(self, theme, remaining: int, duration: int,
                     break_time: int, pet_name: str = None) -> discord.Embed:
        mins, secs = remaining // 60, remaining % 60
        desc = (
            f"**{mins:02d}:{secs:02d}** remaining\n"
            f"Break after: **{break_time} min**"
        )
        if pet_name:
            desc += f"\n\n🐾 **{pet_name}** is studying with you!"
        embed = discord.Embed(
            title=f"{theme.label}  —  {theme.name.upper()}",
            description=desc,
            color=theme.discord_color,
        )
        embed.set_footer(text=f"Total: {duration} min  •  +10 XP & +5 🪙 per minute IN VOICE")
        return embed