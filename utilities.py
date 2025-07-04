import asyncio
import datetime
import json
import random
import string
import unicodedata
import re

import discord

from db_user import get_user, upsert_user
from globals import pool
from embeds import embed_message

# ───────────────────────────────────────────────
# VEHICLE CONDITION THRESHOLDS
# ───────────────────────────────────────────────

def condition_from_usage(commute_count: int) -> str:
    if commute_count < 50:
        return "Brand New"
    elif commute_count < 100:
        return "Good Condition"
    elif commute_count < 150:
        return "Fair Condition"
    elif commute_count < 200:
        return "Poor Condition"
    else:
        return "Broken Down"

# ───────────────────────────────────────────────
# COMMUTE UTILITIES
# ───────────────────────────────────────────────

async def update_vehicle_condition_and_description(pool, user_id: int, vehicle_id: int, vehicle_type_id: int, commute_count: int):
    """
    Updates the vehicle's commute count, condition, and randomly selects a new appearance description
    from cd_vehicle_appearance matching vehicle_type_id and condition.
    """
    new_condition = condition_from_usage(commute_count)

    # Map condition string to condition_id in db (1-based index matching your example)
    condition_map = {
        "Brand New": 1,
        "Good Condition": 2,
        "Fair Condition": 3,
        "Poor Condition": 4,
        "Broken Down": 5,
    }
    condition_id = condition_map.get(new_condition)
    if condition_id is None:
        raise ValueError(f"Unknown condition: {new_condition}")

    # Fetch a random appearance description from cd_vehicle_appearance matching vehicle_type_id and condition_id
    async with pool.acquire() as conn:
        description_record = await conn.fetchrow(
            """
            SELECT description 
            FROM cd_vehicle_appearance
            WHERE vehicle_type_id = $1 AND condition_id = $2
            ORDER BY RANDOM()
            LIMIT 1
            """,
            vehicle_type_id, condition_id
        )
        if not description_record:
            description = "No description available."
        else:
            description = description_record["description"]

        # Update the vehicle record with new commute_count, condition, and appearance_description
        await conn.execute(
            """
            UPDATE user_vehicle_inventory
            SET commute_count = $1, condition = $2, appearance_description = $3
            WHERE user_id = $4 AND vehicle_id = $5
            """,
            commute_count, new_condition, description, user_id, vehicle_id
        )
    return new_condition, description

# ───────────────────────────────────────────────
# Parse amount strings like '1000', '1k', '2.5m', or 'all'
# ───────────────────────────────────────────────

def parse_amount(amount_str: str) -> int | None:
    """
    Parse amount strings like '1000', '1k', '2.5m', or 'all'.
    Returns:
      - int amount if valid
      - -1 if 'all' (special flag)
      - None if invalid input
    """
    s = amount_str.strip().lower()
    if s == "all":
        return -1  # special flag meaning "all funds"

    # Remove commas
    s = s.replace(',', '')

    try:
        # Check for suffixes
        if s.endswith('k'):
            return int(float(s[:-1]) * 1_000)
        elif s.endswith('m'):
            return int(float(s[:-1]) * 1_000_000)
        else:
            # Just a plain integer number
            return int(float(s))
    except ValueError:
        return None

# ───────────────────────────────────────────────
# Other helper functions for balance update
# ───────────────────────────────────────────────

async def reward_user(pool, user_id, amount):
    await update_balance(pool, user_id, delta=amount)

async def charge_user(pool, user_id, amount):
    await update_balance(pool, user_id, delta=-amount)

async def update_balance(pool, user_id, delta):
    async with pool.acquire() as conn:
        await conn.execute("""
            UPDATE users
            SET checking_account = checking_account + $1
            WHERE user_id = $2
        """, delta, user_id)
        
# ───────────────────────────────────────────────
# Fetch user's vehicles from DB
# ───────────────────────────────────────────────

async def get_user_vehicles(pool, user_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch("SELECT * FROM user_vehicle_inventory WHERE user_id = $1", user_id)
        return [dict(row) for row in rows]

# ───────────────────────────────────────────────
# Normalize function for text
# ───────────────────────────────────────────────

def normalize(text: str) -> str:
    # Normalize Unicode characters (decompose accents)
    text = unicodedata.normalize('NFD', text)
    # Remove accents
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    # Convert to lowercase
    text = text.lower()
    # Remove any non-alphanumeric characters except spaces
    text = re.sub(r'[^a-z0-9\s]', '', text)
    # Remove leading/trailing whitespace
    text = text.strip()
    return text
