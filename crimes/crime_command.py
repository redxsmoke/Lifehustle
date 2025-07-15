import discord
from discord import app_commands
from discord.ext import commands
from crimes.crime_views import CrimeSelectionView, ConfirmRobberyView
from crimes.break_job_vault import VaultGameView
import random
from datetime import timedelta
from datetime import datetime
import asyncio


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
                    title="🔐🔓 Breaking In...",
                    description="You're breaking into your workplace safe...If you get caught you will certainly be fired and arrested. Other consequences may also occurr. Do you wish to continue?",
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
            vault_view = VaultGameView(user_id=interaction.user.id, bot=self.bot)

            print("[DEBUG] Sending VaultGameView to channel.")
            msg = await interaction.channel.send(
                embed=discord.Embed(
                    title="🔐 Vault Crack In Progress",
                    description="A mysterious employee is trying to crack the vault...",
                    color=0xFAA61A,
                ),
                view=vault_view
            )
            print("[DEBUG] VaultGameView message sent.")
            await vault_view.disable_snitch_button_later(msg)
            await vault_view.robbery_complete.wait()
            print(f"[DEBUG] VaultGameView robbery completed. Outcome: {vault_view.outcome}, snitched: {vault_view.snitched}")

            if vault_view.outcome == "success":
                base_amount = random.randint(1000, 5000)
                multiplier = round(random.uniform(1.0, 5.0), 2)
                payout = int(base_amount * multiplier)

                async with self.bot.pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT checking_account_balance FROM user_finances WHERE user_id = $1",
                        interaction.user.id
                    )
                    if row:
                        new_balance = row["checking_account_balance"] + payout
                        await conn.execute(
                            "UPDATE user_finances SET checking_account_balance = $1 WHERE user_id = $2",
                            new_balance, interaction.user.id
                        )
                    else:
                        new_balance = payout
                        await conn.execute(
                            "INSERT INTO user_finances (user_id, checking_account_balance) VALUES ($1, $2)",
                            interaction.user.id, payout
                        )

                outcome_embed = discord.Embed(
                    title="✅ Vault Cracked!",
                    description=f"You successfully cracked the vault and escaped with **${payout:,}**. The money has been added to your checking account! 💰",
                    color=0x43B581,
                )

            elif vault_view.outcome == "Caught":
                robber = interaction.guild.get_member(interaction.user.id)
                robber_name = robber.display_name if robber else "The suspect"
                outcome_embed = discord.Embed(
                    title="🚨 Caught!",
                    description=(
                        f"The police searched **{vault_view.chosen_spot}** and found {robber_name} hiding there. "
                        "They’ve been arrested and fired. Their checking account funds have also been seized for investigation 😉😉"
                    ),
                    color=0xF04747,
                )
            elif vault_view.outcome == "failure":
                # Don't send any message — already sent by SnitchConfirmView
                print("[DEBUG] Timeout failure already handled in SnitchConfirmView. Skipping extra embed.")
                return  # skip sending another message

            # --- NEW: Reset finances, fire, and log criminal record when caught or failed ---
            if vault_view.outcome in ("Caught", "failure"):
                try:
                    async with self.bot.pool.acquire() as conn:
                        await conn.execute(
                            "UPDATE user_finances SET checking_account_balance = 0 WHERE user_id = $1",
                            interaction.user.id
                        )
                        await conn.execute(
                            "UPDATE users SET occupation_id = NULL WHERE user_id = $1",
                            interaction.user.id
                        )
                        await conn.execute(
                            "INSERT INTO user_criminal_record (user_id, date_of_offense, crime_id, crime_description, class) VALUES ($1, NOW(), 1, 'Theft', 'Misdemeanor')",
                            interaction.user.id
                        )
                except Exception as e:
                    print(f"[ERROR][handle_rob_job] Failed to update DB on failure: {e}")

            elif vault_view.outcome == "Evaded Police":
                outcome_embed = discord.Embed(
                    title="🏃‍♂️💨 Suspect Evaded Capture!",
                    description="The police searched everywhere but couldn’t find anyone. The suspect evaded capture!",
                    color=0xFAA61A,
                )

            else:
                outcome_embed = discord.Embed(
                    title="⏳ Timeout or Abandoned",
                    description="You gave up or the game timed out.",
                    color=0x747F8D,
                )

            await interaction.channel.send(embed=outcome_embed)
            print("[DEBUG] Sent vault outcome embed.")

        except Exception as e:
            print(f"❌ Exception in vault game: {e}")
            try:
                await interaction.channel.send(
                    embed=discord.Embed(
                        title="❌ Error",
                        description="Something went wrong during the robbery.",
                        color=0xF04747,
                    )
                )
                print("[DEBUG] Sent error message after vault game exception.")
            except Exception as inner_e:
                print(f"❌ Could not send error message: {inner_e}")


async def setup(bot):
    await bot.add_cog(CrimeCommands(bot))
