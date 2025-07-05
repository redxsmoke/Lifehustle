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
from embeds import embed_message
from embeds import COLOR_RED
from views import TravelButtons  # renamed import to match change
from create_education_occupation_tables import setup_db

# Rename imports to avoid name conflicts
from Bot_commands.commands import register_commands as register_general_commands
from Bot_commands.travel_command import register_commands as register_travel_commands  # renamed import
from Bot_commands.vitals_command import register_commands as register_vitals_commands  # Added import for vitals

from data_tier import seed_grocery_types, seed_grocery_categories, drop_vehicle_appearence_table, create_vehicle_appearance_table, seed_vehicle_appearance

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
            ephemeral=True
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
    register_travel_commands(tree)  # renamed call
    await register_vitals_commands(bot)

    # Load your cog extensions
    await bot.load_extension("Bot_commands.bank_commands")
    bot.add_view(TravelButtons())  # renamed to match change

    try:
        synced = await tree.sync()
        print(f"✅ Synced {len(synced)} slash commands.")
    except Exception as e:
        print(f"❌ Error syncing commands in setup_hook: {e}")

    print("🛠️ setup_hook finished.")

# DB Setup
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
    await drop_vehicle_appearence_table(globals.pool)
    await create_vehicle_appearance_table(globals.pool)
    await seed_vehicle_appearance(globals.pool)
    await setup_db

