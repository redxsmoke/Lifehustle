import discord
from discord import app_commands
from discord.ext import commands
from crimes.crime_views import CrimeSelectionView

class CrimeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="crime", description="Commit a crime to earn rewards or penalties.")
    async def crime(self, interaction: discord.Interaction):
        view = CrimeSelectionView(interaction.user)
        await interaction.response.send_message(
            "Choose a crime to commit:", view=view, ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(CrimeCommands(bot))
