import discord
from discord.ui import View, Button, Select
from discord import Interaction, Embed, Color
from embeds import embed_message, COLOR_GREEN, COLOR_RED
import traceback
from db_user import get_user, upsert_user, get_user_finances, upsert_user_finances
import utilities
import vehicle_logic
import globals  # Make sure pool is initialized here
import random
from datetime import datetime, time
from vehicle_logic import ConfirmSellView, sell_all_vehicles
from Bot_commands.lifecheck_command import get_mock_weather_dynamic


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

        # Add Sell All button at the end
        sell_all_btn = Button(label="Sell All", style=discord.ButtonStyle.danger)
        sell_all_btn.callback = self.sell_all_callback
        self.add_item(sell_all_btn)

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

    async def sell_all_callback(self, interaction: discord.Interaction):
        if not self.vehicles:
            await interaction.response.send_message("You have no vehicles to sell.", ephemeral=True)
            return

        # Show confirmation view to the user
        confirm_view = ConfirmSellView(self.user_id, self.vehicles)
        await interaction.response.send_message(
            "Are you sure you want to sell **ALL** your vehicles? This action cannot be undone.",
            view=confirm_view,
            ephemeral=True
        )

        # Wait for the user to respond (confirm or cancel)
        await confirm_view.wait()
        if confirm_view.value is None:
            await interaction.followup.send("⏳ Sale confirmation timed out.", ephemeral=True)
        elif confirm_view.value:  # user confirmed
            total_sale = await sell_all_vehicles(interaction, self.user_id, self.vehicles, globals.pool)
            self.vehicles.clear()
            finances = await get_user_finances(globals.pool, self.user_id)
            new_balance = finances.get("checking_account_balance", 0)
            await interaction.followup.send(f"✅ All vehicles sold for **${total_sale:,}**. Your new balance is **${new_balance:,}**.", ephemeral=True)


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
            # Re-add Sell All button after cancel
            sell_all_btn = Button(label="Sell All", style=discord.ButtonStyle.danger)
            sell_all_btn.callback = self.sell_all_callback
            self.add_item(sell_all_btn)

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

            finances = await get_user_finances(globals.pool, self.user_id)
            if finances is None:
                from datetime import timezone
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
            # Rebuild buttons for remaining vehicles
            for v in self.vehicles:
                if v.get("id"):
                    self.add_item(SellButton(v, self))
            # Re-add Sell All button
            sell_all_btn = Button(label="Sell All", style=discord.ButtonStyle.danger)
            sell_all_btn.callback = self.sell_all_callback
            self.add_item(sell_all_btn)

            if not interaction.response.is_done():
                await interaction.response.edit_message(
                    content=f"✅ You sold your {sold_type} for ${resale:,} ({condition}).",
                    view=self if self.vehicles else None
                )
            else:
                await interaction.followup.send(
                    f"✅ You sold your {sold_type} for ${resale:,} ({condition}).",
                    ephemeral=True
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
    def __init__(self, user_id: int, user_travel_location: int):
        super().__init__(timeout=None)
        self.message = None
        self.user_id = user_id
        self.user_travel_location = user_travel_location


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

    async def charge_user(self, pool, user_id: int, amount: int):
        finances = await get_user_finances(pool, user_id)
        if finances is None:
            finances = {
                "checking_account_balance": 0,
                "savings_account_balance": 0,
                "debt_balance": 0,
                "last_paycheck_claimed": datetime.fromtimestamp(0)
            }

        if finances["checking_account_balance"] >= amount:
            finances["checking_account_balance"] -= amount
            await upsert_user_finances(pool, user_id, finances)
            return True
        else:
            return False

    @discord.ui.button(label="Car 🚗 ($10)", style=discord.ButtonStyle.danger, custom_id="travel_car")
    async def car_button(self, interaction: Interaction, button: Button):
        try:
            from Bot_commands.travel_command import handle_travel

            user_id = interaction.user.id
            pool = globals.pool
            cost = 10

            if not await self.charge_user(pool, user_id, cost):
                await interaction.response.send_message(
                    "❌ You do not have enough funds to drive.", ephemeral=True)
                return

            await interaction.response.defer()
            await handle_travel(interaction, "car", self.user_travel_location)
            await self.disable_all_items()
        except Exception:
            import traceback
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.followup.send(
                    "❌ Something went wrong processing your car travel. Check the bot logs.",
                    ephemeral=True
                )

    @discord.ui.button(label="Bike 🚴 (+$10)", style=discord.ButtonStyle.success, custom_id="travel_bike")
    async def bike_button(self, interaction: Interaction, button: Button):
        try:
            from Bot_commands.travel_command import handle_travel

            now_utc = datetime.utcnow()
            weather_desc, weather_emoji, temp_c, temp_f = get_mock_weather_dynamic(now_utc)

            # Block biking if it's raining or snowing
            if weather_desc in ["Rain", "Snow"]:
                embed = embed_message(
                    title="🚴‍♂️ Bike Travel Denied!",
                    description=(
                        f"Whoa there! Trying to bike in this weather?\n"
                        f"Unless you want a soggy helmet or a snowman as a travel buddy, better wait it out! "
                        f"{weather_emoji} {weather_desc}"
                    ),
                    color=COLOR_RED
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            user_id = interaction.user.id
            pool = globals.pool
            cost = 10

            if not await self.charge_user(pool, user_id, cost):
                await interaction.response.send_message(
                    "❌ You do not have enough funds to bike.", ephemeral=True)
                return

            await interaction.response.defer()
            await handle_travel(interaction, "bike", self.user_travel_location)
            await self.disable_all_items()
        except Exception:
            import traceback
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.followup.send(
                    "❌ Something went wrong processing your bike travel. Check the bot logs.",
                    ephemeral=True
                )

    @discord.ui.button(label="Subway 🚇 ($10)", style=discord.ButtonStyle.primary, custom_id="travel_subway")
    async def subway_button(self, interaction: Interaction, button: Button):
        try:
            from Bot_commands.travel_command import handle_travel
            await interaction.response.defer()
            await handle_travel(interaction, "subway", self.user_travel_location)
            await self.disable_all_items()
        except Exception:
            import traceback
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.followup.send(
                    "❌ Something went wrong processing your subway travel. Check the bot logs.",
                    ephemeral=True
                )

    @discord.ui.button(label="Bus 🚌 ($5)", style=discord.ButtonStyle.secondary, custom_id="travel_bus")
    async def bus_button(self, interaction: Interaction, button: Button):
        try:
            from Bot_commands.travel_command import handle_travel
            await interaction.response.defer()
            await handle_travel(interaction, "bus", self.user_travel_location)
            await self.disable_all_items()
        except Exception:
            import traceback
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
            "loss": 0.15,
            "gain": 0.35,
        }
    else:
        weights = {
            "neutral": 0.5,
            "loss": 0.35,
            "gain": 0.15,
        }
    print(f"[DEBUG] Fetching travel outcomes for: {travel_type}")
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


class VehicleUseButton(Button):
    def __init__(self, vehicle: dict, method: str):
        label = f"{vehicle.get('vehicle_type', 'Vehicle')} - Plate: {vehicle.get('plate_number', 'N/A')} - Color: {vehicle.get('color', 'Unknown')}"
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.vehicle = vehicle
        self.method = method

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)

            if interaction.user.id != self.view.user_id:
                await interaction.followup.send("❌ This isn't your vehicle menu.", ephemeral=True)
                return

            self.view.disable_all_buttons()
            if hasattr(self.view, "message") and self.view.message:
                await self.view.message.edit(view=self.view)

            pool = globals.pool
            user_id = interaction.user.id

            
            async with pool.acquire() as conn:
                user_row = await conn.fetchrow("SELECT current_location FROM users WHERE user_id = $1", user_id)
                old_location_id = user_row["current_location"] if user_row else None

          
            async def get_location_name(pool, location_id):
                if location_id is None:
                    return "Unknown"
                row = await pool.fetchrow("SELECT location_name FROM cd_locations WHERE id = $1", location_id)
                return row["location_name"] if row else "Unknown"
 
            old_location_name = await get_location_name(pool, old_location_id)
            new_location_name = await get_location_name(pool, self.view.user_travel_location)

            # Update travel count
            async with pool.acquire() as conn:
                await conn.execute(
                    "UPDATE user_vehicle_inventory SET travel_count = travel_count + 1 WHERE id = $1 AND user_id = $2",
                    self.vehicle['id'], user_id
                )
                travel_count_row = await conn.fetchrow(
                    "SELECT travel_count FROM user_vehicle_inventory WHERE id = $1 AND user_id = $2",
                    self.vehicle['id'], user_id
                )
                travel_count = travel_count_row['travel_count'] if travel_count_row else 0

            finances = await get_user_finances(pool, user_id)

            outcome = await select_weighted_travel_outcome(pool, self.method)
            updated_finances = await get_user_finances(pool, user_id)
            updated_balance = updated_finances.get("checking_account_balance", 0)

            outcome_desc = "Nothing happened, and that's... okay."
            effect = 0
            if outcome:
                desc = outcome.get("description", "")
                effect = outcome.get("effect_amount", 0)
                if effect < 0 and updated_balance >= -effect:
                    await charge_user(pool, user_id, -effect)
                    updated_balance -= -effect
                elif effect > 0:
                    await reward_user(pool, user_id, effect)
                    updated_balance += effect
                outcome_desc = desc

  
            embed_text = (
                f"You traveled from **{old_location_name}** to **{new_location_name}** "
                f"using your {self.vehicle.get('vehicle_type', 'vehicle')} "
                f"(Color: {self.vehicle.get('color', 'Unknown')}, Plate: {self.vehicle.get('plate_number', 'N/A')}).\n"
                f"Travel Count: {travel_count}\n"
                f"Condition: {self.vehicle.get('condition', 'Unknown')}\n"
                f"Appearance: {self.vehicle.get('appearance_description', 'No description')}\n\n"
                f"🎲 Outcome: {outcome_desc}\n"
                f"💰 Balance Impact: ${effect}\n\n"
                f"Your current balance is: **${updated_balance:,}**."
            )

            await interaction.followup.send(
                embed=embed_message("🚗 Travel Summary", embed_text, COLOR_GREEN),
                ephemeral=True
            )

            # ✅ NEW: Update user's location in DB
            await pool.execute(
                "UPDATE users SET current_location = $1 WHERE user_id = $2",
                self.view.user_travel_location, user_id
            )

        except Exception:
            import traceback
            traceback.print_exc()
            if not interaction.response.is_done():
                await interaction.followup.send(
                    "❌ Something went wrong while processing your vehicle travel.",
                    ephemeral=True
                )



