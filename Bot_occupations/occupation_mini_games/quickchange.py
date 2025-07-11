import discord
import random
import asyncio

POSITIVE_MESSAGES = [
    "Good job! You nailed the change like a pro! 💰",
    "Way to go! Your math skills are sharp! 🔥",
    "Correct! You’re making bank with that brain! 🧠💵",
    "Excellent! You gave the right change, no sweat! 😎",
    "Bravo! Cash handling level: expert! 🎉"
]

NEGATIVE_MESSAGES = [
    "Oops! That was rough, even a squirrel counts better than you! 🐿️",
    "Wrong change! Did you sleep through math class? 😅",
    "Yikes! Your calculator called in sick today. 🤡",
    "Nope! The customer’s shaking their head at you. 🤦",
    "Wrong answer! Better luck next time, rookie! 🐣"
]

TIMEOUT_MESSAGES = [
    "The customer could tell you were a dunce and got their change from someone competent. 🤡",
    "You froze up! The customer found someone else to help. ❄️",
    "No answer? The customer’s patience ran out, and so did your pay. 🕰️",
    "Too slow! The customer’s already gone with their change. 🏃‍♂️💨",
    "Your brain took a coffee break — without you. Even the cashier’s cat could’ve been faster! 🐱☕️"
]

def get_timeout_message_and_penalty(job_key: str):
    base_penalty = 20
    multiplier = round(random.uniform(1.2, 3.9), 2)
    penalty = int(base_penalty * multiplier)

    # Job-specific timeout messages with placeholders for penalty
    timeout_messages = {
        "dog walker": [
            f"The dogs got tired of waiting and gave you the stink eye. Penalty: ${penalty}.",
            f"You got distracted and stepped in your own mess. Boss docked you ${penalty}.",
            f"Clients reported a 'poop incident' on your watch. Fine of ${penalty} applied.",
            f"The leash slipped! You lost track and got fined ${penalty}.",
            f"Your boss says 'clean up your act' — penalty of ${penalty} imposed.",
        ],
        "street performer": [
            f"The crowd booed you off stage. Fine of ${penalty} incoming.",
            f"Someone threw a tomato, and you ran away. Penalty: ${penalty}.",
            f"You missed your cue — boss docked you ${penalty}.",
            f"Your act was so bad, they canceled your permit. Penalty of ${penalty} applied.",
            f"You forgot your props, and the boss wasn’t happy. Fine: ${penalty}.",
        ],
        "professional cuddler": [
            f"Client walked away cold — penalty of ${penalty} imposed.",
            f"You missed a cuddle session and got fined ${penalty}.",
            f"The boss says ‘no show, no pay’ — penalty: ${penalty}.",
            f"You hugged the air — lost ${penalty} in wages.",
            f"Your warm vibes went missing. Fine of ${penalty} applied.",
        ],
        "human statue": [
            f"You blinked! Boss says that’s a ${penalty} mistake.",
            f"You lost your pose and got fined ${penalty}.",
            f"Hat theft report filed — penalty of ${penalty} incoming.",
            f"You scared the tourists away. Fine: ${penalty}.",
            f"Frozen failure costs you ${penalty}.",
        ],
        "processional line sitter": [
            f"You fell asleep in line and got fined ${penalty}.",
            f"Someone cut in front of you — boss docked ${penalty}.",
            f"Your spot was stolen. Penalty: ${penalty}.",
            f"You missed your cue to move up. Fine of ${penalty} applied.",
            f"The line moved faster without you. Lost ${penalty}.",
        ],
        "grocery store clerk": [
            f"Scanner meltdown! Boss docked you ${penalty}.",
            f"Customers got frustrated — penalty of ${penalty} applied.",
            f"You mixed up the prices and lost ${penalty}.",
            f"Coupon chaos cost you ${penalty} in fines.",
            f"You rang up an empty cart. Penalty: ${penalty}.",
        ],
        "ice cream truck driver": [
            f"Ice cream melted on your watch — penalty ${penalty}.",
            f"Machine broke down and customers complained. Fine: ${penalty}.",
            f"You ran out of cones — boss docked ${penalty}.",
            f"Jingle was off-key. Penalty of ${penalty} applied.",
            f"Sticky mess cost you ${penalty} in fines.",
        ],
        "waiter/waitress": [
            f"Cold soup complaint — penalty ${penalty}.",
            f"Forgot the order, boss docked ${penalty}.",
            f"Slow service got you fined ${penalty}.",
            f"Customer left unhappy, fine of ${penalty} applied.",
            f"Spilled a drink. Penalty: ${penalty}.",
        ],
    }

    default_messages = [
        f"No response received in time. Penalty of ${penalty} applied.",
        f"Timeout! Your boss fined you ${penalty} for slacking off.",
        f"You missed the chance to act — penalty: ${penalty}.",
        f"Task failed due to inactivity, boss docked ${penalty}.",
        f"Time ran out, and so did your patience — fine of ${penalty}.",
    ]

    messages = timeout_messages.get(job_key, default_messages)
    message = random.choice(messages)
    return message, penalty

