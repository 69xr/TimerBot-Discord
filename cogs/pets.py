"""
Pets Cog — Buy, view, rename, and manage your pixel art study companions.
"""

import discord
from discord.ext import commands
from discord import app_commands
import logging

from core.image_engine import PIXEL_PETS, RARITY_COLORS, RARITY_LABELS

log = logging.getLogger("Pets")

RARITY_ORDER = {"common": 0, "uncommon": 1, "rare": 2, "legendary": 3}
SORTED_PETS  = sorted(PIXEL_PETS.items(), key=lambda x: RARITY_ORDER[x[1]["rarity"]])


# ── Pet Shop Paginator ────────────────────────────────────────────────────────
class PetShopView(discord.ui.View):
    def __init__(self, cog: "PetsCog", user: discord.Member, page: int = 0):
        super().__init__(timeout=180)
        self.cog  = cog
        self.user = user
        self.page = page

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your shop session.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary, row=0)
    async def prev(self, interaction: discord.Interaction, _):
        if not await self._check(interaction): return
        self.page = (self.page - 1) % len(SORTED_PETS)
        await self._refresh(interaction)

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction: discord.Interaction, _):
        if not await self._check(interaction): return
        self.page = (self.page + 1) % len(SORTED_PETS)
        await self._refresh(interaction)

    @discord.ui.button(label="🛒  Buy This Pet", style=discord.ButtonStyle.success, row=0)
    async def buy(self, interaction: discord.Interaction, _):
        if not await self._check(interaction): return
        species, pet_data = SORTED_PETS[self.page]
        await self.cog._do_buy_pet(interaction, species, pet_data)

    async def _refresh(self, interaction: discord.Interaction):
        species, pet_data = SORTED_PETS[self.page]
        embed, file = await self.cog._shop_card_embed(species, pet_data, self.user)
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)


# ── Collection Paginator ──────────────────────────────────────────────────────
class PetCollectionView(discord.ui.View):
    def __init__(self, cog: "PetsCog", user: discord.Member, pets: list, page: int = 0):
        super().__init__(timeout=180)
        self.cog  = cog
        self.user = user
        self.pets = pets
        self.page = page

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message("❌ This isn't your collection.", ephemeral=True)
            return False
        return True

    @discord.ui.button(emoji="◀", style=discord.ButtonStyle.secondary, row=0)
    async def prev(self, interaction: discord.Interaction, _):
        if not await self._check(interaction): return
        self.page = (self.page - 1) % len(self.pets)
        await self._refresh(interaction)

    @discord.ui.button(emoji="▶", style=discord.ButtonStyle.secondary, row=0)
    async def next(self, interaction: discord.Interaction, _):
        if not await self._check(interaction): return
        self.page = (self.page + 1) % len(self.pets)
        await self._refresh(interaction)

    @discord.ui.button(label="⭐  Set Active", style=discord.ButtonStyle.primary, row=0)
    async def set_active(self, interaction: discord.Interaction, _):
        if not await self._check(interaction): return
        pet = self.pets[self.page]
        await self.cog.bot.db.set_active_pet(self.user.id, pet["pet_id"])
        self.pets = await self.cog.bot.db.get_pets(self.user.id)
        await self._refresh(interaction)
        await interaction.followup.send(
            f"✅ **{pet['name']}** is now your active companion!", ephemeral=True
        )

    async def _refresh(self, interaction: discord.Interaction):
        pet = self.pets[self.page]
        embed, file = await self.cog._pet_card_embed(pet, self.page, len(self.pets))
        await interaction.response.edit_message(embed=embed, attachments=[file], view=self)


# ── Rename Modal ──────────────────────────────────────────────────────────────
class RenameModal(discord.ui.Modal, title="✏️  Rename Your Pet"):
    new_name = discord.ui.TextInput(
        label="New Name",
        placeholder="Give your companion a new name...",
        min_length=1,
        max_length=32,
    )

    def __init__(self, cog: "PetsCog", pet_id: int, user_id: int, species: str):
        super().__init__()
        self.cog     = cog
        self.pet_id  = pet_id
        self.user_id = user_id
        self.species = species

    async def on_submit(self, interaction: discord.Interaction):
        name = self.new_name.value.strip()
        if not name:
            return await interaction.response.send_message("❌ Name can't be empty.", ephemeral=True)

        await self.cog.bot.db.rename_pet(self.pet_id, self.user_id, name)
        pet = await self.cog.bot.db.get_pet(self.pet_id)
        embed, file = await self.cog._pet_card_embed(pet)
        embed.title = f"✏️  Renamed to **{name}**!"
        await interaction.response.send_message(embed=embed, file=file, ephemeral=False)


