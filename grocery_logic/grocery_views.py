import discord
from discord.ui import View, Select, Button
from discord import Interaction

class GroceryCategoryView(discord.ui.View):
    def __init__(self, options, user_id, bot):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.bot = bot

        self.select = discord.ui.Select(placeholder="Choose grocery category...", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This is not your menu!", ephemeral=True)

        selected_category = self.select.values[0]

        async with self.bot.pool.acquire() as conn:
            groceries = await conn.fetch(
                """
                SELECT id, name, emoji, cost FROM cd_grocery_type
                WHERE category_id = (
                    SELECT id FROM cd_grocery_category WHERE name = $1
                )
                ORDER BY name
                """, selected_category
            )

        if not groceries:
            return await interaction.response.send_message(f"No groceries found for {selected_category}.", ephemeral=True)

        desc_lines = [f"{item['emoji']} **{item['name']}** — ${item['cost']}" for item in groceries]
        embed = discord.Embed(
            title=f"🛒 {selected_category} Grocery Shop",
            description="\n".join(desc_lines),
            color=discord.Color.green()
        )
        
        await interaction.response.edit_message(embed=embed, view=None)

class GroceryStashPaginationView(View):
    def __init__(self, user_id: int, pages: list):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.pages = pages
        self.current_page = 0

    async def update_message(self, interaction: Interaction):
        page_content = self.pages[self.current_page]
        await interaction.response.edit_message(content=page_content, view=self)

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
