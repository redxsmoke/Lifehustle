from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select

import discord

from Bot_occupations.occupation_db_utilities import assign_user_job, get_eligible_occupations, get_user

class JobSelectView(View):
    def __init__(self, pool, options):
        super().__init__()
        self.pool = pool
        self.options = options

        self.select_menu = Select(
            placeholder="Select a job to apply for",
            options=options,
            min_values=1,
            max_values=1
        )
        # Assign the callback properly BEFORE adding the select to the view
        self.select_menu.callback = self.select_callback
        self.add_item(self.select_menu)

    async def select_callback(self, select: discord.ui.Select, interaction: discord.Interaction):
        try:
            selected_id = int(select.values[0])
            print(f"[DEBUG] User {interaction.user.id} selected job {selected_id}")

            success = await assign_user_job(self.pool, interaction.user.id, selected_id)
            selected_label = next(opt.label for opt in self.options if opt.value == select.values[0])

            if success:
                self.select_menu.disabled = True
                # Edit original message
                await interaction.response.edit_message(
                    content=f"🎉 You are now employed as a **{selected_label}**!", view=self
                )
                print(f"[DEBUG] Job assignment succeeded")
            else:
                await interaction.response.send_message(
                    "⚠️ Failed to assign that job. Please try again.", ephemeral=True
                )
                print(f"[DEBUG] Job assignment failed")
        except Exception as e:
            print(f"[ERROR] Exception in select_callback: {e}")
            # Send ephemeral error message (make sure response sent exactly once)
            if not interaction.response.is_done():
                await interaction.response.send_message(f"⚠️ An error occurred: {e}", ephemeral=True)
            else:
                # If response already sent, just log error or notify user differently
                print("[ERROR] Interaction response already sent.")


class JobStatus(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = bot.pool

    @commands.command(name="current_job")
    async def current_job(self, ctx):
        user_id = ctx.author.id
        async with self.pool.acquire() as conn:
            user = await conn.fetchrow('''
                SELECT occupation_id, job_start_date FROM users WHERE user_id = $1
            ''', user_id)
            if not user or not user['occupation_id']:
                await ctx.send("You currently have no job.")
                return

            occupation = await conn.fetchrow('''
                SELECT description, pay_rate, required_shifts_per_day
                FROM cd_occupations WHERE cd_occupation_id = $1
            ''', user['occupation_id'])

            embed = discord.Embed(title="Current Job Info", color=discord.Color.blue())
            embed.add_field(name="Job Title", value=occupation['description'], inline=False)
            embed.add_field(name="Pay Rate (per shift)", value=f"${occupation['pay_rate']}", inline=True)
            embed.add_field(name="Shifts Required Per Day", value=str(occupation['required_shifts_per_day']), inline=True)
            embed.add_field(
                name="Hired Since",
                value=user['job_start_date'].strftime("%Y-%m-%d") if user['job_start_date'] else "Unknown",
                inline=False
            )

            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ApplyJob(bot))
    await bot.add_cog(JobStatus(bot))
