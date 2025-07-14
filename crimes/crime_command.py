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
        print(f"[DEBUG] /crime invoked by {interaction.user} ({interaction.user.id})")
        view = CrimeSelectionView(interaction.user, self.bot)
        await interaction.response.send_message(
            "Choose a crime to commit:", view=view, ephemeral=True
        )

    async def handle_rob_job(self, interaction: discord.Interaction):
        print(f"[DEBUG] handle_rob_job started for {interaction.user} ({interaction.user.id})")
        try:
            view = VaultGameView(user_id=interaction.user.id)
            await interaction.response.send_message(
                content="💼 You're breaking into your workplace safe... Try to crack the code!",
                view=view,
                ephemeral=True
            )

            # Wait for the game view to finish or timeout
            await view.wait()

            print(f"[DEBUG] VaultGameView ended with outcome: {view.outcome}")

            if view.outcome == "success":
                await interaction.followup.send(
                    "✅ You successfully cracked the vault and got away with the loot! (Payout pending)",
                    ephemeral=True
                )
            elif view.outcome == "failure":
                await interaction.followup.send(
                    "🚨 You failed to crack the vault. Alarm triggered. Police are on their way!",
                    ephemeral=True
                )
            else:
                await interaction.followup.send(
                    "🤔 You gave up or the game timed out.",
                    ephemeral=True
                )

        except Exception as e:
            print(f"❌ Exception in handle_rob_job: {e}")
            try:
                if not interaction.response.is_done():
                    await interaction.response.send_message("Something went wrong.", ephemeral=True)
                else:
                    await interaction.followup.send("Something went wrong.", ephemeral=True)
            except Exception as inner_e:
                print(f"❌ Failed to send error message: {inner_e}")

async def setup(bot):
    await bot.add_cog(CrimeCommands(bot))