# Entrypoint
async def main():
    await create_pool()
    await setup_database()
    print("✅ Starting bot...")
    await bot.start(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    asyncio.run(main())


import asyncio
import asyncpg

EDUCATION_LEVELS = [
    (1, "None", 0, "No formal education"),
    (2, "High School Diploma", 1, "Basic education level"),
    (3, "Associate's Degree", 2, "Some college"),
    (4, "Bachelor's Degree", 3, "Undergraduate degree"),
    (5, "Master's Degree", 4, "Graduate degree"),
    (6, "PhD", 5, "Doctorate, highest academic level"),
]

OCCUPATIONS = [
    (1, "Professional Cuddler", 40, 1, "Must love hugs", True),
    (2, "Senior Bubble Wrap Popper", 35, 1, "PhD in stress relief", True),
    (3, "Street Performer", 30, 1, "Charismatic personality", True),
    (4, "Dog Walker", 45, 1, "Love for animals", True),
    (5, "Human Statue", 50, 1, "Ability to stand still for hours", True),
    (6, "Professional Line Sitter", 30, 1, "Patience and perseverance", True),
    (7, "Freelance Meme Curator", 45, 1, "Social media savvy", True),
    (8, "Test Subject", 50, 1, "Willingness to participate", True),
    (9, "Coffee Taster", 55, 1, "Highly sensitive palate", True),
    (10, "Parking Enforcement Officer", 60, 1, "Attention to detail", True),
    (11, "Grocery Store Clerk", 50, 2, None, True),
    (12, "Delivery Driver", 70, 2, "Driver’s license", True),
    (13, "Professional Mourner", 70, 2, "Empathy and acting skills", True),
    (14, "Pet Food Taster", 60, 2, "Strong stomach required", True),
    (15, "Professional Whistler", 80, 2, "Exceptional whistling talent", True),
    (16, "Ice Cream Truck Driver", 65, 2, "Driving license", True),
    (17, "Event Setup Crew", 55, 2, "Physical fitness", True),
    (18, "Janitor", 50, 2, "Reliability", True),
    (19, "Waiter/Waitress", 60, 2, "Good communication skills", True),
    (20, "Amusement Park Ride Operator", 65, 2, "Safety conscious", True),
    (21, "Office Assistant", 100, 3, "Basic computer skills", True),
    (22, "Ice Cream Flavor Developer", 90, 3, "Creative palate", True),
    (23, "Waterslide Tester", 120, 3, "Thrill-seeking", True),
    (24, "Odor Judge", 100, 3, "Nose for smells", True),
    (25, "Social Media Manager", 110, 3, "Social media savvy", True),
    (26, "Medical Assistant", 130, 3, "Medical knowledge", True),
    (27, "Graphic Designer", 125, 3, "Creativity", True),
    (28, "Lab Technician", 115, 3, "Detail-oriented", True),
    (29, "Event Coordinator", 120, 3, "Organization skills", True),
    (30, "Legal Assistant", 110, 3, "Knowledge of legal procedures", True),
    (31, "Software Developer", 200, 4, "Programming skills", True),
    (32, "VR World Architect", 150, 4, "Creativity + coding skills", True),
    (33, "Accountant", 180, 4, "Finance knowledge", True),
    (34, "Market Research Analyst", 170, 4, "Analytical skills", True),
    (35, "Engineer", 190, 4, "Engineering degree", True),
    (36, "Teacher", 160, 4, "Teaching skills", True),
    (37, "Journalist", 150, 4, "Strong writing skills", True),
    (38, "Architect", 190, 4, "Design skills", True),
    (39, "IT Consultant", 180, 4, "Technical knowledge", True),
    (40, "Business Analyst", 170, 4, "Analytical skills", True),
    (41, "Research Scientist", 250, 5, "Scientific knowledge", True),
    (42, "University Lecturer", 220, 5, "Teaching and research skills", True),
    (43, "Data Scientist", 240, 5, "Advanced data analysis", True),
    (44, "Clinical Psychologist", 230, 5, "Psychological knowledge", True),
    (45, "Environmental Consultant", 210, 5, "Environmental expertise", True),
    (46, "Pharmacist", 260, 5, "Medical knowledge", True),
    (47, "Urban Planner", 220, 5, "Planning skills", True),
    (48, "Economist", 230, 5, "Economic expertise", True),
    (49, "Statistician", 240, 5, "Statistical analysis", True),
    (50, "Policy Analyst", 210, 5, "Policy knowledge", True),
    (51, "Medical Doctor", 300, 6, "Medical license", True),
    (52, "University Professor", 220, 6, "Teaching skills", True),
    (53, "Head Honcho of Unicorn Wrangling", 250, 6, "Mythical creature expertise", True),
    (54, "Time-Traveling Tax Auditor", 300, 6, "Paradox-proof accounting", True),
    (55, "Chief Scientist", 280, 6, "Leadership and science", True),
    (56, "Aerospace Engineer", 290, 6, "Aeronautics expertise", True),
    (57, "Philosopher", 210, 6, "Deep thinking", True),
    (58, "Geneticist", 270, 6, "Genetic research", True),
    (59, "Quantum Physicist", 300, 6, "Quantum mechanics expertise", True),
    (60, "Galactic Ambassador", 300, 6, "Diplomacy and charm", True),
]

async def seed_education_levels(conn):
    query = """
    INSERT INTO cd_education_levels (cd_education_level_id, description, level_order, notes)
    VALUES ($1, $2, $3, $4)
    ON CONFLICT (cd_education_level_id) DO NOTHING;
    """
    for level in EDUCATION_LEVELS:
        await conn.execute(query, *level)

async def seed_occupations(conn):
    query = """
    INSERT INTO cd_occupations (cd_occupation_id, description, pay_rate, required_shifts_per_day, education_level_id, other_requirements, active)
    VALUES ($1, $2, $3, $4, $5, $6, $7)
    ON CONFLICT (cd_occupation_id) DO NOTHING;
    """
    for occ in OCCUPATIONS:
        await conn.execute(query, *occ)

async def main():
    conn = await asyncpg.connect(user='your_user', password='your_password', database='your_db', host='localhost')
    try:
        await seed_education_levels(conn)
        await seed_occupations(conn)
        print("Seed data inserted successfully.")
    finally:
        await conn.close()

if __name__ == '__main__':
    asyncio.run(main())

