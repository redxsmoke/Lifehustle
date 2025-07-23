import discord
from discord.ui import View, Select, Button
from discord import Interaction
import discord
from discord.ui import View, Select, Button
from discord import Interaction

from db_user import get_user_finances, upsert_user_finances
from utilities import parse_amount, embed_message   


class GroceryCategoryView(View):
    def __init__(self, options, user_id, bot):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.bot = bot

        self.select = Select(placeholder="Choose grocery category...", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your menu!", ephemeral=True)

        selected_category = self.select.values[0]

        # Fetch grocery items for the selected category
        async with self.bot.pool.acquire() as conn:
            groceries = await conn.fetch(
                """
                SELECT id, name, emoji, cost FROM cd_grocery_type
                WHERE category_id = (
                    SELECT id FROM cd_grocery_category WHERE name = $1
                )
                ORDER BY name
                """,
                selected_category,
            )

        if not groceries:
            return await interaction.response.send_message(f"No groceries found for {selected_category}.", ephemeral=True)

        page = GroceryCategoryPageView(user_id=self.user_id, bot=self.bot, category_name=selected_category, groceries=groceries)
        
        embed = page.create_embed()
        await interaction.response.edit_message(embed=embed, view=page)


class GroceryCategoryPageView(View):
    def __init__(self, user_id, bot, category_name, groceries):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.bot = bot
        self.category_name = category_name
        self.groceries = groceries  # List of grocery items for this page

        # Create a buy button per grocery item
        for item in groceries:
            button = Button(
                label=f"Buy (${item['cost']})",
                style=discord.ButtonStyle.success,
                custom_id=f"buy_{item['id']}",
            )
            button.callback = self.buy_callback_factory(item)
            self.add_item(button)

    def create_embed(self):
        desc_lines = [f"{item['emoji']} **{item['name']}** — ${item['cost']}" for item in self.groceries]
        embed = discord.Embed(
            title=f"🛒 {self.category_name} Grocery Shop",
            description="\n".join(desc_lines),
            color=discord.Color.green(),
        )
        return embed

    def buy_callback_factory(self, item):
        async def buy_callback(interaction: Interaction):
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("This is not your menu!", ephemeral=True)
            
            # TODO: Add the grocery item to the user's stash in DB here
            # Example:
            # await add_grocery_to_stash(self.bot.pool, self.user_id, item['id'])

            await interaction.response.send_message(
                f"Added {item['emoji']} **{item['name']}** to your stash for ${item['cost']}!",
                ephemeral=True
            )
        
        return buy_callback

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if hasattr(self, "message"):
            await self.message.edit(view=self)


class GroceryStashPaginationView(View):
    def __init__(self, user_id: int, pages: list):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.pages = pages  # list of (embed, view) tuples or just embed content strings
        self.current_page = 0

    async def update_message(self, interaction: Interaction):
        page = self.pages[self.current_page]
        # page can be an embed or string content
        if isinstance(page, discord.Embed):
            await interaction.response.edit_message(embed=page, view=self)
        else:
            await interaction.response.edit_message(content=page, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your stash.", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your stash.", ephemeral=True)
            return
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if hasattr(self, "message"):
            await self.message.edit(view=self)
