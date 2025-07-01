#IMPORTS
import discord
from discord import app_commands
import random
import asyncio
import json
import os
import re
import time
import asyncpg
import ssl

DEFAULT_USER = {
    'checking_account': 0,
    'savings_account': 0,
    'hunger_level': 100,
    'relationship_status': 'single',
    'car': None,
    'bike': None,
    'fridge': [],
    'debt': 0
}

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

# Get moderator user ID from env var, exit if missing or invalid
try:
    NOTIFY_USER_ID = int(os.environ["NOTIFY_USER_ID"])
except (KeyError, ValueError):
    print("ERROR: NOTIFY_USER_ID environment variable is missing or invalid.")
    exit(1)

DATABASE_URL = os.getenv("DATABASE_URL")
print(f"DATABASE_URL = {DATABASE_URL}")  # This prints the value, whether it's valid or not

if not DATABASE_URL:
    print("ERROR: DATABASE_URL environment variable is missing.")
    exit(1)  # This only stops the app if the URL isn't found

#HELPER FUNCTIONS

import datetime
import random

def is_night_utc():
    hour = datetime.datetime.now(datetime.timezone.utc).hour
    # Define night as 19:00 - 06:00 UTC, adjust if needed
    return hour >= 19 or hour < 6

def get_probability_multiplier(commute_type, outcome_type, is_night):
    if outcome_type == "negative":
        base = 0.10
        if commute_type == "drive":
            base = 0.03
        if is_night:
            if commute_type == "subway":
                base = 0.20
            elif commute_type == "drive":
                base = 0.10
            elif commute_type == "bus":
                base = 0.25
            elif commute_type == "bike":
                base = 0.35
    elif outcome_type == "positive":
        base = 0.10
        if commute_type == "drive":
            base = 0.18
        if not is_night:  # day
            if commute_type == "bus":
                base = 0.20
            elif commute_type == "subway":
                base = 0.15
            elif commute_type == "bike":
                base = 0.35
            elif commute_type == "drive":
                base = 0.40
    else:  # neutral outcomes
        base = 1.0  # treat neutral as default 100% base for weighting
    return base

def choose_outcome(commute_type):
    is_night = is_night_utc()
    outcomes = []
    weights = []

    for category in ["negative", "neutral", "positive"]:
        for outcome in COMMUTE_OUTCOMES[commute_type][category]:
            base_prob = outcome["base_probability"]
            multiplier = get_probability_multiplier(commute_type, category, is_night)
            adjusted_prob = base_prob * multiplier
            outcomes.append(outcome)
            weights.append(adjusted_prob)

    # Normalize weights so they sum to 1
    total = sum(weights)
    normalized_weights = [w / total for w in weights]

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

# Globals
pool = None
last_paycheck_times = {}

class CommuteButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.message = None  # Will hold the message with buttons

    @discord.ui.button(label="Drive 🚗 ($10)", style=discord.ButtonStyle.danger, custom_id="commute_drive")
    async def drive_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_commute(interaction, "drive")

    @discord.ui.button(label="Bike 🚴 (+$10)", style=discord.ButtonStyle.success, custom_id="commute_bike")
    async def bike_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_commute(interaction, "bike")

    @discord.ui.button(label="Subway 🚇 ($10)", style=discord.ButtonStyle.primary, custom_id="commute_subway")
    async def subway_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_commute(interaction, "subway")

    @discord.ui.button(label="Bus 🚌 ($5)", style=discord.ButtonStyle.secondary, custom_id="commute_bus")
    async def bus_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_commute(interaction, "bus")

    async def on_timeout(self):
        # Disable all buttons
        for child in self.children:
            child.disabled = True
        
        if self.message:
            try:
                await self.message.edit(
                    content="⌛ Commute selection timed out. Please try again.",
                    view=self
                )
            except Exception as e:
                print(f"[ERROR] Failed to edit message on timeout: {e}")



