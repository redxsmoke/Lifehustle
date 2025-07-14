import discord
from discord import app_commands
from discord.ext import commands
from crimes.crime_views import CrimeSelectionView, ConfirmRobberyView
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
        try:
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            print("[DEBUG] Sent initial crime selection message successfully.")
        except Exception as e:
            print(f"[ERROR] Failed to send initial crime selection message: {e}")

    async def handle_rob_job(self, interaction: discord.Interaction):
        print(f"[DEBUG] handle_rob_job started for {interaction.user} ({interaction.user.id})")

        confirm_view = ConfirmRobberyView(user_id=interaction.user.id)

        try:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="💼 Breaking In...",
                    description="You're breaking into your workplace safe...If you get caught you will certainly be fired and possible go to jail. Do you with to continue?",
                    color=0xFAA61A,
                ),
                view=confirm_view,
                ephemeral=True,
            )
            print("[DEBUG] Sent robbery confirmation embed with buttons.")
        except Exception as e:
            print(f"[ERROR] Failed to send robbery confirmation message: {e}")
            return

        await confirm_view.wait()
        print(f"[DEBUG] ConfirmRobberyView ended with value: {confirm_view.value}")

        if confirm_view.value is None:
            try:
                await interaction.followup.send(
                    embed=discord.Embed(
                        title="⌛ Timeout",
                        description="You took too long to decide. Robbery cancelled.",
                        color=0x747F8D,
                    ),
                    ephemeral=True,
                )
                print("[DEBUG] Sent timeout message after no button pressed.")
            except Exception as e:
                print(f"[ERROR] Failed to send timeout followup message: {e}")
            return

        if not confirm_view.value:
            print("[DEBUG] Robbery cancelled by user.")
            return

        try:
            vault_view = VaultGameView(user_id=interaction.user.id)

            print("[DEBUG] Sending VaultGameView to user.")
            await confirm_view.user_interaction.followup.send(
                embed=discord.Embed(
                    title="🔐 Vault Crack In Progress",
                    description="Enter the 3-digit code to crack the vault!",
                    color=0xFAA61A,
                ),
                view=vault_view,
                ephemeral=True,
            )
            print("[DEBUG] VaultGameView message sent.")

            await vault_view.wait()
            print(f"[DEBUG] VaultGameView ended with outcome: {vault_view.outcome}")

            if vault_view.outcome == "success":
                # Step 1: Calculate the payout
                base_amount = random.randint(1000, 5000)
                multiplier = round(random.uniform(1.0, 5.0), 2)
                payout = int(base_amount * multiplier)

                # Step 2: Update the database
                async with self.bot.db.execute("SELECT checking_account_balance FROM user_finances WHERE user_id = ?", (interaction.user.id,)) as cursor:
                    row = await cursor.fetchone()
                    if row:
                        new_balance = row[0] + payout
                        await self.bot.db.execute(
                            "UPDATE user_finances SET checking_account_balance = ? WHERE user_id = ?",
                            (new_balance, interaction.user.id)
                        )
                    else:
                        # If the user doesn't exist yet in finances, insert a new row
                        new_balance = payout
                        await self.bot.db.execute(
                            "INSERT INTO user_finances (user_id, checking_account_balance) VALUES (?, ?)",
                            (interaction.user.id, payout)
                        )

                await self.bot.db.commit()

                # Step 3: Send success message with amount
                outcome_embed = discord.Embed(
                    title="✅ Vault Cracked!",
                    description=f"You successfully cracked the vault and escaped with **${payout:,}**! 💰",
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

            await confirm_view.user_interaction.followup.send(embed=outcome_embed, ephemeral=True)
            print("[DEBUG] Sent vault outcome embed.")

        except Exception as e:
            print(f"❌ Exception in vault game: {e}")
            try:
                await confirm_view.user_interaction.followup.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="Something went wrong during the robbery.",
                        color=0xF04747,
                    ),
                    ephemeral=True,
                )
                print("[DEBUG] Sent error message after vault game exception.")
            except Exception as inner_e:
                print(f"❌ Could not send error message: {inner_e}")

async def setup(bot):
    await bot.add_cog(CrimeCommands(bot))
