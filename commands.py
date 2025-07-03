from collections import defaultdict, Counter
import random
import traceback
import asyncio
import defaults
import discord
from discord import app_commands, Interaction
import category_loader
import globals

from datetime import datetime, timezone, timedelta   
from db_user import get_user_finances, upsert_user_finances  
from utilities import embed_message  
from shop_items import TransportationShopButtons

from views import (
    CommuteButtons,
    SellFromStashView,
    GroceryCategoryView,
    GroceryStashPaginationView,
)
from db_user import get_user, upsert_user
from utilities import parse_amount, embed_message, bike_description, normalize

from config import PAYCHECK_AMOUNT, PAYCHECK_COOLDOWN_SECONDS, COLOR_RED, COLOR_GREEN
from category_loader import categories, category_autocomplete
from defaults import DEFAULT_USER

 

# PurchaseVehicleView with buy buttons only
class PurchaseVehicleView(discord.ui.View):
    def __init__(self, vehicles: list):
        super().__init__(timeout=180)
        for vehicle in vehicles:
            label = f"Buy {vehicle['name']} - ${vehicle['cost']:,}"
            emoji = vehicle.get("emoji", "🚗")  # fallback emoji
            label = f"{emoji} Buy {vehicle['name']} - ${vehicle['cost']:,}"
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.success)

            # Attach vehicle data to the callback
            button.callback = self.make_callback(vehicle, handle_vehicle_purchase)
            self.add_item(button)

    def make_callback(self, vehicle, purchase_fn):
        async def callback(interaction: discord.Interaction):
            item = {
                "type": vehicle["name"],
                "vehicle_type_id": vehicle["id"]
            }
            cost = vehicle["cost"]
            await purchase_fn(interaction, item, cost)
        return callback


