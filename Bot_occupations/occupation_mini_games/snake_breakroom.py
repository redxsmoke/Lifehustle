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

    async def get_helper_name(self, interaction):
        async with self.pool.acquire() as conn:
            helper = await conn.fetchrow(
                """
                SELECT user_id FROM users
                WHERE occupation_id = 61
                AND guild_id = $1
                AND user_id != $2
                LIMIT 1
                """,
                self.guild_id,
                self.user_id,
            )

        if helper:
            member = interaction.guild.get_member(helper['user_id'])
            if member:
                return member.mention
            user = await interaction.client.fetch_user(helper['user_id'])
            return f"<@{user.id}>"
        return "Animal Control"

    async def apply_penalty(self, conn):
        penalty = random.randint(20, 100) * random.randint(1, 3)
        await conn.execute(
            "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
            penalty,
            self.user_id,
        )
        return penalty

    async def apply_bonus(self, conn):
        bonus = random.randint(20, 500) * random.randint(1, 4)
        await conn.execute(
            "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
            bonus,
            self.user_id,
        )
        return bonus

    async def handle_outcome(self, interaction: discord.Interaction, outcomes):
        try:
            choice = random.choices(outcomes, k=1)[0]
            async with self.pool.acquire() as conn:
                helper_name = await self.get_helper_name(interaction)

                if choice['type'] == 'positive':
                    amount = await self.apply_bonus(conn)
                    desc = choice['text'].format(helper=helper_name, amount=amount)
                elif choice['type'] == 'negative':
                    amount = await self.apply_penalty(conn)
                    desc = choice['text'].format(helper=helper_name, amount=amount)
                else:
                    desc = choice['text'].format(helper=helper_name)

            self.outcome_summary = desc
            await interaction.response.defer()
            self.stop()
        except Exception as e:
            print(f"Error in handle_outcome: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message("Something went wrong!", ephemeral=True)
                self.stop()

    @discord.ui.button(label="Call Animal Control", style=discord.ButtonStyle.primary)
    async def call_animal_control(self, interaction: discord.Interaction, button: discord.ui.Button):
        outcomes = [
            {"type": "positive", "text": "{helper} arrived just in time and saved the day. You earned a bonus of ${amount}."},
            {"type": "positive", "text": "With {helper}'s help, the snake was removed safely. You got a bonus of ${amount}!"},
            {"type": "neutral",  "text": "{helper} responded and handled the snake. No bonus, but no trouble either."},
            {"type": "neutral",  "text": "You and {helper} watched the snake crawl away. Oddly peaceful. No bonus."},
            {"type": "negative", "text": "{helper} showed up late to remove the snake, and your boss docked your pay by ${amount}."},
            {"type": "negative", "text": "{helper} scared the snake into the vents. Chaos ensued. You were fined ${amount}."},
        ]
        await self.handle_outcome(interaction, outcomes)

    @discord.ui.button(label="Grab it by the neck", style=discord.ButtonStyle.primary)
    async def grab_by_neck(self, interaction: discord.Interaction, button: discord.ui.Button):
        outcomes = [
            {"type": "positive", "text": "You grabbed the snake and danced with it. Somehow this earned you a bonus of ${amount}."},
            {"type": "positive", "text": "You became a snake whisperer for a moment. Bonus: ${amount}."},
            {"type": "neutral",  "text": "You missed, but no one saw. Just walk away."},
            {"type": "neutral",  "text": "You lunged, it slithered. A draw. No pay changes."},
            {"type": "negative", "text": "The snake bit you. You needed a tetanus shot. Pay docked by ${amount} for medical bills."},
            {"type": "negative", "text": "HR saw you and thought it was animal cruelty. You were written up and fined ${amount}."},
        ]
        await self.handle_outcome(interaction, outcomes)

    @discord.ui.button(label="Put a bucket over it", style=discord.ButtonStyle.primary)
    async def put_bucket(self, interaction: discord.Interaction, button: discord.ui.Button):
        outcomes = [
            {"type": "positive", "text": "Genius! The bucket trap worked. Bonus awarded: ${amount}."},
            {"type": "positive", "text": "You saved the day with a bucket and got ${amount}. The janitor is proud."},
            {"type": "neutral",  "text": "The bucket fell over. Snake vanished. Nobody knows, nobody cares."},
            {"type": "neutral",  "text": "You put a bucket over something, but it wasn’t the snake. Oh well."},
            {"type": "negative", "text": "Snake escaped and your boss blamed you. You’re down ${amount}."},
            {"type": "negative", "text": "You used the good bucket. The janitor reported you. Pay docked ${amount}."},
        ]
        await self.handle_outcome(interaction, outcomes)

    @discord.ui.button(label="Distract it with snacks", style=discord.ButtonStyle.primary)
    async def distract_with_snacks(self, interaction: discord.Interaction, button: discord.ui.Button):
        outcomes = [
            {"type": "positive", "text": "Snake loves chips! You bought time and earned a bonus of ${amount}."},
            {"type": "positive", "text": "You fed it gummy worms and it fell asleep. ${amount} bonus!"},
            {"type": "neutral",  "text": "The snake ignored the snacks. At least no one was hurt."},
            {"type": "neutral",  "text": "You distracted the snake, but now it lives in the vending machine."},
            {"type": "negative", "text": "Snake choked on snacks and your boss blamed you. Lost ${amount}."},
            {"type": "negative", "text": "You dropped company snacks. Inventory fine: ${amount}."},
        ]
        await self.handle_outcome(interaction, outcomes)

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

    async def apply_penalty(self, amount):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_finances SET checking_account_balance = checking_account_balance - $1 WHERE user_id = $2",
                amount,
                self.user_id,
            )

    async def apply_bonus(self, amount):
        async with self.pool.acquire() as conn:
            await conn.execute(
                "UPDATE user_finances SET checking_account_balance = checking_account_balance + $1 WHERE user_id = $2",
                amount,
                self.user_id,
            )

    def calculate_bonus(self):
        return random.randint(20, 500) * random.randint(1, 4)

    def calculate_penalty(self):
        return random.randint(20, 100) * random.randint(1, 3)

    @discord.ui.button(label="Safely capture the snake", style=discord.ButtonStyle.primary)
    async def safe_capture(self, interaction: discord.Interaction, button: discord.ui.Button):
        outcomes = [
            ("positive", "You flawlessly capture the snake. Textbook execution."),
            ("positive", "You gently relocate the snake to the wild. It winks at you. Weird."),
            ("neutral", "You hesitated a little, but the snake cooperated. No harm done."),
            ("neutral", "You used the capture pole slightly incorrectly, but it still worked."),
            ("negative", "You botch the capture and the snake slithers into the vending machine."),
            ("negative", "You forgot your gloves and got nipped. You're fine. Your pride isn't."),
        ]
        await self.resolve(interaction, outcomes)

    @discord.ui.button(label="Calm the freaked out employee", style=discord.ButtonStyle.primary)
    async def calm_employee(self, interaction: discord.Interaction, button: discord.ui.Button):
        outcomes = [
            ("positive", "You bring calm with a clipboard and confidence. Bonus time."),
            ("positive", "You distract the employee with a hilarious snake pun. They're fine."),
            ("neutral", "The employee slowly calms down after you hand them a stress ball."),
            ("neutral", "You just stand near them until they stop yelling. Effective? Sure."),
            ("negative", "They scream louder after you mention how venom works. Whoops."),
            ("negative", "You panic slightly and scream too. The supervisor is disappointed."),
        ]
        await self.resolve(interaction, outcomes)

    @discord.ui.button(label="Call for backup", style=discord.ButtonStyle.primary)
    async def call_backup(self, interaction: discord.Interaction, button: discord.ui.Button):
        outcomes = [
            ("positive", "Backup arrives and handles everything perfectly. Like clockwork."),
            ("positive", "You and backup play rock-paper-scissors for who handles the snake. You win."),
            ("neutral", "Backup arrives late, but everything still gets sorted."),
            ("neutral", "The snake just chills while you wait for backup. It’s oddly patient."),
            ("negative", "Backup trips on arrival and breaks the coffee machine. Yikes."),
            ("negative", "You accidentally call pest control instead. They run screaming."),
        ]
        await self.resolve(interaction, outcomes)

    @discord.ui.button(label="Focus on paperwork", style=discord.ButtonStyle.primary)
    async def paperwork(self, interaction: discord.Interaction, button: discord.ui.Button):
        outcomes = [
            ("positive", "You handle the backlog while someone else catches the snake. Genius."),
            ("positive", "Your paperwork is so thorough, you get praised even with a loose snake."),
            ("neutral", "You stay laser-focused while chaos unfolds around you."),
            ("neutral", "You pretend to not notice the snake and finish a full report."),
            ("negative", "Your boss finds out you ignored the snake. Not a great look."),
            ("negative", "Snake climbs into your paperwork bin. You're startled. A report is ruined."),
        ]
        await self.resolve(interaction, outcomes)

    async def resolve(self, interaction, outcome_pool):
        category, message = random.choice(outcome_pool)
        bonus = penalty = 0

        if category == "positive":
            bonus = self.calculate_bonus()
            await self.apply_bonus(bonus)
            message += f" Bonus awarded: ${bonus}."
        elif category == "negative":
            penalty = self.calculate_penalty()
            await self.apply_penalty(penalty)
            message += f" You were fined ${penalty}."

        self.outcome_summary = message
        await interaction.response.defer()
        self.stop()
# ------------------------------
# Dispatcher function to select appropriate minigame based on occupation_id
# ------------------------------

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

async def play(pool, guild_id, user_id, user_occupation_id, pay_rate, _):
    if user_occupation_id == 61:  # Animal Control occupation ID
        return await play_animal_control_snake(pool, guild_id, user_id, user_occupation_id, pay_rate)
    else:
        return await play_snake_breakroom(pool, guild_id, user_id, user_occupation_id, pay_rate)
