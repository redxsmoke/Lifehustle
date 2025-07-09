import discord
from discord.ext import commands
from discord import app_commands
import traceback

from db_user import get_user_achievements  # DB function to fetch achievements
from utilities import embed_message  # Embed helper

class UserAchievements(commands.Cog):
    def __init__(self, bot: commands.Bot, pool):
        self.bot = bot
        self.pool = pool

    async def cog_load(self):
        print("Syncing slash commands for UserAchievements Cog...")
        try:
            await self.bot.tree.sync()
            print("Slash commands synced successfully.")
        except Exception as e:
            print(f"Error syncing slash commands: {e}")

    @app_commands.command(name="achievements", description="Show your achievements")
    async def achievements(self, interaction: discord.Interaction):
        print(f"Achievements command invoked by {interaction.user}")
        await interaction.response.defer(ephemeral=True)  # 🔧 THIS IS THE FIX

        try:
            user_id = interaction.user.id
            achievements = await get_user_achievements(self.pool, user_id)
            print(f"Achievements fetched: {achievements}")

            if not achievements:
                await interaction.followup.send(
                    embed=embed_message(
                        "No Achievements Yet",
                        "You haven't unlocked any achievements yet. Keep playing!",
                        discord.Color.dark_grey()
                    )
                )
                return

            desc_lines = []
            for row in achievements:
                emoji = row.get('achievement_emoji', '🏆')
                name = row.get('achievement_name', 'Unknown Achievement')
                description = row.get('achievement_description', '')
                desc_lines.append(f"{emoji} **{name}** — {description}")

            embed = discord.Embed(
                title=f"🏆 Achievements for {interaction.user.display_name}",
                description="\n".join(desc_lines),
                color=discord.Color.gold()
            )
            await interaction.followup.send(embed=embed)

        except Exception:
            traceback.print_exc()
            await interaction.followup.send(
                "❌ An error occurred while fetching achievements."
            )

async def setup(bot: commands.Bot):
    print("Loading UserAchievements Cog...")
    if bot.get_cog("UserAchievements") is None:
        await bot.add_cog(UserAchievements(bot, bot.pool))
    print("UserAchievements Cog loaded.")
