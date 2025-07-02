from collections import defaultdict, Counter
import json
from main import pool
import random
import asyncio
import time
import defaults
import discord
from discord import app_commands, Interaction
import category_loader

from datetime import datetime, timezone, timedelta   
from db_user import get_user_finances, upsert_user_finances  
from utilities import embed_message  

def register_commands():
    from main import pool  

# CONSTANTS IMPORTS
from constants import (
    PAYCHECK_AMOUNT,
    PAYCHECK_COOLDOWN_SECONDS,
    COLOR_GREEN,
    COLOR_RED,
)


from views import (
    CommuteButtons,
    TransportationShopButtons,
    SellFromStashView,
    GroceryCategoryView,
    GroceryStashPaginationView,
)
from db_user import get_user, upsert_user
from utilities import parse_amount, embed_message, bike_description, normalize
from globals import pool, last_paycheck_times
from config import PAYCHECK_AMOUNT, PAYCHECK_COOLDOWN_SECONDS, COLOR_RED, COLOR_GREEN
from category_loader import categories, category_autocomplete
from defaults import DEFAULT_USER
from shop_items import SHOP_ITEMS  # Assuming you load items from this

def register_commands(tree: app_commands.CommandTree):
    @tree.command(name="submitword", description="Submit a new word to a category")
    @app_commands.describe(category="Select the category for your word")
    @app_commands.autocomplete(category=category_autocomplete)
    async def submitword(interaction: Interaction, category: str):
        if category not in categories:
            await interaction.response.send_message(
                f"Category '{category}' does not exist. Please select a valid category.",
                ephemeral=True
            )
            return
        from modals import SubmitWordModal
        modal = SubmitWordModal(category)
        await interaction.response.send_modal(modal)

    @tree.command(name="bank", description="View your checking and savings account balances")
    async def bank(interaction: Interaction):
        user_id = interaction.user.id
        user = await get_user(pool, user_id)
        if user is None:
            user = DEFAULT_USER.copy()
            await upsert_user(pool, user_id, user)

        await interaction.response.send_message(
            embed=embed_message(
                "💰 Account Balances",
                f"> {interaction.user.display_name}, your account balances are:\n"
                f"> 💰 Checking: ${user['checking_account']:,}\n"
                f"> 🏦 Savings: ${user['savings_account']:,}"
            )
        )

    @tree.command(name="shop", description="Shop for items by category")
    @app_commands.describe(category="Which category to browse?")
    @app_commands.choices(category=[
        app_commands.Choice(name="Transportation", value="transportation"),
        app_commands.Choice(name="Groceries", value="groceries")
    ])
    async def shop(interaction: Interaction, category: app_commands.Choice[str]):
        await interaction.response.defer(ephemeral=True)
        if category.value == "transportation":
            embed = discord.Embed(
                title="🛒 Transportation Shop",
                description=(
                    "Choose a vehicle to purchase:\n\n"
                    "> 🚴 **Bike** — $2,000\n"
                    "> 🚙 **Beater Car** — $10,000\n"
                    "> 🚗 **Sedan Car** — $25,000\n"
                    "> 🏎️ **Sports Car** — $100,000\n"
                    "> 🛻 **Pickup Truck** — $75,000\n\n"
                    "Each vehicle has unique perks!"
                ),
                color=discord.Color.blue()
            )
            view = TransportationShopButtons()
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        elif category.value == "groceries":
            grouped = {}
            for item in SHOP_ITEMS:
                grouped.setdefault(item.get("category", "Misc"), []).append(item)

            pages = [(cat.capitalize(), grouped[cat]) for cat in sorted(grouped)]
            view = GroceryCategoryView(pages, interaction.user.id)
            await view.send(interaction)

    @tree.command(name="deposit", description="Deposit money from checking to savings")
    @app_commands.describe(amount="Amount to deposit")
    async def deposit(interaction: Interaction, amount: str):
        from utilities import parse_amount
        parsed_amount = parse_amount(amount)
        if parsed_amount is None:
            await interaction.response.send_message(embed=embed_message(
                "❌ Invalid Format", "Use numbers like 1000, or 'all'.", COLOR_RED), ephemeral=True)
            return

        user_id = interaction.user.id
        user = await get_user(pool, user_id)
        if user is None:
            user = DEFAULT_USER.copy()

        checking = user.get('checking_account', 0)
        amount_int = checking if parsed_amount == -1 else parsed_amount

        if amount_int <= 0 or amount_int > checking:
            await interaction.response.send_message(embed=embed_message(
                "❌ Invalid Amount", "You don't have enough in checking.", COLOR_RED), ephemeral=True)
            return

        user['checking_account'] -= amount_int
        user['savings_account'] += amount_int
        await upsert_user(pool, user_id, user)

        await interaction.response.send_message(embed=embed_message(
            "✅ Deposit Complete",
            f"> Moved ${amount_int:,} to savings.\n"
            f"> 💰 Checking: ${user['checking_account']:,}\n"
            f"> 🏦 Savings: ${user['savings_account']:,}",
            COLOR_GREEN
        ))

    @tree.command(name="withdraw", description="Withdraw money from savings to checking")
    @app_commands.describe(amount="Amount to withdraw")
    async def withdraw(interaction: Interaction, amount: str):
        from utilities import parse_amount
        parsed_amount = parse_amount(amount)
        if parsed_amount is None:
            await interaction.response.send_message(embed=embed_message(
                "❌ Invalid Format", "Use numbers like 1000, or 'all'.", COLOR_RED), ephemeral=True)
            return

        user_id = interaction.user.id
        user = await get_user(pool, user_id)
        if user is None:
            user = DEFAULT_USER.copy()

        savings = user.get('savings_account', 0)
        amount_int = savings if parsed_amount == -1 else parsed_amount

        if amount_int <= 0 or amount_int > savings:
            await interaction.response.send_message(embed=embed_message(
                "❌ Invalid Amount", "You don't have enough in savings.", COLOR_RED), ephemeral=True)
            return

        user['savings_account'] -= amount_int
        user['checking_account'] += amount_int
        await upsert_user(pool, user_id, user)

        await interaction.response.send_message(embed=embed_message(
            "✅ Withdrawal Complete",
            f"> Moved ${amount_int:,} to checking.\n"
            f"> 💰 Checking: ${user['checking_account']:,}\n"
            f"> 🏦 Savings: ${user['savings_account']:,}",
            COLOR_GREEN
        ))

    @tree.command(name="commute", description="Commute to work using buttons")
    async def commute(interaction: Interaction):
        user_id = interaction.user.id
        user = await get_user(pool, user_id)
        if not user:
            await interaction.response.send_message(embed=embed_message(
                "❌ No Account", "Use `/start` to create an account."), ephemeral=True)
            return

        view = CommuteButtons()
        await interaction.response.send_message(embed=embed_message(
            "🚗 Commute", "Choose your commute method:"), view=view, ephemeral=True)

    @tree.command(name="paycheck", description=f"Claim your paycheck (${PAYCHECK_AMOUNT:,}) every 12h")
    async def paycheck(interaction: Interaction):
        # Ensure the DB pool is initialized
        if pool is None:
            await interaction.response.send_message(
                "Database is not ready yet. Please try again in a moment.",
                ephemeral=True
            )
            return

        user_id = interaction.user.id
        now = datetime.now(timezone.utc)

        # Fetch or initialize this user’s finance record
        finances = await get_user_finances(pool, user_id)
        if finances is None:
            finances = {
                'checking_account_balance': 0,
                'savings_account_balance': 0,
                'debt_balance': 0,
                'last_paycheck_claimed': datetime.fromtimestamp(0, tz=timezone.utc)
            }

        # Parse last claim time
        last_claim = finances['last_paycheck_claimed']
        if not isinstance(last_claim, datetime):
            try:
                last_claim = datetime.fromisoformat(str(last_claim))
            except:
                last_claim = datetime.fromtimestamp(0, tz=timezone.utc)

        # Check cooldown
        elapsed = (now - last_claim).total_seconds()
        if elapsed < PAYCHECK_COOLDOWN_SECONDS:
            remaining = PAYCHECK_COOLDOWN_SECONDS - elapsed
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            await interaction.response.send_message(embed=embed_message(
                "⏳ Cooldown",
                f"> Try again in {hours}h {minutes}m.",
                COLOR_RED
            ), ephemeral=True)
            return

        # Grant paycheck and update timestamp
        finances['checking_account_balance'] += PAYCHECK_AMOUNT
        finances['last_paycheck_claimed'] = now
        await upsert_user_finances(pool, user_id, finances)

        # Send confirmation
        await interaction.response.send_message(embed=embed_message(
            "💵 Paycheck Claimed",
            f"> You got ${PAYCHECK_AMOUNT:,}!\n💰 New Balance: ${finances['checking_account_balance']:,}",
            COLOR_GREEN
        ), ephemeral=True)


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
                msg = await interaction.client.wait_for('message', timeout=10.0, check=check)
            except asyncio.TimeoutError:
                await interaction.followup.send(
                    embed=embed_message(
                        "⏱️ Time's Up!",
                        "> You took too long to answer. Game over!"
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

                user['checking_account'] += 10
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

    @tree.command(name="stash", description="View your inventory by category.")
    @app_commands.describe(category="Which category do you want to check?")
    @app_commands.choices(category=[
        app_commands.Choice(name="Transportation", value="transportation"),
        app_commands.Choice(name="Groceries", value="groceries")
    ])
    async def stash(interaction: discord.Interaction, category: app_commands.Choice[str]):
        await interaction.response.defer()

        user_id = interaction.user.id
        user = await get_user(pool, user_id)

        if not user:
            await interaction.followup.send("❌ You don’t have an account yet. Use `/start` first.")
            return

        inventory = user.get("inventory", [])

        if category.value == "transportation":
            vehicles = [
                item for item in inventory
                if isinstance(item, dict) and item.get("type") in {
                    "Bike", "Beater Car", "Sedan Car", "Sports Car", "Pickup Truck"
                }
            ]
            if not vehicles:
                await interaction.followup.send("You don’t own any transportation items yet.")
                return

            desc_lines = []
            for item in vehicles:
                vehicle_type = item.get("type", "Unknown")
                color = item.get("color", "Unknown")
                condition = item.get("condition", "Unknown")
                commute_count = item.get("commute_count", 0)
                purchase_date_str = item.get("purchase_date")
                purchase_date = datetime.date.fromisoformat(purchase_date_str) if purchase_date_str else datetime.date.today()

                if vehicle_type == "Bike":
                    description = bike_description(purchase_date, condition)
                    desc_lines.append(f"🚴 **{vehicle_type}** — {color} — {description} ({condition})")
                else:
                    tag = item.get("tag", "N/A")
                    emoji = {
                        "Beater Car": "🚙",
                        "Sedan Car": "🚗",
                        "Sports Car": "🏎️",
                        "Pickup Truck": "🛻"
                    }.get(vehicle_type, "🚗")
                    desc_lines.append(f"{emoji} **{vehicle_type}** — {color} — Tag: {tag} — {condition}")

            embed = discord.Embed(
                title="🚗 Your Vehicles",
                description="\n".join(desc_lines),
                color=discord.Color.teal()
            )

            view = SellFromStashView(user_id, vehicles)
            await interaction.followup.send(embed=embed, view=view)
            return

        elif category.value == "groceries":
            with open("shop_items.json", "r", encoding="utf-8") as f:
                item_data = json.load(f)

            name_to_category = {
                f"{item['emoji']} {item['name']}": item.get("category", "Misc")
                for item in item_data
            }

            groceries = [item for item in inventory if isinstance(item, str)]
            counts = Counter(groceries)

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
                category_name = name_to_category.get(item, "Misc").capitalize()
                categorized[category_name].append(f"> {item} — {count}")

            embeds = []
            for cat, items in sorted(categorized.items()):
                emoji = {
                    "Produce": "🥬",
                    "Dairy": "🧀",
                    "Protein": "🍖",
                    "Snacks": "🍪",
                    "Baked": "🍞",
                    "Misc": "📦"
                }.get(cat, "📦")
                embeds.append(discord.Embed(
                    title=f"{emoji} {cat}",
                    description="\n".join(items),
                    color=discord.Color.green()
                ))

            if len(embeds) == 1:
                await interaction.followup.send(embed=embeds[0])
            else:
                view = GroceryStashPaginationView(interaction.user.id, embeds)
                await view.send(interaction)


    @tree.command(name="purge", description="Delete last 100 messages to clear clutter")
    async def purge(interaction: discord.Interaction):
        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ This command can't be used in DMs.",
                ephemeral=True
            )
            return

        if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
            await interaction.response.send_message(
                "❌ I need the Manage Messages permission to purge.",
                ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        deleted = await interaction.channel.purge(limit=100)

        await interaction.followup.send(
            embed=embed_message(
                "🧹 Purge Complete",
                f"Deleted {len(deleted)} messages to clear clutter.",
                discord.Color.green()
            ),
            ephemeral=True
        )