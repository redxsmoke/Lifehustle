import random
import discord
from db_user import get_user, upsert_user
from globals import pool

# Base prices for resale calculation
BASE_PRICES = {
    "Beater Car": 10000,
    "Sedan Car": 25000,
    "Sports Car": 100000,
    "Pickup Truck": 75000,
    "Bike": 2000,
    "Motorcycle": 18000
}

# Condition → resale percent
CONDITION_TO_PERCENT = {
    "Brand New": 0.85,
    "Good Condition": 0.70,
    "Fair Condition": 0.50,
    "Poor Condition": 0.30,
    "Broken Down": 0.10
}


async def get_vehicle_type_name(conn, vehicle_type_id: int) -> str:
    row = await conn.fetchrow(
        "SELECT name FROM cd_vehicle_type WHERE id = $1", vehicle_type_id
    )
    return row["name"] if row else "Unknown Vehicle"


async def get_condition_name(conn, condition_id: int) -> str:
    row = await conn.fetchrow(
        "SELECT name FROM cd_vehicle_condition WHERE id = $1", condition_id
    )
    return row["name"] if row else "Unknown Condition"


async def fetch_random_color(conn, vehicle_type_id: int) -> str:
    row = await conn.fetchrow(
        """
        SELECT name FROM cd_vehicle_color
        WHERE vehicle_type_id = $1
        ORDER BY random()
        LIMIT 1
        """,
        vehicle_type_id
    )
    return row['name'] if row else "Unknown Color"


async def fetch_appearance_description(conn, vehicle_type_id: int, condition_id: int) -> str:
    row = await conn.fetchrow(
        """
        SELECT description FROM cd_vehicle_appearence
        WHERE vehicle_type_id = $1 AND condition_id = $2
        ORDER BY random()
        LIMIT 1
        """,
        vehicle_type_id, condition_id
    )
    return row['description'] if row else "has an indescribable look"


def generate_random_plate() -> str:
    return ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))


async def handle_vehicle_purchase(
    interaction: discord.Interaction,
    item: dict,
    cost: int,
):
    user_id = interaction.user.id
    vehicle_type_id = item.get("vehicle_type_id")
    print(f"[DEBUG] Starting purchase: user_id={user_id}, cost={cost}, vehicle_type_id={vehicle_type_id}")

    user = await get_user(pool, user_id)
    if user is None:
        await interaction.response.send_message("You don't have an account yet. Use `/start`.", ephemeral=True)
        return

    if user["checking_account"] < cost:
        await interaction.response.send_message(f"🚫 Not enough money to buy {item.get('type', 'that item')}.", ephemeral=True)
        return

    if vehicle_type_id is None:
        await interaction.response.send_message("🚫 Internal error: No vehicle_type_id provided.", ephemeral=True)
        return

    # Enforce ownership limits
    if vehicle_type_id in (5, 6):  # Bike or Motorcycle
        exists = await pool.fetchrow(
            "SELECT 1 FROM user_vehicle_inventory WHERE user_id = $1 AND vehicle_type_id IN (5,6) LIMIT 1",
            user_id
        )
        if exists:
            await interaction.response.send_message("🚲 You already own a bike or motorcycle. You can't buy another one.", ephemeral=True)
            return
    else:
        exists = await pool.fetchrow(
            "SELECT 1 FROM user_vehicle_inventory WHERE user_id = $1 AND vehicle_type_id NOT IN (5,6) LIMIT 1",
            user_id
        )
        if exists:
            await interaction.response.send_message("🚗 You already own a car or truck. You can't buy another one.", ephemeral=True)
            return

    # Deduct funds
    user["checking_account"] -= cost
    await upsert_user(pool, user_id, user)

    plate = generate_random_plate()

    # Condition and travel count logic
    if vehicle_type_id == 1:  # Beater Car always poor condition
        condition_id = 4  # Poor Condition
        travel_count = 151
    else:
        condition_id = 1  # Brand New
        travel_count = 0

    async with pool.acquire() as conn:
        vehicle_type_name = await get_vehicle_type_name(conn, vehicle_type_id)
        condition_name = await get_condition_name(conn, condition_id)
        color = await fetch_random_color(conn, vehicle_type_id)
        appearance_description = await fetch_appearance_description(conn, vehicle_type_id, condition_id)

        resale_percent = CONDITION_TO_PERCENT.get(condition_name, 0.5)
        resale_value = int(BASE_PRICES.get(vehicle_type_name, cost) * resale_percent)

        await conn.execute(
            """
            INSERT INTO user_vehicle_inventory (
                user_id, vehicle_type_id, plate_number, color, appearance_description,
                condition, travel_count, resale_value, resale_percent, created_at, sold_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, EXTRACT(EPOCH FROM NOW())::int, NULL)
            """,
            user_id, vehicle_type_id, plate, color, appearance_description,
            condition_name, travel_count, resale_value, resale_percent
        )

    await interaction.response.send_message(
        f"✅ You purchased a {color} {vehicle_type_name} ({condition_name}) with plate `{plate}` that {appearance_description}.",
        ephemeral=True
    )


async def get_user_vehicles(pool, user_id: int) -> list:
    query = """
    SELECT
        cvt.name AS vehicle_type,
        uvi.vehicle_type_id,
        uvi.color,
        uvi.appearance_description,
        uvi.plate_number,
        uvi.condition,
        uvi.travel_count,
        uvi.resale_value,
        uvi.resale_percent,
        uvi.id
    FROM user_vehicle_inventory uvi
    JOIN cd_vehicle_type cvt ON cvt.id = uvi.vehicle_type_id
    WHERE uvi.user_id = $1
    ORDER BY uvi.id
    """
    return await pool.fetch(query, user_id)


async def remove_vehicle_by_id(pool, vehicle_id: int):
    await pool.execute("DELETE FROM user_vehicle_inventory WHERE id = $1", vehicle_id)


# ✅ View + Button to Trigger Purchase
class PurchaseVehicleView(discord.ui.View):
    def __init__(self, item: dict, cost: int):
        super().__init__(timeout=180)
        self.item = item
        self.cost = cost

    @discord.ui.button(label="Buy Vehicle", style=discord.ButtonStyle.success)
    async def buy_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        print(f"[DEBUG] Buy button clicked by {interaction.user.id}")
        await handle_vehicle_purchase(interaction, self.item, self.cost)
