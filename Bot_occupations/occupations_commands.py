from discord import app_commands
from discord.ext import commands
from discord.ui import View
import discord

# Make sure to import these from your occupations views or relevant module:
from Bot_occupations.occupations get assign_user_job, get_eligible_occupations

class ApplyJob(commands.Cog):
    def __init__(self, bot, pool):
        self.bot = bot
        self.pool = pool

    @app_commands.command(name="apply_job", description="Apply for a new job!")
    async def apply_job(self, interaction: discord.Interaction):
        user = await get_user(self.pool, interaction.user.id)
        user_edu_level = user.get('education_level_id', 1)

        occupations = await get_eligible_occupations(self.pool, user_edu_level)

        if not occupations:
            await interaction.response.send_message("You don't qualify for any jobs right now.", ephemeral=True)
            return

        options = [
            discord.SelectOption(label=row['description'], value=str(row['cd_occupation_id']))
            for row in occupations
        ]

        class JobSelectView(View):
            @discord.ui.select(placeholder="Select a job to apply for", options=options)
            async def select_callback(self, select: discord.ui.Select, interaction2: discord.Interaction):
                selected_id = int(select.values[0])
                await assign_user_job(self.pool, interaction.user.id, selected_id)
                # Find label for selected option to show proper job name
                selected_label = next(opt.label for opt in options if opt.value == select.values[0])
                await interaction2.response.send_message(f"🎉 You are now employed as a **{selected_label}**!", ephemeral=True)

        await interaction.response.send_message("Choose a job to apply for:", view=JobSelectView(), ephemeral=True)

async def setup(bot, pool):
    await bot.add_cog(ApplyJob(bot, pool))


import discord
from discord.ext import commands

class JobStatus(commands.Cog):
    def __init__(self, bot, pool):
        self.bot = bot
        self.pool = pool

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
            embed.add_field(name="Hired Since", value=user['job_start_date'].strftime("%Y-%m-%d") if user['job_start_date'] else "Unknown", inline=False)
            
            await ctx.send(embed=embed)

async def setup(bot, pool):
    await bot.add_cog(JobStatus(bot, pool))
