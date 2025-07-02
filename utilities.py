import asyncio
import datetime
import json
import random
import string

import discord

from db_user import get_user, upsert_user
from globals import pool
from embeds import embed_message

#HELPER FUNCTIONS

def bike_condition_from_usage(usage_count: int) -> str:
    if usage_count < 1:
        return "Pristine"
    elif usage_count < 2:
        return "Lightly Used"
    elif usage_count < 3:
        return "Heavily Used"
    else:
        return "Rusted"

def car_condition_from_usage(commute_count: int) -> str:
    if commute_count < 1:
        return "Pristine"
    elif commute_count < 2:
        return "Lightly Used"
    elif commute_count < 3:
        return "Heavily Used"
    else:
        return "Rusted"


async def can_user_buy_vehicle(user_inventory, item):
    vehicle_types = ["bike", "car"]
    item_type = item.get("type")  # assume you define this in item data

    for inv_item in user_inventory:
        if inv_item.get("type") == item_type:
            return False
    return True


async def plate_exists_in_any_inventory(plate: str) -> bool:
    users = await get_all_users(pool)  # You must implement this function to fetch all users
    for user in users:
        inventory = user.get("inventory", [])
        for item in inventory:
            if isinstance(item, dict) and item.get("plate") == plate:
                return True
    return False

async def update_bike_usage(user: dict):
    inventory = user.get("inventory", [])
    for item in inventory:
        if isinstance(item, dict) and item.get("type") == "Bike":
            # Increment commute count
            current_count = item.get("commute_count", 0)
            new_count = current_count + 1
            item["commute_count"] = new_count

            # Update condition based on usage count
            item["condition"] = condition_from_usage(new_count)
            break  # Assuming only one bike per user

    user["inventory"] = inventory
    await upsert_user(pool, user["user_id"], user)

def generate_random_plate(length=8):
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=length))

BIKE_COLORS = [
    "Neon Green",
    "Cherry Red",
    "Electric Blue",
    "Matte Black",
    "Sunshine Yellow",
    "Bright Orange",
    "Cool Cyan",
    "Hot Pink",
    "Deep Purple",
    "Metallic Silver"
]

CAR_COLORS = [
    "Crimson Red",
    "Electric Blue",
    "Midnight Black",
    "Pearl White",
    "Gunmetal Gray",
    "Emerald Green",
    "Sunburst Yellow",
    "Tangerine Orange",
    "Royal Purple",
    "Ocean Teal",
    "Candy Apple Red",
    "Sunset Bronze",
    "Ice Silver",
    "Lime Zest",
    "Deep Maroon"
]


def bike_description(purchase_date: datetime.date, condition: str) -> str:
    days_since = (datetime.date.today() - purchase_date).days

    pristine_descs = [
        "just picked up today",
        "shiny as a new penny",
        "looks as new as a freshly minted coin"
    ]
    lightly_used_descs = [
        "has a few scratches but rides smooth",
        "shows some love from the road",
        "starting to show character"
    ]
    heavily_used_descs = [
        "rattles and squeaks but still rides",
        "getting battered but hanging in there",
        "has seen better days"
    ]
    rusted_descs = [
        "rusted and worn down",
        "barely holding together",
        "looks like it survived a hurricane"
    ]

    if condition == "Pristine":
        desc = random.choice(pristine_descs)
    elif condition == "Lightly Used":
        desc = random.choice(lightly_used_descs)
    elif condition == "Heavily Used":
        desc = random.choice(heavily_used_descs)
    else:  # Rusted
        desc = random.choice(rusted_descs)

    return desc


def is_night_utc():
    hour = datetime.datetime.now(datetime.timezone.utc).hour
    # Define night as 19:00 - 06:00 UTC, adjust if needed
    return hour >= 19 or hour < 6

def get_probability_multiplier(commute_type, outcome_type, is_night):
    if outcome_type == "negative":
        if is_night:
            # Stronger negative boost for bike, bus, subway at night
            if commute_type in ("bike", "bus", "subway"):
                return 3.0  # triple the chance of bad events at night
            elif commute_type == "drive":
                return 1.5  # mild boost for driving at night
            else:
                return 1.0  # default no boost
        else:
            return 0.5  # reduce negative events during the day

    elif outcome_type == "positive":
        if is_night:
            return 0.5  # reduce positive events at night
        else:
            return 2.0  # double positive events during the day

    else:  # neutral
        return 1.0


