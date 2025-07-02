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
from discord import Interaction, app_commands
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

# Create client and command tree
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

# Import and register commands (make sure your commands.py file has a register_commands function)
from commands import register_commands
register_commands(tree)

# Your testing guild ID (replace with your actual guild ID)
GUILD_ID = 1389059101165883482
guild = discord.Object(id=GUILD_ID)

@client.event
async def on_ready():
    global pool
    if pool is None:
        pool = await create_pool()
        await init_db(pool)

    print(f"Logged in as {client.user} (ID: {client.user.id})")
    # Sync commands only to your guild for faster updates during development
    await tree.sync(guild=guild)
    print("Commands synced to guild.")

# Run the bot
client.run(DISCORD_BOT_TOKEN)
