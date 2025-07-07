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
from db_pool import init_db
from embeds import embed_message, COLOR_RED
from views import TravelButtons  # renamed import to match change
from create_education_occupation_tables import setup

# Rename imports to avoid name conflicts
from Bot_commands.commands import register_commands as register_general_commands
from Bot_commands.travel_command import register_commands as register_travel_commands
from Bot_commands.lifecheck_command import register_commands as register_lifecheck_commands

from data_tier import (
    seed_grocery_types,
    seed_grocery_categories,
    drop_vehicle_appearence_table,
    create_vehicle_appearance_table,
    seed_vehicle_appearance,
)

import globals

# Bot Setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree


@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error):
    print(f"❌ Slash command error: {error}")
    try:
        await interaction.response.send_message(
            embed=embed_message("❌ Error", str(error), COLOR_RED),
            ephemeral=True,
        )
    except Exception as e:
        print(f"Failed to send error message: {e}")


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} (ID: {bot.user.id})")


@bot.event
async def setup_hook():
    print("🛠️ setup_hook starting...")

    # Register commands from all modules
    register_general_commands(tree)
    register_travel_commands(tree)
    await register_lifecheck_commands(bot)

    # Load your cog extensions - extensions can access pool via bot.pool
    await bot.load_extension("Bot_commands.bank_commands")
    await bot.load_extension("Bot_occupations.occupations_commands")
    await bot.load_extension("Bot_occupations.career_path_command")

    bot.add_view(TravelButtons())  # renamed to match change

    # Register the test say command cog
    bot.add_cog(TestCommands(bot))

    try:
        synced = await tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Error syncing commands in setup_hook: {e}")

    print("🛠️ setup_hook finished.")


# New Cog for /say command
class TestCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="say", description="Make the bot say a message")
    @app_commands.describe(message="Message for the bot to send")
    async def say(self, interaction: discord.Interaction, message: str):
        await interaction.response.send_message(message)


# DB Setup
async def create_pool():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    globals.pool = await asyncpg.create_pool(DATABASE_URL, ssl=ssl_context)
    bot.pool = globals.pool  # Make pool accessible to cogs via bot.pool
    print("✅ Database connection pool created.")


async def setup_database():
    await init_db(globals.pool)
    await seed_grocery_categories(globals.pool)
    await seed_grocery_types(globals.pool)
    await drop_vehicle_appearence_table(globals.pool)
    await create_vehicle_appearance_table(globals.pool)
    await seed_vehicle_appearance(globals.pool)
    await setup()  # Setup education and occupation tables


# Entrypoint
async def main():
    await create_pool()
    await setup_database()
    print("✅ Starting bot...")
    await bot.start(DISCORD_BOT_TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
