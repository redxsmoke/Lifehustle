from discord.ui import View, Select, Button
import discord
import traceback

from Bot_occupations.occupation_db_utilities import assign_user_job

class OfferConfirmationView(View):
    def __init__(self, pool, user_id, occupation):
        super().__init__(timeout=300)  # Optional: 5 min timeout
        self.pool = pool
        self.user_id = user_id
        self.occupation = occupation

    @discord.ui.button(label="Accept Position", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        success = await assign_user_job(self.pool, self.user_id, self.occupation['cd_occupation_id'])
        if success:
            await interaction.response.edit_message(
                content=(
                    f"✅ Congratulations! You have accepted the position as **{self.occupation['description']}** "
                    f"at **{self.occupation['company_name']}**."
                ),
                view=None
            )
        else:
            await interaction.response.send_message("⚠️ Failed to accept the job. Please try again.", ephemeral=True)
        self.stop()

    @discord.ui.button(label="Decline Position", style=discord.ButtonStyle.danger)
    async def decline(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(
            content="❌ You have declined the position. Feel free to apply for another job!", 
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

            # Fetch occupation details from DB
            async with self.pool.acquire() as conn:
                occupation = await conn.fetchrow('''
                    SELECT cd_occupation_id, company_name, description, pay_rate, required_shifts_per_day
                    FROM cd_occupations
                    WHERE cd_occupation_id = $1 AND active = TRUE
                ''', selected_id)

            if not occupation:
                await interaction.response.send_message("⚠️ Selected occupation not found or inactive.", ephemeral=True)
                return

            offer_message = (
                f"**Offer Letter from {occupation['company_name']}**\n\n"
                f"{occupation['company_name']} has made you the following employment offer!\n\n"
                f"**Job Title:** {occupation['description']}\n"
                f"**Pay Rate:** ${occupation['pay_rate']} per shift\n"
                f"**Number of Required Shifts:** {occupation['required_shifts_per_day']}\n\n"
                "Do you accept this position?"
            )

            view = OfferConfirmationView(self.pool, interaction.user.id, occupation)

            self.disabled = True  # Disable select menu after choosing
            await interaction.response.edit_message(content=offer_message, view=view)

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
