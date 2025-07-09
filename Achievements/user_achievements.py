import discord
from discord.ext import commands
from discord import app_commands
import random
import datetime

NOTHING_MESSAGES = [
    "Nothing happened.",
    "You feel... slightly warmer?",
    "Still waiting.",
    "A breeze passes. Coincidence?",
    "You hear a faint hum... or not.",
    "The button clicks. That’s all.",
    "Something definitely didn’t happen.",
    "The void remains silent.",
    "You think you saw a flicker. Nope.",
    "Reality stays the same."
]

COOLDOWN_SECONDS = 3  # 1 hour = 3600 seconds (adjust as needed)
REWARD_AMOUNT = 500_000
PRESS_GOAL = 1000

class ButtonGameView(discord.ui.View):
    def __init__(self, user_id, db):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.db = db

    @discord.ui.button(label="Press", style=discord.ButtonStyle.primary, emoji="🔴")
    async def press_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn’t your button to press.", ephemeral=True)
                return

            async with self.db.acquire() as conn:
                record = await conn.fetchrow(
                    "SELECT times_pressed, last_used FROM user_secret_button WHERE user_id = $1",
                    self.user_id
                )

                now = datetime.datetime.utcnow()

                if record:
                    last_used = record['last_used']
                    times_pressed = record['times_pressed']

                    # If user already reached or passed the goal, stop updates and inform
                    if times_pressed >= PRESS_GOAL:
                        await interaction.response.send_message(
                            f"🏅 You already unlocked the **Master of Perseverance** achievement! No need to press more.",
                            ephemeral=True
                        )
                        return

                    if last_used and (now - last_used).total_seconds() < COOLDOWN_SECONDS:
                        remaining = COOLDOWN_SECONDS - (now - last_used).total_seconds()
                        minutes = int(remaining // 60)
                        seconds = int(remaining % 60)
                        await interaction.response.send_message(
                            f"🕒 You must wait {minutes}m {seconds}s before pressing again.",
                            ephemeral=True
                        )
                        return
                else:
                    await conn.execute(
                        "INSERT INTO user_secret_button (user_id, times_pressed, last_used) VALUES ($1, 0, $2)",
                        self.user_id, now
                    )
                    times_pressed = 0

                times_pressed += 1

                await conn.execute(
                    "UPDATE user_secret_button SET times_pressed = $1, last_used = $2 WHERE user_id = $3",
                    times_pressed, now, self.user_id
                )

                if times_pressed >= PRESS_GOAL:
                    # Reward user
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        REWARD_AMOUNT, self.user_id
                    )

                    # Insert achievement if not already unlocked
                    # Use ON CONFLICT DO NOTHING to avoid duplicates
                    await conn.execute("""
                        INSERT INTO cd_user_achievements 
                        (user_id, achievement_id, achievement_name, achievement_description, achievement_emoji, date_unlocked, guild_id)
                        VALUES ($1, $2, $3, $4, $5, $6, $7)
                        ON CONFLICT (user_id, achievement_id) DO NOTHING;
                    """,
                    self.user_id,
                    1,
                    'Master of Perseverance',
                    'Clicked the button 1000 times',
                    '🏅⏳💪',
                    now,
                    interaction.guild.id if interaction.guild else None
                    )

                    await interaction.response.edit_message(
                        embed=discord.Embed(
                            title="🌟 Something *Finally* Happened!",
                            description=(
                                f"You've pressed the button **{PRESS_GOAL} times**.\n\n"
                                f"💰 **${REWARD_AMOUNT:,}** has been added to your account.\n\n"
                                "🏅⏳💪 **Master of Perseverance** unlocked!\n"
                                "You will now get **twice as much** when running the `/needfunds` command."
                            ),
                            color=discord.Color.gold()
                        ),
                        view=None
                    )
                else:
                    message = random.choice(NOTHING_MESSAGES)
                    await interaction.response.edit_message(
                        embed=discord.Embed(
                            title="You pressed the button.",
                            description=message,
                            color=discord.Color.red()
                        ),
                        view=self
                    )
        except Exception as e:
            print(f"Error in button press callback: {e}")
            try:
                await interaction.response.send_message(f"An error occurred: {e}", ephemeral=True)
            except Exception:
                pass  # fail silently if can't respond


class ButtonGame(commands.Cog):
    def __init__(self, bot, db):
        self.bot = bot
        self.db = db

    @app_commands.command(name="button", description="Just a button. Totally normal.")
    async def button(self, interaction: discord.Interaction):
        view = ButtonGameView(user_id=interaction.user.id, db=self.db)
        await interaction.response.send_message(
            embed=discord.Embed(
                title="Mystery Button",
                description="Press it. Or don't.",
                color=discord.Color.dark_gray()
            ),
            view=view,
            ephemeral=True
        )


async def setup(bot):
    await bot.add_cog(ButtonGame(bot, bot.pool))
