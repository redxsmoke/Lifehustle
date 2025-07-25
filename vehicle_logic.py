import random
import discord
from db_user import get_user, upsert_user, get_user_finances, upsert_user_finances
from globals import pool
from datetime import datetime, timezone

# Base prices for resale calculation
BASE_PRICES = {
    1: 10000,    # Beater Car
    2: 25000,    # Sedan Car
    3: 100000,   # Sports Car
    4: 75000,    # Pickup Truck
    5: 2000,     # Bike
    6: 18000     # Motorcycle
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

    finances = await get_user_finances(pool, user_id)
    if finances is None:
        finances = {
            "checking_account_balance": 0,
            "savings_account_balance": 0,
            "debt_balance": 0,
            "last_paycheck_claimed": datetime.fromtimestamp(0, tz=timezone.utc)
        }

    if finances["checking_account_balance"] < cost:
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

    # Deduct funds from finances properly
    finances["checking_account_balance"] -= cost
    await upsert_user_finances(pool, user_id, finances)

    plate = generate_random_plate()

    # Condition and travel count logic
    if vehicle_type_id == 1:  
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
        resale_value = int(BASE_PRICES.get(vehicle_type_id, cost) * resale_percent)
        print(f"[DEBUG] vehicle_type_id={vehicle_type_id}, resale_percent={resale_percent}, resale_value={resale_value}")
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
        cvt.class_type,
        uvi.location_id,
        uvi.id
    FROM user_vehicle_inventory uvi
    JOIN cd_vehicle_type cvt ON cvt.id = uvi.vehicle_type_id
    WHERE uvi.user_id = $1
    ORDER BY uvi.id
    """
    records = await pool.fetch(query, user_id)
    return [dict(record) for record in records]


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

class ConfirmSellView(discord.ui.View):
    def __init__(self, user_id, vehicles, timeout=60):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.vehicles = vehicles
        self.value = None  # will be True if confirmed, False if cancelled

    @discord.ui.button(label="Confirm Sell All", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This confirmation is not for you.", ephemeral=True)
            return

        self.value = True
        self.stop()
        await interaction.response.edit_message(content="✅ Confirmed! Selling all vehicles...", view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("> This confirmation is not for you.", ephemeral=True)
            return

        self.value = False
        self.stop()
        await interaction.response.edit_message(content="> ❌ Sale cancelled.", view=None)

async def sell_all_vehicles(interaction, user_id, vehicles, pool):
    try:
        if not vehicles:
            await interaction.response.send_message("> You have no vehicles to sell.", ephemeral=True)
            return 0  # Return 0 when no vehicles to sell

        total_resale = 0
        vehicle_ids = []

        vehicles = await pool.fetch(
            """
            SELECT uvi.id, uvi.vehicle_type_id, uvi.resale_percent, cvt.cost
            FROM user_vehicle_inventory uvi
            JOIN cd_vehicle_type cvt ON uvi.vehicle_type_id = cvt.id
            WHERE uvi.user_id = $1
            ORDER BY uvi.id
            """,
            user_id
        )

        for vehicle in vehicles:
            resale_percent = vehicle['resale_percent'] or 0.1  # fallback if null
            cost = vehicle['cost'] or 0
            resale = int(cost * resale_percent)
            total_resale += resale
            vehicle_ids.append(vehicle['id'])

        # Delete all vehicles in one query
        await pool.execute(
            "DELETE FROM user_vehicle_inventory WHERE id = ANY($1::int[])",
            vehicle_ids
        )

        from db_user import get_user_finances, upsert_user_finances
        from datetime import datetime, timezone

        finances = await get_user_finances(pool, user_id)
        if finances is None:
            finances = {
                "checking_account_balance": 0,
                "savings_account_balance": 0,
                "debt_balance": 0,
                "last_paycheck_claimed": datetime.fromtimestamp(0, tz=timezone.utc)
            }

        finances["checking_account_balance"] += total_resale
        await upsert_user_finances(pool, user_id, finances)

        await interaction.followup.send(
            content=f"> ✅ You sold **ALL** your vehicles for a total of ${total_resale:,}.",
            ephemeral=True  # or False, depending on what you want
        )

    except Exception as e:
        print(f"Error in sell_all_vehicles: {e}")
        import traceback
        traceback.print_exc()

        try:
            await interaction.response.send_message(
                "> ❌ Something went wrong while selling all your vehicles. Please try again later.",
                ephemeral=True
            )
        except discord.InteractionResponded:
            # fallback if the interaction was already responded to
            await interaction.followup.send(
                "> ❌ Something went wrong while selling all your vehicles. Please try again later.",
                ephemeral=True
            )