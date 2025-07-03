import datetime
import random
import discord
from discord.ui import View, Button
from discord import Interaction, Embed

import utilities
import vehicle_logic
from db_user import get_user, upsert_user
from globals import pool


# Fixed base prices by vehicle type
BASE_PRICES = {
    "Bike": 2000,
    "Beater Car": 10000,
    "Sedan Car": 25000,
    "Sports Car": 100000,
    "Pickup Truck": 75000
}


# COMMUTE BUTTONS VIEW
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
        await handle_commute(interaction, "drive")

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


# SELL FROM STASH VIEW
class SellButton(Button):
    def __init__(self, item, parent_view):
        label = parent_view.make_button_label(item)
        super().__init__(label=label, style=discord.ButtonStyle.danger)
        self.item = item
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.parent_view.user_id:
            await interaction.response.send_message("This isn't your stash.", ephemeral=True)
            return

        await self.parent_view.start_sell_flow(interaction, self.item)


class SellFromStashView(View):
    def __init__(self, user_id: int, vehicles: list):
        super().__init__(timeout=None)  # Use no timeout or increase as needed
        self.user_id = user_id
        self.vehicles = vehicles
        self.pending_item = None

        for vehicle in vehicles:
            self.add_item(SellButton(vehicle, self))

    def make_button_label(self, item):
        emoji = {
            "Bike": "🚴",
            "Beater Car": "🚙",
            "Sedan Car": "🚗",
            "Sports Car": "🏎️",
            "Pickup Truck": "🛻"
        }.get(item.get("type"), "❓")

        desc = item.get("tag") or item.get("color", "Unknown")
        condition = item.get("condition", "Unknown")

        base_price = BASE_PRICES.get(item.get("type"), 0)
        resale_percent = item.get("resale_percent", 0.10)  # e.g. 0.85
        resale = int(base_price * resale_percent)

        return f"Sell {emoji} {desc} ({condition}) - ${resale:,}"

    async def start_sell_flow(self, interaction: discord.Interaction, item):
        self.clear_items()
        self.pending_item = item

        confirm_btn = Button(label="Confirm Sale", style=discord.ButtonStyle.success)
        cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.secondary)

        async def confirm_callback(i: discord.Interaction):
            if i.user.id != self.user_id:
                await i.response.send_message("This isn't your stash.", ephemeral=True)
                return
            await self.confirm_sale(i)

        async def cancel_callback(i: discord.Interaction):
            if i.user.id != self.user_id:
                await i.response.send_message("This isn't your stash.", ephemeral=True)
                return
            self.pending_item = None
            self.clear_items()
            for vehicle in self.vehicles:
                self.add_item(SellButton(vehicle, self))
            await i.response.edit_message(content="Sale cancelled.", view=self)

        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback

        self.add_item(confirm_btn)
        self.add_item(cancel_btn)

        await interaction.response.edit_message(
            content=f"Are you sure you want to sell your {item.get('type')} ({item.get('color', 'Unknown')}, {item.get('condition', 'Unknown')})?",
            view=self
        )

    async def confirm_sale(self, interaction: discord.Interaction):
        if not self.pending_item:
            await interaction.response.send_message("❌ No item pending confirmation.", ephemeral=True)
            return

        user = await get_user(pool, self.user_id)
        if not user:
            await interaction.response.send_message("You don’t have an account yet.", ephemeral=True)
            return

        plate = self.pending_item.get("plate")
        if not plate:
            await interaction.response.send_message("❌ Cannot find vehicle plate to remove.", ephemeral=True)
            return

        # Remove vehicle from DB
        await pool.execute(
            "DELETE FROM user_vehicle_inventory WHERE user_id = $1 AND plate_number = $2",
            self.user_id, plate
        )

        base_price = BASE_PRICES.get(self.pending_item.get("type"), 0)
        resale_percent = self.pending_item.get("resale_percent", 0.10)
        resale = int(base_price * resale_percent)

        # Credit user
        user["checking_account"] += resale
        await upsert_user(pool, self.user_id, user)

        sold_type = self.pending_item.get("type", "vehicle")
        condition = self.pending_item.get("condition", "Unknown")

        self.pending_item = None
        self.clear_items()

        await interaction.response.edit_message(
            content=f"✅ You sold your {sold_type} for ${resale:,} ({condition}).",
            view=None
        )


# ConfirmSellButton and SellVehicleView (using SQL vehicle id and resale_value)
class ConfirmSellButton(Button):
    def __init__(self, vehicle_id: int, resale_value: int):
        super().__init__(label="Sell", style=discord.ButtonStyle.danger)
        self.vehicle_id = vehicle_id
        self.resale_value = resale_value

    async def callback(self, interaction: Interaction):
        user_id = interaction.user.id
        user = await get_user(pool, user_id)

        if not user:
            await interaction.response.send_message("❌ You don’t have an account.", ephemeral=True)
            return

        await remove_vehicle_by_id(pool, self.vehicle_id)

        user["checking_account"] += self.resale_value
        await upsert_user(pool, user_id, user)

        await interaction.response.send_message(
            embed=Embed(
                title="✅ Vehicle Sold",
                description=f"You sold your vehicle for ${self.resale_value:,}.",
                color=discord.Color.green()
            ),
            ephemeral=True
        )


class SellVehicleView(View):
    def __init__(self, vehicle_id: int, resale_value: int):
        super().__init__(timeout=None)
        self.add_item(ConfirmSellButton(vehicle_id, resale_value))


class GroceryCategoryView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Minimal stub, add your real code here later


class GroceryStashPaginationView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO: Add your pagination logic here later
