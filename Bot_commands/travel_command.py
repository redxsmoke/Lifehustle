import asyncio
import json
import random
import string
import discord
import unicodedata
import globals
import datetime

from embeds import COLOR_GREEN, COLOR_RED
from discord import app_commands, Interaction
from discord.ext import commands
from db_user import get_user, upsert_user, get_user_finances, fetch_vehicle_with_pricing, update_last_used_vehicle
from vehicle_logic import ConfirmSellView, sell_all_vehicles
from .lifecheck_command import get_mock_weather_dynamic
from Travel_commands.Repair_options import RepairOptionsView


from utilities import (
    charge_user,
    update_vehicle_condition_and_description,
    reward_user
)
from vehicle_logic import get_user_vehicles
from embeds import embed_message, COLOR_GREEN
from views import select_weighted_travel_outcome, VehicleUseView, TravelButtons

user_travel_location = {}
HOME_LOCATION_ID = 3

def condition_from_usage(travel_count: int, breakdown_threshold: int = 200) -> str:
    if 0 <= travel_count < 50:
        return "Brand New"
    elif travel_count < 100:
        return "Good Condition"
    elif travel_count < 150:
        return "Fair Condition"
    elif travel_count < breakdown_threshold:
        return "Poor Condition"
    else:
        return "Broken Down"

