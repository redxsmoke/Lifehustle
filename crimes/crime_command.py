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
        embed = discord.Embed(
            title="Choose a Crime",
            description="Select a crime to commit:",
            color=0x7289DA
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def handle_rob_job(self, interaction: discord.Interaction):
        print(f"[DEBUG] handle_rob_job started for {interaction.user} ({interaction.user.id})")

        class ConfirmRobberyView(discord.ui.View):
            def __init__(self, user_id):
                super().__init__(timeout=60)
                self.user_id = user_id
                self.value = None

            async def interaction_check(self, interaction: discord.Interaction) -> bool:
                if interaction.user.id != self.user_id:
                    await interaction.response.send_message(
                        "This isn't your robbery to confirm/cancel!", ephemeral=True
                    )
                    return False
                return True

            @discord.ui.button(label="Continue", style=discord.ButtonStyle.green)
            async def continue_button(self, button, interaction: discord.Interaction):
                self.value = True
                await interaction.response.send_message(
                    "✅ Robbery confirmed! Cracking the vault now...", ephemeral=True
                )
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
            async def cancel_button(self, button, interaction: discord.Interaction):
                self.value = False
                await interaction.response.send_message(
                    "❌ Robbery cancelled.", ephemeral=True
                )
                self.stop()

        confirm_view = ConfirmRobberyView(user_id=interaction.user.id)

        # DEFER the initial slash command response (required for followups)
        await interaction.response.defer(ephemeral=True)

        # Send embed with buttons as a FOLLOWUP
        await interaction.followup.send(
            embed=discord.Embed(
                title="💼 Breaking In...",
                description="You're breaking into your workplace safe... Try to crack the code!",
                color=0xFAA61A,
            ),
            view=confirm_view,
            ephemeral=True,
        )

        # Wait for button press
        await confirm_view.wait()

        # Handle timeout (no button clicked)
        if confirm_view.value is None:
            await interaction.followup.send(
                embed=discord.Embed(
                    title="⌛ Timeout",
                    description="You took too long to decide. Robbery cancelled.",
                    color=0x747F8D,
                ),
                ephemeral=True,
            )
            return

        # If user cancelled (already responded), just return
        if not confirm_view.value:
            return

        # User confirmed — start vault game
        try:
            vault_view = VaultGameView(user_id=interaction.user.id)

            await interaction.followup.send(
                embed=discord.Embed(
                    title="🔐 Vault Crack In Progress",
                    description="Enter the 3-digit code to crack the vault!",
                    color=0xFAA61A,
                ),
                view=vault_view,
                ephemeral=True,
            )

            await vault_view.wait()

            print(f"[DEBUG] VaultGameView ended with outcome: {vault_view.outcome}")

            if vault_view.outcome == "success":
                outcome_embed = discord.Embed(
                    title="✅ Vault Cracked!",
                    description="You successfully cracked the vault and got away with the loot! 💰",
                    color=0x43B581,
                )
            elif vault_view.outcome == "failure":
                outcome_embed = discord.Embed(
                    title="🚨 Alarm Triggered!",
                    description="You failed to crack the vault. Police are on their way! 🚓",
                    color=0xF04747,
                )
            else:
                outcome_embed = discord.Embed(
                    title="⏳ Timeout or Abandoned",
                    description="You gave up or the game timed out.",
                    color=0x747F8D,
                )

            await interaction.followup.send(embed=outcome_embed, ephemeral=True)

        except Exception as e:
            print(f"❌ Exception in vault game: {e}")
            try:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="Something went wrong during the robbery.",
                        color=0xF04747,
                    ),
                    ephemeral=True,
                )
            except Exception as inner_e:
                print(f"❌ Could not send error message: {inner_e}")

async def setup(bot):
    await bot.add_cog(CrimeCommands(bot))
