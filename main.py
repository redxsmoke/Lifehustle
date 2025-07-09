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

from db_user import add_unique_constraint

# --- Local Imports ---
from config import DISCORD_BOT_TOKEN, DATABASE_URL
from db_pool import init_db
from embeds import embed_message, COLOR_RED
from views import TravelButtons  # renamed import to match change

# New import for user DB functions
from db_user import ensure_user_exists

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
intents.members = True  # <<< Needed to receive member info and join events!
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

##### DATABASE UPDATES
async def reset_user_secret_button_table(pool):
    async with pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS user_secret_button;")
        await conn.execute("""
            CREATE TABLE user_secret_button (
                user_id BIGINT PRIMARY KEY,
                times_pressed INT NOT NULL DEFAULT 0,
                last_used TIMESTAMP
            );
        """)
    print("✅ user_secret_button table reset successfully.")
#### DATABASE UPDATES

async def setup_database():
    await init_db(globals.pool)
    await seed_grocery_categories(globals.pool)
    await seed_grocery_types(globals.pool)
    await drop_vehicle_appearence_table(globals.pool)
    await create_vehicle_appearance_table(globals.pool)
    await seed_vehicle_appearance(globals.pool)
    await reset_user_secret_button_table(globals.pool)


async def create_pool():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    globals.pool = await asyncpg.create_pool(DATABASE_URL, ssl=ssl_context)
    bot.pool = globals.pool  # Make pool accessible to cogs via bot.pool
    print("✅ Database connection pool created.")


# Entrypoint
async def main():
    await create_pool()
    await add_unique_constraint()
    await setup_database()
    print("✅ Starting bot...")
    await bot.start(DISCORD_BOT_TOKEN)


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
    await bot.load_extension("Easter_eggs.secretbutton")
    await bot.load_extension("Achievements.user_achievements")


    bot.add_view(TravelButtons())  # renamed to match change

    try:
        synced = await tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Error syncing commands in setup_hook: {e}")

    print("🛠️ setup_hook finished.")


@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.application_command:
        guild_id = interaction.guild.id if interaction.guild else None
        await ensure_user_exists(bot.pool, interaction.user.id, str(interaction.user), guild_id)
    await bot.process_application_commands(interaction)


if __name__ == "__main__":
    asyncio.run(main())
