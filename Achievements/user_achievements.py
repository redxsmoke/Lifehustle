import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import traceback

from db_user import get_user_achievements  # Your DB function to fetch achievements
from utilities import embed_message  # Your embed helper

class ButtonGame(commands.Cog):
    def __init__(self, bot: commands.Bot, pool):
        self.bot = bot
        self.pool = pool

    @app_commands.command(name="achievements", description="Show your achievements")
    async def achievements(self, interaction: discord.Interaction):
        try:
            user_id = interaction.user.id
            achievements = await get_user_achievements(self.pool, user_id)
            if not achievements:
                await interaction.response.send_message(
                    embed=embed_message(
                        "No Achievements Yet",
                        "You haven't unlocked any achievements yet. Keep playing!",
                        discord.Color.dark_grey()
                    ),
                    ephemeral=True
                )
                return

            desc_lines = []
            for row in achievements:
                emoji = row.get('achievement_emoji', '')
                name = row.get('achievement_name', 'Unknown Achievement')
                description = row.get('achievement_description', '')
                desc_lines.append(f"{emoji} **{name}** — {description}")

            embed = discord.Embed(
                title=f"🏆 Achievements for {interaction.user.display_name}",
                description="\n".join(desc_lines),
                color=discord.Color.gold()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            traceback.print_exc()
            await interaction.response.send_message(
                "❌ An error occurred while fetching achievements.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    # Prevent duplicate Cog loading:
    if bot.get_cog("ButtonGame") is None:
        await bot.add_cog(ButtonGame(bot, bot.pool))
