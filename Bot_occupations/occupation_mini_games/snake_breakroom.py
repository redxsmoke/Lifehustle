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
        self.penalty_chance = 0.07  # 7% chance of penalty
        self.penalty_amount = int(pay_rate * 0.1)  # 10% pay dock penalty
        self.outcome_summary = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def apply_penalty(self):
        if random.random() < self.penalty_chance:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                    self.penalty_amount,
                    self.user_id,
                )
            return True
        return False

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

                    bonus = self.pay_rate * 2
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
                    desc = f"You called Animal Control! {helper_name} from Fur Get About It Animal Control rushed in to help {user_name}. Both get a bonus of ${int(bonus)}!"
                else:
                    desc = "You called Animal Control but no one is available. No bonus awarded."

            penalty_applied = await self.apply_penalty()
            if penalty_applied:
                desc += f"\n\nYour boss docked your pay for causing a fuss over a harmless snake. You lost ${self.penalty_amount}."

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
            multiplier = random.uniform(1.1, 1.5)
            success = random.random() < 0.4  # 40% success chance
            bonus = int(self.pay_rate * multiplier)

            async with self.pool.acquire() as conn:
                if success:
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        self.user_id,
                    )
                    desc = f"You grabbed the snake by the neck and totally nailed it! The snake didn’t stand a chance against your heroic grip. Bonus: ${bonus} (x{multiplier:.2f})."
                else:
                    desc = "You tried to grab the snake, but it slipped away laughing at your incompetence. Snake 1, you 0."

            penalty_applied = await self.apply_penalty()
            if penalty_applied:
                desc += f"\n\nYou tried to grab the snake and it bit you. The EMTs think you're a moron. You paid ${self.penalty_amount} in medical bills and an infinite amount in emotional damage."

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
            desc = (
                "You put a bucket over the snake and walked away, hoping someone else deals with it. "
                "Not exactly team spirit, but hey — no trouble (or bonus) for you either."
            )

            penalty_applied = await self.apply_penalty()
            if penalty_applied:
                desc += f"\n\nYour boss noticed your lack of initiative. Pay docked by ${self.penalty_amount}."

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
            success = random.random() < 0.5
            bonus = int(self.pay_rate * 1.5)

            async with self.pool.acquire() as conn:
                if success:
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        self.user_id,
                    )
                    desc = f"You distracted the snake with snacks and it calmed down! Bonus ${bonus} awarded."
                else:
                    desc = "Your distraction backfired and the snake got angrier. No bonus this time."

            penalty_applied = await self.apply_penalty()
            if penalty_applied:
                desc += f"\n\nManagement isn’t thrilled. They’re considering replacing you with a cardboard cutout. You lost ${self.penalty_amount} from your pay."

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
        self.penalty_chance = 0.02  # 2% chance penalty for pros
        self.penalty_amount = int(pay_rate * 0.05)  # 5% pay dock penalty for rare screwups
        self.outcome_summary = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def apply_penalty(self):
        if random.random() < self.penalty_chance:
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                    self.penalty_amount,
                    self.user_id,
                )
            return True
        return False

    @discord.ui.button(label="Safely capture the snake", style=discord.ButtonStyle.primary)
    async def safe_capture(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            bonus = int(self.pay_rate * 2.5)
            async with self.pool.acquire() as conn:
                await conn.execute(
                    "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                    bonus,
                    self.user_id,
                )
            desc = f"You expertly capture the snake with your equipment. Bonus ${bonus} awarded!"
            penalty_applied = await self.apply_penalty()
            if penalty_applied:
                desc += f"\n\nEven pros have off days! Minor mishap cost you ${self.penalty_amount}."
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
            success = random.random() < 0.8
            bonus = int(self.pay_rate * 1.2)
            async with self.pool.acquire() as conn:
                if success:
                    await conn.execute(
                        "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                        bonus,
                        self.user_id,
                    )
                    desc = f"You calm the panicked employee with your expert knowledge. Bonus ${bonus}!"
                else:
                    desc = "The employee panics even more. No bonus this time."

            penalty_applied = await self.apply_penalty()
            if penalty_applied:
                desc += f"\n\nYour calming skills slipped! You lost ${self.penalty_amount}."
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

                bonus = int(self.pay_rate * 1.8)
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
                desc = f"You call for backup and handle the snake safely. {user_name} and {len(helpers)} helpers ({', '.join(helper_names)}) receive ${bonus} each!"

            penalty_applied = await self.apply_penalty()
            if penalty_applied:
                desc += f"\n\nYour backup plan backfired a bit! You lost ${self.penalty_amount}."
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
            desc = "You decide to focus on paperwork instead of the snake. No bonus, but at least no trouble!"

            penalty_applied = await self.apply_penalty()
            if penalty_applied:
                desc += f"\n\nYour boss isn't thrilled with your choice. You lost ${self.penalty_amount}."
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
