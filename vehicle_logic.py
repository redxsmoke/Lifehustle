import datetime
from db_user import get_user, upsert_user
import discord
from globals import pool


async def handle_vehicle_purchase(interaction: discord.Interaction, item: dict, cost: int):
    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    if user is None:
        await interaction.response.send_message("You don't have an account yet. Use `/start`.", ephemeral=True)
        return

    if user["checking_account"] < cost:
        await interaction.response.send_message(f"🚫 Not enough money to buy {item.get('type', 'that item')}.", ephemeral=True)
        return

    inventory = user.get("inventory", [])
    print(f"DEBUG: Inventory at purchase check: {inventory}")

    def is_same_vehicle(v1, v2):
        if not isinstance(v1, dict) or not isinstance(v2, dict):
            return False
        # Check by plate or tag
        if "plate" in v1 and "plate" in v2 and v1["plate"] == v2["plate"]:
            return True
        if "tag" in v1 and "tag" in v2 and v1["tag"] == v2["tag"]:
            return True
        return False

    # Check if user already owns a bike (only one allowed)
    if item.get("type") == "Bike":
        for owned in inventory:
            if isinstance(owned, dict) and owned.get("type") == "Bike":
                await interaction.response.send_message("🚲 You already own a bike. You can't buy another one.", ephemeral=True)
                return

    # Check if user already owns any car/truck (only one allowed)
    else:
        for owned in inventory:
            if isinstance(owned, dict) and owned.get("type") != "Bike":
                # Check if this car is actually the same plate/tag as new one — if yes, block; else allow new different car (optional)
                # But since you want only one car, block if any car owned:
                await interaction.response.send_message("🚗 You already own a car or truck. You can't buy another one.", ephemeral=True)
                return

    # Deduct money and add vehicle to inventory
    user["checking_account"] -= cost
    inventory.append(item)
    user["inventory"] = inventory

    await upsert_user(pool, user_id, user)

    await interaction.response.send_message(f"✅ You purchased a {item.get('type', 'vehicle')} for ${cost:,}!", ephemeral=True)


async def get_user_vehicles(pool, user_id: int):
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
