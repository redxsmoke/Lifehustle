import discord
from discord.ui import View, Button
import random

from globals import pool
from embeds import embed_message, COLOR_RED
from utilities import charge_user, update_vehicle_condition_and_description, reward_user
from vehicle_logic import remove_vehicle_by_id
from db_user import get_user_finances

class RepairOptionsView(View):
    def __init__(self, vehicle, user_id):
        super().__init__(timeout=120)
        self.vehicle = vehicle
        self.user_id = user_id
        print(f"[DEBUG] RepairOptionsView created for user_id={user_id} vehicle_id={vehicle.get('id')}")

    @discord.ui.button(label="🛠️ Have a mechanic repair it", style=discord.ButtonStyle.primary)
    async def mechanic_repair(self, interaction: discord.Interaction, button: Button):
        print(f"[DEBUG] mechanic_repair button clicked by {interaction.user} (id={interaction.user.id})")
        cost = int(50 * random.uniform(1.5, 5.5))
        finances = await get_user_finances(pool, self.user_id)
        print(f"[DEBUG] User finances: {finances}")

        if finances.get("checking_account_balance", 0) < cost:
            print("[DEBUG] Not enough funds for mechanic repair")
            await interaction.response.send_message(
                f"🚫 You need ${cost:,} to pay the mechanic but don't have enough funds.",
                ephemeral=True
            )
            return

        await charge_user(pool, self.user_id, cost)
        print(f"[DEBUG] Charged ${cost} to user {self.user_id}")

        await update_vehicle_condition_and_description(
            pool, self.user_id, self.vehicle["id"],
            self.vehicle["vehicle_type_id"], 150
        )
        print("[DEBUG] Vehicle condition reset to Poor Condition with travel count 150")

        await interaction.response.edit_message(
            content=f"🛠️ Mechanic repaired your vehicle for **${cost:,}**. "
                    f"Condition reset to **Poor Condition** with travel count 150.",
            view=None
        )
        print("[DEBUG] Edited message after mechanic repair")

    @discord.ui.button(label="🍺 Have Uncle Bill take a look", style=discord.ButtonStyle.secondary)
    async def uncle_bill(self, interaction: discord.Interaction, button: Button):
        print(f"[DEBUG] uncle_bill button clicked by {interaction.user} (id={interaction.user.id})")
        choice = random.choice(["fix", "drinks"])
        print(f"[DEBUG] Uncle Bill choice: {choice}")

        if choice == "fix":
            cost = int(20 * random.uniform(1.0, 9.5))
            finances = await get_user_finances(pool, self.user_id)
            print(f"[DEBUG] User finances: {finances}")

            if finances.get("checking_account_balance", 0) < cost:
                print("[DEBUG] Not enough funds for Uncle Bill fix")
                await interaction.response.send_message(
                    f"🚫 You need ${cost:,} to pay Uncle Bill but don't have enough funds.",
                    ephemeral=True
                )
                return

            await charge_user(pool, self.user_id, cost)
            print(f"[DEBUG] Charged ${cost} to user {self.user_id}")

            await update_vehicle_condition_and_description(
                pool, self.user_id, self.vehicle["id"],
                self.vehicle["vehicle_type_id"], 150
            )
            print("[DEBUG] Vehicle condition reset to Poor Condition with travel count 150")

            await interaction.response.edit_message(
                content=f"🧰 Uncle Bill fixed your vehicle for **${cost:,}**. "
                        f"Condition reset to **Poor Condition** with travel count 150.",
                view=None
            )
            print("[DEBUG] Edited message after Uncle Bill fix")

        else:
            cost = int(60 * random.uniform(3.0, 5.0))
            await charge_user(pool, self.user_id, cost)
            print(f"[DEBUG] Charged ${cost} for drunk Uncle Bill scenario")

            await update_vehicle_condition_and_description(
                pool, self.user_id, self.vehicle["id"],
                self.vehicle["vehicle_type_id"], 199
            )
            funny = "a raccoon is now living in your glovebox."
            print("[DEBUG] Vehicle travel count reset to 199, condition remains broken")

            await interaction.response.edit_message(
                content=f"🍻 Uncle Bill had one too many... "
                        f"he *sort of* fixed it but {funny}\nYou were charged **${cost:,}**.",
                view=None
            )
            print("[DEBUG] Edited message after drunk Uncle Bill scenario")

    @discord.ui.button(label="💸 Sell it for parts", style=discord.ButtonStyle.danger)
    async def sell_for_parts(self, interaction: discord.Interaction, button: Button):
        print(f"[DEBUG] sell_for_parts button clicked by {interaction.user} (id={interaction.user.id})")
        resale_value = self.vehicle.get("resale_value", 0)

        await remove_vehicle_by_id(pool, self.vehicle["id"])
        print(f"[DEBUG] Vehicle {self.vehicle['id']} removed from inventory")

        await reward_user(pool, self.user_id, resale_value)
        print(f"[DEBUG] Rewarded user {self.user_id} with ${resale_value}")

        await interaction.response.edit_message(
            content=f"💰 You sold your vehicle for parts and earned **${resale_value:,}**.",
            view=None
        )
        print("[DEBUG] Edited message after selling vehicle")
