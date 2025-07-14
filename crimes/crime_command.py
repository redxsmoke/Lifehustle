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
            color=0x7289DA  # blurple
        )
        await interaction.response.send_message(
            embed=embed, view=view, ephemeral=True
        )

    async def handle_rob_job(self, interaction: discord.Interaction):
        print(f"[DEBUG] handle_rob_job started for {interaction.user} ({interaction.user.id})")

        class ConfirmRobberyView(discord.ui.View):
            def __init__(self, user_id, timeout=60):
                super().__init__(timeout=timeout)
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
            async def continue_button(self, button: discord.ui.Button, interaction: discord.Interaction):
                self.value = True
                for child in self.children:
                    child.disabled = True
                await interaction.response.edit_message(
                    content="Robbery confirmed! Preparing to crack the vault...", view=self
                )
                self.stop()

            @discord.ui.button(label="Cancel", style=discord.ButtonStyle.red)
            async def cancel_button(self, button: discord.ui.Button, interaction: discord.Interaction):
                self.value = False
                for child in self.children:
                    child.disabled = True
                await interaction.response.edit_message(
                    content="Robbery cancelled.", view=self
                )
                self.stop()

        intro_embed = discord.Embed(
            title="💼 Breaking In...",
            description="You're breaking into your workplace safe... Try to crack the code!",
            color=0xFAA61A
        )

        view = ConfirmRobberyView(user_id=interaction.user.id)
        await interaction.response.send_message(embed=intro_embed, view=view, ephemeral=True)

        await view.wait()

        if view.value is None:
            timeout_embed = discord.Embed(
                title="⌛ Timeout",
                description="You took too long to decide. Robbery cancelled.",
                color=0x747F8D
            )
            await interaction.followup.send(embed=timeout_embed, ephemeral=True)
            return

        if not view.value:
            cancel_embed = discord.Embed(
                title="❌ Robbery Cancelled",
                description="You decided not to rob your job. Smart choice!",
                color=0xF04747
            )
            await interaction.followup.send(embed=cancel_embed, ephemeral=True)
            return

        try:
            vault_view = VaultGameView(user_id=interaction.user.id)
            await interaction.followup.send(
                embed=discord.Embed(
                    title="💼 Vault Crack In Progress",
                    description="Enter the 3-digit code to crack the vault!",
                    color=0xFAA61A
                ),
                view=vault_view,
                ephemeral=True
            )

            await vault_view.wait()

            print(f"[DEBUG] VaultGameView ended with outcome: {vault_view.outcome}")

            if vault_view.outcome == "success":
                success_embed = discord.Embed(
                    title="✅ Vault Cracked!",
                    description="You successfully cracked the vault and got away with the loot! (Payout pending)",
                    color=0x43B581
                )
                await interaction.followup.send(embed=success_embed, ephemeral=True)

            elif vault_view.outcome == "failure":
                failure_embed = discord.Embed(
                    title="🚨 Alarm Triggered!",
                    description="You failed to crack the vault. Alarm triggered. Police are on their way!",
                    color=0xF04747
                )
                await interaction.followup.send(embed=failure_embed, ephemeral=True)

            else:
                neutral_embed = discord.Embed(
                    title="⏳ Timeout or Abandoned",
                    description="You gave up or the game timed out.",
                    color=0x747F8D
                )
                await interaction.followup.send(embed=neutral_embed, ephemeral=True)

        except Exception as e:
            print(f"❌ Exception in handle_rob_job: {e}")
            error_embed = discord.Embed(
                title="❌ Error",
                description="Something went wrong during the robbery attempt.",
                color=0xF04747
            )
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=error_embed, ephemeral=True)
            else:
                await interaction.followup.send(embed=error_embed, ephemeral=True)
        except Exception as inner_e:
            print(f"❌ Failed to send error message: {inner_e}")

async def setup(bot):
    await bot.add_cog(CrimeCommands(bot))
