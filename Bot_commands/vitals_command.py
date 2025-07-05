import discord
from discord.ext import commands
from discord import app_commands
import datetime
import random

def c_to_f(c):
    return c * 9 / 5 + 32

def get_temp_range(month, weather_type):
    if month in [12,1,2]:  # Winter
        base_min, base_max = -10, 5
    elif month in [3,4,5]:  # Spring
        base_min, base_max = 5, 15
    elif month in [6,7,8]:  # Summer
        base_min, base_max = 15, 30
    elif month in [9,10,11]:  # Fall
        base_min, base_max = 5, 20
    else:
        base_min, base_max = 0, 20

    if weather_type == "Sunny":
        base_min += 5
        base_max += 7
    elif weather_type == "Cloudy":
        base_min -= 2
        base_max -= 1
    elif weather_type == "Rain":
        base_min -= 3
        base_max -= 3
    elif weather_type == "Snow":
        base_min -= 8
        base_max -= 5
    elif weather_type == "Clear Night":
        base_min -= 5
        base_max -= 5

    return base_min, base_max

def get_weather_for_date(date: datetime.date):
    month = date.month
    base_weathers = ["Sunny", "Cloudy", "Rain"]
    if month in [11, 12, 1, 2]:
        base_weathers.append("Snow")
    night_weather_desc = "Clear Night"
    night_weather_emoji = "🌙"

    seed = int(date.strftime("%Y%m%d"))
    rnd = random.Random(seed)

    def pick_weather():
        w = rnd.choice(base_weathers)
        emoji_map = {
            "Sunny": "☀️",
            "Cloudy": "⛅",
            "Rain": "🌧️",
            "Snow": "❄️"
        }
        base_min, base_max = get_temp_range(month, w)
        temp_c = rnd.uniform(base_min, base_max)
        temp_f = c_to_f(temp_c)
        return (w, emoji_map[w], round(temp_c,1), round(temp_f,1))

    morning = pick_weather()
    afternoon = pick_weather()

    night_base_min, night_base_max = get_temp_range(month, night_weather_desc)
    night_temp_c = (night_base_min + night_base_max) / 2 - 2
    night_temp_f = c_to_f(night_temp_c)
    night = (night_weather_desc, night_weather_emoji, round(night_temp_c,1), round(night_temp_f,1))

    return morning, afternoon, night

def get_mock_weather_dynamic(now=None):
    if now is None:
        now = datetime.datetime.utcnow()

    morning, afternoon, night = get_weather_for_date(now.date())

    hour = now.hour
    if 0 <= hour < 6:
        return night
    elif 6 <= hour < 12:
        return morning
    elif 12 <= hour < 18:
        return afternoon
    else:
        return night

async def get_user_checking_balance(user_id):
    # Replace with your DB call; placeholder for now
    return 12345

class Vitals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="vitals", description="Show your vitals including weather and balance")
    async def vitals(self, interaction: discord.Interaction):
        now_utc = datetime.datetime.utcnow()
        hour = now_utc.hour
        time_emoji = "🌞" if 6 <= hour < 18 else "🌙"
        time_str = now_utc.strftime("%H:%M UTC")
        date_str = now_utc.strftime("%Y-%m-%d")

        weather_desc, weather_emoji, temp_c, temp_f = get_mock_weather_dynamic(now_utc)
        checking_balance = await get_user_checking_balance(interaction.user.id)

        embed = discord.Embed(title="🩺 Vitals", color=0x00ff00)
        embed.add_field(name="Time", value=f"{time_emoji} {time_str}", inline=True)
        embed.add_field(name="Date", value=f"📅 {date_str}", inline=True)
        embed.add_field(name="Cash on Hand", value=f"💰 ${checking_balance:,}", inline=False)
        embed.add_field(name="Weather", value=f"{weather_emoji} {weather_desc} | {temp_f}°F / {temp_c}°C", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def register_commands(tree: app_commands.CommandTree):
    bot = tree._bot
    vitals_cog = Vitals(bot)
    bot.add_cog(vitals_cog)
    tree.add_command(vitals_cog.vitals)
