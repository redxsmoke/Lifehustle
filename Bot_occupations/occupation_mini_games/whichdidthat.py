import random
import discord

generic_roast_lines = [
    "How do you mess up *that* badly?",
    "The dogs are judging you. And they’re right.",
    "Retire. Just... retire.",
    "Your paycheck is embarrassed to be associated with this.",
    "Even the NPCs are laughing at you.",
    "A toddler could've done better blindfolded.",
    "You’ve officially disappointed everyone, including yourself.",
    "Mistakes were made. By you. All of them.",
    "You're not leading the pack — you're lucky they didn’t vote you off the leash.",
    "That flop was so loud it echoed across servers.",
    "You didn’t just miss — you invented a new level of wrong.",
    "They’ll be teaching this fail in training videos.",
    "Consider a career change. Immediately.",
    "You fumbled so hard, you owe the game an apology.",
    "It wasn’t a fail — it was a full-blown biopic about failure, starring you.",
]

JOB_ROASTS = {
    "dog walker": [
        "You’re one poop away from being replaced by a Roomba.",
        "The dogs are planning a mutiny — you’re the reason why.",
        "You walk dogs, but you can’t even handle a simple poop.",
        "Your leash skills are weaker than your excuses.",
    ],
    "street performer": [
        "You performed so badly the tomatoes formed a union.",
        "The crowd threw tomatoes — at you, ironically.",
        "Your act is so bad it’s considered a public disturbance.",
        "Even the pigeons heckle better than you.",
    ],
    "professional cuddler": [
        "You cuddled so badly even your own shadow ran away.",
        "Your hugs have been officially declared hazardous.",
        "The only thing you’re comforting is your own ego.",
        "You couldn’t cuddle your way out of a paper bag.",
    ],
    "human statue": [
        "You yelled at a kid so hard, even the pigeons started avoiding you.",
        "You stood so still, even the tourists fell asleep.",
        "Your painted hat theft was the highlight of the day — and not in a good way.",
        "You’re less statue, more sad decoration.",
        "The only thing you’re frozen in is failure.",
    ],
    "processional line sitter": [
        "You waited so long, the line moved faster without you.",
        "Even the mannequins got tired of standing next to you.",
        "You’re the human equivalent of buffering… forever.",
        "Congrats, you mastered the art of doing absolutely nothing.",
    ],
}

MINIGAME_CONFIGS = {
    "dog walker": {
        "prompt": "Uh-oh, someone left a surprise! 🐾 Who pooped?",
        "choices": ["Milo 🐕", "Bella 🐶", "Rex 🐕‍🦺", "Luna 🐩"],
        "positive_outcomes": [
            "You caught the culprit before anyone stepped in it. Clients are thrilled!",
            "Right on the tail! {choice} was the pooper. Cleaned up in no time."
        ],
        "neutral_outcomes": [
            "You cleaned all four dogs just in case. Exhausting, but effective.",
            "You weren't sure, so you just reported it and moved on."
        ],
        "negative_outcomes": [
            "Oops! You scolded the wrong dog. The real pooper got away.",
            "You missed it — the sidewalk wasn’t so lucky. Clients weren’t happy."
        ],
    },
    "street performer": {
        "prompt": "Someone threw a tomato! 🍅 Who did it?",
        "choices": ["Grumpy Man 😠", "Bored Teen 😑", "Old Lady 😲", "Annoyed Vendor 🧑‍🌾"],
        "positive_outcomes": [
            "You called out {choice} — crowd cheers as security steps in!",
            "You dodged the tomato and embarrassed {choice}. Respect +10."
        ],
        "neutral_outcomes": [
            "You gave a dramatic bow and carried on. The show must go on!",
            "You laughed it off. The crowd appreciated your humor."
        ],
        "negative_outcomes": [
            "Wrong guess — now you're covered in tomato. Tips plummet.",
            "You accused the wrong person — now the crowd's booing YOU."
        ],
    },
    "human statue": {
        "prompt": "Your painted hat is missing! 🎨 Who stole it?",
        "choices": ["Sneaky Kid 👦", "Distracted Mom 👩", "Tourist with Camera 📷", "Busy Photographer 📸"],
        "positive_outcomes": [
            "You caught {choice} red-handed and recovered your hat. Nice reflexes!",
            "You didn't flinch, but your eyes tracked {choice} perfectly. Got it back!"
        ],
        "neutral_outcomes": [
            "You just stood still and hoped for the best. It worked... kinda.",
            "Someone returned your hat anonymously. Strange, but okay?"
        ],
        "negative_outcomes": [
            "You stayed frozen... but the hat is long gone. That was your best one!",
            "You blamed the wrong person and lost your crowd. Oof."
        ],
    },
    "processional line sitter": {
        "prompt": "You’re holding a spot in line. Who cut ahead?",
        "choices": ["Impatient Shopper 🛒", "Texting Teen 📱", "Slow Walker 🚶‍♂️", "Chatty Stranger 🗣️"],
        "positive_outcomes": [
            "You politely confronted {choice} and held your spot. Victory!",
            "You caught {choice} sneaking ahead and reported them. Justice served."
        ],
        "neutral_outcomes": [
            "You sighed and let it go. Sometimes it’s not worth the fight.",
            "You lost track and the line moved on without you."
        ],
        "negative_outcomes": [
            "You yelled at the wrong person and embarrassed yourself.",
            "You accidentally let {choice} cut again. Line chaos ensues."
        ],
    },
    "professional cuddler": {
        "prompt": "Someone’s not feeling cozy. Who’s avoiding the cuddle?",
        "choices": ["Shy Client 😊", "Grumpy Client 😠", "Sleepy Client 😴", "Indifferent Client 😐"],
        "positive_outcomes": [
            "You warmed up {choice} with your cuddles. Success!",
            "You found the perfect cuddle technique for {choice}. They smiled."
        ],
        "neutral_outcomes": [
            "You gave a friendly smile but no cuddle. Maybe next time.",
            "You waited patiently but {choice} remained distant."
        ],
        "negative_outcomes": [
            "You hugged the air — {choice} wasn’t even there.",
            "You accidentally scared {choice} away. Oof."
        ],
    },
}

