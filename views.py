# views.py
import discord
from discord.ui import View, Button
from discord import Interaction, Embed
import traceback

import globals              # for your asyncpg pool
from db_user import get_user, upsert_user
import utilities
import vehicle_logic
from commands import handle_commute   # import handle_commute from your commands module

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
        plate = vehicle.get("plate")
        if not plate or not isinstance(plate, str) or plate.strip() == "":
            raise ValueError(f"Vehicle missing valid 'plate': {vehicle}")

        label = parent_view.make_button_label(vehicle)
        super().__init__(label=label, style=discord.ButtonStyle.danger)

        self.vehicle = vehicle
        self.parent_view = parent_view
        self.plate = plate.upper()

    async def callback(self, interaction: Interaction):
        if interaction.user.id != self.parent_view.user_id:
            await interaction.response.send_message("This isn't your stash.", ephemeral=True)
            return
        await self.parent_view.start_sell_flow(interaction, self.vehicle, self.plate)


class SellFromStashView(View):
    def __init__(self, user_id: int, vehicles: list):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.vehicles = vehicles
        self.pending_vehicle = None
        self.pending_plate = None

        # Add a button for each vehicle that has a plate
        for vehicle in vehicles:
            plate = vehicle.get("plate")
            if plate and isinstance(plate, str) and plate.strip():
                self.add_item(SellButton(vehicle, self))
            else:
                print(f"[WARNING] Vehicle without valid plate skipped: {vehicle}")

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
        resale_percent = vehicle.get("resale_percent", 0.10)
        resale = int(base_price * resale_percent)

        return f"Sell {emoji} {desc} ({condition}) - ${resale:,}"

    async def start_sell_flow(self, interaction: Interaction, vehicle, plate):
        # store state before clearing
        self.pending_vehicle = vehicle
        self.pending_plate = plate

        self.clear_items()
        confirm = Button(label="Confirm Sale", style=discord.ButtonStyle.success)
        cancel = Button(label="Cancel", style=discord.ButtonStyle.secondary)

        async def on_confirm(i: Interaction):
            if i.user.id != self.user_id:
                await i.response.send_message("This isn't your stash.", ephemeral=True)
                return
            await self.confirm_sale(i)

        async def on_cancel(i: Interaction):
            if i.user.id != self.user_id:
                await i.response.send_message("This isn't your stash.", ephemeral=True)
                return
            # reset
            self.pending_vehicle = None
            self.pending_plate = None
            self.clear_items()
            for v in self.vehicles:
                p = v.get("plate")
                if p and p.strip():
                    self.add_item(SellButton(v, self))
            await i.response.edit_message(content="Sale cancelled.", view=self)

        confirm.callback = on_confirm
        cancel.callback = on_cancel

        self.add_item(confirm)
        self.add_item(cancel)

        await interaction.response.edit_message(
            content=(
                f"Are you sure you want to sell your "
                f"{vehicle.get('type')} "
                f"({vehicle.get('color','Unknown')}, {vehicle.get('condition','Unknown')})?"
            ),
            view=self
        )

    async def confirm_sale(self, interaction: Interaction):
        try:
            if not (self.pending_vehicle and self.pending_plate):
                return await interaction.response.send_message(
                    "❌ No vehicle pending confirmation.", ephemeral=True
                )

            user = await get_user(globals.pool, self.user_id)
            if not user:
                return await interaction.response.send_message(
                    "You don’t have an account yet.", ephemeral=True
                )

            # delete from DB
            await globals.pool.execute(
                "DELETE FROM user_vehicle_inventory WHERE user_id = $1 AND plate_number = $2",
                self.user_id,
                self.pending_plate
            )

            # compute resale
            base = BASE_PRICES.get(self.pending_vehicle.get("type"), 0)
            pct = self.pending_vehicle.get("resale_percent", 0.10)
            resale = int(base * pct)

            # update user balance
            bal = user.get("checking_account_balance", 0) + resale
            user["checking_account_balance"] = bal
            await upsert_user(globals.pool, self.user_id, user)

            sold_type = self.pending_vehicle.get("type", "vehicle")
            cond = self.pending_vehicle.get("condition", "Unknown")

            # clear state & buttons
            self.pending_vehicle = None
            self.pending_plate = None
            self.clear_items()

            await interaction.response.edit_message(
                content=f"✅ You sold your {sold_type} for ${resale:,} ({cond}).",
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
        self.message = None

    async def disable_all_items(self, interaction: Interaction):
        for child in self.children:
            child.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except Exception as e:
                print(f"[ERROR] Failed to edit message when disabling buttons: {e}")

    @discord.ui.button(label="Drive 🚗 ($10)", style=discord.ButtonStyle.danger, custom_id="commute_drive")
    async def drive_button(self, interaction: Interaction, button: Button):
        await self.disable_all_items(interaction)
        await handle_commute(interaction, "drive")

    @discord.ui.button(label="Bike 🚴 (+$10)", style=discord.ButtonStyle.success, custom_id="commute_bike")
    async def bike_button(self, interaction: Interaction, button: Button):
        await self.disable_all_items(interaction)
        await handle_commute(interaction, "bike")

    @discord.ui.button(label="Subway 🚇 ($10)", style=discord.ButtonStyle.primary, custom_id="commute_subway")
    async def subway_button(self, interaction: Interaction, button: Button):
        await self.disable_all_items(interaction)
        await handle_commute(interaction, "subway")

    @discord.ui.button(label="Bus 🚌 ($5)", style=discord.ButtonStyle.secondary, custom_id="commute_bus")
    async def bus_button(self, interaction: Interaction, button: Button):
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
