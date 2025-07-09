# This makes the folder a Python packageimport discord
from discord.ext import commands
from discord import app_commands

class Achievements(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="achievements", description="View your earned achievements.")
    async def achievements(self, interaction: discord.Interaction):
        user_id = interaction.user.id

        async with self.bot.pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT achievement_emoji, achievement_name, achievement_description
                FROM user_achievements
                WHERE user_id = $1
            """, user_id)

        if not rows:
            embed = discord.Embed(
                title="No Achievements Yet",
                description="You have no achievements yet, you bum. 🧹 Try doing something impressive first.",
                color=discord.Color.dark_gray()
            )
        else:
            embed = discord.Embed(
                title="🏆 Your Achievements",
                color=discord.Color.green()
            )
            for row in rows:
                emoji = row['achiev]()
