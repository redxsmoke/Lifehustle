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

        # Add nav buttons immediately
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        # Add buy buttons immediately
        self.add_buy_buttons()

    def create_embed(self):
        category_name, groceries = self.categories_with_items[self.current_page]
        embed = discord.Embed(
            title=f"🛒 {category_name} Market",
            description="Browse the items and click Buy to purchase.",
            color=discord.Color.green()
        )
        for item in groceries:
            embed.add_field(
                name=f"{item['emoji']} {item['name']}",
                value=f"**Price:** ${item['cost']}\n**Shelf Life:** {item['shelf_life']} days",
                inline=False
            )
        embed.set_footer(text=f"Page {self.current_page + 1} of {len(self.categories_with_items)}")
        return embed

    def add_buy_buttons(self):
        # Clear all buttons except nav buttons first
        # Remove all buttons except prev/next
        buttons_to_remove = [child for child in self.children if child not in (self.prev_button, self.next_button)]
        for button in buttons_to_remove:
            self.remove_item(button)

        _, groceries = self.categories_with_items[self.current_page]
        for item in groceries:
            button = Button(
                label="Buy",
                style=discord.ButtonStyle.success,
                custom_id=f"buy_{item['id']}"
            )
            button.callback = self.make_buy_callback(item)
            self.add_item(button)

        # Re-add navigation buttons at bottom
        # (They are already added, just ensure disabled states)
        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == len(self.categories_with_items) - 1

    def make_buy_callback(self, item):
        async def callback(interaction: Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
                return

            # Get current user finances & stash
            finances = await get_user_finances(self.bot.pool, self.user_id)
            balance = finances.get("money", 0)
            current_stash = finances.get("groceries", [])

            # Cap enforcement: max 10 groceries
            if len(current_stash) >= 10:
                await interaction.response.send_message(
                    "🧊 Your fridge is full! You’re one step away from being featured on *Hoarders: Cold Storage Edition.*",
                    ephemeral=True
                )
                return

            # Check if user can afford
            if balance < item['cost']:
                await interaction.response.send_message(
                    "💸 You can’t afford that! Get your bread up. Or just buy bread.",
                    ephemeral=True
                )
                return

            # Deduct cost from user balance
            new_balance = balance - item['cost']
            await upsert_user_finances(self.bot.pool, self.user_id, money=new_balance)

            # Add item to stash and reset shelf life if repurchased
            await add_grocery_to_stash(self.bot.pool, self.user_id, item)

            await interaction.response.send_message(
                f"{item['emoji']} **{item['name']}** added to your stash for ${item['cost']}!",
                ephemeral=True
            )
        return callback

    async def prev_page(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    async def next_page(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
            return
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
