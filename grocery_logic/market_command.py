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
            # Fetch all grocery categories and their items
            categories = await conn.fetch("SELECT id, name, emoji FROM cd_grocery_category ORDER BY name")

            categories_with_items = []
            for category in categories:
                groceries = await conn.fetch(
                    """
                    SELECT id, name, emoji, cost, shelf_life, category_id
                    FROM cd_grocery_type
                    WHERE category_id = $1
                    ORDER BY name
                    """,
                    category["id"]
                )
                categories_with_items.append((category["name"], groceries))

        # Build the view and first embed
        view = GroceryMarketView(user_id=interaction.user.id, bot=self.bot, categories_with_items=categories_with_items)
        embed = view.create_embed()


        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(GroceryCog(bot))
