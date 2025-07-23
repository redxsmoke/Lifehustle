import discord
from discord import app_commands, Interaction
from discord.ext import commands
from grocery_logic.grocery_views import GroceryMarketView

class GroceryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="market", description="Browse and buy groceries")
    async def market(self, interaction: Interaction):
        async with self.bot.pool.acquire() as conn:
            # Fetch all grocery categories
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

                # Format each grocery row into a dictionary with expected keys
                formatted_items = [
                    {
                        "id": item["id"],
                        "emoji": item["emoji"],
                        "name": item["name"],
                        "cost": item["cost"],
                        "shelf_life": item["shelf_life"],
                        "value_per_unit": "N/A"  # Optional field; update if you calculate this
                    }
                    for item in groceries
                ]

                categories_with_items.append((category["name"], formatted_items))

        view = GroceryMarketView(user_id=interaction.user.id, bot=self.bot, categories_with_items=categories_with_items)
        text = view.build_message_text()
        view.message = await interaction.response.send_message(content=text, view=view, ephemeral=True)

        await interaction.response.send_message(content=content, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(GroceryCog(bot))
