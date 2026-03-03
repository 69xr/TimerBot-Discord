"""
Pets Cog — Buy, view, rename, and manage your study pets.
"""

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import logging

from core.image_engine import PETS, RARITY_COLORS, RARITY_BADGES

log = logging.getLogger("Pets")

# Rarity order for shop display
RARITY_ORDER = {"common": 0, "uncommon": 1, "rare": 2, "legendary": 3}
SORTED_PETS = sorted(PETS.items(), key=lambda x: RARITY_ORDER[x[1]["rarity"]])


# ── Pet Shop UI ───────────────────────────────────────────────────────────────
class PetShopView(discord.ui.View):
    def __init__(self, cog: "PetsCog", user: discord.Member, page: int = 0):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.page = page
        self.per_page = 1

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.defer()
        self.page = (self.page - 1) % len(SORTED_PETS)
        await self._refresh(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.defer()
        self.page = (self.page + 1) % len(SORTED_PETS)
        await self._refresh(interaction)

    @discord.ui.button(label="🛒  Buy This Pet", style=discord.ButtonStyle.success)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.defer()
        species, pet_data = SORTED_PETS[self.page]
        await self.cog._buy_pet(interaction, species, pet_data)

    async def _refresh(self, interaction: discord.Interaction):
        species, pet_data = SORTED_PETS[self.page]
        embed, file = await self.cog._build_shop_card(species, pet_data, self.user)
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)


