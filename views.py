import discord
from discord.ui import View, Select, Button
from discord import Interaction, Embed, Color
import traceback

import utilities
import vehicle_logic
from db_user import get_user, upsert_user
import globals  # Make sure pool is initialized here
import random
from datetime import datetime, time


# Fixed base prices by vehicle type
BASE_PRICES = {
    "Bike": 2000,
    "Motorcycle": 18000,
    "Beater Car": 10000,
    "Sedan Car": 25000,
    "Sports Car": 100000,
    "Pickup Truck": 75000
}

class SellButton(Button):
    def __init__(self, vehicle, parent_view):
        vehicle_id = vehicle.get("id")
        if not vehicle_id:
            raise ValueError(f"Vehicle missing valid 'id': {vehicle}")

        label = parent_view.make_button_label(vehicle)  # call the method on the parent view
        super().__init__(label=label, style=discord.ButtonStyle.danger)

        self.vehicle = vehicle
        self.parent_view = parent_view
        self.vehicle_id = vehicle_id

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.parent_view.user_id:
            await interaction.response.send_message("This isn't your stash.", ephemeral=True)
            return
        await self.parent_view.start_sell_flow(interaction, self.vehicle, self.vehicle_id)


class SellFromStashView(View):
    def __init__(self, user_id: int, vehicles: list):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.vehicles = vehicles
        self.pending_vehicle = None
        self.pending_vehicle_id = None

        for vehicle in vehicles:
            if vehicle.get("id"):
                self.add_item(SellButton(vehicle, self))
            else:
                print(f"[WARNING] Vehicle without valid ID skipped: {vehicle}")

    def make_button_label(self, vehicle):
        emoji = {
            "Bike": "🚴",
            "Beater Car": "🚙",
            "Sedan Car": "🚗",
            "Sports Car": "🏎️",
            "Pickup Truck": "🛻"
        }.get(vehicle.get("type"), "❓")

        desc = vehicle.get("tag") or vehicle.get("color", "Unknown")
        condition = vehicle.get("condition", "Unknown")

        base_price = BASE_PRICES.get(vehicle.get("type"), 0)
        resale_percent = vehicle.get("resale_percent")
        if resale_percent is None:
            resale_percent = 0.10  # fallback to 10%

        resale = int(base_price * resale_percent)

        return f"Sell {emoji} {desc} ({condition}) - ${resale:,}"

    async def start_sell_flow(self, interaction: Interaction, vehicle, vehicle_id):
        self.pending_vehicle = vehicle
        self.pending_vehicle_id = vehicle_id

        self.clear_items()

        confirm_btn = Button(label="Confirm Sale", style=discord.ButtonStyle.success)
        cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.secondary)

        async def confirm_callback(i: Interaction):
            if i.user.id != self.user_id:
                await i.response.send_message("This isn't your stash.", ephemeral=True)
                return
            await self.confirm_sale(i)

        async def cancel_callback(i: Interaction):
            if i.user.id != self.user_id:
                await i.response.send_message("This isn't your stash.", ephemeral=True)
                return
            self.pending_vehicle = None
            self.pending_vehicle_id = None
            self.clear_items()
            for v in self.vehicles:
                if v.get("id"):
                    self.add_item(SellButton(v, self))
            await i.response.edit_message(content="Sale cancelled.", view=self)

        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback

        self.add_item(confirm_btn)
        self.add_item(cancel_btn)

        await interaction.response.edit_message(
            content=f"Are you sure you want to sell your {vehicle.get('type')} "
                    f"({vehicle.get('color', 'Unknown')}, {vehicle.get('condition', 'Unknown')})?",
            view=self
        )

    async def confirm_sale(self, interaction: Interaction):
        try:
            if not self.pending_vehicle or not self.pending_vehicle_id:
                await interaction.response.send_message("❌ No vehicle pending confirmation.", ephemeral=True)
                return

            # Delete vehicle by ID
            await globals.pool.execute(
                "DELETE FROM user_vehicle_inventory WHERE id = $1",
                self.pending_vehicle_id
            )

            # Remove vehicle from local stash list
            self.vehicles = [v for v in self.vehicles if v.get("id") != self.pending_vehicle_id]

            base_price = BASE_PRICES.get(self.pending_vehicle.get("type"), 0)
            resale_percent = self.pending_vehicle.get("resale_percent", 0.10)
            resale = int(base_price * resale_percent)

            from db_user import get_user_finances, upsert_user_finances
            from datetime import datetime, timezone

            finances = await get_user_finances(globals.pool, self.user_id)
            if finances is None:
                finances = {
                    "checking_account_balance": 0,
                    "savings_account_balance": 0,
                    "debt_balance": 0,
                    "last_paycheck_claimed": datetime.fromtimestamp(0, tz=timezone.utc)
                }

            finances["checking_account_balance"] += resale
            await upsert_user_finances(globals.pool, self.user_id, finances)

            sold_type = self.pending_vehicle.get("type", "vehicle")
            condition = self.pending_vehicle.get("condition", "Unknown")

            self.pending_vehicle = None
            self.pending_vehicle_id = None
            self.clear_items()

            await interaction.response.edit_message(
                content=f"✅ You sold your {sold_type} for ${resale:,} ({condition}).",
                view=None
            )
        except Exception:
            print("Error in confirm_sale:")
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.response.send_message(
                    "❌ Something went wrong while selling your vehicle. Please try again later.",
                    ephemeral=True
                )


class TravelButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.message = None  # Will hold the message with buttons

    def set_message(self, message: discord.Message):
        self.message = message

    async def disable_all_items(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                print(f"[ERROR] Failed to edit message when disabling buttons: {e}")

    @discord.ui.button(label="Drive 🚗 ($10)", style=discord.ButtonStyle.danger, custom_id="travel_drive")
    async def drive_button(self, interaction: Interaction, button: Button):
        try:
            from travel_command import handle_travel  # consider renaming this if desired
            await interaction.response.defer()
            await handle_travel(interaction, "drive")
            await self.disable_all_items()
        except Exception:
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.followup.send(
                    "❌ Something went wrong processing your drive travel. Check the bot logs.",
                    ephemeral=True
                )

    @discord.ui.button(label="Bike 🚴 (+$10)", style=discord.ButtonStyle.success, custom_id="travel_bike")
    async def bike_button(self, interaction: Interaction, button: Button):
        try:
            from travel_command import handle_travel
            await interaction.response.defer()
            await handle_travel(interaction, "bike")
            await self.disable_all_items()
        except Exception:
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.followup.send(
                    "❌ Something went wrong processing your bike travel. Check the bot logs.",
                    ephemeral=True
                )

    @discord.ui.button(label="Subway 🚇 ($10)", style=discord.ButtonStyle.primary, custom_id="travel_subway")
    async def subway_button(self, interaction: Interaction, button: Button):
        try:
            from travel_command import handle_travel
            await interaction.response.defer()
            await handle_travel(interaction, "subway")
            await self.disable_all_items()
        except Exception:
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.followup.send(
                    "❌ Something went wrong processing your subway travel. Check the bot logs.",
                    ephemeral=True
                )

    @discord.ui.button(label="Bus 🚌 ($5)", style=discord.ButtonStyle.secondary, custom_id="travel_bus")
    async def bus_button(self, interaction: Interaction, button: Button):
        try:
            from travel_command import handle_travel
            await interaction.response.defer()
            await handle_travel(interaction, "bus")
            await self.disable_all_items()
        except Exception:
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.followup.send(
                    "❌ Something went wrong processing your bus travel. Check the bot logs.",
                    ephemeral=True
                )

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(
                    content="⌛ Travel selection timed out. Please try again.",
                    view=self
                )
            except Exception as e:
                print(f"[ERROR] Failed to edit message on timeout: {e}")


async def select_weighted_travel_outcome(pool, travel_type):
    now = datetime.now().time()
    day_start = time(6, 0)
    day_end = time(18, 0)
    is_day = day_start <= now <= day_end

    if is_day:
        weights = {
            "neutral": 0.5,
            "negative": 0.15,
            "positive": 0.35,
        }
    else:
        weights = {
            "neutral": 0.5,
            "negative": 0.35,
            "positive": 0.15,
        }

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, description, effect_amount, effect_type
            FROM cd_travel_summaries
            WHERE travel_type = $1
            """,
            travel_type
        )

    weighted_choices = []
    for row in rows:
        eff_type = row["effect_type"]
        # DB stored probability per row, multiply by adjusted weights
        base_prob = row.get("probability", 1.0)
        weight = weights.get(eff_type, 0) * base_prob
        if weight > 0:
            weighted_choices.append((row, weight))

    if not weighted_choices:
        return None

    total_weight = sum(w for _, w in weighted_choices)
    r = random.uniform(0, total_weight)
    upto = 0
    for row, w in weighted_choices:
        if upto + w >= r:
            return row
        upto += w
    return weighted_choices[-1][0]

class TravelVehicleSelect(Select):
    def __init__(self, vehicles, method):
        options = []
        for v in vehicles:
            label = v.get("vehicle_type", "Unknown")
            desc = v.get("appearance_description", "") or ""
            # Option label: vehicle type + maybe short desc
            options.append(discord.SelectOption(label=label, description=desc[:100], value=str(v["id"])))
        super().__init__(placeholder=f"Select your {method}...", min_values=1, max_values=1, options=options)
        self.method = method
        self.vehicles = {str(v["id"]): v for v in vehicles}

    async def callback(self, interaction: Interaction):
        vehicle_id = self.values[0]
        vehicle = self.vehicles.get(vehicle_id)
        if not vehicle:
            await interaction.response.send_message("❌ Vehicle not found. Please try again.", ephemeral=True)
            return
        # Disable dropdown after selection
        self.view.clear_items()
        await interaction.response.edit_message(view=self.view)
        # Call the travel handler continuation
        await continue_travel_with_vehicle(interaction, self.method, vehicle)


class TravelVehicleSelectView(View):
    def __init__(self, vehicles, method):
        super().__init__(timeout=60)
        self.add_item(TravelVehicleSelect(vehicles, method))





class GroceryCategoryView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Implement grocery category view buttons or logic here if needed


class GroceryStashPaginationView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Implement grocery stash pagination buttons or logic here if needed
