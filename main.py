# --- Standard Library ---
import asyncio
import json
import time
from data_tier import seed_grocery_types, seed_grocery_categories
from collections import defaultdict

# --- Third-Party Libraries ---
import asyncpg
import discord
from discord import app_commands
from discord.ext import commands

# --- Local Imports ---
from config import (
    DISCORD_BOT_TOKEN,
    DATABASE_URL,
    PAYCHECK_AMOUNT,
    PAYCHECK_COOLDOWN_SECONDS,
    CATEGORIES,
    GAME_RESPONSE_TIMEOUT,
    MAX_GUESSES,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_ORANGE,
    COLOR_TEAL,
    DISCORD_CHANNEL_ID,
)
from db_pool import create_pool, init_db
from db_user import get_user, upsert_user
from globals import pool
from defaults import DEFAULT_USER
from autocomplete import (
    category_autocomplete,
    commute_method_autocomplete,
    commute_direction_autocomplete,
)
from category_loader import load_categories
from utilities import handle_commute, handle_purchase
from vehicle_logic import handle_vehicle_purchase
from embeds import embed_message
from views import (
    CommuteButtons,
    TransportationShopButtons,
    SellFromStashView,
    GroceryCategoryView,
    GroceryStashPaginationView,
)

# Load JSON data
with open("commute_outcomes.json", "r") as f:
    COMMUTE_OUTCOMES = json.load(f)

with open("shop_items.json", "r", encoding="utf-8") as f:
    SHOP_ITEMS = json.load(f)

with open("categories.json", "r") as f:
    categories = json.load(f)

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree  # Shortcut

# --- SQL: Create and Reset Tables ---
RESET_VEHICLE_CONDITION_SQL = """
DROP TABLE IF EXISTS cd_vehicle_condition;

CREATE TABLE cd_vehicle_condition (
    id SERIAL PRIMARY KEY,
    vehicle_type_id INTEGER NOT NULL REFERENCES cd_vehicle_type(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    min_commute_count INTEGER NOT NULL,
    max_commute_count INTEGER NOT NULL,
    resale_percent INTEGER NOT NULL,
    starting_commute_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(vehicle_type_id, description)
);
"""

CREATE_INVENTORY_SQL = """
CREATE TABLE IF NOT EXISTS cd_vehicle_type (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    cost INTEGER NOT NULL,
    emoji TEXT
);

CREATE TABLE IF NOT EXISTS user_vehicle_inventory (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    vehicle_type_id INTEGER NOT NULL REFERENCES cd_vehicle_type(id),
    color TEXT NOT NULL,
    appearance_description TEXT NOT NULL,
    plate_number TEXT,
    condition TEXT NOT NULL,
    commute_count INTEGER NOT NULL DEFAULT 0,
    resale_value INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sold_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS cd_grocery_category (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    emoji TEXT
);

CREATE TABLE IF NOT EXISTS cd_grocery_type (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    category_id INTEGER NOT NULL REFERENCES cd_grocery_category(id),
    cost INTEGER NOT NULL,
    emoji TEXT
);

CREATE TABLE IF NOT EXISTS user_grocery_inventory (
    id SERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    grocery_type_id INTEGER NOT NULL REFERENCES cd_grocery_type(id),
    quantity INTEGER NOT NULL DEFAULT 1,
    expiration_date DATE,
    condition TEXT NOT NULL,
    resale_value INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sold_at TIMESTAMP
);

CREATE OR REPLACE VIEW user_item_summary AS
SELECT 
    uvi.user_id,
    'vehicle' AS item_type,
    vt.name AS item_name,
    uvi.color,
    uvi.appearance_description AS description,
    uvi.plate_number,
    uvi.condition,
    vt.cost AS base_cost,
    uvi.resale_value,
    uvi.created_at,
    vt.emoji
FROM user_vehicle_inventory uvi
JOIN cd_vehicle_type vt ON uvi.vehicle_type_id = vt.id
WHERE uvi.sold_at IS NULL

UNION ALL

SELECT 
    ugi.user_id,
    'grocery' AS item_type,
    gt.name AS item_name,
    NULL AS color,
    CONCAT('Qty: ', ugi.quantity, ', Exp: ', ugi.expiration_date) AS description,
    NULL AS plate_number,
    ugi.condition,
    gt.cost AS base_cost,
    ugi.resale_value,
    ugi.created_at,
    gt.emoji
FROM user_grocery_inventory ugi
JOIN cd_grocery_type gt ON ugi.grocery_type_id = gt.id
WHERE ugi.sold_at IS NULL;
"""