class LocationSelect(discord.ui.Select):
    def __init__(self, locations, user_id, pool):
        self.user_id = user_id
        self.pool = pool
        self.locations = locations
        self.selected_location_id = None
        options = [
            discord.SelectOption(
                label=loc["location_name"],
                description=loc["location_description"] or None,
                value=str(loc["cd_location_id"])
            )
            for loc in locations
        ]
        super().__init__(placeholder="Where to?", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        try:
            self.selected_location_id = int(self.values[0])
            selected_location = next(
                loc for loc in self.locations if int(loc["cd_location_id"]) == self.selected_location_id
            )

            user_travel_location[self.user_id] = {
                "cd_location_id": self.selected_location_id,
                "location_name": selected_location["location_name"]
            }

            view = TravelButtons(user_id=self.user_id, user_travel_location=self.selected_location_id)

            await interaction.response.send_message(
                embed=embed_message(
                    "🧭 Choose Travel Method",
                    f"You're heading to **{selected_location['location_name']}**.\nHow would you like to get there?",
                    discord.Color.blurple()
                ),
                view=view,
                ephemeral=True
            )
        except Exception as e:
            print(f"[ERROR] Exception in LocationSelect callback: {e}")
            import traceback
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message("❌ Something went wrong. Try again.", ephemeral=True)






class LocationTravelView(discord.ui.View):
    def __init__(self, locations, user_id, pool):
        super().__init__(timeout=60)
        self.add_item(LocationSelect(locations, user_id, pool))


def register_commands(tree: app_commands.CommandTree):
    @tree.command(name="travel", description="Travel to a different location")
    async def travel(interaction: Interaction):
        pool = globals.pool
        if pool is None:
            await interaction.response.send_message(
                "⚠️ The database isn’t ready yet. Try again in a moment.", ephemeral=True
            )
            return

        user_id = interaction.user.id
        user = await get_user(pool, user_id)
        if not user:
            await interaction.response.send_message(
                embed=embed_message(
                    "❌ No Account", "Use `/start` to create an account.", discord.Color.red()
                ),
                ephemeral=True
            )
            return

        current_location = user.get("current_location")
        print(f"[DEBUG] current_location (type {type(current_location)}): {current_location}")

        results = await pool.fetch(
            """
            SELECT cd_location_id, location_name, location_description
            FROM cd_locations
            WHERE active = true AND cd_location_id != $1
            """,
            current_location,
        )

        print(f"[DEBUG] Found {len(results)} locations available for travel.")
        if not results:
            await interaction.response.send_message(
                embed=embed_message("⛔ Nowhere to Go", "You're already at the only active location.", COLOR_RED),
                ephemeral=True
            )
            return

        for loc in results:
            print(f"[DEBUG] Location: {loc['location_name']} (ID: {loc['cd_location_id']})")


        view = LocationTravelView(results, user_id, pool)
        await interaction.response.send_message(
            embed=embed_message(
                "🌍 Where to?",
                "Pick a destination from the list below.",
                discord.Color.blue()
            ),
            view=view,
            ephemeral=True
        )

async def show_vehicle_selection(interaction, user_id, vehicles, method, user_travel_location, previous_location):
    print(f"[DEBUG] show_vehicle_selection called with method={method} and {len(vehicles)} vehicles")
    pool = globals.pool
    user = await get_user(pool, user_id)
    current_location = user.get("current_location")
    current_vehicle_id = user.get("current_vehicle_id")
    

    restricted = False
    filtered_vehicles = vehicles

    
    # ENFORCE VEHICLE LOCK REGARDLESS OF METHOD
    if current_location != HOME_LOCATION_ID and current_vehicle_id:
        filtered_vehicles = [v for v in vehicles if v["id"] == current_vehicle_id]
        restricted = True

    view = await VehicleUseView.create(user_id, filtered_vehicles, method, user_travel_location, previous_location)

    description = (
        "> You have multiple vehicles. Please choose one to travel with:"
    )

    if restricted:
        description = (
            "> Since you're away from home, you can only travel using the vehicle you left with.\n"
            "> To switch vehicles, return 🏠 home first."
        )

    embed = embed_message(
        f"🚗 Your {method.title()}s",
        description,
        discord.Color.blue() if method == 'car' else discord.Color.green()
    )

    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


async def handle_travel(interaction: Interaction, method: str, user_travel_location: int):
    pool = globals.pool
    user_id = interaction.user.id

    user = await get_user(pool, user_id)
    current_location = user.get("current_location")
    current_vehicle_id = user.get("current_vehicle_id")
    previous_location = current_location  

    vehicles = await get_user_vehicles(pool, user_id)
    working_vehicles = [v for v in vehicles if v.get("condition") != "Broken Down"]

    print(f"[DEBUG] Total vehicles: {len(vehicles)}")
    print(f"[DEBUG] Working vehicles: {len(working_vehicles)}")
    print(f"[DEBUG] Current location: {current_location}, Current vehicle ID: {current_vehicle_id}")

    # 🚫 Enforce same vehicle usage if away from home
    last_used_vehicle = user.get("last_used_vehicle")

    if current_location != HOME_LOCATION_ID and last_used_vehicle and method in ['car', 'bike']:
        allowed_vehicle = next((v for v in working_vehicles if v["id"] == last_used_vehicle), None)
        if not allowed_vehicle:
            print("[DEBUG] User trying to use a vehicle not allowed away from home")
            await interaction.response.send_message(
                embed=embed_message(
                    "🚫 Wrong Vehicle",
                    "> You're currently away from home using a different vehicle. You must return 🏠 home before switching.",
                    COLOR_RED
                ),
                ephemeral=True
            )
            return
        else:
            print(f"[DEBUG] Allowed vehicle found: {allowed_vehicle.get('plate_number', 'N/A')}")

    if method == 'car':
        cars = [v for v in working_vehicles if v.get("class_type") == "car"]
        print(f"[DEBUG] Cars available for travel: {len(cars)}")

        if not cars:
            await interaction.followup.send(
                embed=embed_message(
                    "❌🔧 **No Available Vehicle**",
                    "> Looks like your cars are on vacation or broken down. No joyrides today!",
                    discord.Color.red()
                ),
                ephemeral=True
            )
            return

        if len(cars) == 1:
            print("[DEBUG] Exactly one car available, proceeding to travel")
            await handle_travel_with_vehicle(interaction, cars[0], method, user_travel_location, previous_location)
        else:
            print("[DEBUG] Multiple cars available, prompting user to select")
            await show_vehicle_selection(interaction, user_id, cars, method, user_travel_location, previous_location)
        return

    elif method == 'bike':
        bikes = [v for v in working_vehicles if v.get("class_type") == "bike"]
        print(f"[DEBUG] Bikes available for travel: {len(bikes)}")

        if not bikes:
            await interaction.followup.send(
                embed=embed_message(
                    "❌🔧 **No Available Vehicle**",
                    "> No bike? No fun! Get one or fix that broken two-wheeler first.",
                    discord.Color.red()
                ),
                ephemeral=True
            )
            return

        if len(bikes) == 1:
            print("[DEBUG] Exactly one bike available, proceeding to travel")
            await handle_travel_with_vehicle(interaction, bikes[0], method, user_travel_location, previous_location)   

        else:
            print("[DEBUG] Multiple bikes available, prompting user to select")
            await show_vehicle_selection(interaction, user_id, bikes, method, user_travel_location, previous_location)
        return

    elif method in ['subway', 'bus']:
        cost = 10 if method == 'subway' else 5
        finances = await get_user_finances(pool, user_id)
        print(f"[DEBUG] User finances: {finances.get('checking_account_balance', 0)}")
        if finances.get("checking_account_balance", 0) < cost:
            await interaction.followup.send(
                embed=embed_message(
                    "❌ Insufficient Funds",
                    f"> You need ${cost} to travel by {method}, but your balance is ${finances.get('checking_account_balance', 0)}.",
                    discord.Color.red()
                ),
                ephemeral=True
            )
            return

        await charge_user(pool, user_id, cost)

        outcome = await select_weighted_travel_outcome(pool, method)
        updated_finances = await get_user_finances(pool, user_id)
        updated_balance = updated_finances.get("checking_account_balance", 0)

        old_location_id = user.get("current_location")
        old_loc = await pool.fetchrow("SELECT location_name FROM cd_locations WHERE cd_location_id = $1", old_location_id)
        old_location_name = old_loc["location_name"] if old_loc else f"Location {old_location_id}"

        new_loc = await pool.fetchrow("SELECT location_name FROM cd_locations WHERE cd_location_id = $1", user_travel_location)
        new_location_name = new_loc["location_name"] if new_loc else f"Location {user_travel_location}"

        embed_text = (
            f"> You traveled from **{old_location_name}** to **{new_location_name}** by **{method.title()}** for ${cost}.\n"
            f"> Your updated balance is: **${updated_balance}**."
        )

        if outcome:
            desc = outcome.get("description", "")
            effect = outcome.get("effect_amount", 0)

            if effect < 0 and updated_balance >= -effect:
                await charge_user(pool, user_id, -effect)
                updated_balance -= -effect
            elif effect > 0:
                await reward_user(pool, user_id, effect)
                updated_balance += effect

            embed_text += f"\n\n🎲 Outcome: {desc}\n💰 Balance Impact +/-: ${effect}"

        # Determine vehicle_id_used for car/bike; for subway/bus this is None
        vehicle_id_used = None
        if method in ['car', 'bike']:
            vehicle_id_used = last_used_vehicle or current_vehicle_id

      
        if previous_location == HOME_LOCATION_ID and user_travel_location != HOME_LOCATION_ID and vehicle_id_used:
            print(f"[DEBUG] Leaving home: setting last_used_vehicle to {vehicle_id_used}")
            await pool.execute(
                "UPDATE users SET last_used_vehicle = $1 WHERE user_id = $2",
                vehicle_id_used,
                user_id
            )
        elif user_travel_location == HOME_LOCATION_ID:
            print("[DEBUG] Returning home: clearing last_used_vehicle")
            await pool.execute(
                "UPDATE users SET last_used_vehicle = NULL WHERE user_id = $1",
                user_id
            )


        location_id = user_travel_location if isinstance(user_travel_location, int) else user_travel_location.get("cd_location_id")

        await pool.execute(
            "UPDATE users SET current_location = $1 WHERE user_id = $2",
            location_id,
            user_id
        )

        user_after_update = await get_user(pool, user_id)
        print(f"[DEBUG] After UPDATE, current_location in DB: {user_after_update.get('current_location')}")

        await interaction.followup.send(
            embed=embed_message(
                f"{'🚇' if method == 'subway' else '🚌'} Travel Summary",
                embed_text,
                COLOR_GREEN
            ),
            ephemeral=False
        )
        return

    else:
        await interaction.followup.send(
            embed=embed_message(
                "❌ Invalid Travel Method",
                "> Are you hacking us?! How did you select this as a travel option 🤔? Pick one of these: drive, bike, subway, or bus.",
                discord.Color.red()
            ),
            ephemeral=True
        )

async def handle_travel_with_vehicle(interaction, vehicle, method, user_travel_location, previous_location):

    pool = globals.pool
    user_id = interaction.user.id

    cost = 10 if method == "car" else -10 if method == "bike" else 0
    finances = await get_user_finances(pool, user_id)

    if finances.get("checking_account_balance", 0) < cost:
        await interaction.followup.send(
            embed=embed_message(
                "❌ Insufficient Funds",
                f"> You need ${cost} to {method} your {vehicle.get('vehicle_type', 'vehicle')}, but your balance is ${finances.get('checking_account_balance', 0)}.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    await charge_user(pool, user_id, cost)
    current_balance = finances.get("checking_account_balance", 0) - cost
    
    vehicle_status = "stored" if user_travel_location == 3 else "in use"

    outcome = await select_weighted_travel_outcome(pool, method)
    outcome_desc = "No special events today."
    effect = 0

    if outcome:
        effect = outcome.get("effect_amount", 0)
        outcome_desc = outcome.get("description", "")
        if effect < 0 and current_balance >= -effect:
            await charge_user(pool, user_id, -effect)
            current_balance -= -effect
        elif effect > 0:
            await reward_user(pool, user_id, effect)
            current_balance += effect

    async with pool.acquire() as conn:
        updated_vehicle = await conn.fetchrow(
            """
            UPDATE user_vehicle_inventory
            SET travel_count = travel_count + 1
            WHERE user_id = $1 AND plate_number = $2
            RETURNING id, travel_count, vehicle_type_id, breakdown_threshold, condition_id
            """,
            user_id, vehicle.get("plate_number")
        )

    if updated_vehicle:
        updated_info = await update_vehicle_condition_and_description(
            pool,
            user_id,
            updated_vehicle["id"],
            updated_vehicle["vehicle_type_id"],
            updated_vehicle["travel_count"],
            updated_vehicle["breakdown_threshold"],
            interaction=interaction
        )

        if updated_info["condition"] == "Broken Down":
            vehicle_full = await fetch_vehicle_with_pricing(globals.pool, user_id, updated_vehicle["id"])
            view = RepairOptionsView(globals.pool, vehicle_full, user_id)

            msg = await interaction.followup.send(
                embed=embed_message(
                    "🚨 Vehicle Broken Down",
                    "Your vehicle is broken down and can't be used for travel. Please repair it first.\n\nChoose a repair option below:",
                    COLOR_RED
                ),
                view=view,
                ephemeral=True
            )
            view.message = msg
            return  # stop travel here

        travel_count = updated_info["travel_count"]
        condition_str = updated_info["condition"]
        appearance_desc = updated_info["description"]
    else:
        travel_count = vehicle.get("travel_count", 0) + 1
        condition_str = vehicle.get("condition", "Unknown")
        appearance_desc = vehicle.get("appearance_description", "No description available.")

    user = await get_user(pool, user_id)
    old_location_id = user.get("current_location")
    print(f"[DEBUG] user_travel_location: {user_travel_location} (type: {type(user_travel_location)})")
    print(f"[DEBUG] user_id: {user_id} (type: {type(user_id)})")

    location_id = user_travel_location

    await pool.execute(
        "UPDATE users SET current_location = $1 WHERE user_id = $2",
        location_id,
        user_id
    )

    user_after_update = await get_user(pool, user_id)
    print(f"[DEBUG] After UPDATE, current_location in DB: {user_after_update.get('current_location')}")
    print(f"[DEBUG] previous_location (type {type(previous_location)}): {previous_location}")
    print(f"[DEBUG] location_id (type {type(location_id)}): {location_id}")
    print(f"[DEBUG] HOME_LOCATION_ID (type {type(HOME_LOCATION_ID)}): {HOME_LOCATION_ID}")

    # ======= HERE IS THE NEW FIXED PART: CALL update_last_used_vehicle =======
    if previous_location == HOME_LOCATION_ID and location_id != HOME_LOCATION_ID:
        await update_last_used_vehicle(pool, user_id, vehicle["id"], vehicle_status, location_id)
    elif location_id == HOME_LOCATION_ID:
        await update_last_used_vehicle(pool, user_id, None, None, location_id)

    # ==========================================================================

    old_loc = await pool.fetchrow("SELECT location_name FROM cd_locations WHERE cd_location_id = $1", old_location_id)
    old_location_name = old_loc["location_name"] if old_loc else f"Location {old_location_id}"

    new_loc = await pool.fetchrow("SELECT location_name FROM cd_locations WHERE cd_location_id = $1", user_travel_location)
    new_location_name = new_loc["location_name"] if new_loc else f"Location {user_travel_location}"

    embed = discord.Embed(
        title=f"{'🚗' if method == 'car' else '🚴'} Travel Summary",
        description=(
            f"You traveled **from `{old_location_name}` to `{new_location_name}`** using your "
            f"{vehicle.get('vehicle_type', 'vehicle')} (Color: {vehicle.get('color', 'Unknown')}, "
            f"Plate: {vehicle.get('plate_number', 'N/A')}).\n"
            f"- Travel Count: {travel_count}\n"
            f"- Condition: {condition_str}\n"
            f"- Appearance: {appearance_desc}\n\n"
            f"🎲 Outcome: {outcome_desc}\n"
            f"💰 Balance Impact +/-: ${effect}\n\n"
            f"Your current balance is: ${current_balance:,}."
        ),
        color=COLOR_GREEN
    )

    await interaction.followup.send(embed=embed, ephemeral=False)



async def on_sell_all_button_click(interaction: discord.Interaction, user_id, vehicles):
    confirm_view = ConfirmSellView(user_id, vehicles)
    await interaction.response.send_message(
        "Are you sure you want to **sell all your vehicles**? This action cannot be undone.",
        view=confirm_view,
        ephemeral=True
    )

    await confirm_view.wait()

    if confirm_view.value is None:
        await interaction.followup.send("⏳ Sale confirmation timed out.", ephemeral=True)
    elif confirm_view.value:
        await sell_all_vehicles(interaction, user_id, vehicles)

class Travel(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="bike_travel")
    async def bike_travel_command(self, ctx):
        now_utc = datetime.datetime.utcnow()
        weather_desc, weather_emoji, temp_c, temp_f = get_mock_weather_dynamic(now_utc)

        if weather_desc in ["Rain", "Snow"]:
            embed = discord.Embed(
                title="🚴‍♂️ Bike Travel Denied!",
                description=(
                    "> Whoa there! Trying to bike in this weather? "
                    "> Unless you want a soggy helmet or a snowman as a travel buddy, better wait it out! 🌧️❄️🚴‍♂️"
                ),
                color=COLOR_RED,
            )
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(
            title="🚴‍♂️ Bike Travel",
            description="> You hop on your bike and enjoy a smooth ride! 🚲💨",
            color=COLOR_GREEN,
        )
        await ctx.send(embed=embed)

def setup(bot):
    bot.add_cog(Travel(bot))
#