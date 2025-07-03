# main.py

# --- Standard Library ---
import os
import ssl
import json
import asyncio
from datetime import datetime, timezone
from collections import defaultdict

# --- Third-Party Libraries ---
import asyncpg
import discord
from discord.ext import commands
from discord import app_commands
from db_user import reset_user_finances_table




# --- Local Imports ---
from config import (
    DISCORD_BOT_TOKEN,
    DATABASE_URL,
    PAYCHECK_AMOUNT,
    PAYCHECK_COOLDOWN_SECONDS,
    COLOR_GREEN,
    COLOR_RED,
    DISCORD_CHANNEL_ID,
)
from db_pool import init_db  # migrations / CREATE TABLE logic
from commands import register_commands  # registers slash commands
import globals  # holds pool and last_paycheck_times
from data_tier import seed_grocery_types, seed_grocery_categories

# --- Load JSON data ---
with open("commute_outcomes.json", "r") as f:
    COMMUTE_OUTCOMES = json.load(f)
with open("shop_items.json", "r", encoding="utf-8") as f:
    SHOP_ITEMS = json.load(f)
with open("categories.json", "r") as f:
    CATEGORIES = json.load(f)

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- SQL & Seed SQL ---
RESET_VEHICLE_CONDITION_SQL = '''
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
'''

CREATE_INVENTORY_SQL = '''
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
'''

ALTER_INVENTORY_SQL = '''
ALTER TABLE cd_vehicle_type
    ADD COLUMN IF NOT EXISTS emoji TEXT;
ALTER TABLE cd_grocery_category
    ADD COLUMN IF NOT EXISTS emoji TEXT;
ALTER TABLE user_grocery_inventory
    ADD COLUMN IF NOT EXISTS grocery_category_id INTEGER REFERENCES cd_grocery_category(id);
'''

CREATE_USER_FINANCES_SQL = '''
CREATE TABLE IF NOT EXISTS user_finances (
    id SERIAL PRIMARY KEY,
    user_id BIGINT UNIQUE NOT NULL,
    checking_account_balance NUMERIC(12,2) DEFAULT 0,
    savings_account_balance NUMERIC(12,2) DEFAULT 0,
    debt_balance NUMERIC(12,2) DEFAULT 0,
    last_paycheck_claimed TIMESTAMP
);
'''

# --- Table creation and seeding ---
async def create_inventory_tables(pool):
    async with pool.acquire() as conn:
        await conn.execute(CREATE_INVENTORY_SQL)
    print("✅ Inventory tables and views ensured.")

async def alter_inventory_tables(pool):
    async with pool.acquire() as conn:
        await conn.execute(ALTER_INVENTORY_SQL)
    print("✅ Altered inventory tables (emoji columns).")

async def reset_vehicle_condition_table(pool):
    async with pool.acquire() as conn:
        await conn.execute(RESET_VEHICLE_CONDITION_SQL)
    print("✅ Vehicle condition table reset.")



async def seed_vehicle_conditions(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT id, name FROM cd_vehicle_type;")
        vehicle_type_map = {r['name']: r['id'] for r in rows}

        standard_conditions = [
            ('Brand New', 0, 50, 85, 0),
            ('Good Condition', 51, 100, 70, 0),
            ('Fair Condition', 101, 150, 50, 0),
            ('Poor Condition', 151, 200, 30, 0),
            ('Broken Down', 201, 202, 0, 0),
        ]

        data = []
        for name, vid in vehicle_type_map.items():
            for desc, min_c, max_c, resale, start in standard_conditions:
                data.append((vid, desc, min_c, max_c, resale, start))

        await conn.executemany(
            """
            INSERT INTO cd_vehicle_condition 
                (vehicle_type_id, description, min_commute_count, max_commute_count, resale_percent, starting_commute_count)
            VALUES ($1, $2, $3, $4, $5, $6)
            ON CONFLICT (vehicle_type_id, description) DO NOTHING
            """,
            data
        )
    print("✅ Seeded vehicle conditions.")

async def setup_user_finances_table(pool):
    async with pool.acquire() as conn:
        await conn.execute(CREATE_USER_FINANCES_SQL)
    print("✅ user_finances table ensured.")


async def rename_username_column(pool):
    async with pool.acquire() as conn:
        result = await conn.fetchrow("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'users' AND column_name = 'username';
        """)
        if result:
            await conn.execute("""ALTER TABLE users RENAME COLUMN username TO user_name;""")
            print("✅ Renamed 'username' to 'user_name'.")
        else:
            print("ℹ️ Column 'username' does not exist or was already renamed.")

# --- Bot Events & Startup ---
async def create_pool():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    globals.pool = await asyncpg.create_pool(DATABASE_URL, ssl=ssl_context)
    print("✅ Database connection pool created.")

@bot.event
async def on_ready():
    if globals.pool is None:
        await create_pool()
        await init_db(globals.pool)
        await create_inventory_tables(globals.pool)
        await reset_vehicle_condition_table(globals.pool)
        await alter_inventory_tables(globals.pool)
        await seed_vehicle_conditions(globals.pool)
        await seed_grocery_categories(globals.pool)
        await seed_grocery_types(globals.pool)
        await setup_user_finances_table(globals.pool)
        await reset_user_finances_table(globals.pool)
        await rename_username_column(globals.pool)


    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    register_commands(tree)
    print("✅ Commands registered.")

    try:
        await tree.sync()
        print("✅ Slash commands synced.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")



# --- Run the Bot ---
if __name__ == "__main__":
    bot.run(DISCORD_BOT_TOKEN)