ALTER_INVENTORY_SQL = """
ALTER TABLE cd_vehicle_type
    ADD COLUMN IF NOT EXISTS emoji TEXT;

ALTER TABLE cd_grocery_category
    ADD COLUMN IF NOT EXISTS emoji TEXT;

ALTER TABLE cd_grocery_type
    ADD COLUMN IF NOT EXISTS emoji TEXT;
"""

async def create_inventory_tables(pool):
    async with pool.acquire() as conn:
        await conn.execute(CREATE_INVENTORY_SQL)
        print("✅ Inventory tables and views ensured.")

async def alter_inventory_tables(pool):
    async with pool.acquire() as conn:
        await conn.execute(ALTER_INVENTORY_SQL)
        print("✅ Altered inventory tables to add emoji columns if missing.")

async def reset_vehicle_condition_table(pool):
    async with pool.acquire() as conn:
        await conn.execute(RESET_VEHICLE_CONDITION_SQL)
        print("✅ Vehicle condition table reset.")

async def seed_vehicle_types(pool):
    vehicle_types = [
        ("Blue Car", 10000, "🚙"),
        ("Red Car", 25000, "🚗"),
        ("Sports Car", 100000, "🏎️"),
        ("Pickup Truck", 30000, "🛻"),
        ("Bike", 1500, "🚲"),
    ]
    async with pool.acquire() as conn:
        for name, cost, emoji in vehicle_types:
            await conn.execute(
                """
                INSERT INTO cd_vehicle_type (name, cost, emoji)
                VALUES ($1, $2, $3)
                ON CONFLICT (name) DO NOTHING
                """,
                name,
                cost,
                emoji,
            )
    print("✅ Seeded vehicle types.")

async def seed_vehicle_conditions(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name FROM cd_vehicle_type;")
        vehicle_type_map = {r['name']: r['id'] for r in rows}

        conditions_data = []

        standard_conditions = [
            ('Brand New', 0, 50, 85, 0),
            ('Good Condition', 51, 100, 70, 0),
            ('Fair Condition', 101, 150, 50, 0),
            ('Poor Condition', 151, 200, 30, 0),
            ('Broken Down', 201, 202, 0, 0),
        ]

        for vehicle_name, vehicle_id in vehicle_type_map.items():
            if vehicle_name == 'Blue Car':
                conditions_data.extend([
                    (vehicle_id, 'Brand New', 0, 50, 85, 0),
                    (vehicle_id, 'Good Condition', 51, 100, 70, 0),
                    (vehicle_id, 'Fair Condition', 101, 150, 50, 0),
                    (vehicle_id, 'Poor Condition', 151, 200, 30, 151),
                    (vehicle_id, 'Broken Down', 201, 202, 0, 0),
                ])
            else:
                for desc, min_c, max_c, resale, start_c in standard_conditions:
                    conditions_data.append((vehicle_id, desc, min_c, max_c, resale, start_c))

        await conn.executemany(
            """
            INSERT INTO cd_vehicle_condition 
                (vehicle_type_id, description, min_commute_count, max_commute_count, resale_percent, starting_commute_count)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (vehicle_type_id, description) DO NOTHING
            """,
            conditions_data,
        )
    print("✅ Seeded vehicle conditions with starting commute counts.")

@bot.event
async def on_ready():
    global pool
    if pool is None:
        pool = await create_pool()
        await init_db(pool)
        await create_inventory_tables(pool)
        await reset_vehicle_condition_table(pool)
        await alter_inventory_tables(pool)
        await seed_vehicle_types(pool)
        await seed_vehicle_conditions(pool)
        await seed_grocery_categories(pool)
        await seed_grocery_types(pool)

    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    try:
        await tree.sync()
        print("✅ Slash commands synced to dev guild.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

    print("✅ [Main] after sync, tree has:", [c.name for c in tree.walk_commands()])

# Register slash commands after bot defined
from commands import register_commands
print("⏳ [Main] before register_commands, tree has:", [c.name for c in tree.walk_commands()])
register_commands(tree)
print("✅ [Main] after register_commands, tree has:", [c.name for c in tree.walk_commands()])

# --- Run the Bot ---
bot.run(DISCORD_BOT_TOKEN)
