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

    async def handle_rob_job(self, base_interaction: discord.Interaction):
        print(f"[DEBUG] handle_rob_job started for {base_interaction.user} ({base_interaction.user.id})")

        # Step 1: Confirmation View
        class ConfirmRobberyView(discord.ui.View):
            def __init__(self, user_id):
                super().__init__(timeout=60)
                self.user_id = user_id
                self.value = None
                self.interaction: discord.Interaction = None

            async def interaction_check(self, interaction: discord.Interaction):
                if interaction.user.id != self.user_id:
                    await interaction.response.send_message(
                        "This isn't your robbery to confirm/cancel!", ephemeral=True
                    )
                    return False
                self.interaction = interaction  # Store interaction for followup
                return True

            @discord.ui.button(label="Continue", style=discord.ButtonStyle.green)
            async def continue_button(self, button, interaction: discord.Interaction):
                self.value = True
                for child in self.children:
                    child.disabled = True
                await interaction.response.edit_message(
                    content="✅ Robbery confirmed! Cracking the vault now...",
                    view=self,
                    embed=None
                )
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
            async def cancel_button(self, button, interaction: discord.Interaction):
                self.value = False
                for child in self.children:
                    child.disabled = True
                await interaction.response.edit_message(
                    content="❌ Robbery cancelled.",
                    view=self,
                    embed=None
                )
                self.stop()

        confirm_embed = discord.Embed(
            title="💼 Breaking In...",
            description="You're breaking into your workplace safe... Try to crack the code!",
            color=0xFAA61A
        )

        confirm_view = ConfirmRobberyView(user_id=base_interaction.user.id)
        await base_interaction.response.send_message(embed=confirm_embed, view=confirm_view, ephemeral=True)

        await confirm_view.wait()

        # Don't use base_interaction anymore. Use confirm_view.interaction.
        if confirm_view.value is None:
            await confirm_view.interaction.followup.send(
                embed=discord.Embed(
                    title="⌛ Timeout",
                    description="You took too long to decide. Robbery cancelled.",
                    color=0x747F8D
                ),
                ephemeral=True
            )
            return

        if not confirm_view.value:
            await confirm_view.interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Robbery Cancelled",
                    description="You decided not to rob your job. Smart choice!",
                    color=0xF04747
                ),
                ephemeral=True
            )
            return

        # Step 2: Start vault game
        try:
            vault_view = VaultGameView(user_id=base_interaction.user.id)
            await confirm_view.interaction.followup.send(
                embed=discord.Embed(
                    title="🔐 Vault Crack In Progress",
                    description="Enter the 3-digit code to crack the vault!",
                    color=0xFAA61A
                ),
                view=vault_view,
                ephemeral=True
            )

            await vault_view.wait()

            print(f"[DEBUG] VaultGameView ended with outcome: {vault_view.outcome}")

            if vault_view.outcome == "success":
                await confirm_view.interaction.followup.send(
                    embed=discord.Embed(
                        title="✅ Vault Cracked!",
                        description="You successfully cracked the vault and got away with the loot! 💰",
                        color=0x43B581
                    ),
                    ephemeral=True
                )

            elif vault_view.outcome == "failure":
                await confirm_view.interaction.followup.send(
                    embed=discord.Embed(
                        title="🚨 Alarm Triggered!",
                        description="You failed to crack the vault. Police are on their way! 🐷",
                        color=0xF04747
                    ),
                    ephemeral=True
                )
            else:
                await confirm_view.interaction.followup.send(
                    embed=discord.Embed(
                        title="🕒 Timeout or Abandoned",
                        description="You gave up or the game timed out.",
                        color=0x747F8D
                    ),
                    ephemeral=True
                )

        except Exception as e:
            print(f"❌ Exception in vault game: {e}")
            await confirm_view.interaction.followup.send(
                embed=discord.Embed(
                    title="❌ Error",
                    description="Something went wrong during the robbery.",
                    color=0xF04747
                ),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(CrimeCommands(bot))