class QuickChangeButton(discord.ui.Button):
    def __init__(self, label: str, amount: float, is_correct: bool, parent_view):
        super().__init__(label=label, style=discord.ButtonStyle.primary)
        self.amount = amount
        self.is_correct = is_correct
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        # Disable all buttons after click
        for child in self.parent_view.children:
            child.disabled = True
        await interaction.response.edit_message(view=self.parent_view)

        if self.is_correct:
            multiplier = random.uniform(1.5, 8.5)
            bonus = int(75 * multiplier)
            message = random.choice(POSITIVE_MESSAGES)
            self.parent_view.result = {
                "result": "correct",
                "bonus": bonus,
                "message": message,
            }
        else:
            multiplier = random.uniform(1, 3)
            # Dock based on the bill amount stored in parent view
            dock = int(self.parent_view.bill * multiplier)
            message = random.choice(NEGATIVE_MESSAGES)
            self.parent_view.result = {
                "result": "wrong",
                "dock": dock,
                "message": message,
            }
        self.parent_view.stop()

class QuickChangeView(discord.ui.View):
    def __init__(self, bill: float, payment: float, correct_change: float, options: list, job_key: str, timeout=5):
        super().__init__(timeout=timeout)
        self.bill = bill
        self.payment = payment
        self.correct_change = correct_change
        self.job_key = job_key
        self.result = None

        for amount in options:
            is_correct = abs(amount - correct_change) < 0.01
            self.add_item(QuickChangeButton(f"${amount:.2f}", amount, is_correct, self))

    async def on_timeout(self):
        if self.result is None:
            message, penalty = get_timeout_message_and_penalty(self.job_key)
            self.result = {
                "result": "timeout",
                "penalty": penalty,
                "message": message,
            }
            # Disable buttons when timeout
            for child in self.children:
                child.disabled = True
            # Edit the original message to disable buttons
            # NOTE: This requires that the view has a message reference, you'll set it on call
            if hasattr(self, 'message'):
                await self.message.edit(view=self)
            self.stop()

# THE ONLY CHANGE IS: add `job_key` parameter here
async def run_quick_math_game(interaction: discord.Interaction, job_key: str):
    bill = round(random.uniform(10.00, 49.99), 2)
    possible_payments = [20, 30, 40, 50, 100]
    payments = [p for p in possible_payments if p > bill]
    payment = random.choice(payments)

    correct_change = round(payment - bill, 2)

    incorrect_options = set()
    while len(incorrect_options) < 3:
        option = round(random.uniform(0.01, payment), 2)
        if abs(option - correct_change) > 0.01:
            incorrect_options.add(option)

    options = list(incorrect_options) + [correct_change]
    random.shuffle(options)

    embed = discord.Embed(
        title="Quick Math: Make Change",
        description=(
            f"A customer's bill is **${bill:.2f}** and they hand you **${payment:.2f}**.\n"
            "Make the correct change by clicking one of the options below!"
        ),
        color=discord.Color.blue(),
    )

    view = QuickChangeView(bill, payment, correct_change, options, job_key=job_key, timeout=5)

    await interaction.followup.send(embed=embed, view=view)

    # Save the sent message reference for view to edit later on timeout
    view.message = await interaction.original_response()

    await view.wait()

    if view.result is None:
        message, penalty = get_timeout_message_and_penalty(view.job_key)
        view.result = {
            "result": "timeout",
            "penalty": penalty,
            "message": message,
        }
    return view.result
