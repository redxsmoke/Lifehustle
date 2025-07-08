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
    def __init__(self, bill: float, payment: float, correct_change: float, options: list, timeout=5):
        super().__init__(timeout=timeout)
        self.bill = bill
        self.payment = payment
        self.correct_change = correct_change
        self.result = None

        for amount in options:
            is_correct = abs(amount - correct_change) < 0.01
            self.add_item(QuickChangeButton(f"${amount:.2f}", amount, is_correct, self))

    async def on_timeout(self):
        if self.result is None:
            self.result = {
                "result": "timeout",
                "penalty": 20,
                "message": random.choice(TIMEOUT_MESSAGES),
            }
            # Disable buttons when timeout
            for child in self.children:
                child.disabled = True
            # Edit the original message to disable buttons
            # NOTE: This requires that the view has a message reference, you'll set it on call
            if hasattr(self, 'message'):
                await self.message.edit(view=self)
            self.stop()

async def run_quick_math_game(interaction: discord.Interaction):
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

    view = QuickChangeView(bill, payment, correct_change, options, timeout=5)

    await interaction.response.send_message(embed=embed, view=view)

    # Save the sent message reference for view to edit later on timeout
    view.message = await interaction.original_response()

    await view.wait()

    # Return results or timeout result
    return view.result
