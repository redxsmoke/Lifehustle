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
from views import select_weighted_travel_outcome, VehicleUseView

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
            await handle_travel_with_vehicle(interaction, cars[0], method)
        else:
            view = VehicleUseView(user_id=user_id, vehicles=cars, method=method)
            embed = embed_message(
                "🚗 Your Cars",
                "> You have multiple vehicles. Please choose one to travel with:",
                discord.Color.blue()
            )
            msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            view.message = msg
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
            # Auto use the only bike - send confirmation
            await handle_travel_with_vehicle(interaction, bikes[0], method)
        else:
            view = VehicleUseView(user_id=user_id, vehicles=bikes, method=method)
            embed = embed_message(
                "🚴 Your Bikes",
                "> You have multiple bikes. Please choose one to travel with:",
                discord.Color.green()
            )
            msg = await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            view.message = msg

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

        # --- Outcome and effect ---
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

            embed_text += f"\n\n🎲 Outcome: {desc}\n💰 Balance: ${effect}"

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
                "> Are you hacking us?! How did you select this as a travel option 🤔? Pick one of these: drive, bike, subway, or bus.",
                discord.Color.red()
            ),
            ephemeral=True
        )

async def handle_travel_with_vehicle(interaction: Interaction, vehicle: dict, method: str):
    pool = globals.pool
    user_id = interaction.user.id

    cost = 10 if method == "drive" else 5 if method == "bike" else 0

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

    await interaction.followup.send(
        embed=discord.Embed(
            title=f"{'🚗' if method == 'drive' else '🚴'} Travel Summary",
            description=(
                f"You traveled using your {vehicle.get('vehicle_type', 'vehicle')} "
                f"(Color: {vehicle.get('color', 'Unknown')}, Plate: {vehicle.get('plate', 'N/A')}).\n"
                f"Travel Count: {vehicle.get('travel_count', 0) + 1}\n\n"
                f"🎲 Outcome: {outcome_desc}\n"
                f"💰 Balance: ${effect}\n\n"
                f"Your current balance is: ${current_balance:,}."
            ),
            color=COLOR_GREEN
        ),
        ephemeral=True
    )
async def on_sell_all_button_click(interaction: discord.Interaction, user_id, vehicles):
    # Send confirmation prompt
    confirm_view = ConfirmSellView(user_id, vehicles)
    await interaction.response.send_message(
        "Are you sure you want to **sell all your vehicles**? This action cannot be undone.",
        view=confirm_view,
        ephemeral=True
    )

    # Wait for user to click confirm or cancel
    await confirm_view.wait()

    if confirm_view.value is None:
        # User did not respond within timeout
        await interaction.followup.send("⏳ Sale confirmation timed out.", ephemeral=True)
    elif confirm_view.value:
        # User confirmed sale
        # Proceed with selling vehicles here (your existing sale logic)
        # For example:
        await sell_all_vehicles(interaction, user_id, vehicles)
    else:
        # User cancelled
        # Nothing else needed, message already updated
        pass
