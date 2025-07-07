import asyncio
import datetime
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
from db_user import get_user, upsert_user, get_user_finances
from vehicle_logic import ConfirmSellView, sell_all_vehicles
from .lifecheck_command import get_mock_weather_dynamic


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


# ------------------------------
# Repair Options UI for Broken Vehicle
# ------------------------------
class RepairOptionsView(discord.ui.View):
    def __init__(self, user_id, vehicle, current_balance):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.vehicle = vehicle
        self.current_balance = current_balance
        self.result_message = None

    async def update_condition_and_notify(self, interaction: Interaction, new_condition: str, new_travel_count: int, cost: int, message: str):
        # Update the vehicle condition and travel count in DB
        async with globals.pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE user_vehicle_inventory
                SET condition = $1, travel_count = $2
                WHERE user_id = $3 AND plate_number = $4
                """,
                new_condition, new_travel_count, self.user_id, self.vehicle.get("plate_number")
            )

        # Deduct cost
        if cost > 0:
            await charge_user(globals.pool, self.user_id, cost)
            self.current_balance -= cost

        # Notify user about condition change
        await interaction.response.edit_message(
            content=f"🔧 {message}\n💰 Repair cost: ${cost}\n🛠️ Vehicle condition is now: **{new_condition}**\n💵 Your new balance: ${self.current_balance}",
            view=None
        )
        self.stop()

    @discord.ui.button(label="Have a mechanic repair it", style=discord.ButtonStyle.primary)
    async def mechanic_repair(self, interaction: Interaction, button: discord.ui.Button):
        # Cost between $50 * (1.5 to 5.5 multiplier)
        multiplier = random.uniform(1.5, 5.5)
        cost = int(50 * multiplier)
        new_condition = "Poor Condition"
        new_travel_count = 150  # reset travel count to 150

        # Check if user has enough balance
        finances = await get_user_finances(globals.pool, self.user_id)
        if finances.get("checking_account_balance", 0) < cost:
            await interaction.response.send_message(
                f"🚫 You don't have enough money (${cost} needed) for the mechanic repair.",
                ephemeral=True
            )
            return

        await self.update_condition_and_notify(
            interaction,
            new_condition,
            new_travel_count,
            cost,
            "Your mechanic has repaired the vehicle!"
        )

    @discord.ui.button(label="Have Uncle Bill take a look", style=discord.ButtonStyle.secondary)
    async def uncle_bill(self, interaction: Interaction, button: discord.ui.Button):
        # Two outcomes: positive or negative

        # Check user balance for positive repair cost ($20 * 1 to 9.5 multiplier)
        multiplier = random.uniform(1, 9.5)
        repair_cost = int(20 * multiplier)

        # Negative wreck cost ($60 * 3.0 to 5.0 multiplier)
        wreck_multiplier = random.uniform(3.0, 5.0)
        wreck_cost = int(60 * wreck_multiplier)

        finances = await get_user_finances(globals.pool, self.user_id)
        user_balance = finances.get("checking_account_balance", 0)

        outcome = random.choice(["positive", "negative"])

        if outcome == "positive":
            if user_balance < repair_cost:
                await interaction.response.send_message(
                    f"🚫 You don't have enough money (${repair_cost} needed) for Uncle Bill's repair.",
                    ephemeral=True
                )
                return

            new_condition = "Poor Condition"
            new_travel_count = 150
            await self.update_condition_and_notify(
                interaction,
                new_condition,
                new_travel_count,
                repair_cost,
                "Uncle Bill fixed your vehicle for parts!"
            )
        else:
            # Uncle Bill got a bit drunk but managed to get it running, funny message, reset to 199 travel count
            new_condition = "Broken Down"
            new_travel_count = 199
            if user_balance < wreck_cost:
                await interaction.response.send_message(
                    f"🚫 You don't have enough money (${wreck_cost} needed) to pay Uncle Bill after his mishap.",
                    ephemeral=True
                )
                return

            funny_reasons = [
                "the engine sounds like deranged cats throwing a rave under the hood",
                "it makes a noise like a blender full of rocks",
                "the muffler is now loudly singing opera",
                "it smells like burnt popcorn every time you start it",
                "there's a mysterious leak that smells like old socks",
            ]
            funny_reason = random.choice(funny_reasons)

            await self.update_condition_and_notify(
                interaction,
                new_condition,
                new_travel_count,
                wreck_cost,
                f"Uncle Bill had a few too many before popping the hood — he got it running, but it sounds like {funny_reason}."
            )

    @discord.ui.button(label="Sell it for parts", style=discord.ButtonStyle.danger)
    async def sell_for_parts(self, interaction: Interaction, button: discord.ui.Button):
        # Reuse your sell logic or trigger selling the vehicle
        # For now, just confirm and stop

        # Assuming you have a sell_vehicle_by_id function (you can implement or reuse your existing logic)
        from vehicle_logic import remove_vehicle_by_id

        await remove_vehicle_by_id(globals.pool, self.vehicle.get("id"))

        # Give user the resale value for parts (say 50% of resale_value)
        resale_value = self.vehicle.get("resale_value", 0)
        parts_value = int(resale_value * 0.5)

        finances = await get_user_finances(globals.pool, self.user_id)
        finances["checking_account_balance"] += parts_value
        await upsert_user_finances(globals.pool, self.user_id, finances)

        await interaction.response.edit_message(
            content=f"🚙 You sold your vehicle for parts and received ${parts_value}. Your new balance is ${finances['checking_account_balance']}.",
            view=None
        )
        self.stop()


async def handle_travel_with_vehicle(interaction: Interaction, vehicle: dict, method: str):
    pool = globals.pool
    user_id = interaction.user.id

    cost = 10 if method == "car" else 5 if method == "bike" else 0

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

    # Check if vehicle is broken down BEFORE charging for travel
    if vehicle.get("condition") == "Broken Down":
        # Show repair options UI
        view = RepairOptionsView(user_id, vehicle, finances.get("checking_account_balance", 0))
        await interaction.response.send_message(
            embed=embed_message(
                "🚨 Vehicle Broken Down",
                "Your vehicle is broken down! What do you want to do?",
                discord.Color.red()
            ),
            view=view,
            ephemeral=True
        )
        return  # Do NOT proceed with travel if broken down

    # Charge user for travel
    await charge_user(pool, user_id, cost)
    current_balance = finances.get("checking_account_balance", 0) - cost

    print(f"[DEBUG] Travel method passed: {method}")
    outcome = await select_weighted_travel_outcome(pool, method)
    print(f"[DEBUG] Outcome result for {method}: {outcome}")
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
        # Increment travel_count
        await conn.execute(
            """
            UPDATE user_vehicle_inventory
            SET travel_count = travel_count + 1
            WHERE user_id = $1 AND plate_number = $2
            """,
            user_id, vehicle.get("plate_number")
        )

        # Fetch updated vehicle info needed for condition update
        updated_vehicle = await conn.fetchrow(
            """
            SELECT id, travel_count, vehicle_type_id
            FROM user_vehicle_inventory
            WHERE user_id = $1 AND plate_number = $2
            """,
            user_id, vehicle.get("plate_number")
        )

    if updated_vehicle:
        updated_info = await update_vehicle_condition_and_description(
            pool,
            user_id,
            updated_vehicle["id"],
            updated_vehicle["vehicle_type_id"],
            updated_vehicle["travel_count"]
        )

        travel_count = updated_info["travel_count"]
        condition_str = updated_info["condition"]
        appearance_desc = updated_info["description"]
    else:
        # fallback if vehicle not found (shouldn't happen)
        travel_count = vehicle.get("travel_count", 0) + 1
        condition_str = vehicle.get("condition", "Unknown")
        appearance_desc = vehicle.get("appearance_description", "No description available.")

    await interaction.followup.send(
        embed=discord.Embed(
            title=f"{'🚗' if method == 'car' else '🚴'} Travel Summary",
            description=(
                f"You traveled using your {vehicle.get('vehicle_type', 'vehicle')} "
                f"(Color: {vehicle.get('color', 'Unknown')}, Plate: {vehicle.get('plate_number', 'N/A')}).\n"
                f"Travel Count: {travel_count}\n"
                f"Condition: {condition_str}\n"
                f"Appearance: {appearance_desc}\n\n"
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