def choose_outcome(commute_type):
    is_night = is_night_utc()
    outcomes = []
    weights = []

    # Gather all possible outcomes with adjusted weights
    for category in ["negative", "neutral", "positive"]:
        for outcome in COMMUTE_OUTCOMES[commute_type][category]:
            base_prob = outcome["base_probability"]
            multiplier = get_probability_multiplier(commute_type, category, is_night)
            adjusted_prob = base_prob * multiplier
            outcomes.append(outcome)
            weights.append(adjusted_prob)

    # Normalize weights so they sum to 1
    total_weight = sum(weights)
    if total_weight == 0:
        # Fallback if no weights (shouldn't happen)
        return random.choice(outcomes)

    normalized_weights = [w / total_weight for w in weights]

    # Select one outcome based on weighted probabilities
    chosen = random.choices(outcomes, weights=normalized_weights, k=1)[0]
    return chosen




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


async def handle_purchase(interaction, item, cost):
    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    
    if not user:
        await interaction.response.send_message("You don't have an account yet. Use `/start` to begin.", ephemeral=True)
        return
    
    if user["checking_account"] < cost:
        await interaction.response.send_message("🚫 You don’t have enough money.", ephemeral=True)
        return
    
    inventory = user.get("inventory") or []
    
    if item in inventory:
        await interaction.response.send_message(f"🚗 You already own **{item}**.", ephemeral=True)
        return
    
    inventory.append(item)
    
    async with pool.acquire() as conn:
        await conn.execute(
            'UPDATE users SET checking_account=$1, inventory=$2 WHERE user_id=$3',
            user["checking_account"] - cost,
            json.dumps(inventory),
            user_id
        )
    
    await interaction.response.send_message(f"✅ You purchased **{item}** for ${cost:,}!", ephemeral=True)

async def handle_commute(interaction: discord.Interaction, method: str):
    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    if user is None:
        user = DEFAULT_USER.copy()
        await upsert_user(pool, user_id, user)

    # Define costs and rewards per method
    costs = {
        'drive': 10,
        'subway': 10,
        'bus': 5,
    }
    rewards = {
        'bike': 10
    }

    # Check ownership requirements
    if method == 'drive' and not user.get('car'):
        await interaction.response.send_message("❌ You don't own a car to drive.", ephemeral=True)
        return
    if method == 'bike' and not user.get('bike'):
        await interaction.response.send_message("❌ You don't own a bike to ride.", ephemeral=True)
        return

    # ✅ Update bike commute count and condition
    if method == 'bike':
        inventory = user.get("inventory", [])
        for item in inventory:
            if isinstance(item, dict) and item.get("type") == "Bike":
                item["commute_count"] = item.get("commute_count", 0) + 1
                item["condition"] = condition_from_usage(item["commute_count"])
                break
        user["inventory"] = inventory

    checking_balance = user.get('checking_account', 0)

    # Calculate new balance and action text
    if method in costs:
        cost = costs[method]
        new_balance = checking_balance - cost
        action = f"spent ${cost}"
    elif method in rewards:
        reward = rewards[method]
        if checking_balance < 0:
            debt = abs(checking_balance)
            payment = min(debt, reward)
            new_balance = checking_balance + payment
            remainder = reward - payment
            if remainder > 0:
                new_balance += remainder
            action = f"earned ${reward} (paid off ${payment} of your debt)"
        else:
            new_balance = checking_balance + reward
            action = f"earned ${reward}"
    else:
        await interaction.response.send_message("❌ Invalid commute method.", ephemeral=True)
        return

    # Check bankruptcy
    if new_balance <= -500_000:
        user['checking_account'] = 0
        await upsert_user(pool, user_id, user)
        await interaction.response.send_message(
            "💥 Your debt exceeded $500,000! You have declared bankruptcy. Your balance has been reset to $0.",
            ephemeral=True
        )
        return
    else:
        user['checking_account'] = new_balance
        await upsert_user(pool, user_id, user)

    # Select random commute outcome
    outcome = choose_outcome(method)

    # Apply money changes from outcome if any
    money_change = outcome.get("money_change", 0)
    if money_change != 0:
        new_balance += money_change
        user['checking_account'] = new_balance
        await upsert_user(pool, user_id, user)

    # Compose response message
    emoji_map = {
        "drive": "🚗",
        "bike": "🚴",
        "subway": "🚇",
        "bus": "🚌"
    }
    emoji = emoji_map.get(method, "")
    msg = (
        f"{emoji} You commuted to work by {method} and {action}.\n"
        f"{outcome['description']}\n"
        f"New checking balance: ${user['checking_account']:,}."
    )

    embed = embed_message(f"{emoji} Commute Summary", f"  {msg}")
    await interaction.response.send_message(embed=embed)


#NORMALIZE FUNCTION
import unicodedata
import re

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


# db_helpers.py

