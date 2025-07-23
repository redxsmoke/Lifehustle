import discord
from discord import app_commands, Interaction
from discord.ext import commands


class GroceryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="market", description="Browse and buy groceries")
    async def market(self, interaction: Interaction):
        async with self.bot.pool.acquire() as conn:
            # Fetch grocery categories
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

                # Format items
                formatted_items = [
                    {
                        "id": item["id"],
                        "emoji": item["emoji"],
                        "name": item["name"],
                        "cost": item["cost"],
                        "shelf_life": item["shelf_life"]
                    }
                    for item in groceries
                ]

                categories_with_items.append((category["name"], formatted_items))

        # Initial message (needed to anchor the view)
        await interaction.response.send_message("🛒 Loading market...", ephemeral=True)
        main_msg = await interaction.original_response()

        # Start view
        view = GroceryMarketView(user_id=interaction.user.id, bot=self.bot, categories_with_items=categories_with_items, main_message=main_msg)
        await view.send_item_messages()

# Setup function for bot.load_extension
async def setup(bot: commands.Bot):
    await bot.add_cog(GroceryCog(bot))
