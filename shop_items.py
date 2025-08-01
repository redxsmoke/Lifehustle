import discord
from discord.ui import Button, View
from discord import ButtonStyle
import random
import string
import time
from datetime import datetime

# Placeholder functions/constants — replace with your real implementations
def embed_message(title, description, color=None):
    embed = discord.Embed(title=title, description=description, color=color)
    return embed

COLOR_RED = discord.Color.red()
COLOR_GREEN = discord.Color.green()


class TransportationShopButtons(View):
    def __init__(self, pool):
        super().__init__(timeout=None)
        self.pool = pool  # save pool for use later

    async def setup_buttons(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, emoji, name, cost FROM cd_vehicle_type ORDER BY cost ASC")

            for row in rows:
                vehicle_id = row["id"]
                name = row["name"]
                emoji = row["emoji"]
                cost = row["cost"]

                self.add_item(VehicleButton(vehicle_id, name, emoji, cost, self.pool))


class VehicleButton(Button):
    def __init__(self, vehicle_id, name, emoji, cost, pool):
        super().__init__(
            label=f"Buy {name} - ${cost:,}",
            style=ButtonStyle.green,
            custom_id=f"shop_vehicle_buy_{vehicle_id}"
        )
        self.vehicle_id = vehicle_id
        self.name = name
        self.emoji = emoji
        self.cost = cost
        self.pool = pool

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id

        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT checking_account_balance FROM user_finances WHERE user_id = $1", user_id)

            if not user or user["checking_account_balance"] < self.cost:
                return await interaction.followup.send(embed=embed_message(
                    "❌ Not Enough Funds",
                    f"You need ${self.cost:,} to buy this {self.name}.",
                    COLOR_RED
                ), ephemeral=True)

            # Fetch vehicle details
            vehicle = await conn.fetchrow(
                """
                SELECT cvc.description AS condition, cvc.resale_percent
                FROM cd_vehicle_type cvt
                JOIN cd_vehicle_condition cvc ON cvc.vehicle_type_id = cvt.id
                WHERE cvt.id = $1
                """,
                self.vehicle_id
            )

            if not vehicle:
                return await interaction.followup.send(embed=embed_message(
                    "❌ Vehicle not found.",
                    "",
                    COLOR_RED
                ), ephemeral=True)

            # Compute resale value
            resale_percent = vehicle["resale_percent"] or 0.25
            resale_value = int(self.cost * resale_percent)

            # Randomized attributes
            color = random.choice(["Red", "Blue", "Black", "White", "Green", "Silver"])
            appearance = random.choice([
                "still smells like a dealership",
                "gleams under the sun",
                "has tinted windows",
                "rides smoother than silk",
                "looks like it just got waxed"
            ])
            plate = ''.join(random.choices(string.ascii_uppercase + string.digits, k=7))
            condition = "pristine" if vehicle["condition"] == "new" else vehicle["condition"]
            travel_count = 0 if condition != "beater" else random.randint(150, 192)
            created_at = datetime.utcnow()

            # Always assign breakdown_threshold randomly 200-250 for all cars
            breakdown_threshold = random.randint(200, 250)

            # Deduct money
            await conn.execute(
                "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                self.cost, user_id
            )

            # Add to inventory
            await conn.execute("""
                INSERT INTO user_vehicle_inventory 
                    (user_id, vehicle_type_id, color, appearance_description, plate_number, condition, travel_count, resale_value, created_at, sold_at, breakdown_threshold)
                VALUES 
                    ($1, $2, $3, $4, $5, $6, $7, $8, $9, NULL, $10)
            """, user_id, self.vehicle_id, color, appearance, plate, condition, travel_count, resale_value, created_at, breakdown_threshold)

        await interaction.followup.send(embed=embed_message(
            "✅ Vehicle Purchased!",
            f"You bought a {color} {self.name} {self.emoji} with license plate `{plate}`.\n"
            f"It {appearance} and is in **{condition}** condition.",
            COLOR_GREEN
        ), ephemeral=True)
