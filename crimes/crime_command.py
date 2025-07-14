import discord
from discord import app_commands
from discord.ext import commands
from crimes.crime_views import CrimeSelectionView
from crimes.break_job_vault import VaultGameView

class CrimeCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="crime", description="Commit a crime to earn rewards or penalties.")
    async def crime(self, interaction: discord.Interaction):
        view = CrimeSelectionView(interaction.user, self.bot)
        await interaction.response.send_message(
            "Choose a crime to commit:", view=view, ephemeral=True
        )

    async def handle_rob_job(self, interaction: discord.Interaction):
        view = VaultGameView(user_id=interaction.user.id)
        await interaction.response.send_message(
            content="💼 You're breaking into your workplace safe... Try to crack the code!",
            view=view
        )
        await view.wait()

        if view.outcome == "success":
            # TODO: Issue payout logic here
            await interaction.followup.send("✅ You successfully cracked the vault and got away with the loot! (Payout pending)")

        elif view.outcome == "failure":
            # TODO: Trigger police response options here
            await interaction.followup.send("🚨 You failed to crack the vault. Alarm triggered. Police are on their way!")

async def setup(bot):
    await bot.add_cog(CrimeCommands(bot))
