import asyncio
import datetime
import json
import random
import string
import unicodedata
import re

import discord

from db_user import get_user, upsert_user, get_user_finances, upsert_user_finances
from globals import pool
from embeds import embed_message, COLOR_RED

# ───────────────────────────────────────────────
# VEHICLE CONDITION THRESHOLDS
# ───────────────────────────────────────────────

def condition_from_usage(travel_count: int) -> str:
    if travel_count < 50:
        return "Brand New"
    elif travel_count < 100:
        return "Good Condition"
    elif travel_count < 150:
        return "Fair Condition"
    elif travel_count < 200:
        return "Poor Condition"
    else:
        return "Broken Down"

# ───────────────────────────────────────────────
# TRAVEL UTILITIES
# ───────────────────────────────────────────────

async def update_vehicle_condition_and_description(pool, user_id, vehicle_id, vehicle_type_id, travel_count, breakdown_threshold, interaction=None):
    """
    Increment travel_count, recalculate condition_id, pick a random new appearance,
    update the user_vehicle_inventory record, and return the new state.
    Sends an ephemeral embed message if the condition changes.
    """
    # Determine new condition string with breakdown threshold logic:
    if breakdown_threshold is not None and travel_count >= breakdown_threshold:
        new_cond_str = "Broken Down"
    else:
        # Cap condition at "Poor Condition" if breakdown threshold not yet reached
        if travel_count >= 200:
            new_cond_str = "Poor Condition"
        else:
            new_cond_str = condition_from_usage(travel_count)
    
    # Map to numeric condition_id
    condition_map = {
        "Brand New": 1,
        "Good Condition": 2,
        "Fair Condition": 3,
        "Poor Condition": 4,
        "Broken Down": 5,
    }
    new_cond_id = condition_map[new_cond_str]

    async with pool.acquire() as conn:
        old_row = await conn.fetchrow(
            "SELECT condition_id, vehicle_type_id FROM user_vehicle_inventory WHERE id = $1 AND user_id = $2",
            vehicle_id, user_id
        )
        if not old_row:
            raise ValueError(f"Vehicle {vehicle_id} not found for user {user_id}")
        old_condition_id = old_row["condition_id"]
        vehicle_type_id = old_row["vehicle_type_id"]

        desc_row = await conn.fetchrow(
            """
            SELECT description
            FROM cd_vehicle_appearance
            WHERE vehicle_type_id = $1 AND condition_id = $2
            ORDER BY random() LIMIT 1
            """,
            vehicle_type_id, new_cond_id
        )
        description = desc_row["description"] if desc_row else "No description available."

        await conn.execute(
            """
            UPDATE user_vehicle_inventory
            SET
              travel_count          = $1,
              condition_id          = $2,
              appearance_description = $3
            WHERE id = $4 AND user_id = $5
            """,
            travel_count, new_cond_id, description, vehicle_id, user_id
        )

    # Determine if message should be sent
    send_message = False
    reverse_map = {v: k for k, v in condition_map.items()}
    old_cond_name = reverse_map.get(old_condition_id, "Unknown")
    new_cond_name = reverse_map.get(new_cond_id, "Unknown")

    if new_cond_name == "Broken Down":
        if old_cond_name != "Broken Down":
            send_message = True
    else:
        if old_condition_id != new_cond_id:
            send_message = True

    if interaction is not None and send_message:
        embed = embed_message(
            title="🚨 Vehicle Condition Change",
            description=f"> Your vehicle's condition changed from **{old_cond_name}** to **{new_cond_name}**.",
            color=COLOR_RED
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    return {
        "travel_count": travel_count,
        "condition_id": new_cond_id,
        "condition": new_cond_str,
        "description": description
    }

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
        return -1
    s = s.replace(',', '')
    try:
        if s.endswith('k'):
            return int(float(s[:-1]) * 1_000)
        elif s.endswith('m'):
            return int(float(s[:-1]) * 1_000_000)
        else:
            return int(float(s))
    except ValueError:
        return None

# ───────────────────────────────────────────────
# Other helper functions for balance update
# ───────────────────────────────────────────────

async def reward_user(pool, user_id, amount):
    finances = await get_user_finances(pool, user_id)
    if finances is None:
        return   
    finances["checking_account_balance"] += amount
    await upsert_user_finances(pool, user_id, finances)

async def charge_user(pool, user_id, amount):
    finances = await get_user_finances(pool, user_id)
    if finances is None:
        return  # Or raise an error if you prefer
    finances["checking_account_balance"] -= amount
    await upsert_user_finances(pool, user_id, finances)

async def update_balance(pool, user_id, delta):
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE user_finances
            SET checking_account_balance = checking_account_balance + $1
            WHERE user_id = $2
            """,
            delta, user_id
        )

# ───────────────────────────────────────────────
# Fetch user's vehicles from DB
# ───────────────────────────────────────────────

async def get_user_vehicles(pool, user_id):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT * FROM user_vehicle_inventory WHERE user_id = $1",
            user_id
        )
        return [dict(row) for row in rows]

# ───────────────────────────────────────────────
# Normalize function for text
# ───────────────────────────────────────────────

def normalize(text: str) -> str:
    text = unicodedata.normalize('NFD', text)
    text = ''.join(ch for ch in text if unicodedata.category(ch) != 'Mn')
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)
    return text.strip()
