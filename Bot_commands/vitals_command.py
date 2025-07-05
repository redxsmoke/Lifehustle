import discord
from discord.ext import commands
from datetime import datetime

def get_mock_weather(hour_utc):
    if 6 <= hour_utc < 12:
        return "Sunny", "☀️"
    elif 12 <= hour_utc < 15:
        return "Cloudy", "⛅"
    elif 15 <= hour_utc < 18:
        return "Rain", "🌧️"
    elif 18 <= hour_utc < 20:
        return "Snow", "❄️"
    else:
        return "Clear Night", "🌙"

async def get_user_checking_balance(user_id):
    # Replace this stub with your actual DB call
    return 12345

class Vitals(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="vitals")
    async def vitals_command(self, ctx):
        now_utc = datetime.utcnow()
        hour = now_utc.hour
        weather_desc, weather_emoji = get_mock_weather(hour)

        checking_balance = await get_user_checking_balance(ctx.author.id)

        time_emoji = "🌞" if 6 <= hour < 18 else "🌙"
        time_str = now_utc.strftime("%H:%M UTC")
        date_str = now_utc.strftime("%Y-%m-%d")

        embed = discord.Embed(title="🩺 Vitals", color=0x00ff00)
        embed.add_field(name="Time", value=f"{time_emoji} {time_str}", inline=True)
        embed.add_field(name="Date", value=f"📅 {date_str}", inline=True)
        embed.add_field(name="Cash on Hand", value=f"💰 ${checking_balance:,}", inline=False)
        embed.add_field(name="Weather", value=f"{weather_emoji} {weather_desc}", inline=False)

        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Vitals(bot))
