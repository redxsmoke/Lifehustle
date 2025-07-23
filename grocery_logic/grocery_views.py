import discord
from discord.ui import View, Button
from discord import Interaction
from db_user import get_user_finances, upsert_user_finances, add_grocery_to_stash
from utilities import embed_message


class GroceryMarketView(View):
    def __init__(self, user_id, bot, categories_with_items):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.bot = bot
        self.categories_with_items = categories_with_items
        self.current_page = 0
        self.message = None

        self.prev_button = Button(label="Previous", style=discord.ButtonStyle.secondary)
        self.next_button = Button(label="Next", style=discord.ButtonStyle.secondary)
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        # ✅ Fix 1: Add buy buttons immediately
        self.add_buy_buttons()

    def create_embed(self):
        category_name, groceries = self.categories_with_items[self.current_page]
        embed = discord.Embed(
            title=f"🛒 {category_name} Market",
            description="",
            color=discord.Color.green()
        )
        for item in groceries:
            embed.add_field(
                name=f"{item['emoji']} {item['name']}",
                value=f"**Price:** ${item['cost']}\n**Shelf Life:** {item['shelf_life']} days",
                inline=False
            )
        return embed

    def add_buy_buttons(self):
        self.clear_items()
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        _, groceries = self.categories_with_items[self.current_page]
        for item in groceries:
            button = Button(
                label=f"Buy (${item['cost']})",
                style=discord.ButtonStyle.success,
                custom_id=f"buy_{item['id']}"
            )
            button.callback = self.make_buy_callback(item)
            self.add_item(button)

    def make_buy_callback(self, item):
        async def callback(interaction: Interaction):
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("This isn’t your market view.", ephemeral=True)

            # Get current balance and stash
            finances = await get_user_finances(self.bot.pool, self.user_id)
            balance = finances.get("money", 0)
            current_stash = finances.get("groceries", [])

            if len(current_stash) >= 10:
                return await interaction.response.send_message(
                    "🧊 Your fridge is full! You’re one step away from being featured on *Hoarders: Cold Storage Edition.*",
                    ephemeral=True
                )

            # Check if user has enough money
            if balance < item['cost']:
                return await interaction.response.send_message(
                    "💸 You can’t afford that! Get your bread up. Or just buy bread.",
                    ephemeral=True
                )

            # Deduct money and update user
            new_balance = balance - item['cost']
            await upsert_user_finances(self.bot.pool, self.user_id, money=new_balance)

            # Reset shelf life & add to stash
            await add_grocery_to_stash(self.bot.pool, self.user_id, item)

            await interaction.response.send_message(
                f"{item['emoji']} **{item['name']}** added to your stash for ${item['cost']}!",
                ephemeral=True
            )
        return callback

    async def prev_page(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    async def next_page(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
        if self.current_page < len(self.categories_with_items) - 1:
            self.current_page += 1
            await self.update_message(interaction)

    async def update_message(self, interaction: Interaction):
        self.add_buy_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)
