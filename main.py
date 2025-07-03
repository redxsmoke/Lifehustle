# --- Standard Library ---
import os
import ssl
import json
import asyncio
from datetime import datetime
from collections import defaultdict

# --- Third-Party ---
import asyncpg
import discord
from discord.ext import commands
from discord import app_commands

# --- Local Imports ---
from config import DISCORD_BOT_TOKEN, DATABASE_URL
from db_user import reset_user_finances_table
from db_pool import init_db
from commands import register_commands
from data_tier import seed_grocery_types, seed_grocery_categories
import globals

# --- Load JSON Data ---
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

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

@bot.event
async def setup_hook():
    print("🛠️ setup_hook starting...")
    register_commands(tree)
    try:
        synced = await tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Error syncing commands in setup_hook: {e}")
    print("🛠️ setup_hook finished.")

# --- DB Setup ---
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

# --- Entrypoint ---
async def main():
    await create_pool()
    await setup_database()
    print("✅ Starting bot...")
    # Start the bot (this will block until bot closes)
    await bot.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
