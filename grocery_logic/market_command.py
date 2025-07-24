import discord
from discord.ext import commands
from discord import app_commands, Interaction
from discord.ui import View, Button, Select
import asyncio

ITEMS_PER_PAGE = 20

class ItemButton(Button):
    def __init__(self, item, user_id, bot):
        super().__init__(label=f"Accept (${item['cost']})", style=discord.ButtonStyle.success)
        self.item = item
        self.user_id = user_id
        self.bot = bot

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
            return

        # Your purchase logic here - placeholder
        await interaction.response.send_message(f"Bought {self.item['emoji']} **{self.item['name']}** for ${self.item['cost']}!", ephemeral=True)


class CategorySelect(Select):
    def __init__(self, control_view: "ControlView"):
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
        await interaction.response.edit_message(content=self.control_view.build_main_message_text(), view=self.control_view)


class ControlView(View):
    def __init__(self, user_id, bot, categories_with_items, channel, main_message):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bot = bot
        self.categories_with_items = categories_with_items
        self.current_category_index = 0
        self.current_page = 0
        self.channel = channel
        self.main_message = main_message
        self.item_messages = []

        self.prev_button = Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        self.next_button = Button(label="Next ➡️", style=discord.ButtonStyle.secondary)
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page

        self.category_select = CategorySelect(self)
        self.add_item(self.category_select)

        self.add_buy_buttons()

    def build_nav_view(self):
        view = View()
        self.prev_button.disabled = self.current_page == 0
        category_name, groceries = self.categories_with_items[self.current_category_index]
        total_items = len(groceries)
        max_page = max(0, (total_items - 1) // ITEMS_PER_PAGE)
        self.next_button.disabled = self.current_page == max_page
        view.add_item(self.prev_button)
        view.add_item(self.next_button)
        return view

    async def send_item_messages(self):
        for msg in self.item_messages:
            try:
                await msg.delete()
            except:
                pass
        self.item_messages = []

        if hasattr(self, 'footer_message') and self.footer_message:
            try:
                await self.footer_message.delete()
            except:
                pass
            self.footer_message = None

        category_name, groceries = self.categories_with_items[self.current_category_index]
        total_items = len(groceries)
        max_page = max(0, (total_items - 1) // ITEMS_PER_PAGE)
        start = self.current_page * ITEMS_PER_PAGE
        end = start + ITEMS_PER_PAGE
        page_items = groceries[start:end]

        for idx, item in enumerate(page_items, start=1 + self.current_page * ITEMS_PER_PAGE):
            content = (
                f"{item['emoji']} {item['name']}\n"
                f"├ Price: ${item['cost']}\n"
                f"├ Expires: {item['shelf_life']} days\n"
            )
            view = View()
            view.add_item(ItemButton(item, self.user_id, self.bot))
            msg = await self.channel.send(content=content, view=view)
            self.item_messages.append(msg)

        footer_text = self.build_main_message_text()
        footer_view = self.build_nav_view()
        self.footer_message = await self.channel.send(content=footer_text, view=footer_view)

    def build_main_message_text(self):
        total_categories = len(self.categories_with_items)
        category_name, groceries = self.categories_with_items[self.current_category_index]
        total_items = len(groceries)
        max_page = max(0, (total_items - 1) // ITEMS_PER_PAGE)
        return f"🛒 **{category_name} Market**\nPage {self.current_page + 1} / {max_page + 1} — Category {self.current_category_index + 1} / {total_categories}"

    def add_buy_buttons(self):
        self.clear_items()
        self.add_item(self.category_select)

        _, groceries = self.categories_with_items[self.current_category_index]

        for item in groceries:
            button = Button(
                label=f"Buy (${item['cost']})",
                style=discord.ButtonStyle.success,
                custom_id=f"buy_{item['id']}"
            )
            button.callback = self.make_buy_callback(item)
            self.add_item(button)

        self.add_item(self.prev_button)
        self.add_item(self.next_button)

        self.prev_button.disabled = self.current_page == 0
        max_page = max(0, (len(groceries) - 1) // ITEMS_PER_PAGE)
        self.next_button.disabled = self.current_page == max_page


    def make_buy_callback(self, item):
        async def callback(interaction: Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
                return

            # Replace with your actual purchase logic
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
            await interaction.response.edit_message(content=self.build_main_message_text(), view=self)

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
            await interaction.response.edit_message(content=self.build_main_message_text(), view=self)

    async def on_timeout(self):
        for msg in self.item_messages:
            try:
                await msg.delete()
            except:
                pass
        if self.main_message:
            for child in self.children:
                child.disabled = True
            await self.main_message.edit(view=self)


class GroceryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="market", description="Browse and buy groceries")
    async def market(self, interaction: discord.Interaction):
        async with self.bot.pool.acquire() as conn:
            categories = await conn.fetch("SELECT id, name, emoji FROM cd_grocery_category ORDER BY name")
            categories_with_items = []
            for category in categories:
                groceries = await conn.fetch(
                    """
                    SELECT id, name, emoji, cost, shelf_life
                    FROM cd_grocery_type
                    WHERE category_id = $1
                    ORDER BY name
                    """,
                    category["id"]
                )
                formatted_items = [
                    {
                        "id": item["id"],
                        "emoji": item["emoji"],
                        "name": item["name"],
                        "cost": item["cost"],
                        "shelf_life": item["shelf_life"],
                    }
                    for item in groceries
                ]
                categories_with_items.append((category["name"], formatted_items))

        await interaction.response.defer(ephemeral=False)
        main_msg = await interaction.followup.send("Loading market...", ephemeral=False)

        view = ControlView(interaction.user.id, self.bot, categories_with_items, interaction.channel, main_msg)
        await view.send_item_messages()


async def setup(bot: commands.Bot):
    await bot.add_cog(GroceryCog(bot))
