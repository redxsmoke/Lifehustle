import discord
from discord.ui import View, Button
import random

# ------------------------------
# Regular Snake Breakroom Minigame
# ------------------------------
class SnakeBreakroomView(View):
    def __init__(self, pool, guild_id, user_id, user_occupation_id, pay_rate):
        super().__init__(timeout=60)
        self.pool = pool
        self.guild_id = guild_id
        self.user_id = user_id
        self.user_occupation_id = user_occupation_id
        self.pay_rate = pay_rate
        self.outcome_summary = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def apply_penalty(self, min_penalty=20, max_penalty=100, max_multiplier=3):
        # Random penalty amount between min and max multiplied by a random multiplier between 1 and max_multiplier
        penalty_amount = random.randint(min_penalty, max_penalty) * random.randint(1, max_multiplier)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                penalty_amount,
                self.user_id,
            )
        return penalty_amount

    @discord.ui.button(label="Call Animal Control", style=discord.ButtonStyle.primary)
    async def call_animal_control(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            async with self.pool.acquire() as conn:
                helper = await conn.fetchrow(
                    """
                    SELECT user_id FROM users
                    WHERE occupation_id = 61  -- Animal Control occupation ID
                    AND guild_id = $1
                    AND user_id != $2
                    LIMIT 1
                    """,
                    self.guild_id,
                    self.user_id,
                )

                if helper:
                    helper_member = interaction.guild.get_member(helper['user_id'])
                    if helper_member:
                        helper_name = helper_member.mention
                    else:
                        user_obj = await interaction.client.fetch_user(helper['user_id'])
                        helper_name = f"<@{user_obj.id}>"

                    user_member = interaction.guild.get_member(self.user_id)
                    if user_member:
                        user_name = user_member.mention
                    else:
                        user_obj = await interaction.client.fetch_user(self.user_id)
                        user_name = f"<@{user_obj.id}>"

                    bonus = random.randint(20, 500) * random.randint(1, 4)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        self.user_id,
                    )
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        helper['user_id'],
                    )
                    desc = (
                        f"You called Animal Control! {helper_name} from Fur Get About It Animal Control rushed in to help {user_name}. "
                        f"Both get a bonus of ${bonus}!"
                    )
                else:
                    # No helper found, generic message, no penalty
                    desc = (
                        "You called Animal Control but no one showed up. Animal Control was late and your boss docked your pay for their poor punctuality or something."
                    )
                    # Apply penalty because of late arrival
                    penalty_amount = await self.apply_penalty()
                    desc += f"\n\nYour pay was docked by ${penalty_amount}."

            self.outcome_summary = desc
            await interaction.response.edit_message(content=desc, embed=None, view=None)
            self.stop()
        except Exception as e:
            print(f"Error in call_animal_control: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong!", ephemeral=True)
            self.stop()

    @discord.ui.button(label="Grab it by the neck", style=discord.ButtonStyle.danger)
    async def grab_by_neck(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            outcome_roll = random.random()
            desc = ""
            penalty_amount = None
            bonus = None

            async with self.pool.acquire() as conn:
                if outcome_roll < 0.33:
                    # Negative outcome - penalty
                    penalty_amount = random.randint(20, 100) * random.randint(1, 3)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                        penalty_amount,
                        self.user_id,
                    )
                    desc = (
                        "You tried to grab the snake by the neck but it bit you viciously! "
                        f"You lost ${penalty_amount} in medical bills and emotional trauma."
                    )
                elif outcome_roll < 0.66:
                    # Neutral outcome - no bonus/penalty
                    desc = (
                        "You tried to grab the snake but it slipped away laughing at your incompetence. Snake 1, you 0."
                    )
                else:
                    # Positive outcome - bonus
                    bonus = random.randint(20, 500) * random.randint(1, 4)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        self.user_id,
                    )
                    desc = (
                        f"You grabbed the snake by the neck and totally nailed it! The snake didn’t stand a chance against your heroic grip. Bonus: ${bonus}!"
                    )

            self.outcome_summary = desc
            await interaction.response.edit_message(content=desc, embed=None, view=None)
            self.stop()

        except Exception as e:
            print(f"Error in grab_by_neck: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong!", ephemeral=True)
            self.stop()

    @discord.ui.button(label="Put a bucket over it", style=discord.ButtonStyle.secondary)
    async def put_bucket(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            outcome_roll = random.random()
            desc = ""
            penalty_amount = None

            async with self.pool.acquire() as conn:
                if outcome_roll < 0.33:
                    # Negative outcome - penalty
                    penalty_amount = random.randint(20, 100) * random.randint(1, 3)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                        penalty_amount,
                        self.user_id,
                    )
                    desc = (
                        f"Your boss noticed your lack of initiative and docked your pay by ${penalty_amount}."
                    )
                elif outcome_roll < 0.66:
                    # Neutral outcome - no penalty or bonus
                    desc = (
                        "You put a bucket over the snake and walked away, hoping someone else deals with it. Not exactly team spirit, but no trouble for you either."
                    )
                else:
                    # Positive outcome - bonus
                    bonus = random.randint(20, 500) * random.randint(1, 4)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        self.user_id,
                    )
                    desc = (
                        f"You cleverly trapped the snake under the bucket and earned a bonus of ${bonus} for your initiative!"
                    )

            self.outcome_summary = desc
            await interaction.response.edit_message(content=desc, embed=None, view=None)
            self.stop()

        except Exception as e:
            print(f"Error in put_bucket: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong!", ephemeral=True)
            self.stop()

    @discord.ui.button(label="Distract it with snacks", style=discord.ButtonStyle.success)
    async def distract_with_snacks(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            outcome_roll = random.random()
            desc = ""
            penalty_amount = None
            bonus = None

            async with self.pool.acquire() as conn:
                if outcome_roll < 0.33:
                    # Negative outcome - penalty
                    penalty_amount = random.randint(20, 100) * random.randint(1, 3)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                        penalty_amount,
                        self.user_id,
                    )
                    desc = (
                        f"Your distraction backfired and the snake got angrier. Management docked your pay by ${penalty_amount}."
                    )
                elif outcome_roll < 0.66:
                    # Neutral outcome
                    desc = "You distracted the snake with snacks but it didn't calm down much. No bonus this time."
                else:
                    # Positive outcome - bonus
                    bonus = random.randint(20, 500) * random.randint(1, 4)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        self.user_id,
                    )
                    desc = (
                        f"You successfully distracted the snake with snacks! Bonus of ${bonus} awarded."
                    )

            self.outcome_summary = desc
            await interaction.response.edit_message(content=desc, embed=None, view=None)
            self.stop()

        except Exception as e:
            print(f"Error in distract_with_snacks: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong!", ephemeral=True)
            self.stop()

