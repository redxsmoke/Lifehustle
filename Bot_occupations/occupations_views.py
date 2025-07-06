from discord.ui import View, Select
import discord
import traceback

from Bot_occupations.occupation_db_utilities import assign_user_job

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
            print(f"[DEBUG] callback called with interaction type: {type(interaction)} and self.values: {getattr(self, 'values', None)}")

            selected_id = int(self.values[0])
            print(f"[DEBUG] User {interaction.user.id} selected job {selected_id}")

            success = await assign_user_job(self.pool, interaction.user.id, selected_id)
            selected_label = next(opt.label for opt in self.options if opt.value == str(selected_id))

            if success:
                self.disabled = True  # disable the select menu
                await interaction.response.edit_message(
                    content=f"🎉 You are now employed as a **{selected_label}**!",
                    view=self.view
                )
                print("[DEBUG] Job assignment succeeded")
            else:
                await interaction.response.send_message(
                    "⚠️ Failed to assign that job. Please try again.", ephemeral=True
                )
                print("[DEBUG] Job assignment failed")

        except Exception as e:
            print(f"[ERROR] Exception in callback: {e}")
            traceback.print_exc()
            # Send ephemeral error message if no response sent yet
            if not interaction.response.is_done():
                await interaction.response.send_message(f"⚠️ An error occurred: {e}", ephemeral=True)

class JobSelectView(View):
    def __init__(self, pool, options):
        super().__init__()
        self.pool = pool
        self.job_select = JobSelect(pool, options)
        self.add_item(self.job_select)
