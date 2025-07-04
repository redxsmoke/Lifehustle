import asyncio
import datetime
import json
import random
import string
import discord
import unicodedata
import globals
import re

from discord import app_commands, Interaction

from db_user import get_user, upsert_user
from embeds import embed_message
from utilities import charge_user, update_vehicle_condition_and_description, reward_user
from views import CommuteButtons
from vehicle_logic import get_user_vehicles

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
# Slash command registration
# ───────────────────────────────────────────────

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
            await interaction.response.send_message(embed=embed_message(
                "❌ No Account", "Use `/start` to create an account."), ephemeral=True)
            return

        view = CommuteButtons()

        # Defer the interaction first
        await interaction.response.defer(ephemeral=True)

        # Send followup message and assign it to view.message for editing later
        msg = await interaction.followup.send(
            embed=embed_message(
                "🚗 Commute",
                "Choose your commute method:",
                discord.Color.blue()
            ),
            view=view,
            ephemeral=True
        )

        # Save the message object to the view so buttons can edit it (disable)
        view.message = msg
# ───────────────────────────────────────────────
# COMMUTE LOGIC
# ───────────────────────────────────────────────

async def handle_commute(interaction: discord.Interaction, method: str):
    pool = globals.pool
    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    if user is None:
        await interaction.followup.send(
            "❌ Oops! You don’t have an account yet. Maybe create one before trying to teleport to work? Use `/start`!",
            ephemeral=True
        )
        return

    # Make sure you have this function imported or defined somewhere:
    vehicles = await get_user_vehicles(pool, user_id)
    working_vehicles = [v for v in vehicles if v["condition"] != "Broken Down"]

    if method == 'drive':
        cars = [v for v in working_vehicles if v["type"] in ("Beater Car", "Sedan", "Sports Car", "Pickup Truck", "Motorcycle")]
        if not cars:
            await interaction.followup.send(
                "❌ Your car is more 'carcass' than 'car' right now. No working car or motorcycle found!",
                ephemeral=True
            )
            return
        vehicle = cars[0]
        await process_vehicle_commute(interaction, pool, user_id, vehicle)

    elif method == 'bike':
        bikes = [v for v in working_vehicles if v["type"] == "Bike"]
        if not bikes:
            await interaction.followup.send(
                "❌ Your bike seems to have taken a permanent vacation. No working bike found!",
                ephemeral=True
            )
            return
        vehicle = bikes[0]
        await process_vehicle_commute(interaction, pool, user_id, vehicle, earn_bonus=True)

    elif method in ('subway', 'bus'):
        cost = 10 if method == 'subway' else 5
        await charge_user(pool, user_id, cost)
        await interaction.followup.send(
            embed=embed_message(
                f"{'🚇' if method == 'subway' else '🚌'} Commute Summary",
                f"You bravely commuted using the **{method.title()}** for just ${cost}. Don't forget to hold onto the strap!"
            ),
            ephemeral=True
        )

    else:
        await interaction.followup.send(
            "❌ You tried to invent a new commute method? Nice try, but that’s not a thing. Pick subway, bus, bike, or drive!",
            ephemeral=True
        )
