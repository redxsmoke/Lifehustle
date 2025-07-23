import discord
from discord.ui import View, Button
from discord import Interaction
from db_user import get_user_finances, upsert_user_finances, add_grocery_to_stash

ITEMS_PER_PAGE = 3

class GroceryMarketView(View):
    def __init__(self, user_id, bot, categories_with_items):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.bot = bot
        self.categories_with_items = categories_with_items
        self.current_category_index = 0
        self.current_page = 0

        # Create nav buttons
        self.prev_button = Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        self.next_button = Button(label="Next ➡️", style=discord.ButtonStyle.secondary)
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        self.add_buy_buttons()

    def build_market_message(self):
        category_name, groceries = self.categories_with_items[self.current_category_index]

        total_items = len(groceries)
        max_page = max(0, (total_items - 1) // ITEMS_PER_PAGE)

        start = self.current_page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = groceries[start:end]

        lines = [f"🛒 **{category_name} Market**\n"]

        for idx, item in enumerate(page_items, start=1 + self.current_page * ITEMS_PER_PAGE):
            lines.append(f"**Buying {idx} {item['emoji']} {item['name']}**")
            lines.append(f"├ For: ${item['cost']}")
            lines.append(f"├ Value per Unit: {item.get('value_per_unit', 'N/A')}")
            lines.append(f"├ Expires: {item['shelf_life']} days")
            lines.append(f"├ ID: {item['id']}")
            lines.append("")  # spacer before button

        lines.append(f"Page {self.current_page + 1} / {max_page + 1} — Category {self.current_category_index + 1} / {len(self.categories_with_items)}")

        return "\n".join(lines)

    def add_buy_buttons(self):
        self.clear_items()

        _, groceries = self.categories_with_items[self.current_category_index]
        total_items = len(groceries)
        max_page = max(0, (total_items - 1) // ITEMS_PER_PAGE)

        start = self.current_page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = groceries[start:end]

        for idx, item in enumerate(page_items):
            button = Button(
                label=f"Accept (${item['cost']})",
                style=discord.ButtonStyle.success,
                custom_id=f"buy_{item['id']}",
                row=idx  # 🟩 this forces vertical stacking (1 button per row)
            )
            button.callback = self.make_buy_callback(item)
            self.add_item(button)

        # Nav buttons below all item buttons
        nav_row = len(page_items)
        self.prev_button.row = nav_row
        self.next_button.row = nav_row
        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        self.prev_button.disabled = self.current_page == 0
        self.next_button.disabled = self.current_page == max_page

    def make_buy_callback(self, item):
        async def callback(interaction: Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
                return

            finances = await get_user_finances(self.bot.pool, self.user_id)
            balance = finances.get("money", 0)
            current_stash = finances.get("groceries", [])

            if len(current_stash) >= 10:
                await interaction.response.send_message(
                    "🧊 Your fridge is full! You’re one step away from being featured on *Hoarders: Cold Storage Edition.*",
                    ephemeral=True
                )
                return

            if balance < item['cost']:
                await interaction.response.send_message(
                    "💸 You can’t afford that! Get your bread up. Or just buy bread.",
                    ephemeral=True
                )
                return

            new_balance = balance - item['cost']
            await upsert_user_finances(self.bot.pool, self.user_id, money=new_balance)
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
            self.add_buy_buttons()
            await interaction.response.edit_message(content=self.build_market_message(), view=self)

    async def next_page(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
            return
        _, groceries = self.categories_with_items[self.current_category_index]
        total_items = len(groceries)
        max_page = max(0, (total_items - 1) // ITEMS_PER_PAGE)
        if self.current_page < max_page:
            self.current_page += 1
            self.add_buy_buttons()
            await interaction.response.edit_message(content=self.build_market_message(), view=self)

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if hasattr(self, "message") and self.message:
            await self.message.edit(view=self)
