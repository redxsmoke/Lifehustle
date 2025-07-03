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
    ],
    "Good Condition": [
        "well-maintained and runs smoothly",
        "with minor scratches but rides like a dream",
        "in great shape with reliable brakes",
        "showing some signs of use but nothing serious",
        "well-oiled chain and solid frame"
    ],
    "Fair Condition": [
        "with a few dents and a slightly creaky chain",
        "functional but could use a tune-up",
        "paint chipped but still roadworthy",
        "a bit worn but gets you where you need to go",
        "starting to show its age but dependable"
    ],
    "Poor Condition": [
        "rust creeping in on the frame",
        "tires nearly bald and brakes needing work",
        "lots of scratches and some squeaky parts",
        "chain slips occasionally and frame is bent",
        "a struggling ride with visible wear and tear"
    ],
    "Broken Down": [
        "barely holds together, likely to break down anytime",
        "frame cracked and tires flat",
        "rusted beyond repair and missing parts",
        "loud grinding noises with every pedal",
        "ready for the junkyard and needs a full rebuild"
    ]
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
    "Good Condition": [
        "runs reliably with only minor cosmetic blemishes",
        "engine purring and interior well-kept",
        "a clean ride that’s ready for any trip",
        "solid performance with no major issues",
        "well maintained and looks sharp"
    ],
    "Fair Condition": [
        "some scratches and dents but still drives fine",
        "engine sounds a little rough but works",
        "interior shows wear but seats are intact",
        "tires a bit worn but still have tread",
        "could use some repairs but functional"
    ],
    "Poor Condition": [
        "rust spots on the body and noisy engine",
        "frequent stalling and worn-out suspension",
        "windows cracked and seats torn",
        "exhaust fumes strong and paint faded",
        "lots of dents and a squeaky chassis"
    ],
    "Broken Down": [
        "won’t start and parts missing from the engine",
        "frame bent and interior ruined",
        "smoke pouring out with every attempt to drive",
        "tires flat and body full of holes",
        "ready for scrap, with no hope of repair"
    ]
}

async def handle_vehicle_purchase(
    interaction: discord.Interaction,
    item: dict,
    cost: int,
):
    user_id = interaction.user.id
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

    # Check ownership restrictions: only one bike or one car/truck allowed
    # Adjusted for your IDs: bike is 5 or 6, beater car is 1
    if vehicle_type_id in (5, 6):  # Bike
        exists = await pool.fetchrow(
            "SELECT 1 FROM user_vehicle_inventory WHERE user_id = $1 AND vehicle_type_id IN (5, 6) LIMIT 1",
            user_id
        )
        if exists:
            await interaction.response.send_message("🚲 You already own a bike. You can't buy another one.", ephemeral=True)
            return
    else:
        exists = await pool.fetchrow(
            "SELECT 1 FROM user_vehicle_inventory WHERE user_id = $1 AND vehicle_type_id NOT IN (5, 6) LIMIT 1",
            user_id
        )
        if exists:
            await interaction.response.send_message("🚗 You already own a car or truck. You can't buy another one.", ephemeral=True)
            return

    # Deduct money
    user["checking_account"] -= cost
    await upsert_user(pool, user_id, user)

    # Generate plate number using helper
    plate = generate_random_plate()

    # Assign attributes based on vehicle type
    if vehicle_type_id == 1:  # Beater Car
        condition = "Poor Condition"
        color = random.choice(CAR_COLORS)
        appearance_description = random.choice(CAR_DESCRIPTIONS.get(condition, [""]))
        commute_count = random.randint(151, 195)
    elif vehicle_type_id in (5, 6):  # Bikes
        condition = "Brand New"
        color = random.choice(BIKE_COLORS)
        appearance_description = random.choice(BIKE_DESCRIPTIONS.get(condition, [""]))
        commute_count = 0
    else:  # Other cars/trucks
        condition = "Brand New"
        color = random.choice(CAR_COLORS)
        appearance_description = random.choice(CAR_DESCRIPTIONS.get(condition, [""]))
        commute_count = 0

    # Fetch resale value from conditions table, fallback to cost if missing
    resale_row = await pool.fetchrow(
        "SELECT resale_value FROM cd_vehicle_condition WHERE vehicle_type_id = $1 AND condition = $2 LIMIT 1",
        vehicle_type_id,
        condition
    )
    resale_value = resale_row["resale_value"] if resale_row else cost

    # Insert vehicle into user_vehicle_inventory table
    await pool.execute(
        """
        INSERT INTO user_vehicle_inventory (
            user_id, vehicle_type_id, plate_number, color, appearance_description,
            condition, commute_count, resale_value, created_at, sold_at
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, EXTRACT(EPOCH FROM NOW())::int, NULL)
        """,
        user_id, vehicle_type_id, plate, color, appearance_description,
        condition, commute_count, resale_value
    )

    await interaction.response.send_message(
        f"✅ You purchased a {color} {item.get('type', 'vehicle')} ({condition}) with plate `{plate}` that {appearance_description}.",
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
        uvi.resale_value
    FROM user_vehicle_inventory uvi
    JOIN users u ON u.user_id = uvi.user_id
    JOIN cd_vehicle_type cvt ON cvt.id = uvi.vehicle_type_id
    WHERE u.user_id = $1
    """
    return await pool.fetch(query, user_id)


# SELL VEHICLE HELPER
async def remove_vehicle_by_id(pool, vehicle_id: int):
    async with pool.acquire() as conn:
        await conn.execute("DELETE FROM user_vehicle_inventory WHERE id = $1", vehicle_id)


# HELPER: Generate vehicle license plate
def generate_random_plate() -> str:
    return ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=8))
