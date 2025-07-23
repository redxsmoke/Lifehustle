import discord
from discord.ui import View, Button
from discord import Interaction

from db_user import get_user_finances, upsert_user_finances, add_grocery_to_stash
from utilities import embed_message


class GroceryCategoryPageView(View):
    def __init__(self, user_id, bot, category_name, groceries):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.bot = bot
        self.category_name = category_name
        self.groceries = groceries  # List of grocery items for this category

        # Add a Buy button per grocery item
        for item in groceries:
            btn = Button(
                label=f"Buy (${item['cost']})",
                style=discord.ButtonStyle.success,
                custom_id=f"buy_{item['id']}"
            )
            btn.callback = self.make_buy_callback(item)
            self.add_item(btn)

    def create_embed(self):
        desc_lines = [f"{item['emoji']} **{item['name']}** — ${item['cost']}" for item in self.groceries]
        embed = discord.Embed(
            title=f"🛒 {self.category_name} Grocery Shop",
            description="\n".join(desc_lines),
            color=discord.Color.green()
        )
        return embed

    def make_buy_callback(self, item):
        async def buy_callback(interaction: Interaction):
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("This is not your menu!", ephemeral=True)

            # Check user balance
            finances = await get_user_finances(self.bot.pool, self.user_id)
            cost = item['cost']
            if finances is None or finances['checking_account_balance'] < cost:
                return await interaction.response.send_message(
                    "❌ You don't have enough money to buy this item.",
                    ephemeral=True
                )

            # Deduct money
            finances['checking_account_balance'] -= cost
            await upsert_user_finances(self.bot.pool, self.user_id, finances)

            # Add item to stash
            await add_grocery_to_stash(
                pool=self.bot.pool,
                user_id=self.user_id,
                item=item
            )

            await interaction.response.send_message(
                f"✅ Added {item['emoji']} **{item['name']}** to your stash for ${cost}!",
                ephemeral=True
            )
        return buy_callback

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if hasattr(self, "message"):
            await self.message.edit(view=self)


class GroceryMarketView(View):
    def __init__(self, user_id, bot, categories_with_items):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.bot = bot
        self.categories_with_items = categories_with_items  # List of tuples (category_name, groceries_list)
        self.current_page = 0

        # Add navigation buttons
        self.prev_button = Button(label="Previous", style=discord.ButtonStyle.secondary)
        self.next_button = Button(label="Next", style=discord.ButtonStyle.secondary)
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        self.update_page_view()

    def update_page_view(self):
        self.clear_items()
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        category_name, groceries = self.categories_with_items[self.current_page]
        self.page_view = GroceryCategoryPageView(self.user_id, self.bot, category_name, groceries)

        for item in self.page_view.children:
            self.add_item(item)

    async def prev_page(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't your market view.", ephemeral=True)

        if self.current_page > 0:
            self.current_page -= 1
            self.update_page_view()
            embed = self.page_view.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()

    async def next_page(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn't your market view.", ephemeral=True)

        if self.current_page < len(self.categories_with_items) - 1:
            self.current_page += 1
            self.update_page_view()
            embed = self.page_view.create_embed()
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.defer()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if hasattr(self, "message"):
            await self.message.edit(view=self)
