import discord
from discord.ui import View, Button
import random

from embeds import embed_message, COLOR_RED
from utilities import charge_user, update_vehicle_condition_and_description, reward_user
from vehicle_logic import remove_vehicle_by_id
from db_user import get_user_finances

def get_random_travel_count(vehicle_type_id: int) -> int | None:
    # Returns a random travel count based on vehicle type, or None if bike (id=5)
    if vehicle_type_id == 1:  # Beater Car
        return random.randint(150, 199)
    elif vehicle_type_id == 2:  # Sedan
        return random.randint(100, 149)
    elif vehicle_type_id == 3:  # Sports Car
        return random.randint(50, 115)
    elif vehicle_type_id == 4:  # Pickup Truck
        return random.randint(65, 185)
    elif vehicle_type_id == 6:  # Motorcycle
        return random.randint(25, 100)
    elif vehicle_type_id == 5:  # Bike (excluded)
        return None
    else:
        return 150  # Fallback default

class RepairOptionsView(View):
    def __init__(self, pool, vehicle, user_id):
        super().__init__(timeout=120)
        self.pool = pool
        self.vehicle = vehicle
        self.user_id = user_id
        print(f"[DEBUG] RepairOptionsView created for user_id={user_id} vehicle_id={vehicle.get('id')}")

    @discord.ui.button(label="🛠️ Have a mechanic repair it", style=discord.ButtonStyle.primary)
    async def mechanic_repair(self, interaction: discord.Interaction, button: Button):
        print(f"[DEBUG] mechanic_repair button clicked by {interaction.user} (id={interaction.user.id})")
        try:
            cost = int(50 * random.uniform(1.5, 5.5))
            finances = await get_user_finances(self.pool, self.user_id)
            print(f"[DEBUG] User finances: {finances}")

            if finances.get("checking_account_balance", 0) < cost:
                print("[DEBUG] Not enough funds for mechanic repair")
                await interaction.response.send_message(
                    f"🚫 You need ${cost:,} to pay the mechanic but don't have enough funds.",
                    ephemeral=True
                )
                return

            await charge_user(self.pool, self.user_id, cost)
            print(f"[DEBUG] Charged ${cost} to user {self.user_id}")

            # New randomized travel count and breakdown threshold
            new_travel_count = get_random_travel_count(self.vehicle["vehicle_type_id"])
            if new_travel_count is None:
                await interaction.response.send_message(
                    "❌ This vehicle type cannot be repaired by mechanic.",
                    ephemeral=True
                )
                return
            new_breakdown_threshold = random.randint(200, 299)

            await update_vehicle_condition_and_description(
                self.pool,
                self.user_id,
                self.vehicle["id"],
                self.vehicle["vehicle_type_id"],
                new_travel_count,
                new_breakdown_threshold
            )
            print(f"[DEBUG] Vehicle condition reset with travel count {new_travel_count} and breakdown threshold {new_breakdown_threshold}")

            await interaction.response.edit_message(
                content=f"🛠️ Mechanic repaired your vehicle for **${cost:,}**. "
                        f"The mechanic also tweaked your odometer and reset your travel count **{new_travel_count}**.",
                view=None
            )
            print("[DEBUG] Edited message after mechanic repair")
        except Exception as e:
            print(f"[ERROR] Exception in mechanic_repair callback: {e}")
            try:
                await interaction.response.send_message(
                    "⚠️ Something went wrong during mechanic repair. Please try again later.",
                    ephemeral=True
                )
            except Exception as e2:
                print(f"[ERROR] Failed to send error message in mechanic_repair: {e2}")

    @discord.ui.button(label="🍺 Have Uncle Bill take a look", style=discord.ButtonStyle.secondary)
    async def uncle_bill(self, interaction: discord.Interaction, button: Button):
        print(f"[DEBUG] uncle_bill button clicked by {interaction.user} (id={interaction.user.id})")
        try:
            choice = random.choice(["fix", "drinks"])
            print(f"[DEBUG] Uncle Bill choice: {choice}")

            if choice == "fix":
                cost = int(20 * random.uniform(1.0, 9.5))
                finances = await get_user_finances(self.pool, self.user_id)
                print(f"[DEBUG] User finances: {finances}")

                if finances.get("checking_account_balance", 0) < cost:
                    print("[DEBUG] Not enough funds for Uncle Bill fix")
                    await interaction.response.send_message(
                        f"🚫 You need ${cost:,} to pay Uncle Bill but don't have enough funds.",
                        ephemeral=True
                    )
                    return

                await charge_user(self.pool, self.user_id, cost)
                print(f"[DEBUG] Charged ${cost} to user {self.user_id}")

                # New randomized travel count and breakdown threshold
                new_travel_count = get_random_travel_count(self.vehicle["vehicle_type_id"])
                if new_travel_count is None:
                    await interaction.response.send_message(
                        "❌ This vehicle type cannot be repaired by Uncle Bill.",
                        ephemeral=True
                    )
                    return
                new_breakdown_threshold = random.randint(200, 299)

                await update_vehicle_condition_and_description(
                    self.pool,
                    self.user_id,
                    self.vehicle["id"],
                    self.vehicle["vehicle_type_id"],
                    new_travel_count,
                    new_breakdown_threshold
                )
                print(f"[DEBUG] Vehicle condition reset with travel count {new_travel_count} and breakdown threshold {new_breakdown_threshold}")

                await interaction.response.edit_message(
                    content=f"🧰 Uncle Bill fixed your vehicle for **${cost:,}**. "
                            f"He also tinkered with your odometer and reset your travel count to **{new_travel_count}**.",
                    view=None
                )
                print("[DEBUG] Edited message after Uncle Bill fix")

            else:
                cost = int(60 * random.uniform(3.0, 5.0))
                await charge_user(self.pool, self.user_id, cost)
                print(f"[DEBUG] Charged ${cost} for drunk Uncle Bill scenario")

                await update_vehicle_condition_and_description(
                    self.pool,
                    self.user_id,
                    self.vehicle["id"],
                    self.vehicle["vehicle_type_id"],
                    199,  # Keeping this fixed for drunk scenario as before
                    random.randint(200, 299)
                )
                new_travel_count = 199  # Fix: define this variable before using it in the message
                funny = "a raccoon is now living in your glovebox."
                print("[DEBUG] Vehicle travel count reset to 199, condition remains broken")

                await interaction.response.edit_message(
                    content=(
                        f"🍻 Uncle Bill had one too many... "
                        f"> He *sort of* fixed it but {funny}\n"
                        f"> Your travel count is now **{new_travel_count}**. "
                        f"> You were charged **${cost:,}**."
                    ),
                    view = None 
                )
                print("[DEBUG] Edited message after drunk Uncle Bill scenario")

        except Exception as e:
            print(f"[ERROR] Exception in uncle_bill callback: {e}")
            try:
                await interaction.response.send_message(
                    "⚠️ Something went wrong with Uncle Bill's repair. Please try again later.",
                    ephemeral=True
                )
            except Exception as e2:
                print(f"[ERROR] Failed to send error message in uncle_bill: {e2}")

    @discord.ui.button(label="💸 Sell it for parts", style=discord.ButtonStyle.danger)
    async def sell_for_parts(self, interaction: discord.Interaction, button: Button):
        print(f"[DEBUG] sell_for_parts button clicked by {interaction.user} (id={interaction.user.id})")
        try:
            resale_value = self.vehicle.get("resale_value", 0)

            await remove_vehicle_by_id(self.pool, self.vehicle["id"])
            print(f"[DEBUG] Vehicle {self.vehicle['id']} removed from inventory")

            await reward_user(self.pool, self.user_id, resale_value)
            print(f"[DEBUG] Rewarded user {self.user_id} with ${resale_value}")

            await interaction.response.edit_message(
                content=f"💰 You sold your vehicle for parts and earned **${resale_value:,}**.",
                view=None
            )
            print("[DEBUG] Edited message after selling vehicle")
        except Exception as e:
            print(f"[ERROR] Exception in sell_for_parts callback: {e}")
            try:
                await interaction.response.send_message(
                    "⚠️ Something went wrong selling the vehicle. Please try again later.",
                    ephemeral=True
                )
            except Exception as e2:
                print(f"[ERROR] Failed to send error message in sell_for_parts: {e2}")