def get_roast_line(job_name: str) -> str:
    job_lines = JOB_ROASTS.get(job_name.lower())
    if job_lines:
        return random.choice(job_lines)
    return random.choice(generic_roast_lines)

class WhichDidThatView(discord.ui.View):
    def __init__(self, pool, guild_id, user_id, job_key, config):
        super().__init__(timeout=60)
        self.pool = pool
        self.guild_id = guild_id
        self.user_id = user_id
        self.job_key = job_key
        self.config = config
        self.choice = None
        self.outcome_summary = None
        self.outcome_type = "neutral"  # default

        # Add buttons for each choice
        for choice_text in config["choices"]:
            self.add_item(WhichDidThatButton(choice_text, self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the user who triggered the game to interact
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("This is not your game!", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        if not self.choice:
            # User didn't respond in time
            self.outcome_summary = "You didn't choose in time. The situation resolved itself..."
            self.outcome_type = "neutral"

class WhichDidThatButton(discord.ui.Button):
    def __init__(self, label, parent_view):
        super().__init__(style=discord.ButtonStyle.primary, label=label)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.choice:
            await interaction.response.send_message("You've already made a choice!", ephemeral=True)
            return

        self.parent_view.choice = self.label
        config = self.parent_view.config
        culprit = random.choice(config["choices"])

        # Decide outcome
        if self.parent_view.choice == culprit:
            outcome_text = random.choice(config["positive_outcomes"]).replace("{choice}", culprit)
            bonus = 10
            outcome_type = "positive"
        else:
            if random.random() < 0.33:
                outcome_text = random.choice(config["neutral_outcomes"]).replace("{choice}", culprit)
                bonus = 0
                outcome_type = "neutral"
            else:
                outcome_text = random.choice(config["negative_outcomes"]).replace("{choice}", culprit)
                roast = get_roast_line(self.parent_view.job_key)
                outcome_text += f" {roast}"
                bonus = -5
                outcome_type = "negative"

        self.parent_view.outcome_summary = outcome_text
        self.parent_view.outcome_type = outcome_type

        # Disable buttons after choice
        for child in self.parent_view.children:
            child.disabled = True
            if child.label == self.label:
                child.style = discord.ButtonStyle.success if outcome_type == "positive" else discord.ButtonStyle.danger

        await interaction.response.edit_message(content=outcome_text, view=self.parent_view)

async def play(pool, guild_id, user_id, user_occupation_id, pay_rate, extra=None):
    # Fetch the user's job name from DB
    async with pool.acquire() as conn:
        user_job = await conn.fetchval("SELECT name FROM cd_occupations WHERE id = $1", user_occupation_id)

    if not user_job:
        embed = discord.Embed(
            title="Mini-Game",
            description="You have no job assigned, so no mini-game this time.",
            color=discord.Color.greyple()
        )
        return embed, WhichDidThatView(pool, guild_id, user_id, "", {})

    job_key = user_job.lower()
    config = MINIGAME_CONFIGS.get(job_key)

    if not config:
        embed = discord.Embed(
            title="Mini-Game",
            description=f"No mini-game configured for your job: {user_job}.",
            color=discord.Color.greyple()
        )
        return embed, WhichDidThatView(pool, guild_id, user_id, job_key, {})

    embed = discord.Embed(
        title=f"Mini-Game: {user_job}",
        description=config["prompt"],
        color=discord.Color.blue()
    )

    view = WhichDidThatView(pool, guild_id, user_id, job_key, config)
    return embed, view
