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

# Register slash commands
from commands import register_commands
print("⏳ [Main] before register_commands, tree has:", [c.name for c in tree.walk_commands()])
register_commands(tree)
print("✅ [Main] after register_commands, tree has:", [c.name for c in tree.walk_commands()])

# Optional: specify dev guild for faster sync
DEV_GUILD_ID = 1389059101165883482  # Replace with your dev server ID
dev_guild = discord.Object(id=DEV_GUILD_ID)

@bot.event
async def on_ready():
    global pool
    if pool is None:
        pool = await create_pool()
        await init_db(pool)

    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")

    try:
        await tree.sync(guild=dev_guild)  # For testing/dev only
        print("✅ Slash commands synced to dev guild.")
    except Exception as e:
        print(f"❌ Error syncing commands: {e}")

    print("✅ [Main] after sync, tree has:", [c.name for c in tree.walk_commands()])

# --- Run the Bot ---
bot.run(DISCORD_BOT_TOKEN)