# Make sure this is a top-level async function — NOT nested inside another function!

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

    checking_balance = user.get('checking_account', 0)

    # Calculate new balance and action text
    if method in costs:
        cost = costs[method]
        new_balance = checking_balance - cost
        action = f"spent ${cost}"
    elif method in rewards:
        reward = rewards[method]
        # If negative balance (debt), reward pays off debt first
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

    # Check bankruptcy (debt >= 500,000)
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

    # Select a random outcome from commute outcomes JSON with day/night adjustments
    outcome = choose_outcome(method)

    # Apply money changes from outcome if any
    money_change = outcome.get("money_change", 0)
    if money_change != 0:
        new_balance += money_change
        user['checking_account'] = new_balance
        await upsert_user(pool, user_id, user)

    # Compose response message with emoji, action, and outcome description
    verb = "commuted"
    emoji_map = {
        "drive": "🚗",
        "bike": "🚴",
        "subway": "🚇",
        "bus": "🚌"
    }
    emoji = emoji_map.get(method, "")
    msg = (
        f"{emoji} You {verb} to work by {method} and {action}.\n"
        f"{outcome['description']}\n"
        f"New checking balance: ${user['checking_account']:,}."
    )

    embed = embed_message(f"{emoji} Commute Summary", msg)
    await interaction.response.send_message(embed=embed)


# --- Database functions ---

async def create_pool():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return await asyncpg.create_pool(DATABASE_URL, ssl=ssl_context)

