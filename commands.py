from collections import defaultdict, Counter
import datetime
import json
import random
import asyncio
import time

import discord
from discord import app_commands

from views import (
    CommuteButtons,
    TransportationShopButtons,
    SellFromStashView,
    GroceryCategoryView,
    GroceryStashPaginationView,
)

from db_user import get_user, upsert_user
from utilities import parse_amount, embed_message, bike_description, normalize
from globals import pool, DEFAULT_USER, last_paycheck_times, categories, SHOP_ITEMS
from config import PAYCHECK_AMOUNT, PAYCHECK_COOLDOWN_SECONDS, COLOR_RED, COLOR_GREEN


# CATEGORIES GAME COMMANDS

@tree.command(name="submitword", description="Submit a new word to a category")
@app_commands.describe(category="Select the category for your word")
@app_commands.autocomplete(category=category_autocomplete)
async def submitword(interaction: discord.Interaction, category: str):
    if category not in categories:
        await interaction.response.send_message(
            f"Category '{category}' does not exist. Please select a valid category.",
            ephemeral=True
        )
        return
    modal = SubmitWordModal(category)
    await interaction.response.send_modal(modal)


# FINANCIAL COMMANDS

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
@app_commands.describe(category="Which category to browse?")
@app_commands.choices(category=[
    app_commands.Choice(name="Transportation", value="transportation"),
    app_commands.Choice(name="Groceries", value="groceries")
])
async def shop(interaction: discord.Interaction, category: app_commands.Choice[str]):
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
        grouped = defaultdict(list)
        for item in SHOP_ITEMS:
            grouped[item.get("category", "Misc")].append(item)

        pages = []
        for cat in sorted(grouped):
            pages.append((cat.capitalize(), grouped[cat]))

        view = GroceryCategoryView(pages, interaction.user.id)
        await view.send(interaction)


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
        if checking_balance == 0:
            await interaction.response.send_message(
                embed=embed_message(
                    "❌ Insufficient Funds",
                    "> You have no funds to deposit.",
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
                "> Amount must be positive.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    if checking_balance < amount_int:
        await interaction.response.send_message(
            embed=embed_message(
                "❌ Insufficient Funds",
                "> Not enough funds in your checking account.",
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
            f"> Deposited ${amount_int:,} from 💰 checking to 🏦 savings.\n"
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
        if savings_balance == 0:
            await interaction.response.send_message(
                embed=embed_message(
                    "❌ Insufficient Funds",
                    "> You have no funds to withdraw.",
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
                "> Amount must be positive.",
                discord.Color.red()
            ),
            ephemeral=True
        )
        return

    if savings_balance < amount_int:
        await interaction.response.send_message(
            embed=embed_message(
                "❌ Insufficient Funds",
                "> Not enough funds in your savings account.",
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
            f"> Withdrew ${amount_int:,} from 🏦 savings to 💰 checking.\n"
            f"> New balances:\n💰 Checking Account: ${user['checking_account']:,}\n🏦 Savings Account: ${user['savings_account']:,}",
            discord.Color.green()
        )
    )


@tree.command(name="commute", description="Commute to work using buttons (drive, bike, subway, bus)")
async def commute(interaction: discord.Interaction):
    user_id = interaction.user.id
    user = await get_user(pool, user_id)

    if not user:
        await interaction.response.send_message(
            embed=embed_message("❌ No Account Found", "Use `/start` to create your account."),
            ephemeral=True
        )
        return

    view = CommuteButtons()
    view.message = None  # Will be set after sending message

    await interaction.response.send_message(
        embed=embed_message("Commute", "Choose your commute method below:"),
        view=view,
        ephemeral=True
    )


@tree.command(name="paycheck", description=f"Claim your paycheck (${PAYCHECK_AMOUNT:,} every 12 hours)")
async def paycheck(interaction: discord.Interaction):
    user_id = interaction.user.id
    now = time.time()
    last_time = last_paycheck_times.get(user_id, 0)
    cooldown = PAYCHECK_COOLDOWN_SECONDS

    if now - last_time < cooldown:
        remaining = cooldown - (now - last_time)
        hours = int(remaining // 3600)
        minutes = int((remaining % 3600) // 60)
        await interaction.response.send_message(
            embed=embed_message(
                "⏳ Paycheck Cooldown",
                f"> You have already claimed your paycheck. Try again in {hours}h {minutes}m.",
                COLOR_RED
            ),
            ephemeral=True
        )
        return

    user = await get_user(pool, user_id)
    if user is None:
        user = DEFAULT_USER.copy()

    user['checking_account'] = user.get('checking_account', 0) + PAYCHECK_AMOUNT
    await upsert_user(pool, user_id, user)
    last_paycheck_times[user_id] = now

    await interaction.response.send_message(
        embed=embed_message(
            "💵 Paycheck Received",
            f"> {interaction.user.display_name}, you have received your paycheck of ${PAYCHECK_AMOUNT:,}!\n"
            f"Your new 💰 checking balance is ${user['checking_account']:,}.",
            COLOR_GREEN
        ),
        ephemeral=True
    )


# CATEGORIES GAME

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
    if interaction.guild is None:
        await interaction.response.send_message("❌ This command can't be used in DMs.", ephemeral=True)
        return

    if not interaction.channel.permissions_for(interaction.guild.me).manage_messages:
        await interaction.response.send_message("❌ I need the Manage Messages permission to purge.", ephemeral=True)
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


@tree.command(name="stash", description="View your inventory by category.")
@app_commands.describe(category="Which category do you want to check
