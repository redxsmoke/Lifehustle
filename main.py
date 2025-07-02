# main.py

# --- Standard Library ---
import json

# --- Third‑Party Libraries ---
import discord
from discord.ext import commands

# --- Local Imports ---
from config import DISCORD_BOT_TOKEN
from db_pool import create_pool, init_db
from globals import pool
from commands import register_commands  # your register_commands(tree) function

# Load any JSON data you need here:
with open("commute_outcomes.json", "r") as f:
    COMMUTE_OUTCOMES = json.load(f)
with open("shop_items.json", "r", encoding="utf-8") as f:
    SHOP_ITEMS = json.load(f)
with open("categories.json", "r") as f:
    CATEGORIES_DATA = json.load(f)

# Intents
intents = discord.Intents.default()
intents.message_content = True

# Create a commands.Bot (NOT discord.Client)
bot = commands.Bot(command_prefix=None, intents=intents)
tree = bot.tree

# DEBUG: before registering
print("⏳ [Main] before register_commands, tree has:", [c.name for c in tree.walk_commands()])

# Register all commands
register_commands(tree)

# DEBUG: after registering
print("✅ [Main] after register_commands, tree has:", [c.name for c in tree.walk_commands()])

@bot.event
async def on_ready():
    global pool
    if pool is None:
        pool = await create_pool()
        await init_db(pool)

    print(f"Logged in as {bot.user} (ID: {bot.user.id})")

    # Do a GLOBAL sync
    await bot.tree.sync()
    print("✅ [Main] after GLOBAL sync, tree has:", [c.name for c in tree.walk_commands()])

bot.run(DISCORD_BOT_TOKEN)
