import discord
from discord.ext import commands, tasks
import datetime
from Bot_occupations.career_path_views import ConfirmResignView
from embeds import COLOR_GREEN, COLOR_RED

class CareerPath(commands.Cog):
    def __init__(self, bot, db_pool):
        self.bot = bot
        self.db_pool = db_pool
        self.daily_shift_check.start()

    def cog_unload(self):
        self.daily_shift_check.cancel()

    @commands.hybrid_group(name="careerpath", description="Manage your career path")
    async def careerpath(self, ctx):
        if ctx.invoked_subcommand is None:
            await ctx.send("Please use a subcommand: workshift or resign")

    @careerpath.command(name="workshift", description="Log a work shift and add your pay")
    async def workshift(self, ctx):
        await ctx.defer()
        user_id = ctx.author.id
        print(f"[workshift] Started for user_id: {user_id}")

        try:
            async with self.db_pool.acquire() as conn:
                print("[workshift] Checking occupation_needs_warning...")
                try:
                    needs_warning = await conn.fetchval(
                        "SELECT occupation_needs_warning FROM users WHERE user_id = $1",
                        user_id
                    )
                    print(f"[workshift] occupation_needs_warning: {needs_warning}")
                except Exception as e:
                    print(f"[workshift] ERROR fetching occupation_needs_warning: {e}")
                    raise

                if needs_warning:
                    print("[workshift] Sending warning message...")
                    await self._send_warning_message(ctx)
                    try:
                        await conn.execute(
                            "UPDATE users SET occupation_needs_warning = FALSE WHERE user_id = $1",
                            user_id
                        )
                        print("[workshift] Cleared occupation_needs_warning flag.")
                    except Exception as e:
                        print(f"[workshift] ERROR clearing occupation_needs_warning: {e}")
                        raise

                print("[workshift] Fetching occupation info...")
                occ_query = """
                    SELECT o.cd_occupation_id, o.description, o.pay_rate, o.required_shifts_per_day
                    FROM users u
                    JOIN cd_occupations o ON u.occupation_id = o.cd_occupation_id
                    WHERE u.user_id = $1
                    AND u.occupation_id IS NOT NULL;
                """
                occupation = await conn.fetchrow(occ_query, user_id)
                print(f"[workshift] Occupation row: {occupation}")
                occupation_name = occupation['description']
                pay_rate = occupation['pay_rate']
                required_shifts_per_day = occupation['required_shifts_per_day']

                try:
                    occupation = await conn.fetchrow(occ_query, user_id)
                    print(f"[workshift] Occupation row: {occupation}")
                except Exception as e:
                    print(f"[workshift] ERROR fetching occupation info: {e}")
                    raise

                if occupation is None:
                    print("[workshift] No active occupation found.")
                    await ctx.send("You don't currently have an active occupation.")
                    return

                print("[workshift] Inserting new shift log...")
                try:
                    await conn.execute(
                        "INSERT INTO user_work_log(user_id, work_timestamp) VALUES ($1, NOW())",
                        user_id
                    )
                    print("[workshift] Shift log inserted.")
                except Exception as e:
                    print(f"[workshift] ERROR inserting shift log: {e}")
                    raise

                print("[workshift] Counting today's shifts...")
                try:
                    shifts_today = await conn.fetchval(
                        "SELECT COUNT(*) FROM user_work_log WHERE user_id = $1 AND work_timestamp >= CURRENT_DATE",
                        user_id
                    )
                    print(f"[workshift] Shifts today: {shifts_today}")
                except Exception as e:
                    print(f"[workshift] ERROR counting shifts: {e}")
                    raise

                print("[workshift] Updating user balance...")
                try:
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        occupation['pay_rate'],
                        user_id
                    )
                    print("[workshift] Balance updated.")
                except Exception as e:
                    print(f"[workshift] ERROR updating balance: {e}")
                    raise

            embed = discord.Embed(
                title="🕒 Shift Logged",
                description=(
                    f"You completed your shift as a **{occupation_name}** and earned **${pay_rate:.2f}**.\n"
                    f"Your total completed shifts today: **{shifts_today}/{required_shifts}**\n\n"
                    f"💵 ${pay_rate:.2f} has been deposited into your checking account.\n"
                    f"**New Balance:** ${new_balance:.2f}\n\n"
                    f"*Paid. Hopefully this cash sticks around longer than your last situationship.*"
                ),
                color=COLOR_GREEN
            )

            await ctx.send(embed=embed)
            print("[workshift] Response sent.")

        except Exception as e:
            print(f"[workshift] Exception caught: {e}")
            try:
                await ctx.send("An error occurred while logging your shift. Please try again later.")
            except:
                print("[workshift] Failed to send error message to user.")

    @careerpath.command(name="resign", description="Resign from your job with confirmation")
    async def resign(self, ctx):
        await ctx.defer(ephemeral=True)
        user_id = ctx.author.id
        print(f"[resign] Started for user_id: {user_id}")

        try:
            embed = discord.Embed(
                title="📝 Submit Letter of Resignation",
                description="Are you sure you want to resign?",
                color=discord.Color.orange()
            )
            view = ConfirmResignView(ctx.author)
            await ctx.send(embed=embed, view=view, ephemeral=True)
            print("[resign] Confirmation view sent.")

            await view.wait()
            print(f"[resign] View result: {view.value}")

            if view.value is None:
                embed = discord.Embed(
                    title="⏰ Resignation Timed Out",
                    description="No changes were made.",
                    color=COLOR_RED
                )
                await ctx.send(embed=embed, ephemeral=True)
                print("[resign] Resignation timed out, no changes.")

            elif view.value:
                async with self.db_pool.acquire() as conn:
                    print("[resign] Clearing user's occupation in DB...")
                    await conn.execute(
                        "UPDATE users SET occupation_id = NULL, occupation_failed_days = 0, occupation_needs_warning = FALSE WHERE user_id = $1",
                        user_id
                    )
                    print("[resign] Occupation cleared.")

                embed = discord.Embed(
                    title="✅ Resignation Successful",
                    description="You have successfully resigned from your job.",
                    color=COLOR_GREEN
                )
                await ctx.send(embed=embed, ephemeral=True)
                print("[resign] Success message sent.")

            else:
                print("[resign] Resignation cancelled by user.")
                # No further action needed.

        except Exception as e:
            print(f"[resign] Exception caught: {e}")
            try:
                await ctx.send("An error occurred during resignation. Please try again later.", ephemeral=True)
            except:
                print("[resign] Failed to send error message to user.")

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
            f"Thanks for your time with us. Better luck next game! 🎮👋"
        )
        try:
            await user.send(msg)
        except:
            pass


async def setup(bot):
    await bot.add_cog(CareerPath(bot, bot.pool), override=True)
