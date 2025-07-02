# --- Standard Library ---
import asyncio
import json
import time
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

CREATE_INVENTORY_SQL = """
-- Vehicle Types with cost
CREATE TABLE IF NOT EXISTS cd_vehicle_type (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    cost INTEGER NOT NULL
);

-- Vehicle Condition Thresholds
CREATE TABLE IF NOT EXISTS cd_vehicle_condition (
    name TEXT PRIMARY KEY,
    min_commute_count INTEGER,
    max_commute_count INTEGER,
    resale_percent INTEGER
);

-- User Vehicle Inventory
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

-- Vehicle Ownership History
CREATE TABLE IF NOT EXISTS vehicle_ownership_history (
    id SERIAL PRIMARY KEY,
    vehicle_inventory_id INTEGER NOT NULL REFERENCES user_vehicle_inventory(id) ON DELETE CASCADE,
    owner_user_id BIGINT NOT NULL,
    acquired_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    sold_at TIMESTAMP
);

-- Grocery Categories
CREATE TABLE IF NOT EXISTS cd_grocery_category (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL
);

-- Grocery Types with Category and Cost
CREATE TABLE IF NOT EXISTS cd_grocery_type (
    id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    category_id INTEGER NOT NULL REFERENCES cd_grocery_category(id),
    cost INTEGER NOT NULL
);

-- User Grocery Inventory
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

-- User Item Summary View
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
    uvi.created_at
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
    ugi.created_at
FROM user_grocery_inventory ugi
JOIN cd_grocery_type gt ON ugi.grocery_type_id = gt.id
WHERE ugi.sold_at IS NULL;
"""

async def create_inventory_tables(pool):
    async with pool.acquire() as conn:
        await conn.execute(CREATE_INVENTORY_SQL)
        print("✅ Inventory tables and views ensured.")

@bot.event
async def on_ready():
    global pool
    if pool is None:
        pool = await create_pool()
        await init_db(pool)
        await create_inventory_tables(pool)

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
