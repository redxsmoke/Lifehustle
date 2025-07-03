import discord
from discord.ui import View, Button
from discord import Interaction, Embed
import traceback

import utilities
import vehicle_logic
from db_user import get_user, upsert_user
import globals  # Make sure pool is initialized here

# Fixed base prices by vehicle type
BASE_PRICES = {
    "Bike": 2000,
    "Beater Car": 10000,
    "Sedan Car": 25000,
    "Sports Car": 100000,
    "Pickup Truck": 75000
}

class SellButton(Button):
    def __init__(self, vehicle, parent_view):
        label = parent_view.make_button_label(vehicle)
        super().__init__(label=label, style=discord.ButtonStyle.danger)
        self.vehicle = vehicle
        self.parent_view = parent_view
        # Store plate on the button for easy access
        self.plate = vehicle.get("plate", "").upper()

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.parent_view.user_id:
            await interaction.response.send_message("This isn't your stash.", ephemeral=True)
            return
        # Pass the vehicle and plate explicitly
        await self.parent_view.start_sell_flow(interaction, self.vehicle, self.plate)

class SellFromStashView(View):
    def __init__(self, user_id: int, vehicles: list):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.vehicles = vehicles
        self.pending_vehicle = None
        self.pending_plate = None  # Store plate for confirmation

        for vehicle in vehicles:
            self.add_item(SellButton(vehicle, self))

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
        resale_percent = vehicle.get("resale_percent", 0.10)  # default 10%
        resale = int(base_price * resale_percent)

        return f"Sell {emoji} {desc} ({condition}) - ${resale:,}"

    async def start_sell_flow(self, interaction: Interaction, vehicle, plate):
        self.clear_items()
        self.pending_vehicle = vehicle
        self.pending_plate = plate  # Save plate for sale confirmation

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
            self.pending_plate = None
            self.clear_items()
            for v in self.vehicles:
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
            if not self.pending_vehicle or not self.pending_plate:
                await interaction.response.send_message("❌ No vehicle pending confirmation.", ephemeral=True)
                return

            user = await get_user(globals.pool, self.user_id)
            if not user:
                await interaction.response.send_message("You don’t have an account yet.", ephemeral=True)
                return

            plate = self.pending_plate
            if not plate:
                await interaction.response.send_message("❌ Cannot find vehicle plate to remove.", ephemeral=True)
                return

            # Delete vehicle from DB using user_id and plate_number
            await globals.pool.execute(
                "DELETE FROM user_vehicle_inventory WHERE user_id = $1 AND plate_number = $2",
                self.user_id,
                plate
            )

            base_price = BASE_PRICES.get(self.pending_vehicle.get("type"), 0)
            resale_percent = self.pending_vehicle.get("resale_percent", 0.10)
            resale = int(base_price * resale_percent)

            # Add resale money to user's checking account
            current_balance = user.get("checking_account_balance", 0)
            user["checking_account_balance"] = current_balance + resale

            await upsert_user(globals.pool, self.user_id, user)

            sold_type = self.pending_vehicle.get("type", "vehicle")
            condition = self.pending_vehicle.get("condition", "Unknown")

            self.pending_vehicle = None
            self.pending_plate = None
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


class GroceryCategoryView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

class GroceryStashPaginationView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)


class CommuteButtons(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.message = None  # Will hold the message with buttons

    async def disable_all_items(self, interaction: discord.Interaction):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                print(f"[ERROR] Failed to edit message when disabling buttons: {e}")

    @discord.ui.button(label="Drive 🚗 ($10)", style=discord.ButtonStyle.danger, custom_id="commute_drive")
    async def drive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.disable_all_items(interaction)
        await handle_commute(interaction, "drive")  # Make sure handle_commute is imported/defined

    @discord.ui.button(label="Bike 🚴 (+$10)", style=discord.ButtonStyle.success, custom_id="commute_bike")
    async def bike_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.disable_all_items(interaction)
        await handle_commute(interaction, "bike")

    @discord.ui.button(label="Subway 🚇 ($10)", style=discord.ButtonStyle.primary, custom_id="commute_subway")
    async def subway_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.disable_all_items(interaction)
        await handle_commute(interaction, "subway")

    @discord.ui.button(label="Bus 🚌 ($5)", style=discord.ButtonStyle.secondary, custom_id="commute_bus")
    async def bus_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.disable_all_items(interaction)
        await handle_commute(interaction, "bus")

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(
                    content="⌛ Commute selection timed out. Please try again.",
                    view=self
                )
            except Exception as e:
                print(f"[ERROR] Failed to edit message on timeout: {e}")
#