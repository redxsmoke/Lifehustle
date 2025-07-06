from discord import app_commands
from discord.ext import commands
import discord

from Bot_occupations.occupation_db_utilities import get_user, get_eligible_occupations
from Bot_occupations.occupations_views import JobSelectView  # Make sure this file exists and is correct!

class ApplyJob(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.pool = bot.pool

    @app_commands.command(name="need_money", description="Apply for a new job!")
    async def need_money(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)

        user = await get_user(self.pool, interaction.user.id)
        if not user:
            async with self.pool.acquire() as conn:
                await conn.execute('''
                    INSERT INTO users (user_id, education_level_id, occupation_id)
                    VALUES ($1, 1, NULL)
                    ON CONFLICT (user_id) DO NOTHING
                ''', interaction.user.id)
            user_edu_level = 1
        else:
            user_edu_level = user.get('education_level_id') or 1

        occupations = await get_eligible_occupations(self.pool, user_edu_level)
        if not occupations:
            await interaction.followup.send("You don't qualify for any jobs right now.", ephemeral=True)
            return

        options = [
            discord.SelectOption(label=row['description'], value=str(row['cd_occupation_id']))
            for row in occupations
        ]

        view = JobSelectView(self.pool, options)
        await interaction.followup.send(
            "Choose a job to apply for:",
            view=view,
            ephemeral=True
        )

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
