import discord
from discord.ext import commands
from discord import app_commands, Interaction
from discord.ui import View, Button
import asyncio

ITEMS_PER_PAGE = 3

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


class ControlView(View):
    def __init__(self, user_id, bot, categories_with_items, main_message):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.bot = bot
        self.categories_with_items = categories_with_items
        self.current_category_index = 0
        self.current_page = 0
        self.main_message = main_message
        self.item_messages = []

        self.prev_button = Button(label="⬅️ Prev", style=discord.ButtonStyle.secondary)
        self.next_button = Button(label="Next ➡️", style=discord.ButtonStyle.secondary)
        self.prev_button.callback = self.prev_page
        self.next_button.callback = self.next_page
        # Note: NOT adding buttons to self here; we'll build nav-only view at bottom

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
        # Delete old item messages including nav/footer message if exists
        for msg in self.item_messages:
            try:
                await msg.delete()
            except:
                pass
        self.item_messages = []

        # Also delete old footer message if we have one stored
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

        # Send one message per item, each with accept button
        for idx, item in enumerate(page_items, start=1 + self.current_page * ITEMS_PER_PAGE):
            content = (
                f"**Buying {idx} {item['emoji']} {item['name']}**\n"
                f"├ For: ${item['cost']}\n"
                f"├ Value per Unit: {item.get('value_per_unit', 'N/A')}\n"
                f"├ Expires: {item['shelf_life']} days\n"
                f"├ ID: {item['id']}\n"
            )
            view = View()
            view.add_item(ItemButton(item, self.user_id, self.bot))
            msg = await self.main_message.channel.send(content=content, view=view)
            self.item_messages.append(msg)

        # Now send the footer + nav buttons as a new message below all items
        footer_text = self.build_main_message_text()
        footer_view = self.build_nav_view()
        self.footer_message = await self.main_message.channel.send(content=footer_text, view=footer_view)

        # Optionally, delete the original main message since it's just a dummy placeholder
        try:
            await self.main_message.delete()
        except:
            pass


    def build_main_message_text(self):
        total_categories = len(self.categories_with_items)
        category_name, groceries = self.categories_with_items[self.current_category_index]
        total_items = len(groceries)
        max_page = max(0, (total_items - 1) // ITEMS_PER_PAGE)
        return f"🛒 **{category_name} Market**\nPage {self.current_page + 1} / {max_page + 1} — Category {self.current_category_index + 1} / {total_categories}"

    async def prev_page(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.defer()
            await self.send_item_messages()

    async def next_page(self, interaction: Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn’t your market view.", ephemeral=True)
            return
        category_name, groceries = self.categories_with_items[self.current_category_index]
        total_items = len(groceries)
        max_page = max(0, (total_items - 1) // ITEMS_PER_PAGE)
        if self.current_page < max_page:
            self.current_page += 1
            await interaction.response.defer()
            await self.send_item_messages()

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
    async def market(self, interaction: Interaction):
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
                        "value_per_unit": "N/A"
                    }
                    for item in groceries
                ]
                categories_with_items.append((category["name"], formatted_items))

        # Send a dummy message for controls first
        main_msg = await interaction.response.send_message(content="Loading market...", ephemeral=True)
        main_msg = await interaction.original_response()

        view = ControlView(interaction.user.id, self.bot, categories_with_items, main_msg)
        await view.send_item_messages()  # Send item messages after main

        # Edit main message with proper content and view
        await main_msg.edit(content=view.build_main_message_text(), view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(GroceryCog(bot))
