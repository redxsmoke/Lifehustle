import asyncio
import datetime
import json
import random
import string
import discord
import unicodedata
import re

from discord import app_commands, Interaction

from db_user import get_user, upsert_user
from globals import pool
from embeds import embed_message
from utilities import charge_user, update_vehicle_condition_and_description, reward_user
from views import CommuteButtons

# ───────────────────────────────────────────────
# VEHICLE CONDITION THRESHOLDS
# ───────────────────────────────────────────────

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

# ───────────────────────────────────────────────
# COMMUTE LOGIC
# ───────────────────────────────────────────────

async def handle_commute(interaction: discord.Interaction, method: str):
    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    if user is None:
        await interaction.response.send_message(
            "❌ Oops! You don’t have an account yet. Maybe create one before trying to teleport to work? Use `/start`!", ephemeral=True
        )
        return

    vehicles = await get_user_vehicles(pool, user_id)
    working_vehicles = [v for v in vehicles if v["condition"] != "Broken Down"]

    if method == 'drive':
        cars = [v for v in working_vehicles if v["type"] in ("Beater Car", "Sedan", "Sports Car", "Pickup Truck", "Motorcycle")]
        if not cars:
            await interaction.response.send_message(
                "❌ Your car is more 'carcass' than 'car' right now. No working car or motorcycle found!", ephemeral=True
            )
            return
        vehicle = cars[0]
        await process_vehicle_commute(interaction, pool, user_id, vehicle)

    elif method == 'bike':
        bikes = [v for v in working_vehicles if v["type"] == "Bike"]
        if not bikes:
            await interaction.response.send_message(
                "❌ Your bike seems to have taken a permanent vacation. No working bike found!", ephemeral=True
            )
            return
        vehicle = bikes[0]
        await process_vehicle_commute(interaction, pool, user_id, vehicle, earn_bonus=True)

    elif method in ('subway', 'bus'):
        cost = 10 if method == 'subway' else 5
        await charge_user(pool, user_id, cost)
        await interaction.response.send_message(embed=embed_message(
            f"{'🚇' if method == 'subway' else '🚌'} Commute Summary",
            f"You bravely commuted using the **{method.title()}** for just ${cost}. Don't forget to hold onto the strap!"), ephemeral=True
        )
    else:
        await interaction.response.send_message(
            "❌ You tried to invent a new commute method? Nice try, but that’s not a thing. Pick subway, bus, bike, or drive!", ephemeral=True
        )

async def process_vehicle_commute(interaction: discord.Interaction, pool, user_id: int, vehicle: dict, earn_bonus=False):
    vehicle_id = vehicle["vehicle_id"]
    commute_count = vehicle.get("commute_count", 0) + 1
    vehicle_type_id = vehicle.get("vehicle_type_id")
    old_condition = vehicle.get("condition", "Unknown")

    new_condition, new_description = await update_vehicle_condition_and_description(
        pool, user_id, vehicle_id, vehicle_type_id, commute_count
    )

    if new_condition == "Broken Down":
        await interaction.response.send_message(embed=embed_message(
            "💥 Vehicle Broken Down",
            f"Your **{vehicle['type']}** is broken down and must be repaired or sold before further commuting."
        ), ephemeral=True)
        return

    bonus = 10 if earn_bonus else 0
    if bonus:
        await reward_user(pool, user_id, bonus)

    msg = (
        f"🚗 You commuted using your **{vehicle['type']}**.\n"
        f"🏁 Commute Count: {commute_count}\n"
        f"⚙️ Condition: **{new_condition}**\n"
        f"📝 Appearance: {new_description}"
    )
    if new_condition != old_condition:
        msg += f"\n⚠️ Condition changed from **{old_condition}**."

    if bonus:
        msg += f"\n💸 Earned **${bonus}** for biking!"

    await interaction.response.send_message(embed=embed_message("✅ Commute Complete", msg), ephemeral=True)

# ───────────────────────────────────────────────
# DB UTILITIES
# ───────────────────────────────────────────────

async def get_user_vehicles(pool, user_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM user_vehicle_inventory WHERE user_id = $1", user_id)
        return [dict(row) for row in rows]

# ───────────────────────────────────────────────
# Slash command registration
# ───────────────────────────────────────────────

@ app_commands.command(name="commute", description="Commute to work using buttons")
async def commute(interaction: Interaction):
    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    if not user:
        await interaction.response.send_message(embed=embed_message(
            "❌ No Account", "Use `/start` to create an account."), ephemeral=True)
        return

    view = CommuteButtons()
    await interaction.response.send_message(embed=embed_message(
        "🚗 Commute",
        "Choose your commute method:",
        discord.Color.blue()
    ), view=view, ephemeral=True)
