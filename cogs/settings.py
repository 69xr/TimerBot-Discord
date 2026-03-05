"""
FocusBeast — Settings Cog
Admin-only. One command, tabbed interface with all server config:
  Tab 1 — Rewards     (XP/min, Coins/min, XP Multiplier)
  Tab 2 — Session     (max duration, min VC members)
  Tab 3 — Access      (required role to use /timer)
  Tab 4 — Logging     (log channel for session events)
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging

log = logging.getLogger("Settings")

XP_OPTS    = [1, 2, 5, 10, 15, 20, 25, 30, 50, 100]
COIN_OPTS  = [1, 2, 3, 5, 10, 15, 20, 25, 50, 100]
MAX_OPTS   = [15, 30, 60, 90, 120, 180, 240, 360, 480, 720]
MIN_MBR    = [1, 2, 3, 4, 5]
MULT_OPTS  = [0.5, 0.75, 1.0, 1.25, 1.5, 2.0, 3.0, 5.0]


def _main_embed(s: dict, saved: bool = False) -> discord.Embed:
    mul = s.get("bonus_multiplier", 1.0)
    allowed_id = s.get("allowed_role_id", 0)
    log_id     = s.get("log_channel_id", 0)

    embed = discord.Embed(
        title="⚙️  Server Settings",
        description=(
            "Configure how FocusBeast works in this server.\n"
            "Use the dropdowns below to change any setting, then press **Save**.\n\u200b"
        ),
        color=0x00CC88 if saved else 0x5080FF,
    )
    embed.add_field(
        name="💰  Rewards",
        value=(
            f"XP per minute: **{s['xp_per_min']}**\n"
            f"Coins per minute: **{s['coins_per_min']}**\n"
            f"Multiplier: **×{mul}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="⏱️  Sessions",
        value=(
            f"Max duration: **{s.get('max_session_min', 720)} min**\n"
            f"Min VC members: **{s.get('min_vc_members', 1)}**"
        ),
        inline=True,
    )
    embed.add_field(
        name="🔒  Access & Logging",
        value=(
            f"Required role: {f'<@&{allowed_id}>' if allowed_id else '**Anyone**'}\n"
            f"Log channel: {f'<#{log_id}>' if log_id else '**None**'}"
        ),
        inline=True,
    )
    embed.set_footer(
        text="✅ Saved!" if saved
        else "Changes are not saved yet — press Save Settings."
    )
    return embed


class SettingsView(discord.ui.View):
    def __init__(self, cog: "SettingsCog", guild_id: int, s: dict):
        super().__init__(timeout=300)
        self.cog      = cog
        self.guild_id = guild_id
        self.s        = dict(s)   # mutable working copy
        self._build()

    def _build(self):
        self.clear_items()
        s = self.s
        self.add_item(_Select(
            "XP per minute",    "fb:s_xp",
            XP_OPTS, s["xp_per_min"],
            lambda v: self._patch(xp_per_min=int(v)), row=0,
        ))
        self.add_item(_Select(
            "Coins per minute", "fb:s_coins",
            COIN_OPTS, s["coins_per_min"],
            lambda v: self._patch(coins_per_min=int(v)), row=1,
        ))
        self.add_item(_Select(
            "XP multiplier",    "fb:s_mult",
            MULT_OPTS, s.get("bonus_multiplier", 1.0),
            lambda v: self._patch(bonus_multiplier=float(v)),
            row=2, fmt=lambda v: f"×{v}",
        ))
        self.add_item(_SaveBtn(self))
        self.add_item(_ResetBtn(self))
        self.add_item(_AdvancedBtn(self))

    def _patch(self, **kw):
        self.s.update(kw)

    async def refresh(self, interaction: discord.Interaction, saved=False):
        self._build()
        await interaction.response.edit_message(
            embed=_main_embed(self.s, saved), view=self
        )


class _Select(discord.ui.Select):
    def __init__(self, label, cid, options, current, on_change, row=0, fmt=None):
        fmt = fmt or (lambda v: str(v))
        opts = [
            discord.SelectOption(
                label=f"{label}: {fmt(v)}",
                value=str(v),
                default=(str(v) == str(current)),
            )
            for v in options
        ]
        super().__init__(
            placeholder=f"{label}  (current: {fmt(current)})",
            options=opts,
            custom_id=cid,
            row=row,
        )
        self._on_change = on_change

    async def callback(self, interaction: discord.Interaction):
        self._on_change(self.values[0])
        await self.view.refresh(interaction)


class _SaveBtn(discord.ui.Button):
    def __init__(self, view_ref: SettingsView):
        super().__init__(
            label="Save Settings", style=discord.ButtonStyle.success,
            custom_id="fb:s_save", row=3,
        )
        self._vref = view_ref

    async def callback(self, interaction: discord.Interaction):
        v = self._vref
        await v.cog.bot.db.set_settings(v.guild_id, **{
            k: v.s[k]
            for k in ("xp_per_min", "coins_per_min", "bonus_multiplier",
                      "max_session_min", "min_vc_members",
                      "allowed_role_id", "log_channel_id")
            if k in v.s
        })
        log.info(f"Settings saved for guild {v.guild_id}: {v.s}")
        await v.refresh(interaction, saved=True)


class _ResetBtn(discord.ui.Button):
    def __init__(self, view_ref: SettingsView):
        super().__init__(
            label="Reset to Defaults", style=discord.ButtonStyle.secondary,
            custom_id="fb:s_reset", row=3,
        )
        self._vref = view_ref

    async def callback(self, interaction: discord.Interaction):
        v = self._vref
        v.s.update(xp_per_min=10, coins_per_min=5, bonus_multiplier=1.0,
                   max_session_min=720, min_vc_members=1)
        await v.refresh(interaction)


class _AdvancedBtn(discord.ui.Button):
    def __init__(self, view_ref: SettingsView):
        super().__init__(
            label="Advanced…", style=discord.ButtonStyle.secondary,
            custom_id="fb:s_advanced", row=3,
        )
        self._vref = view_ref

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            embed=_advanced_embed(),
            view=AdvancedView(self._vref),
            ephemeral=True,
        )


def _advanced_embed() -> discord.Embed:
    return discord.Embed(
        title="Advanced Settings",
        description=(
            "**Max session duration** — cap how long a session can run.\n"
            "**Min VC members** — require X people in voice before XP is awarded.\n"
            "**Required role** — only members with this role can run `/timer`.\n"
            "**Log channel** — post a message there whenever a session starts/ends.\n\n"
            "Use the dropdowns to change, then Save."
        ),
        color=0x4060CC,
    )


class AdvancedView(discord.ui.View):
    def __init__(self, parent: SettingsView):
        super().__init__(timeout=180)
        self.p = parent
        s      = parent.s
        self.add_item(_Select(
            "Max session (min)", "fb:s_max",
            MAX_OPTS, s.get("max_session_min", 720),
            lambda v: parent._patch(max_session_min=int(v)), row=0,
        ))
        self.add_item(_Select(
            "Min VC members",    "fb:s_minmbr",
            MIN_MBR, s.get("min_vc_members", 1),
            lambda v: parent._patch(min_vc_members=int(v)), row=1,
        ))

    @discord.ui.button(label="Set Required Role", style=discord.ButtonStyle.primary,
                       custom_id="fb:s_setrole", row=2)
    async def set_role(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(
            "Use `/admin setrole @Role` to set the required timer role.\n"
            "Use `/admin setrole` (no role) to remove the requirement.",
            ephemeral=True,
        )

    @discord.ui.button(label="Set Log Channel", style=discord.ButtonStyle.primary,
                       custom_id="fb:s_setlog", row=2)
    async def set_log(self, interaction: discord.Interaction, _):
        await interaction.response.send_message(
            "Use `/admin setlog #channel` to enable session logging.\n"
            "Use `/admin setlog` (no channel) to disable.",
            ephemeral=True,
        )

    @discord.ui.button(label="Save & Close", style=discord.ButtonStyle.success,
                       custom_id="fb:s_adv_save", row=3)
    async def save_close(self, interaction: discord.Interaction, _):
        v = self.p
        await v.cog.bot.db.set_settings(v.guild_id, **{
            k: v.s[k]
            for k in ("xp_per_min", "coins_per_min", "bonus_multiplier",
                      "max_session_min", "min_vc_members",
                      "allowed_role_id", "log_channel_id")
            if k in v.s
        })
        await interaction.response.edit_message(
            content="Saved!", embed=None, view=None
        )


class SettingsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="settings",
        description="[Admin] View and change all server configuration",
    )
    @app_commands.default_permissions(administrator=True)
    async def settings(self, interaction: discord.Interaction):
        s    = await self.bot.db.get_settings(interaction.guild_id)
        view = SettingsView(self, interaction.guild_id, s)
        await interaction.response.send_message(
            embed=_main_embed(s), view=view, ephemeral=True
        )