async def init_db(pool):
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                checking_account BIGINT DEFAULT 0,
                savings_account BIGINT DEFAULT 0,
                hunger_level INT DEFAULT 100,
                relationship_status TEXT DEFAULT 'single',
                car TEXT,
                bike TEXT,
                fridge TEXT DEFAULT '[]',
                debt BIGINT DEFAULT 0
            );
        ''')

async def get_user(pool, user_id: int):
    async with pool.acquire() as conn:
        row = await conn.fetchrow('SELECT * FROM users WHERE user_id=$1', user_id)
        if row:
            return {
                'user_id': row['user_id'],
                'checking_account': row['checking_account'],
                'savings_account': row['savings_account'],
                'hunger_level': row['hunger_level'],
                'relationship_status': row['relationship_status'],
                'car': row['car'],
                'bike': row['bike'],
                'fridge': json.loads(row['fridge']),
                'debt': row['debt'],
                'inventory': safe_load_inventory(row['inventory'])

            }
        else:
            return None

def safe_load_inventory(inv):
    if not inv or inv.strip() == '':
        return []
    try:
        return json.loads(inv)
    except json.JSONDecodeError:
        return []

async def upsert_user(pool, user_id: int, data: dict):
    async with pool.acquire() as conn:
        fridge_json = json.dumps(data.get('fridge', []))
        inventory_json = json.dumps(data.get('inventory', []))
        await conn.execute('''
            INSERT INTO users (user_id, checking_account, savings_account, hunger_level, relationship_status, car, bike, fridge, debt, inventory)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            ON CONFLICT (user_id) DO UPDATE SET
                checking_account = EXCLUDED.checking_account,
                savings_account = EXCLUDED.savings_account,
                hunger_level = EXCLUDED.hunger_level,
                relationship_status = EXCLUDED.relationship_status,
                car = EXCLUDED.car,
                bike = EXCLUDED.bike,
                fridge = EXCLUDED.fridge,
                debt = EXCLUDED.debt,
                inventory = EXCLUDED.inventory
        ''', user_id,
             data.get('checking_account', 0),
             data.get('savings_account', 0),
             data.get('hunger_level', 100),
             data.get('relationship_status', 'single'),
             data.get('car'),
             data.get('bike'),
             fridge_json,
             data.get('debt', 0),
             inventory_json
        )

# --- Modal for word submission ---

class SubmitWordModal(discord.ui.Modal, title="Submit a new word"):
    def __init__(self, category: str):
        super().__init__()
        self.category = category

        self.word_input = discord.ui.TextInput(
            label="Enter your word",
            placeholder="Type your word here...",
            max_length=100,
        )
        self.add_item(self.word_input)

    async def on_submit(self, interaction: discord.Interaction):
        word_raw = self.word_input.value.strip()

        # Confirm to submitter
        await interaction.response.send_message(
            f"✅ Thanks for your submission of '{word_raw}' in category '{self.category}'. Your word will be reviewed by a moderator.",
            ephemeral=True
        )

        # Notify the moderator by DM
        notify_user = interaction.client.get_user(NOTIFY_USER_ID)
        if notify_user:
            try:
                await notify_user.send(
                    f"📢 New word submission:\n"
                    f"User: {interaction.user} ({interaction.user.id})\n"
                    f"Category: {self.category}\n"
                    f"Word: {word_raw}"
                )
            except Exception as e:
                print(f"[ERROR] Failed to send DM to {NOTIFY_USER_ID}: {e}")
        else:
            print(f"[ERROR] Could not find user with ID {NOTIFY_USER_ID} to send DM.")

# --- Autocomplete for categories ---

async def category_autocomplete(interaction: discord.Interaction, current: str):
    current_lower = current.lower()
    return [
        app_commands.Choice(name=cat, value=cat)
        for cat in categories.keys()
        if current_lower in cat.lower()
    ][:25]

COMMUTE_METHODS = ['drive', 'bike', 'subway', 'bus']
COMMUTE_DIRECTIONS = ['to', 'from']

async def commute_method_autocomplete(interaction: discord.Interaction, current: str):
    current_lower = current.lower()
    return [
        app_commands.Choice(name=method, value=method)
        for method in COMMUTE_METHODS if current_lower in method
    ][:25]

async def commute_direction_autocomplete(interaction: discord.Interaction, current: str):
    current_lower = current.lower()
    return [
        app_commands.Choice(name=direction, value=direction)
        for direction in COMMUTE_DIRECTIONS if current_lower in direction
    ][:25]

# --- Commands ---

@tree.command(name="submitword", description="Submit a new word to a category")
@app_commands.describe(category="Select the category for your word")
@app_commands.autocomplete(category=category_autocomplete)
async def submitword(interaction: discord.Interaction, category: str):
    if category not in categories:
        await interaction.response.send_message(f"Category '{category}' does not exist. Please select a valid category.", ephemeral=True)
        return
    modal = SubmitWordModal(category)
    await interaction.response.send_modal(modal)

@tree.command(name="bank", description="View your checking and savings account balances")
async def bank(interaction: discord.Interaction):
    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    if user is None:
        user = DEFAULT_USER.copy()
        await upsert_user(pool, user_id, user)

    await interaction.response.send_message(
        embed=embed_message(
            "💰 Account Balances",
            f"> {interaction.user.display_name}, your account balances are:\n"
            f"> \u2003 💰 Checking Account: ${user['checking_account']:,}\n"
            f"> \u2003 🏦 Savings Account:  ${user['savings_account']:,}"
        )
    )

@tree.command(name="shop", description="Shop for items by category")
@app_commands.describe(category="Which category of items do you want to browse?")
@app_commands.choices(category=[
    app_commands.Choice(name="Transportation", value="transportation"),
    app_commands.Choice(name="Groceries", value="groceries")
])
async def shop(interaction: discord.Interaction, category: app_commands.Choice[str]):
    if category.value == "transportation":
        embed = embed_message(
            "🛒 Transportation Shop",
            (
                "> Choose a vehicle to purchase:\n\n"
                "> 🚴 **Bike** — $2,000\n"
                "> 🚙 **Blue Car** — $10,000\n"
                "> 🚗 **Red Car** — $25,000\n"
                "> 🏎️ **Sports Car** — $100,000\n"
                "> 🛻 **Pickup Truck** — $30,000\n\n"
                "> Each vehicle comes with unique stats and perks!"
            )
        )
        view = TransportationShopButtons()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class TransportationShopButtons(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.button(label="Buy Bike 🚴", style=discord.ButtonStyle.success, custom_id="buy_bike")
    async def buy_bike(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_transportation_purchase(interaction, item="bike", cost=2000, emoji="🚴")

    @discord.ui.button(label="Buy Beater Car 🚙", style=discord.ButtonStyle.primary, custom_id="buy_blue_car")
    async def buy_blue_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_transportation_purchase(interaction, item="car", value="blue", cost=10000, emoji="🚙")

    @discord.ui.button(label="Buy Sedan 🚗", style=discord.ButtonStyle.primary, custom_id="buy_red_car")
    async def buy_red_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_transportation_purchase(interaction, item="car", value="red", cost=25000, emoji="🚗")

    @discord.ui.button(label="Buy Sports Car 🏎️", style=discord.ButtonStyle.danger, custom_id="buy_sports_car")
    async def buy_sports_car(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_transportation_purchase(interaction, item="car", value="sports", cost=100000, emoji="🏎️")

    @discord.ui.button(label="Buy Pickup Truck 🛻", style=discord.ButtonStyle.secondary, custom_id="buy_truck")
    async def buy_truck(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_transportation_purchase(interaction, item="car", value="truck", cost=75000, emoji="🛻")


async def handle_transportation_purchase(interaction: discord.Interaction, item: str, cost: int, emoji: str, value: str = None):
    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    if user is None:
        user = DEFAULT_USER.copy()

    balance = user.get('checking_account', 0)
    if balance < cost:
        await interaction.response.send_message(
            embed=embed_message(
                "❌ Insufficient Funds",
                f"> You need ${cost:,} to buy this item, but you only have ${balance:,}.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    if item == "bike" and user.get("bike"):
        await interaction.response.send_message(
            embed=embed_message(
                "🚴 Already Owned",
                "> You already own a bike!"
            ),
            ephemeral=True
        )
        return
    elif item == "car" and user.get("car"):
        await interaction.response.send_message(
            embed=embed_message(
                "🚗 Already Own a Car",
                f"> You already own a car (**{user['car']}**). Sell or remove it before buying a new one."
            ),
            ephemeral=True
        )
        return

    user['checking_account'] -= cost
    if item == "bike":
        user['bike'] = "basic"
    elif item == "car":
        user['car'] = value

    await upsert_user(pool, user_id, user)

    await interaction.response.send_message(
        embed=embed_message(
            f"✅ Purchase Successful",
            f"> You bought a {emoji} **{value or 'bike'}** for ${cost:,}.",
            discord.Color.green()
        ),
        ephemeral=True
    )

from discord.ui import View, Button

class ShopView(View):
    def __init__(self, items, user_id):
        super().__init__(timeout=60)
        self.items = items
        self.user_id = user_id

        for item in items:
            button = Button(label=f"{item['emoji']} {item['name']} - ${item['price']}", style=discord.ButtonStyle.primary, custom_id=item['id'])
            button.callback = self.make_callback(item)
            self.add_item(button)

    def make_callback(self, item):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                await interaction.response.send_message("❌ You can't use this button.", ephemeral=True)
                return
            
            user = await get_user(pool, self.user_id)
            if user is None:
                user = DEFAULT_USER.copy()
            
            if user['checking_account'] < item['price']:
                await interaction.response.send_message(
                    f"❌ You don't have enough money to buy {item['emoji']} {item['name']}.",
                    ephemeral=True
                )
                return
            
            user['checking_account'] -= item['price']

            # Add item id to inventory
            inventory = user.get('inventory', [])
            inventory.append(item['id'])
            user['inventory'] = inventory

            # If the item is a vehicle, assign ownership (special logic)
            if item['id'] == "bike":
                user['bike'] = item['id']
            elif item['id'] in ["blue_car", "red_car", "sports_car", "pickup_truck"]:
                user['car'] = item['id']

            await upsert_user(pool, self.user_id, user)

            await interaction.response.send_message(
                f"✅ You bought {item['emoji']} {item['name']} for ${item['price']:,}!",
                ephemeral=True
            )
            self.stop()  # optional, disables buttons after purchase
        return callback


@tree.command(name="deposit", description="Deposit money from checking to savings")
@app_commands.describe(amount="Amount to deposit from checking to savings")
async def deposit(interaction: discord.Interaction, amount: str):
    parsed_amount = parse_amount(amount)
    if parsed_amount is None:
        await interaction.response.send_message(
            embed=embed_message(
                "❌ Invalid Format",
                "> Use numbers, commas, or suffixes like 'k' or 'm', or 'all'.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    if user is None:
        user = DEFAULT_USER.copy()

    checking_balance = user.get('checking_account', 0)

    if parsed_amount == -1:
        # 'all' means deposit all checking funds
        if checking_balance == 0:
            await interaction.response.send_message(
                embed=embed_message(
                    "❌ Insufficient Funds",
                    "> Aww man - if only you didn't spend it all on booze and OnlyFans LOL - Try depositing when your balance is higher than your IQ",
                    discord.Color.red()
                ),
                ephemeral=True
            )
            return
        amount_int = checking_balance
    else:
        amount_int = parsed_amount

    if amount_int <= 0:
        await interaction.response.send_message(
            embed=embed_message(
                "❌ Invalid Amount",
                "> Hey stupid, you can't deposit a negative amount LOL.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    if checking_balance < amount_int:
        await interaction.response.send_message(
            embed=embed_message(
                "❌ Insufficient Funds",
                "> LMAO - unless you're also depositing your hopes and dreams, you don't have this much in your checking account to deposit.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    user['checking_account'] -= amount_int
    user['savings_account'] += amount_int
    await upsert_user(pool, user_id, user)

    await interaction.response.send_message(
        embed=embed_message(
            "✅ Deposit Successful",
            f"> Successfully deposited ${amount_int:,} from 💰 checking to 🏦 savings.\n"
            f"> New balances:\n💰 Checking Account: ${user['checking_account']:,}\n🏦 Savings Account: ${user['savings_account']:,}",
            discord.Color.green()
        )
    )

@tree.command(name="withdraw", description="Withdraw money from savings to checking")
@app_commands.describe(amount="Amount to withdraw from savings to checking")
async def withdraw(interaction: discord.Interaction, amount: str):
    parsed_amount = parse_amount(amount)
    if parsed_amount is None:
        await interaction.response.send_message(
            embed=embed_message(
                "❌ Invalid Format",
                "> Use numbers, commas, or suffixes like 'k' or 'm', or 'all'.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    if user is None:
        user = DEFAULT_USER.copy()

    savings_balance = user.get('savings_account', 0)

    if parsed_amount == -1:
        # 'all' means withdraw all savings funds
        if savings_balance == 0:
            await interaction.response.send_message(
                embed=embed_message(
                    "❌ Insufficient Funds",
                    "> LMAO - money don't grow on trees in real life and it doesn't here either. Try again after you do something with your life.",
                    discord.Color.red()
                ),
                ephemeral=True
            )
            return
        amount_int = savings_balance
    else:
        amount_int = parsed_amount

    if amount_int <= 0:
        await interaction.response.send_message(
            embed=embed_message(
                "❌ Invalid Amount",
                "> Hey stupid, you can't withdraw a negative amount LOL.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    if savings_balance < amount_int:
        await interaction.response.send_message(
            embed=embed_message(
                "❌ Insufficient Funds",
                "> WOW! Wouldn't it be nice if we could all withdraw money we don't have. You don't have enough funds in your savings to do this. Stop spending it on stupid shit.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    user['savings_account'] -= amount_int
    user['checking_account'] += amount_int
    await upsert_user(pool, user_id, user)

    await interaction.response.send_message(
        embed=embed_message(
            "✅ Withdrawal Successful",
            f"> Successfully withdrew ${amount_int:,} from 🏦 savings to 💰 checking.\n"
            f"> New balances:\n💰 Checking Account: ${user['checking_account']:,}\n🏦 Savings Account: ${user['savings_account']:,}",
            discord.Color.green()
        )
    )

@tree.command(name="commute", description="Commute to work using buttons (drive, bike, subway, bus)")
async def commute(interaction: discord.Interaction):
    view = CommuteButtons()
    await interaction.response.send_message(
        embed=embed_message(
            "🚦 Commute",
            "> Pick your method of travel."
        ),
        view=view,
        ephemeral=True
    )

@tree.command(name="paycheck", description="Claim your paycheck ($10,000 every 12 hours)")
async def paycheck(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = time.time()
    last_time = last_paycheck_times.get(user_id, 0)
    cooldown = 12 * 3600  # 12 hours

    if now - last_time < cooldown:
        remaining = cooldown - (now - last_time)
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await interaction.response.send_message(
            embed=embed_message(
                "⏳ Paycheck Cooldown",
                f"> 😞 Wouldn't this be nice? Unfortunagely you've already claimed your paycheck. Try again in {hours}h {minutes}m."
            ),
            ephemeral=True
        )
        return

    user = await get_user(pool, user_id)
    if user is None:
        user = DEFAULT_USER.copy()

    user['checking_account'] = user.get('checking_account', 0) + 10000
    await upsert_user(pool, user_id, user)
    last_paycheck_times[user_id] = now

    await interaction.response.send_message(
        embed=embed_message(
            "💵 Paycheck Received",
            f"> {interaction.user.display_name}, you have received your paycheck of $10,000!\nYour new 💰 checking balance is ${user['checking_account']:,}."
        ),
        ephemeral=True
    )


@tree.command(name="startcategories", description="Start a categories game round")
@app_commands.describe(category="Choose the category to play")
@app_commands.autocomplete(category=category_autocomplete)
async def startcategories(interaction: discord.Interaction, category: str):
    if category not in categories:
        await interaction.response.send_message(
            embed=embed_message(
                "❌ Invalid Category",
                f"? Category '{category}' does not exist.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    letters = [l for l, words in categories[category].items() if words]
    if not letters:
        await interaction.response.send_message(
            embed=embed_message(
                "❌ No Words Found",
                f"> No words found in category '{category}'.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    chosen_letter = random.choice(letters).upper()
    raw_words = categories[category][chosen_letter]
    valid_words = {normalize(w): w for w in raw_words}

    await interaction.response.send_message(
        embed=embed_message(
            f"🎮 Categories Game Started!",
            f"> Category: **{category}**\nLetter: **{chosen_letter}**\nKeep naming words that start with **{chosen_letter}**! Game ends when you mess up."
        ),
        ephemeral=False
    )

    def check(m: discord.Message):
        return m.channel == interaction.channel and m.author == interaction.user

    used_words = set()

    while True:
        try:
            msg = await client.wait_for('message', timeout=10.0, check=check)
        except asyncio.TimeoutError:
            await interaction.followup.send(
                embed=embed_message(
                    "⏱️ Time's Up!",
                    "> Aww shucks! You took to long to answer. Game over!"
                )
            )
            break

        word_raw = msg.content.strip()
        word_clean = normalize(word_raw)

        if not word_raw.lower().startswith(chosen_letter.lower()):
            await interaction.followup.send(
                embed=embed_message(
                    "❌ Wrong Start Letter",
                    f"> **{word_raw}** doesn't start with **{chosen_letter}**. Game over!",
                    discord.Color.red()
                )
            )
            break

        if word_clean in used_words:
            await interaction.followup.send(
                embed=embed_message(
                    "⚠️ Word Used",
                    f"> You've already used **{word_raw}**. Try something else!",
                    discord.Color.orange()
                )
            )
            continue

        if word_clean in valid_words:
            used_words.add(word_clean)

            user_id = interaction.user.id
            user = await get_user(pool, user_id)
            if user is None:
                user = DEFAULT_USER.copy()

            user['checking_account'] = user.get('checking_account', 0) + 10
            await upsert_user(pool, user_id, user)

            await interaction.followup.send(
                embed=embed_message(
                    "✅ Correct!",
                    f"> **{valid_words[word_clean]}** is valid. You earned $10! Keep going!",
                    discord.Color.green()
                )
            )
        else:
            await interaction.followup.send(
                embed=embed_message(
                    "❌ Word Not Found",
                    f"> **{word_raw}** is not in the list. Game over!\n\n*(Game is still in beta testing — many words are still missing)*",
                    discord.Color.red()
                )
            )
            break
@tree.command(name="purge", description="Delete last 100 messages to clear clutter")
async def purge(interaction: discord.Interaction):
    # Only allow command in guild channels, not DMs
    if interaction.guild is None:
        await interaction.response.send_message("❌ This command can't be used in DMs.", ephemeral=True)
        return

    # Check if the bot has permission to manage messages
    if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
        await interaction.response.send_message("❌ I need the Manage Messages permission to purge.", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True)  # defer since purge might take a moment

    deleted = await interaction.channel.purge(limit=100)

    await interaction.followup.send(
        embed=embed_message(
            "🧹 Purge Complete",
            f"Deleted {len(deleted)} messages to clear clutter.",
            discord.Color.green()
        ),
        ephemeral=True
    )

@tree.command(name="stash", description="View items you own")
@app_commands.describe(category="Category of items to view")
@app_commands.choices(category=[
    app_commands.Choice(name="Transportation", value="transportation"),
    app_commands.Choice(name="Groceries", value="groceries")
])
async def stash(interaction: discord.Interaction, category: app_commands.Choice[str]):
    await interaction.response.defer()
    user_id = interaction.user.id
    user = await get_user(pool, user_id)

    if not user:
        await interaction.followup.send("You don’t have an account yet. Try using `/start` first.")
        return

    inventory = user.get("inventory", [])

    if category.value == "transportation":
        vehicles = {
            "🚴": "Bike",
            "🚙": "Blue Car",
            "🚗": "Red Car",
            "🏎️": "Sports Car",
            "🛻": "Pickup Truck"
        }
        owned = [f"{emoji} {label}" for emoji, label in vehicles.items() if f"{emoji} {label}" in inventory]
        description = "\n".join(owned) if owned else "You don’t own any transportation items yet."

        embed = discord.Embed(
            title="🚗 Your Vehicles",
            description=description,
            color=discord.Color.teal()
        )
        await interaction.followup.send(embed=embed)

    elif category.value == "groceries":
        from collections import Counter, defaultdict
        with open("shop_items.json", "r", encoding="utf-8") as f:
            items_data = json.load(f)

        # Map item to category
        item_category_map = {item["name"]: item.get("category", "misc") for item in items_data}

        counts = Counter(item for item in inventory if item not in [
            "🚴 Bike", "🚙 Blue Car", "🚗 Red Car", "🏎️ Sports Car", "🛻 Pickup Truck"
        ])
        if not counts:
            embed = discord.Embed(
                title="🛒 Your Groceries",
                description="You don’t have any groceries yet.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
            return

        categorized = defaultdict(list)
        for item, count in counts.items():
            category = item_category_map.get(item, "misc").capitalize()
            categorized[category].append(f"{item} x{count}")

        category_pages = []
        for cat, items in sorted(categorized.items()):
            emoji_title = {
                "Produce": "🥬 Produce",
                "Dairy": "🧀 Dairy",
                "Protein": "🍖 Protein",
                "Snacks": "🍪 Snacks",
                "Baked": "🍞 Baked",
                "Misc": "📦 Misc"
            }.get(cat, f"📦 {cat}")
            category_pages.append((emoji_title, "\n".join(items)))

        view = GroceryCategoryView(category_pages, user_id)
        await view.send(interaction)



# --- Bot events ---

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

client.run(os.getenv("DISCORD_BOT_TOKEN"))
