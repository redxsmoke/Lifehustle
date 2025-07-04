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
from views import select_weighted_travel_outcome, TravelVehicleSelectView

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

        if len(cars) == 1:
            # auto use the only car
            await continue_travel_with_vehicle(interaction, method, cars[0])
        else:
            # ask user to select car
            view = TravelVehicleSelectView(cars, method)
            await interaction.response.send_message(
                embed=embed_message(
                    "🚗 Select Car",
                    "You own multiple cars. Please select which one to use for travel.",
                    discord.Color.blue()
                ),
                view=view,
                ephemeral=True
            )
            return

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

        if len(bikes) == 1:
            # auto use the only bike
            await continue_travel_with_vehicle(interaction, method, bikes[0])
        else:
            # ask user to select bike
            view = TravelVehicleSelectView(bikes, method)
            await interaction.response.send_message(
                embed=embed_message(
                    "🚴 Select Bike",
                    "You own multiple bikes. Please select which one to use for travel.",
                    discord.Color.blue()
                ),
                view=view,
                ephemeral=True
            )
        return

    elif method in ('subway', 'bus'):
        cost = 10 if method == 'subway' else 5
        finances = await get_user_finances(pool, user_id)

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

        # --- NEW CODE: select outcome and apply effect ---
        outcome = await select_weighted_travel_outcome(pool, method)

        updated_finances = await get_user_finances(pool, user_id)
        updated_balance = updated_finances.get("checking_account_balance", 0)

        embed_text = (
            f"> You traveled by **{method.title()}** for ${cost}.\n"
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

            embed_text += f"\n\n🎲 Outcome: {desc}\n💰 Effect on balance: ${effect}"

        await interaction.followup.send(
            embed=embed_message(
                f"{'🚇' if method == 'subway' else '🚌'} Travel Summary",
                embed_text,
                COLOR_GREEN
            ),
            ephemeral=True
        )
        return

    else:
        await interaction.followup.send(
            embed=embed_message(
                "❌ Invalid Travel Method",
                "> Are you hacking us?! How did you select this as a travel option 🤔? Pick one of: drive, bike, subway, or bus.",
                discord.Color.red()
            ),
            ephemeral=True
        )

async def continue_travel_with_vehicle(interaction: Interaction, method: str, vehicle: dict):
    pool = globals.pool
    user_id = interaction.user.id

    vehicle_type_id = vehicle.get("vehicle_type_id")
    if vehicle_type_id is None:
        await interaction.followup.send("❌ Vehicle data incomplete, contact support.", ephemeral=True)
        return

    finances = await get_user_finances(pool, user_id)
    if finances is None:
        finances = {
            "checking_account_balance": 0,
            "savings_account_balance": 0,
            "debt_balance": 0,
            "last_paycheck_claimed": datetime.datetime.fromtimestamp(0, tz=datetime.timezone.utc)
        }

    # Cost for drive or bike
    cost = 10 if method == 'drive' else 0  # Bike travel cost is zero, user rewarded

    # Check funds if cost > 0
    if cost > 0 and finances.get("checking_account_balance", 0) < cost:
        await interaction.followup.send(
            embed=embed_message(
                "⛽ Empty Tank!",
                f"> You tried to travel with your **{vehicle['vehicle_type']}**, but your wallet is emptier than the gas tank! Need ${cost}, but you only have ${finances.get('checking_account_balance', 0)}.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    if cost > 0:
        await charge_user(pool, user_id, cost)

    new_travel_count = vehicle.get("travel_count", 0) + 1
    await update_vehicle_condition_and_description(
        pool,
        user_id,
        vehicle["id"],
        vehicle_type_id,
        new_travel_count
    )

    # Apply biking bonus for bike
    if method == 'bike':
        await reward_user(pool, user_id, 10)

    # Select weighted outcome and apply effect
    outcome = await select_weighted_travel_outcome(pool, method if method != "drive" else "car")
    updated_finances = await get_user_finances(pool, user_id)
    updated_balance = updated_finances.get("checking_account_balance", 0)

    embed_text = (
        f"> You traveled with your **{vehicle['vehicle_type']}**! Total travels: **{new_travel_count}**.\n"
        f"> Your updated balance is: **${updated_balance}**."
    )
    if method == 'bike':
        embed_text += " +$10 biking bonus!"

    if outcome:
        desc = outcome.get("description", "")
        effect = outcome.get("effect_amount", 0)

        if effect < 0 and updated_balance >= -effect:
            await charge_user(pool, user_id, -effect)
            updated_balance -= -effect
        elif effect > 0:
            await reward_user(pool, user_id, effect)
            updated_balance += effect

        embed_text += f"\n\n🎲 Outcome: {desc}\n💰 Effect on balance: ${effect}"

    await interaction.followup.send(
        embed=embed_message(
            "🚗 Travel Result" if method == "drive" else "🚴 Travel Result",
            embed_text,
            COLOR_GREEN
        ),
        ephemeral=True
    )