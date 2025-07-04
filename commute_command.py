import asyncio
import datetime
import json
import random
import string
import discord
import unicodedata
import globals

from discord import app_commands, Interaction
from db_user import get_user, upsert_user
from utilities import (
    charge_user,
    update_vehicle_condition_and_description,
    reward_user
)
from vehicle_logic import get_user_vehicles
from embeds import embed_message

# VEHICLE CONDITION THRESHOLDS

def condition_from_usage(commute_count: int) -> str:
    if commute_count < 50:
        return "Brand New"
    elif commute_count < 100:
        return "Good Condition"
    elif commute_count < 150:
        return "Fair Condition"
    elif commute_count < 200:
        return "Poor Condition"
    else:
        return "Broken Down"

# Slash command registration

def register_commands(tree: app_commands.CommandTree):
    @tree.command(name="commute", description="Commute to work using buttons")
    async def commute(interaction: Interaction):
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
                    "❌ No Account", "Use `/start` to create an account."), ephemeral=True)
            return

        from views import CommuteButtons
        view = CommuteButtons()
        await interaction.response.defer(ephemeral=True)
        msg = await interaction.followup.send(
            embed=embed_message(
                "🚗 Commute",
                "Choose your commute method:",
                discord.Color.blue()
            ),
            view=view,
            ephemeral=True
        )
        view.message = msg

# COMMUTE LOGIC

async def handle_commute(interaction: Interaction, method: str):
    pool = globals.pool
    user_id = interaction.user.id
    user = await get_user(pool, user_id)

    if user is None:
        await interaction.followup.send(
            "❌ Oops! You don’t have an account yet. Maybe create one before trying to commute? Use `/start`!",
            ephemeral=True
        )
        return

    vehicles = await get_user_vehicles(pool, user_id)
    working_vehicles = [v for v in vehicles if v.get("condition") != "Broken Down"]

    if method == 'drive':
        cars = [v for v in working_vehicles if v.get("vehicle_type") in (
            "Beater Car", "Sedan", "Sports Car", "Pickup Truck", "Motorcycle"
        )]
        if not cars:
            await interaction.followup.send(
                "❌ No working car or motorcycle found!",
                ephemeral=True
            )
            return
        vehicle = cars[0]

        # Charge user $10 for the drive
        await charge_user(pool, user_id, 10)
        # Update vehicle's commute count & condition
        await update_vehicle_condition_and_description(pool, user_id, vehicle["id"])

        new_condition = condition_from_usage(vehicle.get("commute_count", 0) + 1)
        await interaction.followup.send(
            embed=embed_message(
                "🚗 Drive Commute",
                f"You drove your **{vehicle['vehicle_type']}**! New condition: **{new_condition}**."
            ),
            ephemeral=True
        )

    elif method == 'bike':
        bikes = [v for v in working_vehicles if v.get("vehicle_type") == "Bike"]
        if not bikes:
            await interaction.followup.send(
                "❌ No working bike found!",
                ephemeral=True
            )
            return
        vehicle = bikes[0]

        # Charge user $10 for biking
        await charge_user(pool, user_id, 10)
        # Update vehicle's commute count & condition
        await update_vehicle_condition_and_description(pool, user_id, vehicle["id"])
        # Reward biking bonus
        await reward_user(pool, user_id, 10)

        new_condition = condition_from_usage(vehicle.get("commute_count", 0) + 1)
        await interaction.followup.send(
            embed=embed_message(
                "🚴 Bike Commute",
                f"You biked on your **Bike**! New condition: **{new_condition}**. +$10 biking bonus!"
            ),
            ephemeral=True
        )

    elif method in ('subway', 'bus'):
        cost = 10 if method == 'subway' else 5
        await charge_user(pool, user_id, cost)
        await interaction.followup.send(
            embed=embed_message(
                f"{'🚇' if method == 'subway' else '� bus':^3} Commute Summary",
                f"You commuted by **{method.title()}** for ${cost}."
            ),
            ephemeral=True
        )

    else:
        await interaction.followup.send(
            "❌ Invalid commute method. Choose drive, bike, subway, or bus.",
            ephemeral=True
        )
