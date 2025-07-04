import asyncio
import datetime
import json
import random
import string
import discord
import unicodedata
import globals

from discord import app_commands, Interaction
from db_user import get_user, upsert_user, get_user_finances
from utilities import (
    charge_user,
    update_vehicle_condition_and_description,
    reward_user
)
from vehicle_logic import get_user_vehicles
from embeds import embed_message, COLOR_GREEN

def condition_from_usage(travel_count: int) -> str:
    if travel_count < 50:
        return "Brand New"
    elif travel_count < 100:
        return "Good Condition"
    elif travel_count < 150:
        return "Fair Condition"
    elif travel_count < 200:
        return "Poor Condition"
    else:
        return "Broken Down"

def register_commands(tree: app_commands.CommandTree):
    @tree.command(name="travel", description="Travel to work using buttons")
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

        from views import TravelButtons
        view = TravelButtons()
        await interaction.response.defer(ephemeral=True)
        msg = await interaction.followup.send(
            embed=embed_message(
                "🚗 Travel",
                "> Choose your travel method:",
                discord.Color.blue()
            ),
            view=view,
            ephemeral=True
        )
        view.message = msg

async def handle_travel(interaction: Interaction, method: str):
    pool = globals.pool
    user_id = interaction.user.id
    user = await get_user_F(pool, user_id)

    if user is None:
        await interaction.followup.send(
            embed=embed_message(
                "❌ **No Account Found**",
                "> Uh-oh! You don’t have an account yet. Try `/start` and join the cool kids club!",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    finances = await get_user_finances(pool, user_id)
    if finances is None:
        finances = {
            "checking_account_balance": 0,
            "savings_account_balance": 0,
            "debt_balance": 0,
            "last_paycheck_claimed": datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)
        }

    vehicles = await get_user_vehicles(pool, user_id)
    working_vehicles = [v for v in vehicles if v.get("condition") != "Broken Down"]

    if method == 'drive':
        cars = [v for v in working_vehicles if v.get("vehicle_type") in (
            "Beater Car", "Sedan", "Sports Car", "Pickup Truck", "Motorcycle"
        )]
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
        vehicle = cars[0]
        print("VEHICLE DEBUG:", vehicle.keys(), vehicle)

        vehicle_type_id = vehicle.get("vehicle_type_id")
        if vehicle_type_id is None:
            raise ValueError(f"Missing vehicle_type_id in vehicle: {vehicle}")

        cost = 10
        if finances.get("checking_account_balance", 0) < cost:
            await interaction.followup.send(
                embed=embed_message(
                    "⛽ Empty Tank!",
                    f"> You tried to drive your **{vehicle['vehicle_type']}**, but your wallet is emptier than the gas tank! Need ${cost} for gas, but you only have ${finances.get('checking_account_balance', 0)}.",
                    discord.Color.red()
                ),
                ephemeral=True
            )
            return

        await charge_user(pool, user_id, cost)
        new_travel_count = vehicle.get("travel_count", 0) + 1
        await update_vehicle_condition_and_description(
            pool,
            user_id,
            vehicle["id"],
            vehicle_type_id,
            new_travel_count
        )

        updated_user = await get_user(pool, user_id)
        updated_finances = await get_user_finances(pool, user_id)
        updated_balance = updated_finances.get("checking_account_balance", 0)

        await interaction.followup.send(
            embed=embed_message(
                "🚗 Drive Travel",
                f"> You drove your **{vehicle['vehicle_type']}**! Total travels: **{new_travel_count}**.\n"
                f"> Your updated balance is: **${updated_balance}**.",
                COLOR_GREEN
            ),
            ephemeral=True
        )

    elif method == 'bike':
        bikes = [v for v in working_vehicles if v.get("vehicle_type") == "Bike"]
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
        vehicle = bikes[0]
        print("VEHICLE DEBUG:", vehicle.keys(), vehicle)

        vehicle_type_id = vehicle.get("vehicle_type_id")
        if vehicle_type_id is None:
            raise ValueError(f"Missing vehicle_type_id in vehicle: {vehicle}")

        new_travel_count = vehicle.get("travel_count", 0) + 1
        await update_vehicle_condition_and_description(
            pool,
            user_id,
            vehicle["id"],
            vehicle_type_id,
            new_travel_count
        )
        await reward_user(pool, user_id, 10)

        updated_user = await get_user(pool, user_id)
        updated_finances = await get_user_finances(pool, user_id)
        updated_balance = updated_finances.get("checking_account_balance", 0)

        await interaction.followup.send(
            embed=embed_message(
                "🚴 Bike Travel",
                f"> You biked on your **Bike**! Total travels: **{new_travel_count}**.\n"
                f"> Your updated balance is: **${updated_balance}**. +$10 biking bonus!",
                COLOR_GREEN
            ),
            ephemeral=True
        )

    elif method in ('subway', 'bus'):
        cost = 10 if method == 'subway' else 5

        if finances.get("checking_account_balance", 0) < cost:
            await interaction.followup.send(
                embed=embed_message(
                    "❌ Insufficient Funds",
                    f"> Yikes! You need ${cost} to ride the {method}, but your wallet says only ${finances.get('checking_account_balance', 0)}. Maybe find some couch change?",
                    discord.Color.red()
                ),
                ephemeral=True
            )
            return

        await charge_user(pool, user_id, cost)
        updated_finances = await get_user_finances(pool, user_id)
        updated_balance = updated_finances.get("checking_account_balance", 0)
        await interaction.followup.send(
            embed=embed_message(
                f"{'🚇' if method == 'subway' else '🚌'} Travel Summary",
                f"> You traveled by **{method.title()}** for ${cost}.\n"
                f"> Your updated balance is: **${updated_balance}**.",
                COLOR_GREEN
            ),
            ephemeral=True
        )

    else:
        await interaction.followup.send(
            embed=embed_message(
                "❌ Invalid Travel Method",
                "> Are you hacking us?! How did you select this as a travel option 🤔? Pick one of: drive, bike, subway, or bus.",
                discord.Color.red()
            ),
            ephemeral=True
        )
