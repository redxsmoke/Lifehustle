print("✅ DEBUG: Loaded career_path_command.py version 2025-07-06 18:45")

import discord
print(discord.__version__)

from discord.ext import commands, tasks
import datetime
import random
from Bot_occupations.career_path_views import ConfirmResignView

from embeds import COLOR_GREEN, COLOR_RED

# Added imports for mini-games from occupation_mini_games folder
from Bot_occupations.occupation_mini_games import whichdidthat
from Bot_occupations.occupation_mini_games import snake_breakroom
from Bot_occupations.occupation_mini_games.quickchange import run_quick_math_game
from Bot_occupations.occupation_mini_games.shared import build_paystub_embed
from Bot_occupations.occupation_mini_games.late_to_work import SneakInMiniGameView



class CareerPath(commands.Cog):
    def __init__(self, bot, db_pool):
        self.bot = bot
        self.db_pool = db_pool
        self.daily_shift_check.start()

    def cog_unload(self):
        self.daily_shift_check.cancel()

    @commands.hybrid_group(name="careerpath", description="Manage your career path")
    async def careerpath(self, ctx):
        command_obj = self.bot.get_command("careerpath")
        print(f"✅ careerpath group type = {type(command_obj)}")
        print(f"✅ careerpath dir = {dir(command_obj)}")
        
        if ctx.invoked_subcommand is None:
            # No defer here, so just regular send
            await ctx.send("Please use a subcommand: clockin or resign")


    class MiniGameButton(discord.ui.Button):
        def __init__(self, label, view):
            super().__init__(label=label, style=discord.ButtonStyle.primary)
            self.mini_game_view = view

        async def callback(self, interaction: discord.Interaction):
            # Disable all buttons once clicked
            for child in self.mini_game_view.children:
                child.disabled = True
            await interaction.response.edit_message(view=self.mini_game_view)

            # Run the mini-game logic with the player's guess
            result = await play(
                self.mini_game_view.pool,
                interaction.guild_id,
                interaction.user.id,
                self.mini_game_view.user_occupation_id,
                guess=self.label,
            )

            embed = discord.Embed(title=result["title"], description=result["description"])
            if result["bonus"] > 0:
                embed.color = discord.Color.green()
                embed.add_field(name="Bonus", value=f"+${result['bonus']}")
            elif result["bonus"] < 0:
                embed.color = discord.Color.red()
                embed.add_field(name="Penalty", value=f"${result['bonus']}")
            else:
                embed.color = discord.Color.gold()

            await interaction.followup.send(embed=embed)


    class MiniGameView(discord.ui.View):
        def __init__(self, pool, user_occupation_id):
            super().__init__(timeout=60)
            self.pool = pool
            self.user_occupation_id = user_occupation_id
            self.config = None

        async def setup(self):
            # Fetch user job name from DB to get config
            async with self.pool.acquire() as conn:
                user_job = await conn.fetchval("SELECT description FROM cd_occupations WHERE cd_occupation_id = $1", self.user_occupation_id)
            if not user_job:
                return False
            self.job_key = user_job.lower()
            self.config = MINIGAME_CONFIGS.get(self.job_key)
            if not self.config:
                return False

            # Add buttons for each choice
            for choice in self.config["choices"]:
                self.add_item(MiniGameButton(choice, self))

            return True


    @careerpath.command(name="clockin", description="Clock in to work and collect your pay")
    async def clockin(self, ctx):
        print("✅ DEBUG: clockin command invoked")
        await ctx.defer()
        user_id = ctx.author.id
        print(f"[clockin] Started for user_id: {user_id}")

        try:
            async with self.db_pool.acquire() as conn:
                print("[clockin] Checking occupation_needs_warning...")
                try:
                    needs_warning = await conn.fetchval(
                        "SELECT occupation_needs_warning FROM users WHERE user_id = $1",
                        user_id
                    )
                    print(f"[clockin] occupation_needs_warning: {needs_warning}")
                except Exception as e:
                    print(f"[clockin] ERROR fetching occupation_needs_warning: {e}")
                    raise

                if needs_warning:
                    print("[clockin] Sending warning message...")
                    await self._send_warning_message(ctx)
                    try:
                        await conn.execute(
                            "UPDATE users SET occupation_needs_warning = FALSE WHERE user_id = $1",
                            user_id
                        )
                        print("[clockin] Cleared occupation_needs_warning flag.")
                    except Exception as e:
                        print(f"[clockin] ERROR clearing occupation_needs_warning: {e}")
                        raise

                print("[clockin] Fetching occupation info...")
                occ_query = """
                    SELECT o.cd_occupation_id, o.description, o.pay_rate, o.required_shifts_per_day, o.company_name
                    FROM users u
                    JOIN cd_occupations o ON u.occupation_id = o.cd_occupation_id
                    WHERE u.user_id = $1
                    AND u.occupation_id IS NOT NULL;
                """
                occupation = await conn.fetchrow(occ_query, user_id)
                print(f"[clockin] Occupation row: {occupation}")

                if occupation is None:
                    msg = "❌ You don't have a job yet. Use `/need_work` to get hired!"
                    if hasattr(ctx, "followup"):
                        await ctx.followup.send(msg)
                    else:
                        await ctx.send(msg)
                    return

                occupation_id = occupation["cd_occupation_id"]
                occupation_name = occupation["description"]
                company_name = occupation["company_name"]
                pay_rate = float(occupation["pay_rate"])
                required_shifts_per_day = occupation["required_shifts_per_day"]

                # Insert a new shift log
                await conn.execute(
                    "INSERT INTO user_work_log(user_id, work_timestamp) VALUES ($1, NOW())",
                    user_id
                )
                print("[clockin] Shift log inserted.")

                # --- MINI-GAME SELECTION ---
                minigames_by_id = {
                    1: [run_quick_math_game, snake_breakroom, whichdidthat],  # Professional Cuddler
                    2: [snake_breakroom, whichdidthat],                      # Senior Bubble Wrap Popper
                    3: [snake_breakroom, whichdidthat],                      # Street Performer
                    4: [run_quick_math_game, snake_breakroom, whichdidthat], # Dog Walker
                    5: [snake_breakroom, whichdidthat],                      # Human Statue
                    11: [run_quick_math_game, snake_breakroom, whichdidthat, sneak_in_late_game], # Grocery Store Clerk
                    16: [run_quick_math_game, snake_breakroom, whichdidthat, sneak_in_late_game], # Ice Cream Truck Driver
                    19: [sneak_in_late_game], # Waiter/Waitress
                    61: [snake_breakroom, sneak_in_late_game],               # Animal Control only
                }

                mini_game_modules = minigames_by_id.get(occupation_id)
                if not mini_game_modules:
                    no_minigame_msg = (
                        f"🧹 You worked a shift as a **{occupation_name}**, "
                        "but this job doesn't have a mini-game yet. No payout this time!"
                    )
                    if hasattr(ctx, "followup"):
                        await ctx.followup.send(no_minigame_msg)
                    else:
                        await ctx.send(no_minigame_msg)
                    return

                minigame_module = random.choice(mini_game_modules)

                mini_game_result = None
                message = None  # Track message for editing paystub later

                # Existing run_quick_math_game logic
                if minigame_module == run_quick_math_game:
                    mini_game_result = await run_quick_math_game(ctx.interaction, job_key=occupation_name.lower())
                    message = None

                # Your new sneak_in_late_game logic
                elif minigame_module == sneak_in_late_game:
                    mini_game_result = await sneak_in_late_game(ctx, user_id, self.db_pool)
                    message = None  # The wrapper sends its own message

                # Existing .play() interface for other games
                else:
                    embed, view = await minigame_module.play(
                        self.db_pool,
                        ctx.guild.id,
                        user_id,
                        occupation_id,
                        pay_rate if minigame_module == snake_breakroom else None,
                        None
                    )
                    message = await ctx.send(embed=embed, view=view)
                    await view.wait()
                    mini_game_result = {
                        "result": getattr(view, "outcome_type", "neutral"),
                        "bonus": getattr(view, "bonus_amount", 0),
                        "message": getattr(view, "outcome_summary", None),
                        "dock": getattr(view, "dock_amount", 0),
                        "penalty": getattr(view, "penalty_amount", 0),
                    }

                if mini_game_result is None:
                    await ctx.send("❌ Mini-game did not complete correctly. Please try again.")
                    return
                print(f"[DEBUG] mini_game_result raw: {mini_game_result}")

                result_type = mini_game_result.get('result', 'neutral')

                # Pull bonus or fallback to penalty/dock if bonus is missing
                if 'bonus' in mini_game_result:
                    bonus = mini_game_result['bonus']
                elif result_type == 'timeout' and 'penalty' in mini_game_result:
                    bonus = -abs(mini_game_result['penalty'])
                elif result_type in ('wrong', 'negative') and 'dock' in mini_game_result:
                    bonus = -abs(mini_game_result['dock'])
                else:
                    bonus = 0

                print(f"[DEBUG] Calculated bonus: {bonus}")

                outcome_summary = mini_game_result.get('message', "No mini-game outcome.")
                total_pay = pay_rate + bonus
                print(f"[DEBUG] pay_rate: {pay_rate}, total_pay (base + bonus): {total_pay}")

                # Count shifts today
                shifts_today = await conn.fetchval(
                    "SELECT COUNT(*) FROM user_work_log WHERE user_id = $1 AND work_timestamp >= CURRENT_DATE",
                    user_id
                )
                print(f"[clockin] Shifts today: {shifts_today}")

                # Get new balance to show in embed
                new_balance = await conn.fetchval(
                    "SELECT checking_account_balance FROM user_finances WHERE user_id = $1",
                    user_id
                )

            # Update user balance once here
            async with self.db_pool.acquire() as conn:
                await conn.execute(
                    "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                    total_pay,
                    user_id
                )
                new_balance = await conn.fetchval(
                    "SELECT checking_account_balance FROM user_finances WHERE user_id = $1",
                    user_id
                )

            # Build the combined paystub description
            paystub_description = (
                f"> You completed your shift as a **{occupation_name}**.\n"
                f"> Base pay: **${pay_rate:.2f}**\n"
                f"> Mini-game bonus: **${bonus:+.2f}**\n"
                f"> Total earned: **${total_pay:.2f}**\n"
                f"> New balance: **${new_balance:,.2f}**\n"
            )

            if outcome_summary:
                paystub_description += f"\n**Mini-game outcome:**\n{outcome_summary}\n"

            combined_embed = discord.Embed(
                title=f"🕒 Shift Logged - Pay Stub from ***{company_name}***",
                description=paystub_description,
                color=discord.Color.green() if bonus > 0 else discord.Color.red() if bonus < 0 else discord.Color.gold()
            )

            # Edit the original mini-game message to remove buttons and show paystub
            # Only if message is defined (i.e., not None)
            if message:
                await message.edit(embed=combined_embed, view=None)
            else:
                # If no original message (e.g., quick math game or sneak_in_late_game), just send the embed
                await ctx.send(embed=combined_embed)

            print("[clockin] Response sent.")

        except Exception as e:
            print(f"[clockin] Exception caught: {e}")
            error_msg = "❌ An error occurred while processing your shift. Please try again later."
            if hasattr(ctx, "followup"):
                await ctx.followup.send(error_msg)
            else:
                await ctx.send(error_msg)

    @careerpath.command(name="resign", description="Resign from your job with confirmation")
    async def resign(self, ctx):
        import time
        import asyncio

        def log(msg):
            print(f"[resign][{time.strftime('%H:%M:%S')}] {msg}")

        await ctx.defer(ephemeral=True)
        user_id = ctx.author.id
        log(f"Started for user_id: {user_id}")

        try:
            # Step 1: Show confirmation view
            confirm_embed = discord.Embed(
                title="📝 Submit Letter of Resignation",
                description="Are you sure you want to resign?",
                color=discord.Color.orange()
            )
            view = ConfirmResignView(ctx.author)
            message = await ctx.send(embed=confirm_embed, view=view, ephemeral=True)
            log("Confirmation sent")

            # Step 2: Wait for response or timeout
            try:
                await asyncio.wait_for(view.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                view.value = None
                log("Timeout waiting for confirmation")

            # Step 3: Build result embed based on input
            if view.value is None:
                result_embed = discord.Embed(
                    title="⏰ Timed Out",
                    description="No response received. No changes made.",
                    color=COLOR_RED
                )
            elif view.value:
                try:
                    async with self.db_pool.acquire() as conn:
                        log("Clearing occupation...")
                        await conn.execute(
                            "UPDATE users SET occupation_id = NULL, occupation_failed_days = 0, occupation_needs_warning = FALSE WHERE user_id = $1",
                            user_id
                        )
                        log("Occupation cleared")
                    result_embed = discord.Embed(
                        title="✅ Resigned",
                        description="> You're now unemployed. Good luck out there.",
                        color=COLOR_GREEN
                    )
                except Exception as db_err:
                    log(f"DB error: {db_err}")
                    result_embed = discord.Embed(
                        title="❌ DB Error",
                        description="Something went wrong updating your job status.",
                        color=COLOR_RED
                    )
            else:
                result_embed = discord.Embed(
                    title="❎ Cancelled",
                    description="Resignation was cancelled.",
                    color=discord.Color.greyple()
                )

            # Step 4: Finalize interaction
            await message.edit(embed=result_embed, view=None)
            log("Interaction completed")

        except Exception as e:
            log(f"Fatal error: {e}")

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone.utc))
    async def daily_shift_check(self):
        async with self.db_pool.acquire() as conn:
            query = """
            WITH shifts_yesterday AS (
              SELECT user_id, COUNT(*) AS shifts_worked
              FROM user_work_log
              WHERE work_timestamp >= CURRENT_DATE - INTERVAL '1 day'
                AND work_timestamp < CURRENT_DATE
              GROUP BY user_id
            )
            SELECT
              u.user_id,
              o.required_shifts_per_day,
              COALESCE(sy.shifts_worked, 0) AS shifts_worked,
              u.occupation_failed_days,
              o.maxed_amount_failed_shifts
            FROM users u
            JOIN cd_occupations o ON u.occupation_id = o.occupation_id
            LEFT JOIN shifts_yesterday sy ON sy.user_id = u.user_id
            WHERE u.occupation_needs_warning = FALSE
              AND u.occupation_failed_days < o.maxed_amount_failed_shifts
              AND COALESCE(sy.shifts_worked, 0) < o.required_shifts_per_day;
            """

            failed_users = await conn.fetch(query)

            for record in failed_users:
                user_id = record['user_id']
                required = record['required_shifts_per_day']
                worked = record['shifts_worked']
                failed_days = record['occupation_failed_days']
                max_failed = record['maxed_amount_failed_shifts']

                new_failed_days = failed_days + 1

                if new_failed_days >= max_failed:
                    await conn.execute(
                        "UPDATE users SET occupation_id = NULL, occupation_needs_warning = FALSE, occupation_failed_days = $1 WHERE user_id = $2",
                        new_failed_days,
                        user_id
                    )
                    await self._send_fired_message(user_id)
                else:
                    await conn.execute(
                        "UPDATE users SET occupation_failed_days = $1, occupation_needs_warning = TRUE WHERE user_id = $2",
                        new_failed_days,
                        user_id
                    )

            await conn.execute(
                """
                DELETE FROM user_work_log
                WHERE work_timestamp < CURRENT_DATE;
                """
            )

    @daily_shift_check.before_loop
    async def before_daily_shift_check(self):
        await self.bot.wait_until_ready()

    async def _get_company_name(self, user_id):
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT c.company_name
                FROM users u
                JOIN cd_occupations c ON u.occupation_id = c.occupation_id
                WHERE u.user_id = $1
                """,
                user_id
            )
            return row['company_name'] if row else "Your Company"

    async def _send_warning_message(self, ctx):
        company_name = await self._get_company_name(ctx.author.id)
        msg = (
            f"**Message from {company_name} HQ 🚨**\n"
            f"Hey {ctx.author.display_name},\n\n"
            f"You ghosted your shifts yesterday! 👻 That’s a write-up on your virtual clipboard. "
            f"Miss too many, and the digital pink slip’s coming! 📨\n\n"
            f"We believe in second chances — show up or get booted! 💼👢\n\n"
            f"Need help? We got your back. Keep grinding! 🌟"
        )
        await ctx.send(msg)

    async def _send_fired_message(self, user_id):
        user = self.bot.get_user(user_id)
        if user is None:
            try:
                user = await self.bot.fetch_user(user_id)
            except:
                return

        msg = (
            f"**Message from {await self._get_company_name(user_id)} HQ 🚨**\n"
            f"Hey {user.name},\n\n"
            f"You've been fired! The digital pink slip has arrived. "
            f"Thanks for your time with us. Better luck next time! 🎮👋"
        )
        try:
            await user.send(msg)
        except:
            pass


async def setup(bot):
    await bot.add_cog(CareerPath(bot, bot.pool), override=True)
