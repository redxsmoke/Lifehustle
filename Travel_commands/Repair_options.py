import discord
from discord.ui import View, Button
import random

from embeds import embed_message, COLOR_RED, COLOR_GREEN
from utilities import charge_user, update_vehicle_condition_and_description, reward_user
from vehicle_logic import remove_vehicle_by_id
from db_user import get_user_finances

def get_random_travel_count(vehicle_type_id: int) -> int | None:
    if vehicle_type_id == 1:
        return random.randint(150, 199)
    elif vehicle_type_id == 2:
        return random.randint(100, 149)
    elif vehicle_type_id == 3:
        return random.randint(50, 115)
    elif vehicle_type_id == 4:
        return random.randint(65, 185)
    elif vehicle_type_id == 6:
        return random.randint(25, 100)
    elif vehicle_type_id == 5:
        return None
    else:
        return 150

class RepairOptionsView(View):
    def __init__(self, pool, vehicle, user_id):
        super().__init__(timeout=120)
        self.pool = pool
        self.vehicle = vehicle
        self.user_id = user_id
        self.awaiting_confirmation = False

        # Debug: show full vehicle dict
        print(f"[DEBUG] Vehicle passed to RepairOptionsView: {vehicle}")

        resale_value = self.get_resale_value(vehicle)

        self.sell_button = Button(
            label=f"💸 Sell for Parts (${resale_value:,})", style=discord.ButtonStyle.danger
        )
        self.sell_button.callback = self.sell_for_parts
        self.add_item(self.sell_button)

        print(f"[DEBUG] RepairOptionsView created for user_id={user_id} vehicle_id={vehicle.get('id')}")

    def get_resale_value(self, vehicle) -> int:
        # Try base_price first, then cost
        base_price = vehicle.get("base_price")
        if base_price is None:
            base_price = vehicle.get("cost", 0)

        resale_percent = vehicle.get("resale_percent")
        if resale_percent is None:
            resale_percent = 0.10

        resale = int(base_price * float(resale_percent))

        print(f"[DEBUG] Resale calc -> base: {base_price}, percent: {resale_percent}, resale: {resale}")
        return resale


    @discord.ui.button(label="🎩 Have a mechanic repair it", style=discord.ButtonStyle.primary)
    async def mechanic_repair(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG] mechanic_repair button clicked by {interaction.user} (id={interaction.user.id})")
        try:
            # Calculate parts and labor costs
            parts_cost = int(20 * random.uniform(1.0, 2.0))
            labor_cost = int(60 * random.uniform(1.5, 7.5))

            # Check if the user repairing is a mechanic
            async with self.pool.acquire() as conn:
                user_record = await conn.fetchrow(
                    "SELECT occupation_id FROM users WHERE user_id = $1",
                    self.user_id
                )

            if user_record and user_record["occupation_id"] == 62:
                # User is mechanic: labor cost waived
                cost = parts_cost
                is_self_mechanic = True
            else:
                cost = parts_cost + labor_cost
                is_self_mechanic = False

            finances = await get_user_finances(self.pool, self.user_id)
            if finances.get("checking_account_balance", 0) < cost:
                embed = discord.Embed(
                    description=f"🚫 You need ${cost:,} to pay for parts{' and labor' if not is_self_mechanic else ''} but don't have enough funds.",
                    color=COLOR_RED
                )
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return

            await charge_user(self.pool, self.user_id, cost)

            embed_description = ""

            if is_self_mechanic:
                # User is their own mechanic — no mechanic payment
                embed_description = (
                    f"🎩 As a skilled mechanic yourself, you paid **${parts_cost:,}** for parts to fix your vehicle.\n"
                )
            else:
                # User is not mechanic — pay another mechanic if available
                async with self.pool.acquire() as conn:
                    mechanic_record = await conn.fetchrow(
                        "SELECT user_id, discord_id FROM users WHERE occupation_id = 62 LIMIT 1"
                    )

                    if mechanic_record:
                        mechanic_user_id = mechanic_record["user_id"]
                        mechanic_discord_id = mechanic_record.get("discord_id")

                        # Add payment to mechanic's balance
                        await conn.execute(
                            """
                            UPDATE finances
                            SET checking_account_balance = checking_account_balance + $1
                            WHERE user_id = $2
                            """,
                            cost,
                            mechanic_user_id
                        )

                        mechanic_member = interaction.guild.get_member(mechanic_discord_id) if mechanic_discord_id else None
                        mechanic_mention = mechanic_member.mention if mechanic_member else "The Mechanic"

                        embed_description = (
                            f"🎩 {mechanic_mention} fixed your vehicle and you paid them **${cost:,}**.\n"
                        )
                    else:
                        # No mechanic found; just normal payment
                        embed_description = f"🎩 Mechanic repaired your vehicle for **${cost:,}**.\n"

            # Update vehicle condition etc.
            new_travel_count = get_random_travel_count(self.vehicle["vehicle_type_id"])
            if new_travel_count is None:
                await interaction.response.send_message(
                    "❌ This vehicle type cannot be repaired by mechanic.", ephemeral=True
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

            embed_description += (
                f"The mechanic also tweaked your odometer and reset your travel count to **{new_travel_count}**."
            )

            embed = discord.Embed(
                description=embed_description,
                color=COLOR_GREEN
            )
            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            print(f"[ERROR] Exception in mechanic_repair callback: {e}")
            await interaction.response.send_message(
                "⚠️ Something went wrong during mechanic repair. Please try again later.", ephemeral=True
            )


    @discord.ui.button(label="🍺 Have Uncle Bill take a look", style=discord.ButtonStyle.secondary)
    async def uncle_bill(self, interaction: discord.Interaction, button: Button):
        print(f"[DEBUG] uncle_bill button clicked by {interaction.user} (id={interaction.user.id})")
        try:
            choice = random.choice(["fix", "drinks"])

            if choice == "fix":
                cost = int(20 * random.uniform(1.0, 9.5))
                finances = await get_user_finances(self.pool, self.user_id)

                if finances.get("checking_account_balance", 0) < cost:
                    embed = discord.Embed(
                        description=f"🚫 You need ${cost:,} to pay Uncle Bill but don't have enough funds.",
                        color=COLOR_RED
                    )
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                    return

                await charge_user(self.pool, self.user_id, cost)

                new_travel_count = get_random_travel_count(self.vehicle["vehicle_type_id"])
                if new_travel_count is None:
                    await interaction.response.send_message(
                        "❌ This vehicle type cannot be repaired by Uncle Bill.", ephemeral=True
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

                embed = discord.Embed(
                    description=(
                        f"🪰 Uncle Bill fixed your vehicle for **${cost:,}**.\n"
                        f"He also tinkered with your odometer and reset your travel count to **{new_travel_count}**."
                    ),
                    color=COLOR_GREEN
                )
                await interaction.response.edit_message(embed=embed, view=None)

            else:
                cost = int(60 * random.uniform(3.0, 5.0))
                await charge_user(self.pool, self.user_id, cost)

                await update_vehicle_condition_and_description(
                    self.pool,
                    self.user_id,
                    self.vehicle["id"],
                    self.vehicle["vehicle_type_id"],
                    199,
                    random.randint(200, 299)
                )
                new_travel_count = 199
                funny = "it now sounds like a lawn mower with a cold."

                embed = discord.Embed(
                    description=(
                        f"🍻 Uncle Bill had one too many...\n"
                        f"> He *sort of* fixed it but {funny}\n"
                        f"> Your travel count is now **{new_travel_count}**.\n"
                        f"> You were charged **${cost:,}**."
                    ),
                    color=COLOR_GREEN
                )
                await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            print(f"[ERROR] Exception in uncle_bill callback: {e}")
            await interaction.response.send_message(
                "⚠️ Something went wrong with Uncle Bill's repair. Please try again later.", ephemeral=True
            )

    async def sell_for_parts(self, interaction: discord.Interaction):
        if not self.awaiting_confirmation:
            self.awaiting_confirmation = True

            confirm_button = Button(label="Confirm Sale", style=discord.ButtonStyle.success)
            cancel_button = Button(label="Cancel", style=discord.ButtonStyle.secondary)

            async def confirm_callback(i: discord.Interaction):
                if i.user.id != self.user_id:
                    await i.response.send_message("This isn't your vehicle.", ephemeral=True)
                    return
                await self.finalize_sale(i)

            async def cancel_callback(i: discord.Interaction):
                if i.user.id != self.user_id:
                    await i.response.send_message("This isn't your vehicle.", ephemeral=True)
                    return
                self.awaiting_confirmation = False
                self.clear_items()
                self.add_item(self.sell_button)
                await i.response.edit_message(content="Sale cancelled.", view=self)

            confirm_button.callback = confirm_callback
            cancel_button.callback = cancel_callback

            self.clear_items()
            self.add_item(confirm_button)
            self.add_item(cancel_button)

            desc = self.vehicle.get("tag") or self.vehicle.get("color", "Unknown")
            condition = self.vehicle.get("condition", "Unknown")
            resale = self.get_resale_value(self.vehicle)

            await interaction.response.edit_message(
                content=f"Are you sure you want to sell your {self.vehicle.get('type')} ({desc}, {condition}) for **${resale:,}**?",
                view=self
            )
        else:
            await interaction.response.send_message("⏳ Please confirm or cancel the sale first.", ephemeral=True)

    async def finalize_sale(self, interaction: discord.Interaction):
        try:
            resale_value = self.get_resale_value(self.vehicle)
            await remove_vehicle_by_id(self.pool, self.vehicle["id"])
            await reward_user(self.pool, self.user_id, resale_value)

            embed = discord.Embed(
                title="Vehicle Sold",
                description=f"💰 You sold your vehicle for parts and earned **${resale_value:,}**.",
                color=COLOR_GREEN
            )
            await interaction.response.edit_message(embed=embed, content=None, view=None)

        except Exception as e:
            print(f"[ERROR] Exception in finalize_sale: {e}")
            await interaction.response.send_message(
                "❌ Something went wrong selling the vehicle. Please try again later.", ephemeral=True
            )