# ── Pet Collection UI ─────────────────────────────────────────────────────────
class PetCollectionView(discord.ui.View):
    def __init__(self, cog: "PetsCog", user: discord.Member, pets: list, page: int = 0):
        super().__init__(timeout=120)
        self.cog = cog
        self.user = user
        self.pets = pets
        self.page = page

    @discord.ui.button(label="◀", style=discord.ButtonStyle.secondary)
    async def prev(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.defer()
        self.page = (self.page - 1) % len(self.pets)
        await self._refresh(interaction)

    @discord.ui.button(label="▶", style=discord.ButtonStyle.secondary)
    async def next(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.defer()
        self.page = (self.page + 1) % len(self.pets)
        await self._refresh(interaction)

    @discord.ui.button(label="⭐  Set Active", style=discord.ButtonStyle.primary)
    async def set_active(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user.id:
            return await interaction.response.defer()
        pet = self.pets[self.page]
        await self.cog.bot.db.set_active_pet(self.user.id, pet["pet_id"])
        # Refresh pets list
        self.pets = await self.cog.bot.db.get_pets(self.user.id)
        await self._refresh(interaction)
        await interaction.followup.send(
            f"✅ **{pet['name']}** is now your active pet!", ephemeral=True
        )

    async def _refresh(self, interaction: discord.Interaction):
        pet = self.pets[self.page]
        embed, file = await self.cog._build_pet_card(pet)
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)


# ── Rename Modal ──────────────────────────────────────────────────────────────
class RenameModal(discord.ui.Modal, title="Rename Your Pet"):
    new_name = discord.ui.TextInput(
        label="New Name",
        placeholder="Enter a name for your pet...",
        min_length=1,
        max_length=32,
    )

    def __init__(self, cog: "PetsCog", pet_id: int, user_id: int, species: str, old_name: str):
        super().__init__()
        self.cog = cog
        self.pet_id = pet_id
        self.user_id = user_id
        self.species = species
        self.old_name = old_name

    async def on_submit(self, interaction: discord.Interaction):
        name = self.new_name.value.strip()
        if not name:
            return await interaction.response.send_message("❌ Name can't be empty.", ephemeral=True)
        await self.cog.bot.db.rename_pet(self.pet_id, self.user_id, name)

        # Re-render with new name
        pet = await self.cog.bot.db.get_pet(self.pet_id)
        embed, file = await self.cog._build_pet_card(pet)
        embed.title = f"✏️ Renamed to: {name}"
        await interaction.response.send_message(embed=embed, file=file)


# ── Pets Cog ──────────────────────────────────────────────────────────────────
class PetsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # ── /pets shop ───────────────────────────────────────────────────────────
    @app_commands.command(name="petshop", description="🐾 Browse and buy pets for your focus sessions")
    async def petshop(self, interaction: discord.Interaction):
        species, pet_data = SORTED_PETS[0]
        embed, file = await self._build_shop_card(species, pet_data, interaction.user)
        view = PetShopView(self, interaction.user)
        await interaction.response.send_message(embed=embed, file=file, view=view)

    # ── /pets view ────────────────────────────────────────────────────────────
    @app_commands.command(name="pets", description="🐾 View your pet collection")
    async def pets(self, interaction: discord.Interaction):
        pets = await self.bot.db.get_pets(interaction.user.id)
        if not pets:
            embed = discord.Embed(
                title="🐾 No Pets Yet!",
                description="You don't have any pets.\nVisit **/petshop** to buy your first companion!",
                color=0xFF6B9D
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed, file = await self._build_pet_card(pets[0])
        view = PetCollectionView(self, interaction.user, pets)
        await interaction.response.send_message(embed=embed, file=file, view=view)

    # ── /renamepet ────────────────────────────────────────────────────────────
    @app_commands.command(name="renamepet", description="✏️ Rename one of your pets")
    @app_commands.describe(pet_id="The pet's ID (shown in /pets)")
    async def renamepet(self, interaction: discord.Interaction, pet_id: int):
        pet = await self.bot.db.get_pet(pet_id)
        if not pet or pet["user_id"] != interaction.user.id:
            return await interaction.response.send_message("❌ Pet not found.", ephemeral=True)

        modal = RenameModal(self, pet_id, interaction.user.id, pet["species"], pet["name"])
        await interaction.response.send_modal(modal)

    # ── Internal helpers ──────────────────────────────────────────────────────
    async def _build_shop_card(self, species: str, pet_data: dict, user: discord.Member):
        rcolor = RARITY_COLORS[pet_data["rarity"]]
        user_data = await self.bot.db.get_user(user.id)
        coins = user_data["coins"] if user_data else 0

        buf = self.bot.image_engine.render_pet_shop_card(species)
        file = discord.File(buf, filename="pet_shop.png")

        owns = any(
            p["species"] == species
            for p in await self.bot.db.get_pets(user.id)
        )

        embed = discord.Embed(
            title=f"{pet_data['emoji']}  {species.replace('_', ' ').title()}",
            description=(
                f"{pet_data['desc']}\n\n"
                f"**Rarity:** {RARITY_BADGES[pet_data['rarity']]}\n"
                f"**Price:** 🪙 {pet_data['price']:,} coins\n"
                f"Your coins: 🪙 {coins:,}\n\n"
                f"{'✅ Already owned' if owns else '🛒 Use the button below to buy!'}"
            ),
            color=discord.Color.from_rgb(*rcolor),
        )
        embed.set_image(url="attachment://pet_shop.png")
        embed.set_footer(text=f"Pet {SORTED_PETS.index((species, pet_data)) + 1} of {len(SORTED_PETS)} • Use ◀▶ to browse")
        return embed, file

    async def _build_pet_card(self, pet) -> tuple:
        buf = self.bot.image_engine.render_pet_card(
            pet["species"], pet["name"], pet["level"],
            pet["xp"], pet["happiness"], bool(pet["active"])
        )
        file = discord.File(buf, filename="pet_card.png")
        p = PETS.get(pet["species"], {})
        rcolor = RARITY_COLORS.get(pet["rarity"], (160, 160, 160))
        xp_needed = pet["level"] * 100

        embed = discord.Embed(
            title=f"{p.get('emoji', '?')}  {pet['name']}",
            description=(
                f"**Species:** {pet['species'].replace('_', ' ').title()}\n"
                f"**Rarity:** {RARITY_BADGES.get(pet['rarity'], pet['rarity'])}\n"
                f"**Level:** {pet['level']} ({pet['xp']}/{xp_needed} XP)\n"
                f"**ID:** `{pet['pet_id']}`\n\n"
                f"{'⭐ **Active Pet**' if pet['active'] else 'Use ⭐ Set Active to equip'}"
            ),
            color=discord.Color.from_rgb(*rcolor),
        )
        embed.set_image(url="attachment://pet_card.png")
        embed.set_footer(text="Use /renamepet <id> to rename • /pets to browse collection")
        return embed, file

    async def _buy_pet(self, interaction: discord.Interaction, species: str, pet_data: dict):
        db = self.bot.db
        user_id = interaction.user.id

        # Check already owns
        pets = await db.get_pets(user_id)
        if any(p["species"] == species for p in pets):
            return await interaction.response.send_message(
                f"❌ You already own a **{species}**!", ephemeral=True
            )

        # Spend coins
        spent = await db.spend_coins(user_id, pet_data["price"])
        if not spent:
            user_data = await db.get_user(user_id)
            return await interaction.response.send_message(
                f"❌ Not enough coins! You have 🪙 {user_data['coins']:,} but need 🪙 {pet_data['price']:,}.",
                ephemeral=True
            )

        # Default name = species title
        default_name = species.replace("_", " ").title()
        pet_id = await db.add_pet(user_id, species, default_name, pet_data["rarity"])

        buf = self.bot.image_engine.render_pet_card(species, default_name, 1, 0, 100, False)
        file = discord.File(buf, filename="new_pet.png")

        embed = discord.Embed(
            title=f"🎉 New Pet Acquired!",
            description=(
                f"You got **{pet_data['emoji']} {default_name}** ({RARITY_BADGES[pet_data['rarity']]})!\n\n"
                f"Use `/renamepet {pet_id}` to give it a custom name.\n"
                f"Use `/pets` to set it as active!"
            ),
            color=discord.Color.from_rgb(*RARITY_COLORS[pet_data["rarity"]]),
        )
        embed.set_image(url="attachment://new_pet.png")
        await interaction.response.send_message(embed=embed, file=file)