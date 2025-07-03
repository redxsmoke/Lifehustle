import discord
import random
import string
import time


class TransportationShopButtons(discord.ui.View):
    def __init__(self, pool):
        super().__init__(timeout=None)
        self.pool = pool  # save pool for use later

    async def setup_buttons(self):
        async with self.pool.acquire() as conn:
            rows = await conn.fetch("SELECT id, emoji, name, cost FROM cd_vehicle_type")

            for row in rows:
                vehicle_id = row["id"]
                name = row["name"]
                emoji = row["emoji"]
                cost = row["cost"]

                self.add_item(VehicleButton(vehicle_id, name, emoji, cost, self.pool))



class VehicleButton(discord.ui.Button):
    def __init__(self, vehicle_id, name, emoji, cost, pool):
        super().__init__(
            label=f"Buy {name} - ${cost:,}",
            style=ButtonStyle.green,
            custom_id=f"shop_vehicle_buy_{vehicle_id}"  # Updated custom ID format
        )
        self.vehicle_id = vehicle_id
        self.name = name
        self.emoji = emoji
        self.cost = cost
        self.pool = pool

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)  # Prevent double-spam
        user_id = interaction.user.id

        async with self.pool.acquire() as conn:
            user = await conn.fetchrow("SELECT checking_balance FROM user_financials WHERE user_id = $1", user_id)

            if not user or user["checking_balance"] < self.cost:
                return await interaction.followup.send(embed=embed_message(
                    "❌ Not Enough Funds",
                    f"You need ${self.cost:,} to buy this {self.name}.",
                    COLOR_RED
                ), ephemeral=True)

            # Fetch vehicle details
            vehicle = await conn.fetchrow(
                "SELECT condition, resale_value_range FROM cd_vehicle_type WHERE id = $1",
                self.vehicle_id
            )

            if not vehicle:
                return await interaction.followup.send(embed=embed_message(
                    "❌ Vehicle not found.",
                    "",
                    COLOR_RED
                ), ephemeral=True)

            # Parse resale range safely
            resale_range = vehicle["resale_value_range"]
            if not resale_range or "-" not in resale_range:
                resale_min, resale_max = 1000, 3000
            else:
                try:
                    resale_min, resale_max = map(int, resale_range.split("-"))
                except ValueError:
                    resale_min, resale_max = 1000, 3000

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
            commute_count = 0 if condition != "beater" else random.randint(25, 100)
            resale_value = random.randint(resale_min, resale_max)
            created_at = int(time.time())

            # Deduct money
            await conn.execute(
                "UPDATE user_financials SET checking_balance = checking_balance - $1 WHERE user_id = $2",
                self.cost, user_id
            )

            # Add to inventory
            await conn.execute("""
                INSERT INTO user_vehicle_inventory 
                    (user_id, vehicle_type_id, color, appearance_description, plate_number, condition, commute_count, resale_value, created_at, sold_at)
                VALUES 
                    ($1, $2, $3, $4, $5, $6, $7, $8, $9, NULL)
            """, user_id, self.vehicle_id, color, appearance, plate, condition, commute_count, resale_value, created_at)

        await interaction.followup.send(embed=embed_message(
            "✅ Vehicle Purchased!",
            f"You bought a {color} {self.name} {self.emoji} with license plate `{plate}`.\n"
            f"It {appearance} and is in **{condition}** condition.",
            COLOR_GREEN
        ), ephemeral=True)
