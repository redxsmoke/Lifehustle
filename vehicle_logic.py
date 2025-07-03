import random
from typing import List, Dict
from db_user import get_user, upsert_user
import discord
from globals import pool

# Constants for colors  
BIKE_COLORS: List[str] = [
    "Red", "Blue", "Green", "Black", "White", "Yellow", "Orange", "Purple", "Gray", "Cyan"
]
CAR_COLORS: List[str] = [
    "Blue", "Red", "Black", "White", "Silver", "Green", "Yellow", "Orange", "Brown", "Maroon"
]

# Descriptions based on condition for bikes
BIKE_DESCRIPTIONS: Dict[str, List[str]] = {
    "Brand New": [
        "shines like it just rolled off the showroom floor",
        "with flawless paint and a fresh smell of rubber",
        "spotless, with every gear clicking perfectly",
        "gleaming under the light, ready for any ride",
        "brand new with tires that haven’t touched the road yet"
    ]
    # (other bike-condition lists omitted for brevity)
}

# Descriptions based on condition for cars
CAR_DESCRIPTIONS: Dict[str, List[str]] = {
    "Brand New": [
        "polished to perfection with that new-car scent",
        "engine humming smoothly with pristine paint",
        "chrome shining and tires untouched by the road",
        "fully loaded with all the latest features",
        "looks like it just came off the factory line"
    ],
    "Poor Condition": [
        "rust spots on the body and noisy engine",
        "frequent stalling and worn-out suspension",
        "windows cracked and seats torn",
        "exhaust fumes strong and paint faded",
        "lots of dents and a squeaky chassis"
    ]
    # (other car-condition lists omitted for brevity)
}

# Base prices for resale calculation
BASE_PRICES = {
    "Beater Car": 10000,
    "Sedan Car": 25000,
    "Sports Car": 100000,
    "Pickup Truck": 75000,
    "Bike": 2000,
    "Motorcycle": 18000
}

# Map vehicle_type_id to readable name
VEHICLE_TYPE_MAP = {
    1: "Beater Car",
    2: "Sedan Car",
    3: "Sports Car",
    4: "Pickup Truck",
    5: "Bike",
    6: "Bike",
    7: "Motorcycle"
}

# Condition → resale percent
CONDITION_TO_PERCENT = {
    "Brand New": 0.85,
    "Poor Condition": 0.30
}


async def handle_vehicle_purchase(
    interaction: discord.Interaction,
    item: dict,
    cost: int,
):
    user_id = interaction.user.id
    print(f"[DEBUG] Starting purchase: user_id={user_id}, cost={cost}, vehicle_type_id={item.get('vehicle_type_id')}")
    user = await get_user(pool, user_id)
    if user is None:
        await interaction.response.send_message("You don't have an account yet. Use `/start`.", ephemeral=True)
        return

    if user["checking_account"] < cost:
        await interaction.response.send_message(f"🚫 Not enough money to buy {item.get('type', 'that item')}.", ephemeral=True)
        return

    vehicle_type_id = item.get("vehicle_type_id")
    if vehicle_type_id is None:
        await interaction.response.send_message("🚫 Internal error: No vehicle_type_id provided.", ephemeral=True)
        return

    vehicle_type_name = VEHICLE_TYPE_MAP.get(vehicle_type_id, "Unknown")
    print(f"[DEBUG] Mapped vehicle_type_id {vehicle_type_id} → {vehicle_type_name!r}")

    # Enforce ownership limits
    if vehicle_type_id in (5, 6):  # Bike
        exists = await pool.fetchrow(
            "SELECT 1 FROM user_vehicle_inventory WHERE user_id = $1 AND vehicle_type_id IN (5,6) LIMIT 1",
            user_id
        )
        if exists:
            await interaction.response.send_message("🚲 You already own a bike. You can't buy another one.", ephemeral=True)
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

    # Generate random plate
    plate = generate_random_plate()

    # === FIXED: Beater Car branch forced by ID ===
    if vehicle_type_id == 1:  # Beater Car
        print("[DEBUG] BEATER CAR branch")
        condition = "Poor Condition"
        color = random.choice(CAR_COLORS)
        appearance_description = random.choice(CAR_DESCRIPTIONS["Poor Condition"])
        commute_count = 151  # fixed start
        resale_percent = CONDITION_TO_PERCENT["Poor Condition"]
        resale_value = int(BASE_PRICES["Beater Car"] * resale_percent)
    # === END FIX

    elif vehicle_type_id in (5, 6):  # Bike/Motorcycle
        condition = "Brand New"
        color = random.choice(BIKE_COLORS)
        appearance_description = random.choice(BIKE_DESCRIPTIONS["Brand New"])
        commute_count = 0
        resale_percent = CONDITION_TO_PERCENT["Brand New"]
        resale_value = int(BASE_PRICES["Bike"] * resale_percent)
    else:  # Other cars/trucks
        condition = "Brand New"
        color = random.choice(CAR_COLORS)
        appearance_description = random.choice(CAR_DESCRIPTIONS["Brand New"])
        commute_count = 0
        resale_percent = CONDITION_TO_PERCENT["Brand New"]
        resale_value = int(BASE_PRICES.get(vehicle_type_name, cost) * resale_percent)

    print(f"[DEBUG] condition={condition}, resale_percent={resale_percent}, resale_value={resale_value}")

    # Insert into inventory
    await pool.execute(
        """
        INSERT INTO user_vehicle_inventory (
            user_id, vehicle_type_id, plate_number, color, appearance_description,
            condition, commute_count, resale_value, resale_percent, created_at, sold_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, EXTRACT(EPOCH FROM NOW())::int, NULL)
        """,
        user_id, vehicle_type_id, plate, color, appearance_description,
        condition, commute_count, resale_value, resale_percent
    )

    await interaction.response.send_message(
        f"✅ You purchased a {color} {vehicle_type_name} ({condition}) with plate `{plate}` that {appearance_description}.",
        ephemeral=True
    )


async def get_user_vehicles(pool, user_id: int) -> list:
    query = """
    SELECT
        cvt.name AS vehicle_type,
        uvi.color,
        uvi.appearance_description,
        uvi.plate_number,
        uvi.condition,
        uvi.commute_count,
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


def generate_random_plate() -> str:
    return ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))
