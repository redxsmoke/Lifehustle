import discord
from discord.ext import commands
import datetime
import random
import globals  # your global DB pool


# Helper functions you already have (keep these as is)
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

async def get_user_checking_account_balance(user_id):
    query = """
    SELECT checking_account_balance 
    FROM user_finances
    WHERE user_id = $1
    """
    pool = globals.pool
    async with pool.acquire() as connection:
        result = await connection.fetchrow(query, user_id)
    if result and result['checking_account_balance'] is not None:
        return result['checking_account_balance']
    return 0

# Updated lifecheck command with shifts worked logic
async def register_commands(bot: discord.Client):
    @bot.tree.command(name="lifecheck", description="Monitor your wellbeing, work shifts, and weather all in one place.")
    async def lifecheck_command(interaction: discord.Interaction):
        now_utc = datetime.datetime.utcnow()
        hour = now_utc.hour
        time_emoji = "☀️" if 6 <= hour < 18 else "🌙"
        time_str = now_utc.strftime("%H:%M UTC")
        date_str = now_utc.strftime("%A, %B %d, %Y")

        weather_desc, weather_emoji, temp_c, temp_f = get_mock_weather_dynamic(now_utc)
        checking_account_balance = await get_user_checking_account_balance(interaction.user.id)

        pool = globals.pool
        async with pool.acquire() as conn:
            # Get occupation and shift info
            user_job = await conn.fetchrow('''
                SELECT u.occupation_id, o.required_shifts_per_day, o.description AS job_title
                FROM users u
                LEFT JOIN cd_occupations o ON u.occupation_id = o.cd_occupation_id
                WHERE u.user_id = $1
            ''', interaction.user.id)

            shifts_worked = 0
            required_shifts = 0
            occupation_name = "Unemployed"

            if user_job and user_job['occupation_id']:
                required_shifts = user_job['required_shifts_per_day'] or 0
                occupation_name = user_job['job_title'] or "Unknown"

                shifts_worked = await conn.fetchval('''
                    SELECT COUNT(*)
                    FROM user_work_log
                    WHERE user_id = $1
                    AND work_timestamp >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
                ''', interaction.user.id)
                shifts_worked = shifts_worked or 0

            # ✅ Current Location
            location_name = await conn.fetchval('''
                SELECT cl.location_name
                FROM users u
                LEFT JOIN cd_locations cl ON u.current_location = cl.cd_location_id
                WHERE u.user_id = $1
            ''', interaction.user.id)
            location_name = location_name or "Unknown"

            # ✅ Current Vehicle
            vehicle_result = await conn.fetchrow('''
                SELECT vt.name AS vehicle_name, uvi.color, uvi.plate_number
                FROM user_vehicle_inventory uvi
                JOIN cd_vehicle_type vt ON vt.id = uvi.vehicle_type_id
                WHERE uvi.user_id = $1 AND uvi.vehicle_status = 'in use'
                LIMIT 1
            ''', interaction.user.id)

            if vehicle_result:
                vehicle_str = f"{vehicle_result['color']} {vehicle_result['vehicle_name']} (Plate: `{vehicle_result['plate_number']}`)"
            else:
                vehicle_str = "None assigned"

        # ✅ Build Embed
        embed = discord.Embed(
            title="⚕️ Lifecheck Overview",
            description=f"> Current Lifecheck and weather report, {interaction.user.display_name}!",
            color=0x1abc9c,
            timestamp=now_utc
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        info_text = (
            f"Time:             {time_emoji} {time_str}\n"
            f"Date:             {date_str}\n"
            f"Weather:          {weather_emoji} {weather_desc} | {temp_f}°F | {temp_c}°C\n\n"
            f"Current Location: {location_name}\n"
            f"Current Vehicle:  {vehicle_str}\n\n"
            f"Occupation:       {occupation_name}\n"
        )

        if occupation_name == "Unemployed":
            info_text += "Shifts Worked:    Unemployed\n\n"
        else:
            info_text += f"Shifts Worked:    {shifts_worked} / {required_shifts}\n\n"

        info_text += f"Cash on Hand:     ${checking_account_balance:,}\n"

        embed.add_field(name="Overview", value=f"```ansi\n{info_text}```", inline=False)

        embed.set_footer(text="LifeHustle Bot | Stay healthy and safe!")
        await interaction.response.send_message(embed=embed)
