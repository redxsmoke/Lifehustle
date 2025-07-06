from discord.ui import View, Select, Button
import discord
import traceback

from embeds import COLOR_GREEN, COLOR_RED
from Bot_occupations.occupation_db_utilities import assign_user_job

class OfferConfirmationView(View):
    def __init__(self, pool, user_id, occupation):
        super().__init__(timeout=300)  # 5 min timeout
        self.pool = pool
        self.user_id = user_id
        self.occupation = occupation

    @discord.ui.button(label="✅ Accept Position", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        success = await assign_user_job(self.pool, self.user_id, self.occupation['cd_occupation_id'])
        if success:
                embed = discord.Embed(
                    title="✅ Position Accepted!",
                    description=f"> 🥳 Congratulations! You have accepted the position as **{self.occupation['description']}** at **{self.occupation['company_name']}**.",
                    color=discord.Color.green()
                )
        else:
            await interaction.response.send_message("⚠️ Failed to accept the job. Please try again.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="❌ Decline Position", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="You have declined the position. Feel free to apply for another job!",
            embed=None,
            view=None
        )
        self.stop()

class JobSelect(Select):
    def __init__(self, pool, options):
        super().__init__(
            placeholder="Select a job to apply for",
            min_values=1,
            max_values=1,
            options=options
        )
        self.pool = pool

    async def callback(self, interaction: discord.Interaction):
        try:
            selected_id = int(self.values[0])
            print(f"[DEBUG] User {interaction.user.id} selected job {selected_id}")

            # Fetch occupation details
            async with self.pool.acquire() as conn:
                occupation = await conn.fetchrow('''
                    SELECT cd_occupation_id, company_name, description, pay_rate, required_shifts_per_day
                    FROM cd_occupations
                    WHERE cd_occupation_id = $1 AND active = TRUE
                ''', selected_id)

            if not occupation:
                await interaction.response.send_message("⚠️ Selected occupation not found or inactive.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"📄 Offer Letter from {occupation['company_name']}",
                description=f"{occupation['company_name']} has made you the following employment offer!",
                color=discord.Color.green()
            )
            embed.add_field(name="💼 Job Title", value=occupation['description'], inline=False)
            embed.add_field(name="💰 Pay Rate", value=f"${occupation['pay_rate']} per shift", inline=True)
            embed.add_field(name="⏰ Required Shifts Per Day", value=str(occupation['required_shifts_per_day']), inline=True)
            embed.add_field(name="📅 Start Date", value="Immediate Start", inline=False)
            embed.set_footer(text="Do you accept this position?")

            view = OfferConfirmationView(self.pool, interaction.user.id, occupation)

            self.disabled = True  # disable the select menu after selection
            await interaction.response.edit_message(content=None, embed=embed, view=view)

        except Exception as e:
            print(f"[ERROR] Exception in callback: {e}")
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(f"⚠️ An error occurred: {e}", ephemeral=True)

class JobSelectView(View):
    def __init__(self, pool, options):
        super().__init__()
        self.pool = pool
        self.job_select = JobSelect(pool, options)
        self.add_item(self.job_select)
