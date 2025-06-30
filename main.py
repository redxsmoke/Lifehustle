import discord
from discord import app_commands
import random
import asyncio
import json
import os
import re
import time
import asyncpg

# Load categories JSON
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


# Globals
pool = None
last_paycheck_times = {}

# Helpers
def normalize(text):
    return re.sub(r'[\s\-]', '', text.lower())

# --- Database functions ---
import ssl
import asyncpg

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
                fridge TEXT DEFAULT '[]'
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
                'fridge': json.loads(row['fridge'])
            }
        else:
            return None

async def upsert_user(pool, user_id: int, data: dict):
    async with pool.acquire() as conn:
        fridge_json = json.dumps(data.get('fridge', []))
        await conn.execute('''
            INSERT INTO users (user_id, checking_account, savings_account, hunger_level, relationship_status, car, bike, fridge)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
            ON CONFLICT (user_id) DO UPDATE SET
                checking_account = EXCLUDED.checking_account,
                savings_account = EXCLUDED.savings_account,
                hunger_level = EXCLUDED.hunger_level,
                relationship_status = EXCLUDED.relationship_status,
                car = EXCLUDED.car,
                bike = EXCLUDED.bike,
                fridge = EXCLUDED.fridge
        ''', user_id,
             data.get('checking_account', 0),
             data.get('savings_account', 0),
             data.get('hunger_level', 100),
             data.get('relationship_status', 'single'),
             data.get('car'),
             data.get('bike'),
             fridge_json)

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

@tree.command(name="bank", description="View your current checking account balance")
async def bank(interaction: discord.Interaction):
    user_id = interaction.user.id
    user = await get_user(pool, user_id)
    if user is None:
        user = {
            'checking_account': 0,
            'savings_account': 0,
            'hunger_level': 100,
            'relationship_status': 'single',
            'car': None,
            'bike': None,
            'fridge': []
        }
        await upsert_user(pool, user_id, user)

    await interaction.response.send_message(
        f"💰 {interaction.user.display_name}, your current checking account balance is ${user['checking_account']:,}."
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
            f"⏳ You already claimed your paycheck. Try again in {hours}h {minutes}m.",
            ephemeral=True
        )
        return

    user = await get_user(pool, user_id)
    if user is None:
        user = {
            'checking_account': 0,
            'savings_account': 0,
            'hunger_level': 100,
            'relationship_status': 'single',
            'car': None,
            'bike': None,
            'fridge': []
        }

    user['checking_account'] = user.get('checking_account', 0) + 10000
    await upsert_user(pool, user_id, user)
    last_paycheck_times[user_id] = now

    await interaction.response.send_message(
        f"💵 {interaction.user.display_name}, you have received your paycheck of $10,000! Your new balance is ${user['checking_account']:,}.",
        ephemeral=True
    )

@tree.command(name="startcategories", description="Start a categories game round")
@app_commands.describe(category="Choose the category to play")
@app_commands.autocomplete(category=category_autocomplete)
async def startcategories(interaction: discord.Interaction, category: str):
    if category not in categories:
        await interaction.response.send_message(f"Category '{category}' does not exist.", ephemeral=True)
        return

    letters = [l for l, words in categories[category].items() if words]
    if not letters:
        await interaction.response.send_message(f"No words found in category '{category}'.", ephemeral=True)
        return

    chosen_letter = random.choice(letters).upper()
    raw_words = categories[category][chosen_letter]
    valid_words = {normalize(w): w for w in raw_words}

    await interaction.response.send_message(
        f"Category: **{category}**\nLetter: **{chosen_letter}**\nKeep naming words that start with {chosen_letter}! Game ends when you mess up.",
        ephemeral=False
    )

    def check(m: discord.Message):
        return m.channel == interaction.channel and m.author == interaction.user

    used_words = set()

    while True:
        try:
            msg = await client.wait_for('message', timeout=10.0, check=check)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏱️ Time's up! You took too long.")
            break

        word_raw = msg.content.strip()
        word_clean = normalize(word_raw)

        if not word_raw.lower().startswith(chosen_letter.lower()):
            await interaction.followup.send(f"❌ **{word_raw}** doesn't start with **{chosen_letter}**. Game over!")
            break

        if word_clean in used_words:
            await interaction.followup.send(f"⚠️ You've already used **{word_raw}**. Try something else!")
            continue

        if word_clean in valid_words:
            used_words.add(word_clean)

            # Award $10 for correct answer
            user_id = interaction.user.id
            user = await get_user(pool, user_id)
            if user is None:
                user = {
                    'checking_account': 0,
                    'savings_account': 0,
                    'hunger_level': 100,
                    'relationship_status': 'single',
                    'car': None,
                    'bike': None,
                    'fridge': []
                }

            user['checking_account'] = user.get('checking_account', 0) + 10
            await upsert_user(pool, user_id, user)

            await interaction.followup.send(f"✅ Correct! **{valid_words[word_clean]}** is valid. You earned $10! Keep going!")
        else:
            await interaction.followup.send(
                f"❌ **{word_raw}** is not in the list. Game over!\n\n"
                f"*(Game is still in beta testing — many words are still missing)*"
            )
            break

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
