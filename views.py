import discord
from discord.ui import View, Button
from discord import Interaction, Embed
import traceback

import utilities
import vehicle_logic
from db_user import get_user, upsert_user
import globals  # import the global pool correctly

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

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.parent_view.user_id:
            await interaction.response.send_message("This isn't your stash.", ephemeral=True)
            return
        await self.parent_view.start_sell_flow(interaction, self.vehicle)


class SellFromStashView(View):
    def __init__(self, user_id: int, vehicles: list):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.vehicles = vehicles
        self.pending_vehicle = None

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
        resale_percent = vehicle.get("resale_percent", 0.10)  # e.g. 0.85
        resale = int(base_price * resale_percent)

        return f"Sell {emoji} {desc} ({condition}) - ${resale:,}"

    async def start_sell_flow(self, interaction: Interaction, vehicle):
        self.clear_items()
        self.pending_vehicle = vehicle

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
            if not self.pending_vehicle:
                await interaction.response.send_message("❌ No vehicle pending confirmation.", ephemeral=True)
                return

            user = await get_user(globals.pool, self.user_id)
            if not user:
                await interaction.response.send_message("You don’t have an account yet.", ephemeral=True)
                return

            plate = self.pending_vehicle.get("plate", "").upper()
            if not plate:
                await interaction.response.send_message("❌ Cannot find vehicle plate to remove.", ephemeral=True)
                return

            # Delete vehicle from DB
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