async def play_snake_breakroom(pool, guild_id, user_id, user_occupation_id, pay_rate):
    embed = discord.Embed(
        title="🐍 Snake in the Break Room",
        description=(
            "You find a snake in the break room during your shift! What do you want to do?\n\n"
            "1️⃣ Call Animal Control\n"
            "2️⃣ Grab it by the neck\n"
            "3️⃣ Put a bucket over it and leave it\n"
            "4️⃣ Distract it with snacks\n\n"
            "Choose wisely!"
        )
    )
    view = SnakeBreakroomView(pool, guild_id, user_id, user_occupation_id, pay_rate)
    return embed, view

# ------------------------------
# Animal Control Snake Minigame Variant
# ------------------------------
class AnimalControlSnakeView(View):
    def __init__(self, pool, guild_id, user_id, user_occupation_id, pay_rate):
        super().__init__(timeout=60)
        self.pool = pool
        self.guild_id = guild_id
        self.user_id = user_id
        self.user_occupation_id = user_occupation_id
        self.pay_rate = pay_rate
        self.outcome_summary = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def apply_penalty(self, min_penalty=20, max_penalty=100, max_multiplier=3):
        penalty_amount = random.randint(min_penalty, max_penalty) * random.randint(1, max_multiplier)
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                penalty_amount,
                self.user_id,
            )
        return penalty_amount

    @discord.ui.button(label="Safely capture the snake", style=discord.ButtonStyle.primary)
    async def safe_capture(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            outcome_roll = random.random()
            desc = ""
            penalty_amount = None
            bonus = None

            async with self.pool.acquire() as conn:
                if outcome_roll < 0.33:
                    # Negative outcome - penalty
                    penalty_amount = random.randint(20, 100) * random.randint(1, 3)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                        penalty_amount,
                        self.user_id,
                    )
                    desc = (
                        f"You tried to safely capture the snake but it slipped away and you got hurt. "
                        f"You lost ${penalty_amount} in medical bills."
                    )
                elif outcome_roll < 0.66:
                    # Neutral outcome
                    desc = (
                        "You safely captured the snake without incident. No bonus, but no trouble either."
                    )
                else:
                    # Positive outcome - bonus
                    bonus = random.randint(20, 500) * random.randint(1, 4)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        self.user_id,
                    )
                    desc = f"You expertly capture the snake with your equipment. Bonus ${bonus} awarded!"

            self.outcome_summary = desc
            await interaction.response.edit_message(content=desc, embed=None, view=None)
            self.stop()

        except Exception as e:
            print(f"Error in safe_capture: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong!", ephemeral=True)
            self.stop()

    @discord.ui.button(label="Calm the freaked out employee", style=discord.ButtonStyle.success)
    async def calm_employee(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            outcome_roll = random.random()
            desc = ""
            penalty_amount = None
            bonus = None

            async with self.pool.acquire() as conn:
                if outcome_roll < 0.33:
                    # Negative outcome - penalty
                    penalty_amount = random.randint(20, 100) * random.randint(1, 3)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                        penalty_amount,
                        self.user_id,
                    )
                    desc = (
                        f"You tried to calm the employee but made things worse. You lost ${penalty_amount} due to stress leave."
                    )
                elif outcome_roll < 0.66:
                    # Neutral outcome
                    desc = (
                        "You calmed the panicked employee successfully but didn't get a bonus."
                    )
                else:
                    # Positive outcome - bonus
                    bonus = random.randint(20, 500) * random.randint(1, 4)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        self.user_id,
                    )
                    desc = f"You calm the panicked employee with your expert knowledge. Bonus ${bonus}!"

            self.outcome_summary = desc
            await interaction.response.edit_message(content=desc, embed=None, view=None)
            self.stop()

        except Exception as e:
            print(f"Error in calm_employee: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong!", ephemeral=True)
            self.stop()

    @discord.ui.button(label="Call for backup", style=discord.ButtonStyle.secondary)
    async def call_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            async with self.pool.acquire() as conn:
                helpers = await conn.fetch(
                    """
                    SELECT user_id FROM users
                    WHERE occupation_id = 61
                    AND guild_id = $1
                    AND user_id != $2
                    """,
                    self.guild_id,
                    self.user_id,
                )

                helper_names = []
                for helper in helpers:
                    helper_member = interaction.guild.get_member(helper['user_id'])
                    if helper_member:
                        helper_names.append(helper_member.mention)
                    else:
                        user_obj = await interaction.client.fetch_user(helper['user_id'])
                        helper_names.append(f"<@{user_obj.id}>")

                user_member = interaction.guild.get_member(self.user_id)
                if user_member:
                    user_name = user_member.mention
                else:
                    user_obj = await interaction.client.fetch_user(self.user_id)
                    user_name = f"<@{user_obj.id}>"

                if helpers:
                    bonus = random.randint(20, 500) * random.randint(1, 4)
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        self.user_id,
                    )
                    for helper in helpers:
                        await conn.execute(
                            "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                            bonus,
                            helper['user_id'],
                        )
                    desc = (
                        f"You call for backup and handle the snake safely. {user_name} and "
                        f"{len(helpers)} helpers ({', '.join(helper_names)}) receive ${bonus} each!"
                    )
                else:
                    desc = "You called for backup but no one came to help. No bonus awarded."

            self.outcome_summary = desc
            await interaction.response.edit_message(content=desc, embed=None, view=None)
            self.stop()

        except Exception as e:
            print(f"Error in call_backup: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong!", ephemeral=True)
            self.stop()

    @discord.ui.button(label="Focus on paperwork", style=discord.ButtonStyle.danger)
    async def paperwork(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            outcome_roll = random.random()
            desc = ""
            penalty_amount = None

            if outcome_roll < 0.33:
                penalty_amount = random.randint(20, 100) * random.randint(1, 3)
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                        penalty_amount,
                        self.user_id,
                    )
                desc = f"You decide to focus on paperwork instead of the snake. Your boss docked your pay by ${penalty_amount}."
            elif outcome_roll < 0.66:
                desc = "You decide to focus on paperwork instead of the snake. No bonus, but at least no trouble!"
            else:
                bonus = random.randint(20, 500) * random.randint(1, 4)
                async with self.pool.acquire() as conn:
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        self.user_id,
                    )
                desc = f"You decided paperwork was more important, but got a surprise bonus of ${bonus} for efficiency!"

            self.outcome_summary = desc
            await interaction.response.edit_message(content=desc, embed=None, view=None)
            self.stop()

        except Exception as e:
            print(f"Error in paperwork: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong!", ephemeral=True)
            self.stop()

async def play_animal_control_snake(pool, guild_id, user_id, user_occupation_id, pay_rate):
    embed = discord.Embed(
        title="🐍 Snake in the Break Room - Animal Control Edition",
        description=(
            "You’re an expert Animal Control worker and spot a snake in the break room. How do you handle it?\n\n"
            "1️⃣ Safely capture the snake\n"
            "2️⃣ Calm the freaked out employee\n"
            "3️⃣ Call for backup\n"
            "4️⃣ Focus on paperwork\n\n"
            "Choose wisely!"
        )
    )
    view = AnimalControlSnakeView(pool, guild_id, user_id, user_occupation_id, pay_rate)
    return embed, view

# ------------------------------
# Dispatcher function to select appropriate minigame based on occupation_id
# ------------------------------
async def play(pool, guild_id, user_id, user_occupation_id, pay_rate, _):
    if user_occupation_id == 61:  # Animal Control occupation ID
        return await play_animal_control_snake(pool, guild_id, user_id, user_occupation_id, pay_rate)
    else:
        return await play_snake_breakroom(pool, guild_id, user_id, user_occupation_id, pay_rate)
