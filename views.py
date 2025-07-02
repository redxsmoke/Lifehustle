import datetime
import random
import discord
from discord.ui import View, Button
from discord import Interaction, Embed

import utilities
import vehicle_logic
from db_user import get_user, upsert_user
from globals import pool

# Constants for colors etc. (define or import as you have them)
BIKE_COLORS = ["Red", "Blue", "Green", "Black", "White"]
CAR_COLORS = ["Blue", "Red", "Black", "White", "Silver"]


def generate_random_plate():
    return ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))


# COMMUTE BUTTONS VIEW
class CommuteButtons(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.message = None  # Will hold the message with buttons

    @discord.ui.button(label="Drive 🚗 ($10)", style=discord.ButtonStyle.danger, custom_id="commute_drive")
    async def drive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_commute(interaction, "drive")

    @discord.ui.button(label="Bike 🚴 (+$10)", style=discord.ButtonStyle.success, custom_id="commute_bike")
    async def bike_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_commute(interaction, "bike")

    @discord.ui.button(label="Subway 🚇 ($10)", style=discord.ButtonStyle.primary, custom_id="commute_subway")
    async def subway_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_commute(interaction, "subway")

    @discord.ui.button(label="Bus 🚌 ($5)", style=discord.ButtonStyle.secondary, custom_id="commute_bus")
    async def bus_button(self, interaction: discord.Interaction, button: discord.ui.Button):
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


# VEHICLE PURCHASE HANDLER
async def handle_vehicle_purchase(interaction: discord.Interaction, item: dict, cost: int):
    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    if user is None:
        await interaction.response.send_message("❌ You don't have an account yet. Use `/start`.", ephemeral=True)
        return

    if user["checking_account"] < cost:
        await interaction.response.send_message(f"🚫 Not enough money to buy {item.get('type', 'that item')}.", ephemeral=True)
        return

    vehicle_type_id = item.get("vehicle_type_id")
    if vehicle_type_id is None:
        await interaction.response.send_message("🚫 Internal error: No vehicle_type_id provided.", ephemeral=True)
        return

    # Check bike ownership restriction
    if vehicle_type_id == 1:  # Assuming 1 = Bike
        exists = await pool.fetchrow(
            "SELECT 1 FROM user_vehicle_inventory WHERE user_id = $1 AND vehicle_type_id = 1 LIMIT 1", user_id
        )
        if exists:
            await interaction.response.send_message("🚲 You already own a bike. You can't buy another one.", ephemeral=True)
            return
    else:
        # Check if user owns any car/truck (vehicle_type_id != 1)
        exists = await pool.fetchrow(
            "SELECT 1 FROM user_vehicle_inventory WHERE user_id = $1 AND vehicle_type_id != 1 LIMIT 1", user_id
        )
        if exists:
            await interaction.response.send_message("🚗 You already own a car or truck. You can't buy another one.", ephemeral=True)
            return

    # Deduct cost and update user
    user["checking_account"] -= cost
    await upsert_user(pool, user_id, user)

    plate = item.get("plate") or generate_random_plate()
    color = item.get("color", "Unknown")
    condition = item.get("condition", "Pristine")
    commute_count = item.get("commute_count", 0)
    resale_value = cost  # or adjust based on condition if desired

    await pool.execute(
        """
        INSERT INTO user_vehicle_inventory (
            user_id, vehicle_type_id, plate_number, color, condition, commute_count, resale_value
        ) VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        user_id, vehicle_type_id, plate, color, condition, commute_count, resale_value
    )

    await interaction.response.send_message(
        f"✅ You purchased a {item.get('type', 'vehicle')} for ${cost:,}!",
        ephemeral=True
    )


# TRANSPORTATION SHOP BUTTONS VIEW
class TransportationShopButtons(View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Buy Bike 🚴", style=discord.ButtonStyle.success, custom_id="buy_bike")
    async def buy_bike(self, interaction: discord.Interaction, button: Button):
        try:
            color = random.choice(BIKE_COLORS)
            condition = "Pristine"
            bike_item = {
                "type": "Bike",
                "vehicle_type_id": 1,  # Must match your DB vehicle_type_id for bike
                "color": color,
                "condition": condition,
                "purchase_date": datetime.date.today().isoformat(),
                "commute_count": 0
            }
            await handle_vehicle_purchase(interaction, item=bike_item, cost=2000)
        except Exception:
            await interaction.response.send_message("🚫 Failed to buy Bike. Try again later.", ephemeral=True)

    @discord.ui.button(label="Buy Beater Car 🚙", style=discord.ButtonStyle.primary, custom_id="buy_blue_car")
    async def buy_blue_car(self, interaction: discord.Interaction, button: Button):
        try:
            plate = generate_random_plate()
            color = random.choice(CAR_COLORS)
            car_item = {
                "type": "Beater Car",
                "vehicle_type_id": 2,  # Replace with your actual ID for Beater Car
                "plate": plate,
                "color": color,
                "condition": "Heavily Used",
                "commute_count": 0,
                "purchase_date": datetime.date.today().isoformat()
            }
            await handle_vehicle_purchase(interaction, item=car_item, cost=10000)
        except Exception:
            await interaction.response.send_message("🚫 Failed to buy Beater Car. Try again later.", ephemeral=True)

    # Add other car buttons similarly, setting vehicle_type_id accordingly


# SELL FROM STASH VIEW
class SellFromStashView(View):
    def __init__(self, user_id: int, vehicles: list):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.vehicles = vehicles
        self.pending_confirmation = {}  # Tracks items awaiting confirmation keyed by custom_id

        for vehicle in vehicles:
            plate_or_tag = vehicle.get('plate') or vehicle.get('tag') or str(id(vehicle))
            custom_id = f"sell_{plate_or_tag}"
            btn = Button(
                label=self.make_button_label(vehicle),
                style=discord.ButtonStyle.danger,
                custom_id=custom_id
            )
            btn.callback = self.make_sell_request_callback(vehicle, custom_id)
            self.add_item(btn)

    def make_button_label(self, item):
        emoji = {
            "Bike": "🚴",
            "Beater Car": "🚙",
            "Sedan Car": "🚗",
            "Sports Car": "🏎️",
            "Pickup Truck": "🛻"
        }.get(item.get("type"), "❓")
        desc = item.get("tag") or item.get("color", "Unknown")
        cond = item.get("condition", "Unknown")

        base_prices = {
            "Bike": 2000,
            "Beater Car": 10000,
            "Sedan Car": 25000,
            "Sports Car": 100000,
            "Pickup Truck": 75000
        }
        resale_percent = {
            "Pristine": 0.85,
            "Lightly Used": 0.50,
            "Heavily Used": 0.25,
            "Rusted": 0.10
        }
        base_price = base_prices.get(item.get("type"), 0)
        percent = resale_percent.get(cond, 0.10)
        resale = int(base_price * percent)

        return f"Sell {emoji} {desc} ({cond}) - ${resale:,}"

    def make_sell_request_callback(self, item, custom_id):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("This isn't your stash.", ephemeral=True)
                return

            self.pending_confirmation[custom_id] = item

            for child in self.children:
                child.disabled = True

            confirm_btn = Button(label="Confirm Sale", style=discord.ButtonStyle.success, custom_id=f"confirm_{custom_id}")
            cancel_btn = Button(label="Cancel", style=discord.ButtonStyle.secondary, custom_id=f"cancel_{custom_id}")

            async def confirm_callback(i: discord.Interaction):
                await self.confirm_sale(i, item, custom_id)

            async def cancel_callback(i: discord.Interaction):
                if i.user.id != self.user_id:
                    await i.response.send_message("This isn't your stash.", ephemeral=True)
                    return
                self.clear_items()
                for vehicle in self.vehicles:
                    plate_or_tag = vehicle.get('plate') or vehicle.get('tag') or str(id(vehicle))
                    cid = f"sell_{plate_or_tag}"
                    btn = Button(
                        label=self.make_button_label(vehicle),
                        style=discord.ButtonStyle.danger,
                        custom_id=cid
                    )
                    btn.callback = self.make_sell_request_callback(vehicle, cid)
                    self.add_item(btn)
                await i.response.edit_message(content="Sale cancelled.", view=self)

            confirm_btn.callback = confirm_callback
            cancel_btn.callback = cancel_callback

            self.clear_items()
            self.add_item(confirm_btn)
            self.add_item(cancel_btn)

            await interaction.response.edit_message(
                content=f"Are you sure you want to sell your {item.get('type')} ({item.get('color', 'Unknown')}, {item.get('condition', 'Unknown')})?",
                view=self
            )
        return callback

    async def confirm_sale(self, interaction: discord.Interaction, item, custom_id):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your stash.", ephemeral=True)
            return

        user = await get_user(pool, self.user_id)
        if not user:
            await interaction.response.send_message("You don’t have an account yet.", ephemeral=True)
            return

        # Remove vehicle by plate number from DB
        plate = item.get("plate")
        if not plate:
            await interaction.response.send_message("❌ Cannot find vehicle plate to remove.", ephemeral=True)
            return

        # Remove from DB
        await pool.execute(
            "DELETE FROM user_vehicle_inventory WHERE user_id = $1 AND plate_number = $2",
            self.user_id, plate
        )

        condition = item.get("condition", "Unknown")
        base_prices = {
            "Bike": 2000,
            "Beater Car": 10000,
            "Sedan Car": 25000,
            "Sports Car": 100000,
            "Pickup Truck": 75000
        }
        resale_percent = {
            "Pristine": 0.85,
            "Lightly Used": 0.50,
            "Heavily Used": 0.25,
            "Rusted": 0.10
        }
        base_price = base_prices.get(item.get("type"), 0)
        percent = resale_percent.get(condition, 0.10)
        resale = int(base_price * percent)

        # Credit user
        user["checking_account"] += resale
        await upsert_user(pool, self.user_id, user)

        self.clear_items()
        await interaction.response.edit_message(
            content=f"✅ You sold your {item.get('type')} for ${resale:,} ({condition}).",
            view=None
        )


# You can keep the other views (GroceryCategoryView, GroceryStashPaginationView, SubmitWordModal)
# unchanged unless you want them converted to SQL-backed inventories too.

# ConfirmSellButton and SellVehicleView (using SQL vehicle id and resale_value)
class ConfirmSellButton(Button):
    def __init__(self, vehicle_id: int, resale_value: int):
        super().__init__(label="Sell", style=discord.ButtonStyle.red)
        self.vehicle_id = vehicle_id
        self.resale_value = resale_value

    async def callback(self, interaction: Interaction):
        from db_helpers import remove_vehicle_by_id  # Your helper to delete vehicle by id
        from db_user import get_user, upsert_user

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
