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
from db_pool import init_db
from commands import register_commands
import globals
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

# --- Bot Events ---
@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def setup_hook():
    await bot.wait_until_ready()
    register_commands(tree)
    print("✅ Commands registered.")
    try:
        await tree.sync()
        print("✅ Slash commands synced.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

# --- Database Setup ---
async def create_pool():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    globals.pool = await asyncpg.create_pool(DATABASE_URL, ssl=ssl_context)
    print("✅ Database connection pool created.")

async def setup_database():
    await init_db(globals.pool)
    await seed_grocery_categories(globals.pool)
    await seed_grocery_types(globals.pool)
    await reset_user_finances_table(globals.pool)

# --- Entry Point ---
async def main():
    await create_pool()
    await setup_database()
    print("✅ Starting bot...")
    await bot.start(DISCORD_BOT_TOKEN)

# --- Run Bot ---
if __name__ == "__main__":
    asyncio.run(main())