# Moved outside the class
async def handle_vehicle_purchase(interaction: discord.Interaction, item: dict, cost: int):
    print(f"[handle_vehicle_purchase] Start purchase attempt: user={interaction.user.id}, item={item}, cost={cost}")
    pool = globals.pool
    try:
        await interaction.response.defer(ephemeral=True)

        user_id = interaction.user.id

        finances = await get_user_finances(pool, user_id)
        if finances is None:
            finances = {
                "checking_account_balance": 0,
                "savings_account_balance": 0,
                "debt_balance": 0,
                "last_paycheck_claimed": datetime.fromtimestamp(0, tz=timezone.utc)
            }

        checking = finances.get("checking_account_balance", 0)
        print(f"[handle_vehicle_purchase] Current checking balance: {checking}")

        if checking < cost:
            print(f"[handle_vehicle_purchase] Insufficient funds: need {cost}, have {checking}")
            await interaction.followup.send(
                embed=embed_message(
                    "❌ Insufficient Funds",
                    f"> You need ${cost:,} but only have ${checking:,} in checking.",
                    COLOR_RED
                ),
                ephemeral=True
            )
            return

        finances["checking_account_balance"] -= cost
        await upsert_user_finances(pool, user_id, finances)

        if item["type"] == "Beater Car":
            condition = "4"
            commute_count = random.randint(151, 195)
            resale_percent = 0.3
        else:
            condition = "1"
            commute_count = 0
            resale_percent = 0.85

        print(f"[handle_vehicle_purchase] Inserting vehicle with condition '{condition}', commute_count '{commute_count}', resale_percent {resale_percent}")

        async with pool.acquire() as conn:
            # Get random color from code table
            color_row = await conn.fetchrow("SELECT description FROM cd_vehicle_colors ORDER BY random() LIMIT 1")
            color = color_row["description"] if color_row else "Unknown"

            # Convert condition to int
            condition_int = int(condition)

            # Fetch condition description from cd_vehicle_condition by condition_id
            condition_desc_row = await conn.fetchrow(
                "SELECT description FROM cd_vehicle_condition WHERE condition_id = $1",
                condition_int
            )
            if not condition_desc_row:
                condition_desc = "Unknown"  # fallback if not found
            else:
                condition_desc = condition_desc_row["description"]

            # Get random appearance description for vehicle_type + condition_id
            appearance_row = await conn.fetchrow("""
                SELECT description
                FROM cd_vehicle_appearance
                WHERE vehicle_type_id = $1 AND condition_id = $2
                ORDER BY random()
                LIMIT 1
            """, item["vehicle_type_id"], condition_int)

            appearance_description = appearance_row["description"] if appearance_row else "No description available"

            # Insert new vehicle record with condition description string
            await conn.execute("""
                INSERT INTO user_vehicle_inventory (
                    user_id, vehicle_type_id, color, appearance_description, condition, commute_count, created_at, resale_percent
                )
                VALUES ($1, $2, $3, $4, $5, $6, NOW(), $7)
            """, user_id, item["vehicle_type_id"], color, appearance_description, condition_desc, commute_count, resale_percent)


        await interaction.followup.send(
            embed=embed_message(
                "✅ Purchase Successful",
                f"You bought a **{item['type']}** for ${cost:,}.\n"
                f"🎨 Color: {color}\n"
                f"📝 Description: {appearance_description}\n"
                f"💰 Remaining Checking Balance: ${finances['checking_account_balance']:,}",
                COLOR_GREEN
            ),
            ephemeral=True
        )

        print("[handle_vehicle_purchase] Purchase completed successfully.")

    except Exception as e:
        print("[handle_vehicle_purchase] Exception occurred:", e)
        traceback.print_exc()
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❌ An error occurred during purchase. Please try again later.",
                ephemeral=True
            )
        elif not interaction.followup.is_done():
            await interaction.followup.send(
                "❌ An error occurred during purchase. Please try again later.",
                ephemeral=True
            )


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
                f"> 💰 Checking: ${user['checking_account_balance']:,}\n"
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
        from globals import pool
        if category.value == "transportation":
            async with pool.acquire() as conn:
                vehicles = await conn.fetch("SELECT id, emoji, name, cost FROM cd_vehicle_type ORDER BY cost")

            if not vehicles:
                await interaction.followup.send("No vehicles available in the shop right now.", ephemeral=True)
                return

            desc_lines = []
            for v in vehicles:
                desc_lines.append(f"{v['emoji']} **{v['name']}** — ${v['cost']:,}")

            description = "Choose a vehicle to purchase:\n\n" + "\n".join(desc_lines) + "\n\nEach vehicle has unique perks!"
            embed = discord.Embed(title="🛒 Transportation Shop", description=description, color=discord.Color.blue())

            view = PurchaseVehicleView(vehicles)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        elif category.value == "groceries":
            async with pool.acquire() as conn:
                groceries = await conn.fetch("SELECT id, emoji, name, cost FROM cd_grocery_type ORDER BY name")

            if not groceries:
                await interaction.followup.send("No grocery items available right now.", ephemeral=True)
                return

            desc_lines = []
            for item in groceries:
                emoji = item["emoji"] or ""
                desc_lines.append(f"{emoji} **{item['name']}** — ${item['cost']:,}")

            description = "Choose a grocery item to purchase:\n\n" + "\n".join(desc_lines)
            embed = discord.Embed(title="🛒 Grocery Shop", description=description, color=discord.Color.green())

            await interaction.followup.send(embed=embed, ephemeral=True)

    # ... rest of your commands unchanged, omitted here for brevity ...


    @tree.command(name="deposit", description="Deposit money from checking to savings")
    @app_commands.describe(amount="Amount to deposit")
    async def deposit(interaction: Interaction, amount: str):
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
        from globals import pool
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
        from globals import pool
        if pool is None:
            await interaction.response.send_message(
                "Database is not ready yet. Please try again in a moment.",
                ephemeral=True
            )
            return

        user_id = interaction.user.id
        now = datetime.now(timezone.utc)

        finances = await get_user_finances(pool, user_id)
        if finances is None:
            finances = {
                'checking_account_balance': 0,
                'savings_account_balance': 0,
                'debt_balance': 0,
                'last_paycheck_claimed': datetime.fromtimestamp(0, tz=timezone.utc)
            }

        last_claim = finances['last_paycheck_claimed']
        if not isinstance(last_claim, datetime):
            try:
                last_claim = datetime.fromisoformat(str(last_claim))
            except:
                last_claim = datetime.fromtimestamp(0, tz=timezone.utc)

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

        finances['checking_account_balance'] += PAYCHECK_AMOUNT
        finances['last_paycheck_claimed'] = now
        await upsert_user_finances(pool, user_id, finances)

        await interaction.response.send_message(embed=embed_message(
            "💵 Paycheck Claimed",
            f"> You got ${PAYCHECK_AMOUNT:,}!\n💰 New Balance: ${finances['checking_account_balance']:,}",
            COLOR_GREEN
        ), ephemeral=True)

    @tree.command(name="startcategories", description="Start a categories game round")
    @app_commands.describe(category="Choose the category to play")
    @app_commands.autocomplete(category=category_autocomplete)
    async def startcategories(interaction: discord.Interaction, category: str):
        from globals import pool
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
        from globals import pool
        await interaction.response.defer()

        try:
            user_id = interaction.user.id
            user = await get_user(pool, user_id)

            if not user:
                await interaction.followup.send("❌ You don’t have an account yet. Use `/start` first.")
                return

            if category.value == "transportation":
                async with pool.acquire() as conn:
                    vehicles = await conn.fetch("""
                        SELECT DISTINCT
                            uvi.id, uvi.color, uvi.appearance_description, uvi.condition,
                            uvi.commute_count, uvi.created_at, uvi.resale_percent,
                            cvt.name AS type, plate_number, cvt.emoji
                        FROM user_vehicle_inventory uvi
                        JOIN cd_vehicle_type cvt ON uvi.vehicle_type_id = cvt.id
                        JOIN cd_vehicle_condition cvc on uvi.vehicle_type_id = cvt.id
                        WHERE uvi.user_id = $1
                        ORDER BY uvi.created_at DESC
                    """, user_id)

                if not vehicles:
                    await interaction.followup.send("You don’t own any transportation items yet.")
                    return

                vehicles = [dict(v) for v in vehicles]

                desc_lines = []
                for item in vehicles:
                    vehicle_type = item.get("type", "Unknown")
                    condition = item.get("condition", "Unknown")
                    description = item.get("appearance_description", "No description")
                    commute_count = item.get("commute_count", 0)
                    emoji = item.get("emoji", "🚗")

                    desc_lines.append(
                        f"> {emoji} **{vehicle_type}**\n"
                        f"> \u200b    Condition: {condition}\n"
                        f"> \u200b    Description: {description}\n"
                        f"> \u200b    Commute Count: {commute_count}"
                    )

                embed = discord.Embed(
                    title="🚗 Your Vehicles",
                    description="\n\n".join(desc_lines),
                    color=discord.Color.teal()
                )

                view = SellFromStashView(user_id, vehicles)
                await interaction.followup.send(embed=embed, view=view)
                return

            elif category.value == "groceries":
                from db_user import get_grocery_stash

                groceries = await get_grocery_stash(pool, user_id)

                if not groceries:
                    embed = discord.Embed(
                        title="🛒 Your Groceries",
                        description="You don’t have any groceries yet.",
                        color=discord.Color.green()
                    )
                    await interaction.followup.send(embed=embed)
                    return

                categorized = defaultdict(list)
                for row in groceries:
                    line = f"> {row['item_emoji']} **{row['item_name']}** — {row['quantity']}x (exp: {row['expiration_date']})"
                    key = f"{row['category_emoji']} {row['category']}"
                    categorized[key].append(line)

                embeds = []
                for category_name, lines in categorized.items():
                    embed = discord.Embed(
                        title=category_name,
                        description="\n".join(lines),
                        color=discord.Color.green()
                    )
                    embeds.append(embed)

                if len(embeds) == 1:
                    await interaction.followup.send(embed=embeds[0])
                else:
                    view = GroceryStashPaginationView(interaction.user.id, embeds)
                    await view.send(interaction)

        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred: {e}")

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
