import discord
from discord.ui import View, Button, Select
from discord import Interaction
from db_user import get_user_finances, upsert_user_finances, add_grocery_to_stash

ITEMS_PER_PAGE = 3

class CategorySelect(Select):
    def __init__(self, control_view: "GroceryMarketView"):
        self.control_view = control_view
        options = [
            discord.SelectOption(label=cat[0], description=f"Category {i+1}", value=str(i))
            for i, cat in enumerate(control_view.categories_with_items)
        ]
        super().__init__(placeholder="Select Category...", options=options, row=0)

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.control_view.user_id:
            await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
            return

        self.control_view.current_category_index = int(self.values[0])
        self.control_view.current_page = 0
        self.control_view.add_buy_buttons()
        await interaction.response.edit_message(content=self.control_view.build_market_message(), view=self.control_view)


class GroceryMarketView(View):
    def __init__(self, user_id, bot, categories_with_items):
        super().__init__(timeout=180)
        self.user_id = user_id
        self.bot = bot
        self.categories_with_items = categories_with_items
        self.current_category_index = 0
        self.current_page = 0

        # Navigation buttons
        self.prev_button = Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        self.next_button = Button(label="Next ➡️", style=discord.ButtonStyle.secondary)
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        # Category dropdown
        self.category_select = CategorySelect(self)
        self.add_item(self.category_select)

        # Add initial buy buttons and nav buttons
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
            lines.append(f"**{item['emoji']} {item['name']}**")
            lines.append(f"├ Price: ${item['cost']}")
            lines.append(f"├ Expires: {item['shelf_life']} days")
            lines.append("")  # spacer before buttons

        lines.append(f"Page {self.current_page + 1} / {max_page + 1} — Category {self.current_category_index + 1} / {len(self.categories_with_items)}")

        return "\n".join(lines)

    def add_buy_buttons(self):
        # Clear all existing buttons and re-add dropdown + nav + buy buttons for current page
        self.clear_items()
        self.add_item(self.category_select)

        self.prev_button.disabled = self.current_page == 0
        _, groceries = self.categories_with_items[self.current_category_index]
        max_page = max(0, (len(groceries) - 1) // ITEMS_PER_PAGE)
        self.next_button.disabled = self.current_page == max_page

        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        # Add buy buttons for current page items
        start = self.current_page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = groceries[start:end]

        for item in page_items:
            buy_button = Button(label=f"Accept (${item['cost']})", style=discord.ButtonStyle.success)
            buy_button.callback = self.make_buy_callback(item)
            self.add_item(buy_button)

    def make_buy_callback(self, item):
        async def callback(interaction: Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
                return

            finances = await get_user_finances(self.bot.pool, self.user_id)
            balance = finances.get("checking_account_balance", 0)

            if balance < item['cost']:
                await interaction.response.send_message(
                    "💸 You can’t afford that! Get your bread up. Or just buy bread.",
                    ephemeral=True
                )
                return

            new_balance = balance - item['cost']
            await upsert_user_finances(self.bot.pool, self.user_id, {
                "checking_account_balance": new_balance,
                "savings_account_balance": finances.get("savings_account_balance", 0),
                "debt_balance": finances.get("debt_balance", 0),
                "last_paycheck_claimed": finances.get("last_paycheck_claimed"),
            })

            try:
                await add_grocery_to_stash(self.bot.pool, self.user_id, item)
            except ValueError as e:
                await interaction.response.send_message(str(e), ephemeral=True)
                return
            except Exception as e:
                print(f"[ERROR] Adding grocery failed: {e}")
                await interaction.response.send_message("❌ Something went wrong adding the item.", ephemeral=True)
                return

            await interaction.response.send_message(
                f"{item['emoji']} **{item['name']}** added to your stash for ${item['cost']:,}!",
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
