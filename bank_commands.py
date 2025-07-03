import discord
from discord import app_commands, Interaction
from db_user import get_user, upsert_user
from utilities import embed_message, parse_amount
from defaults import DEFAULT_USER
from config import COLOR_RED, COLOR_GREEN
import globals  
from discord.ext import commands


class Bank(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    bank_group = app_commands.Group(name="bank", description="Manage your bank accounts")

    @bank_group.command(name="view", description="View your checking and savings balances")
    async def view(self, interaction: Interaction):
        user_id = interaction.user.id
        user = await get_user(pool, user_id)
        if user is None:
            user = DEFAULT_USER.copy()
            await upsert_user(pool, user_id, user)

        checking = user.get('checking_account_balance', 0)
        savings = user.get('savings_account_balance', 0)

        await interaction.response.send_message(
            embed=embed_message(
                "💰 Account Balances",
                f"> {interaction.user.display_name}, your account balances are:\n"
                f"> 💰 Checking: ${checking:,}\n"
                f"> 🏦 Savings: ${savings:,}"
            )
        )

    @bank_group.command(name="withdraw", description="Withdraw money from savings to checking")
    @app_commands.describe(amount="Amount to withdraw (number or 'all')")
    async def withdraw(self, interaction: Interaction, amount: str):
        parsed_amount = parse_amount(amount)
        if parsed_amount is None:
            await interaction.response.send_message(
                embed=embed_message(
                    "❌ Invalid Format",
                    "Use numbers like 1000, or 'all'.",
                    COLOR_RED
                ),
                ephemeral=True
            )
            return

        user_id = interaction.user.id
        user = await get_user(pool, user_id)
        if user is None:
            user = DEFAULT_USER.copy()

        savings = user.get('savings_account_balance', 0)
        amount_int = savings if parsed_amount == -1 else parsed_amount

        if amount_int <= 0 or amount_int > savings:
            await interaction.response.send_message(
                embed=embed_message(
                    "❌ Invalid Amount",
                    ">The bank laughed at you hysterically for attempting to withdraw more from your savings than you actually have. Try again.",
                    COLOR_RED
                ),
                ephemeral=True
            )
            return

        user['savings_account_balance'] -= amount_int
        user['checking_account_balance'] = user.get('checking_account_balance', 0) + amount_int
        await upsert_user(pool, user_id, user)

        await interaction.response.send_message(
            embed=embed_message(
                "✅ Withdrawal Complete",
                f"> Moved ${amount_int:,} from savings to checking.\n"
                f"> 💰 Checking: ${user['checking_account_balance']:,}\n"
                f"> 🏦 Savings: ${user['savings_account_balance']:,}",
                COLOR_GREEN
            )
        )

    @bank_group.command(name="deposit", description="Deposit money from checking to savings")
    @app_commands.describe(amount="Amount to deposit (number or 'all')")
    async def deposit(self, interaction: Interaction, amount: str):
        parsed_amount = parse_amount(amount)
        if parsed_amount is None:
            await interaction.response.send_message(
                embed=embed_message(
                    "❌ Invalid Format",
                    "Use numbers like 1000, or 'all'.",
                    COLOR_RED
                ),
                ephemeral=True
            )
            return

        user_id = interaction.user.id
        user = await get_user(pool, user_id)
        if user is None:
            user = DEFAULT_USER.copy()

        checking = user.get('checking_account_balance', 0)
        amount_int = checking if parsed_amount == -1 else parsed_amount

        if amount_int <= 0 or amount_int > checking:
            await interaction.response.send_message(
                embed=embed_message(
                    "❌ Invalid Amount",
                    "> You don't have that much money in your checking account to deposit.Try again when your deposit amount is higher than your IQ ",
                    COLOR_RED
                ),
                ephemeral=True
            )
            return

        user['checking_account_balance'] -= amount_int
        user['savings_account_balance'] = user.get('savings_account_balance', 0) + amount_int
        await upsert_user(pool, user_id, user)

        await interaction.response.send_message(
            embed=embed_message(
                "✅ Deposit Complete",
                f"> Moved ${amount_int:,} to savings.\n"
                f"> 💰 Checking: ${user['checking_account_balance']:,}\n"
                f"> 🏦 Savings: ${user['savings_account_balance']:,}",
                COLOR_GREEN
            )
        )

async def setup(bot):
    await bot.add_cog(Bank(bot))
