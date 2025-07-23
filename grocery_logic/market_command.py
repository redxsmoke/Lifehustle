import discord
from discord import app_commands, Interaction, SelectOption
from discord.ext import commands
from grocery_logic.grocery_views import GroceryCategoryView, GroceryStashPaginationView

class GroceryCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="market", description="Browse and buy groceries")
    async def market(self, interaction: Interaction):
        async with self.bot.pool.acquire() as conn:
            categories = await conn.fetch("SELECT name, emoji FROM cd_grocery_category ORDER BY name")

        options = [
            SelectOption(label=cat["name"], description=f"Browse {cat['name']}", emoji=cat["emoji"])
            for cat in categories
        ]

        view = GroceryCategoryView(options=options, user_id=interaction.user.id, bot=self.bot)
        await interaction.response.send_message(
            "Select a grocery category to browse:", view=view, ephemeral=True
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(GroceryCog(bot))