class VehicleUseView(View):
    def __init__(self, user_id: int, vehicles: list, method: str):
        super().__init__(timeout=60)
        self.user_id = user_id
        self.vehicles = vehicles
        self.method = method
        for vehicle in vehicles:
            self.add_item(VehicleUseButton(vehicle, method))

    def disable_all_buttons(self):
        for child in self.children:
            child.disabled = True

    async def on_timeout(self):
        self.disable_all_buttons()
        if hasattr(self, "message") and self.message:
            try:
                await self.message.edit(
                    content="⌛ Vehicle selection timed out. Please try again.",
                    view=self
                )
            except Exception as e:
                print(f"[ERROR] Failed to edit message on timeout: {e}")


class GroceryCategoryView(View):
    def __init__(self):
        super().__init__(timeout=None)
        options = [
            discord.SelectOption(label="Fruits", description="Select fruits category"),
            discord.SelectOption(label="Vegetables", description="Select vegetables category"),
            discord.SelectOption(label="Dairy", description="Select dairy products"),
        ]
        self.select = Select(placeholder="Choose grocery category...", options=options)
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: Interaction):
        selected = self.select.values[0]
        await interaction.response.send_message(f"You selected the {selected} category.", ephemeral=True)


class GroceryStashPaginationView(View):
    def __init__(self, user_id: int, pages: list):
        super().__init__(timeout=120)
        self.user_id = user_id
        self.pages = pages
        self.current_page = 0

    async def update_message(self, interaction: Interaction):
        page_content = self.pages[self.current_page]
        await interaction.response.edit_message(content=page_content, view=self)

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary)
    async def previous_button(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your stash.", ephemeral=True)
            return
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary)
    async def next_button(self, interaction: Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This isn't your stash.", ephemeral=True)
            return
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_message(interaction)
        else:
            await interaction.response.defer()

    async def on_timeout(self):
        for child in self.children:
            child.disabled = True
 


