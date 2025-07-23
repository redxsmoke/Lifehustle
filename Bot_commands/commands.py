from collections import defaultdict, Counter
import random
import traceback
import asyncio
import defaults
import discord
from discord import app_commands, Interaction

from vehicle_logic import generate_random_plate
from grocery_logic.grocery_views import GroceryCategoryView, GroceryStashPaginationView
import globals

from datetime import datetime, timezone, timedelta   
from db_user import get_user_finances, upsert_user_finances, can_user_own_vehicle
from utilities import parse_amount, embed_message, normalize
from shop_items import TransportationShopButtons

from views import (
    TravelButtons, 
    SellFromStashView
)
from db_user import get_user, upsert_user


from config import PAYCHECK_AMOUNT, PAYCHECK_COOLDOWN_SECONDS, COLOR_RED, COLOR_GREEN
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


 
async def handle_vehicle_purchase(interaction: discord.Interaction, item: dict, cost: int):
    print(f"[handle_vehicle_purchase] Start purchase attempt: user={interaction.user.id}, item={item}, cost={cost}")
    pool = globals.pool
    try:
        await interaction.response.defer(ephemeral=True)
        user_id = interaction.user.id

        async with pool.acquire() as conn:
            # 1. Ownership limit check
            can_buy = await can_user_own_vehicle(user_id, item["vehicle_type_id"], conn)
            print(f"[handle_vehicle_purchase] Ownership limit check result: can_buy={can_buy}")
            if not can_buy:
                await interaction.followup.send(
                    embed=embed_message(
                        "🚫 Vehicle Limit Reached",
                        "> You have reached your vehicle limit! Purchase garage space to store more.",
                        COLOR_RED
                    ),
                    ephemeral=True
                )
                return

            # 2. Check finances
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

            # Deduct cost
            finances["checking_account_balance"] -= cost
            await upsert_user_finances(pool, user_id, finances)

            # 3. Prepare vehicle info (your existing logic)
            if item["type"] == "Beater Car":
                condition = "4"
                travel_count = random.randint(151, 195)
                resale_percent = 0.3
            else:
                condition = "1"
                travel_count = 0
                resale_percent = 0.85

            print(f"[handle_vehicle_purchase] Inserting vehicle with condition '{condition}', travel_count '{travel_count}', resale_percent {resale_percent}")

            # 4. Get random color and plate number
            color_row = await conn.fetchrow("SELECT description FROM cd_vehicle_colors ORDER BY random() LIMIT 1")
            color = color_row["description"] if color_row else "Unknown"
            if item["type"] == "Bike":
                funny_suffixes = ["ZOOM", "WHOAH", "SPOKEME", "TIRED-LOL", "RIDEME", "SLOWAF", "WHEEE", "B-ROKE", "RDHOG", "2POOR4CAR"]
                plate_number = random.choice(funny_suffixes)
            else:
                plate_number = generate_random_plate()

            condition_int = int(condition)

            condition_desc_row = await conn.fetchrow(
                "SELECT description FROM cd_vehicle_condition WHERE condition_id = $1",
                condition_int
            )
            condition_desc = condition_desc_row["description"] if condition_desc_row else "Unknown"

            appearance_row = await conn.fetchrow("""
                SELECT description
                FROM cd_vehicle_appearance
                WHERE vehicle_type_id = $1 AND condition_id = $2
                ORDER BY random()
                LIMIT 1
            """, item["vehicle_type_id"], condition_int)

            appearance_description = appearance_row["description"] if appearance_row else "No description available"

            # 5. Insert new vehicle and get vehicle_id
            insert_query = """
                INSERT INTO user_vehicle_inventory (
                    user_id, vehicle_type_id, color, appearance_description, plate_number, condition, travel_count, created_at, resale_percent
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, NOW(), $8)
                RETURNING id
            """
            vehicle_id = await conn.fetchval(
                insert_query,
                user_id, item["vehicle_type_id"], color, appearance_description, plate_number, condition_desc, travel_count, resale_percent
            )

            # 6. Update user's last_used_vehicle
            await conn.execute(
                "UPDATE users SET last_used_vehicle = $1 WHERE user_id = $2",
                vehicle_id, user_id
            )

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


    @tree.command(name="needfunds", description=f"Claim your guberment cheese (${PAYCHECK_AMOUNT:,}) every 24h")
    async def needfunds(interaction: Interaction):
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

        # Check achievement
        achievement = await pool.fetchrow(
            "SELECT 1 FROM user_achievements WHERE user_id = $1 AND achievement_id = 1",
            user_id
        )
        if achievement:
            payout = PAYCHECK_AMOUNT * 2
        else:
            payout = PAYCHECK_AMOUNT

        finances['checking_account_balance'] += payout
        finances['last_paycheck_claimed'] = now
        await upsert_user_finances(pool, user_id, finances)

        await interaction.response.send_message(embed=embed_message(
            "💵 Paycheck Claimed",
            f"> You got ${payout:,}!\n💰 New Balance: ${finances['checking_account_balance']:,}",
            COLOR_GREEN
        ), ephemeral=True)


   

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
                        SELECT
                            uvi.id, uvi.color, uvi.appearance_description, uvi.condition,
                            uvi.travel_count, uvi.created_at, uvi.resale_percent,
                            cvt.name AS type, uvi.plate_number, cvt.emoji
                        FROM user_vehicle_inventory uvi
                        JOIN cd_vehicle_type cvt ON uvi.vehicle_type_id = cvt.id
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
                    travel_count = item.get("travel_count", 0)
                    emoji = item.get("emoji", "🚗")

                    desc_lines.append(
                        f"> {emoji} **{vehicle_type}** | Plate: {item['plate_number']}\n"
                        f"> \u200b\u200b    Condition: {condition}\n"
                        f"> \u200b\u200b    Description: {description}\n"
                        f"> \u200b\u200b    Travel Count: {travel_count}"
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