# ── Pets Cog ──────────────────────────────────────────────────────────────────
class PetsCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    # /petshop
    @app_commands.command(name="petshop", description="🐾 Browse and buy pixel art study companions")
    async def petshop(self, interaction: discord.Interaction):
        species, pet_data = SORTED_PETS[0]
        embed, file = await self._shop_card_embed(species, pet_data, interaction.user)
        view = PetShopView(self, interaction.user)
        await interaction.response.send_message(embed=embed, file=file, view=view)

    # /pets
    @app_commands.command(name="pets", description="🐾 View your pet collection")
    async def pets(self, interaction: discord.Interaction):
        pets = await self.bot.db.get_pets(interaction.user.id)
        if not pets:
            embed = discord.Embed(
                title="🐾  No Companions Yet!",
                description=(
                    "You haven't adopted any pets.\n\n"
                    "Visit **/petshop** to find your first study companion!\n"
                    "Pets level up as you focus and earn XP."
                ),
                color=0xFF6B9D,
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        embed, file = await self._pet_card_embed(pets[0], 0, len(pets))
        view = PetCollectionView(self, interaction.user, list(pets))
        await interaction.response.send_message(embed=embed, file=file, view=view)

    # /renamepet
    @app_commands.command(name="renamepet", description="✏️ Rename one of your companions")
    @app_commands.describe(pet_id="The pet's ID — shown on its card")
    async def renamepet(self, interaction: discord.Interaction, pet_id: int):
        pet = await self.bot.db.get_pet(pet_id)
        if not pet or pet["user_id"] != interaction.user.id:
            return await interaction.response.send_message(
                "❌ No pet with that ID found in your collection.", ephemeral=True
            )
        await interaction.response.send_modal(
            RenameModal(self, pet_id, interaction.user.id, pet["species"])
        )

    # ── Internal helpers ──────────────────────────────────────────────────────
    async def _shop_card_embed(self, species: str, pet_data: dict, user: discord.Member):
        rarity = pet_data["rarity"]
        rc     = RARITY_COLORS[rarity]
        udata  = await self.bot.db.get_user(user.id)
        coins  = udata["coins"] if udata else 0
        pets   = await self.bot.db.get_pets(user.id)
        owned  = any(p["species"] == species for p in pets)

        buf  = self.bot.image_engine.render_pet_shop_card(species)
        file = discord.File(buf, filename="pet_shop.png")

        idx = next(i for i, (s, _) in enumerate(SORTED_PETS) if s == species)
        embed = discord.Embed(
            title=f"{'✅ Owned' if owned else '🛒 For Sale'}  —  {species.replace('_',' ').title()}",
            description=(
                f"{pet_data['desc']}\n\n"
                f"**Rarity:** {RARITY_LABELS[rarity]}\n"
                f"**Price:** 🪙 `{pet_data['price']:,}` coins\n"
                f"**Your balance:** 🪙 `{coins:,}` coins\n\n"
                f"{'✅ Already in your collection!' if owned else '👇 Use the button below to adopt!'}"
            ),
            color=discord.Color.from_rgb(*rc),
        )
        embed.set_image(url="attachment://pet_shop.png")
        embed.set_footer(text=f"Pet {idx + 1} of {len(SORTED_PETS)}  •  ◀ ▶ to browse")
        return embed, file

    async def _pet_card_embed(self, pet, page: int = 0, total: int = 1):
        p_data  = PIXEL_PETS.get(pet["species"], list(PIXEL_PETS.values())[0])
        rarity  = pet["rarity"]
        rc      = RARITY_COLORS[rarity]
        xp_need = pet["level"] * 100

        buf  = self.bot.image_engine.render_pet_card(
            pet["species"], pet["name"], pet["level"],
            pet["xp"], pet["happiness"], bool(pet["active"])
        )
        file = discord.File(buf, filename="pet_card.png")

        embed = discord.Embed(
            title=f"{'⭐ Active — ' if pet['active'] else ''}{pet['name']}",
            description=(
                f"**Species:** {pet['species'].replace('_',' ').title()}\n"
                f"**Rarity:** {RARITY_LABELS[rarity]}\n"
                f"**Level:** {pet['level']}  ({pet['xp']}/{xp_need} XP)\n"
                f"**Pet ID:** `{pet['pet_id']}`\n\n"
                f"{'⭐ This is your active companion' if pet['active'] else 'Press **⭐ Set Active** to equip'}"
            ),
            color=discord.Color.from_rgb(*rc),
        )
        embed.set_image(url="attachment://pet_card.png")
        embed.set_footer(
            text=f"Pet {page + 1} of {total}  •  /renamepet {pet['pet_id']} to rename"
        )
        return embed, file

    async def _do_buy_pet(self, interaction: discord.Interaction, species: str, pet_data: dict):
        db      = self.bot.db
        user_id = interaction.user.id
        pets    = await db.get_pets(user_id)

        if any(p["species"] == species for p in pets):
            return await interaction.response.send_message(
                f"❌ You already own a **{species.replace('_',' ').title()}**!", ephemeral=True
            )

        spent = await db.spend_coins(user_id, pet_data["price"])
        if not spent:
            udata = await db.get_user(user_id)
            need  = pet_data["price"] - udata["coins"]
            return await interaction.response.send_message(
                f"❌ Not enough coins!\n"
                f"🪙 You have `{udata['coins']:,}` — need `{pet_data['price']:,}`\n"
                f"_(You're `{need:,}` coins short — keep focusing!)_",
                ephemeral=True,
            )

        default = species.replace("_", " ").title()
        pet_id  = await db.add_pet(user_id, species, default, pet_data["rarity"])
        buf  = self.bot.image_engine.render_pet_card(species, default, 1, 0, 100, False)
        file = discord.File(buf, filename="new_pet.png")

        embed = discord.Embed(
            title="🎉  New Companion Adopted!",
            description=(
                f"**{default}** ({RARITY_LABELS[pet_data['rarity']]}) joined your team!\n\n"
                f"• Use `/renamepet {pet_id}` to give them a custom name\n"
                f"• Use `/pets` to set them as active\n"
                f"• They level up as you complete focus sessions!"
            ),
            color=discord.Color.from_rgb(*RARITY_COLORS[pet_data["rarity"]]),
        )
        embed.set_image(url="attachment://new_pet.png")
        await interaction.response.send_message(embed=embed, file=file)