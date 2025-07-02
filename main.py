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
import commands
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
categories = load_categories()
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

def embed_message(title: str, description: str, color: discord.Color = discord.Color.blue()) -> discord.Embed:
    return discord.Embed(title=title, description=description, color=color)

#LOAD COMMUTE OUTCOMES JSON
with open("commute_outcomes.json", "r") as f:
    COMMUTE_OUTCOMES = json.load(f)

#LOAD SHOP ITEMS JSON
with open("shop_items.json", "r", encoding="utf-8") as f:
    SHOP_ITEMS = json.load(f)
#LOAD CATEGORIES JSON.
with open('categories.json', 'r') as f:
    categories = json.load(f)

intents = discord.Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)


@client.event
async def on_ready():
    global pool
    if pool is None:
        pool = await create_pool()
        await init_db(pool)

    print(f'Logged in as {client.user} (ID: {client.user.id})')
    await tree.sync()
    print("Commands synced.")

       

# --- Run bot ---



client.run(DISCORD_BOT_TOKEN)

 
