# main.py

# --- Standard Library ---
import asyncio
import datetime
import json
import os
import random
import re
import ssl
import string
import time
from collections import defaultdict

# --- Third-Party Libraries ---
import asyncpg
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View

# --- Local Project Imports ---
from config import (
    DISCORD_BOT_TOKEN,
    DATABASE_URL,
    NOTIFY_USER_ID,
    DISCORD_CHANNEL_ID,
    PAYCHECK_AMOUNT,
    PAYCHECK_COOLDOWN_SECONDS,
    CATEGORIES,
    GAME_RESPONSE_TIMEOUT,
    MAX_GUESSES,
    COLOR_GREEN,
    COLOR_RED,
    COLOR_ORANGE,
    COLOR_TEAL,
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

# Initialize intents
intents = discord.Intents.default()
intents.message_content = True

# Create bot and use its built‑in command tree
bot = commands.Bot(command_prefix=None, intents=intents)
tree = bot.tree

# DEBUG: before registering any commands
print("⏳ [Main] before register_commands, tree has:", [c.name for c in tree.walk_commands()])

# Import and register your slash commands
from commands import register_commands
register_commands(tree)

# DEBUG: after registration
print("✅ [Main] after register_commands, tree has:", [c.name for c in tree.walk_commands()])

# Testing guild ID for fast sync
GUILD_ID = 1389059101165883482
guild = discord.Object(id=GUILD_ID)

@bot.event
async def on_ready():
    global pool
    if pool is None:
        pool = await create_pool()
        await init_db(pool)

    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Sync just to your testing guild
    await bot.tree.sync(guild=guild)
    print("Commands synced to guild.")
    # DEBUG: after sync
    print("✅ [Main] after sync, tree has:", [c.name for c in tree.walk_commands()])

# Run the bot
bot.run(DISCORD_BOT_TOKEN)
