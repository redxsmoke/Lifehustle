from discord import app_commands
from discord.ext import commands
from discord.ui import View, Select

import discord

from Bot_occupations.occupation_db_utilities import assign_user_job, get_eligible_occupations, get_user

class ApplyJob(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = bot.pool

    @app_commands.command(name="need_money", description="Apply for a new job!")
    async def need_money(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user = await get_user(self.pool, interaction.user.id)
        user_edu_level = user.get('education_level_id', 1)

        occupations = await get_eligible_occupations(self.pool, user_edu_level)

        if not occupations:
            await interaction.followup.send("You don't qualify for any jobs right now.", ephemeral=True)
            return

        options = [
            discord.SelectOption(label=row['description'], value=str(row['cd_occupation_id']))
            for row in occupations
        ]

        class JobSelectView(View):
            def __init__(self):
                super().__init__()

                # Add the select menu with options dynamically
                self.select_menu = Select(
                    placeholder="Select a job to apply for",
                    options=options,
                    min_values=1,
                    max_values=1
                )
                self.select_menu.callback = self.select_callback
                self.add_item(self.select_menu)

            async def select_callback(self, select: discord.ui.Select, interaction2: discord.Interaction):
                try:
                    selected_id = int(select.values[0])
                    success = await assign_user_job(self.pool, interaction2.user.id, selected_id)
                    selected_label = next(opt.label for opt in options if opt.value == select.values[0])

                    if success:
                        response_msg = f"🎉 You are now employed as a **{selected_label}**!"
                        # Disable select menu so user can't re-select
                        self.select_menu.disabled = True
                        await interaction2.response.edit_message(content=response_msg, view=self)
                    else:
                        await interaction2.response.send_message("⚠️ Failed to assign that job. Please try again.", ephemeral=True)
                except Exception as e:
                    await interaction2.response.send_message(f"⚠️ An error occurred: {e}", ephemeral=True)

        await interaction.followup.send("Choose a job to apply for:", view=JobSelectView(), ephemeral=True)


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
