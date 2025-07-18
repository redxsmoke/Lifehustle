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
            f"You counted coins like a sloth on NyQuil. The boss nuked your paycheck: -${penalty}.",
            f"You tried to make change with Monopoly money. The dogs unionized. You owe ${penalty}.",
            f"The client aged 10 years waiting. They've invoiced *you* for emotional damage: -${penalty}.",
            f"You asked, ‘Do you want change in pennies?’ They said no. You got smacked with a ${penalty} fine.",
            f"You were doing math like it was a cryptic Sudoku. Time’s up — and so is ${penalty} from your pay.",
            f"You opened your coin pouch like it was a treasure chest. The IRS showed up. -${penalty}.",
            f"The dogs filed a complaint. Reason: ‘Took 3 business days to give a nickel.’ You’re fined ${penalty}.",
            f"You made change so slow, it reversed inflation. Boss charged you a ${penalty} stupidity tax.",
            f"While you were counting, the customer’s dog learned calculus. You owe ${penalty} in damages.",
            f"They asked for $0.75 back. You said ‘carry the one’ — now carry this ${penalty} fine."
        ],
        "auto mechanic": [
            f"You took so long counting coins, the customer rebuilt their own car. Boss fined you ${penalty}.",
            f"You dropped a quarter in the engine bay and spent 10 minutes fishing it out. ${penalty} gone.",
            f"You gave them chocolate gold coins. They were not amused. That’s a ${penalty} hit.",
            f"You tried to pay them in washers and bolts. Boss wasn’t amused. Docked ${penalty}.",
            f"You said ‘hold on’ and disappeared for 30 minutes. They left. ${penalty} penalty applied.",
            f"You were calculating change on a greasy napkin. Mistake cost you ${penalty}.",
            f"You counted change out loud like it was brain surgery. Boss deducted ${penalty} for the performance.",
            f"You handed back a fistful of nickels and a coupon for tacos. ${penalty} fine.",
            f"You tried to convince them exact change was a myth. They disagreed. That’s ${penalty} gone.",
            f"You made change using a socket set. Impressive. Still fined ${penalty}.",
        ],
        "professional cuddler": [
            f"You took so long your brain forgot what basic math even means. Penalty: ${penalty}.",
            f"Counting change shouldn’t require a PhD, but here we are. Penalty: ${penalty}.",
            f"Your fingers moved slower than dial-up internet. Fine: ${penalty}.",
            f"You stared at the coins like they were alien technology. Penalty: ${penalty}.",
            f"Calculating change turned into a full-blown existential crisis. Fine: ${penalty}.",
            f"You couldn’t add two and two without breaking a sweat. Penalty: ${penalty}.",
            f"Watching you count is like watching paint dry—except sadder. Fine: ${penalty}.",
            f"You paused so long I almost thought you were negotiating with the coins. Penalty: ${penalty}.",
            f"Your math skills make a rock look like a genius. Fine: ${penalty}.",
            f"You made simple change feel like quantum physics. Penalty: ${penalty}.",

        ],
        "human statue": [
            f"You moved slower than a glacier melting. Boss took ${penalty} for wasting everyone’s time.",
            f"You froze like a statue and forgot how to count. Penalty: ${penalty}.",
            f"You took so long, even the pigeons lost interest. ${penalty} slapped on for your slowness.",
            f"You stood there dumbfounded, dropping coins like a klutz. Fine of ${penalty} applied.",
            f"Your brain short-circuited mid-count. ${penalty} penalty for the mental shutdown.",
            f"Slow as molasses in winter — boss docked you ${penalty} for the snail pace.",
            f"You acted like you were carved from stone, but without the charm. Penalty: ${penalty}.",
            f"Taking change? More like taking a nap. Fine: ${penalty}.",
            f"Even statues have more hustle than you. Penalty of ${penalty} incoming.",
            f"You counted coins like you were counting grains of sand. ${penalty} deducted for pure stupidity.",
        ],
        "processional line sitter": [
            f"You took so long counting change, the procession passed without you. Penalty: ${penalty}.",
            f"Counting coins? More like napping in line. ${penalty} docked for your snail pace.",
            f"Fell asleep mid-count—guess the boss woke you up with a ${penalty} fine.",
            f"Your change game was slower than the whole line combined. Fine of ${penalty} applied.",
            f"You blinked and missed your turn, now pay up ${penalty}.",
            f"The crowd moved on, but you’re still stuck counting pennies. Penalty: ${penalty}.",
            f"Your hands moved like molasses, so did your paycheck—minus ${penalty}.",
            f"Counting change like it’s a lifetime sentence. Fine of ${penalty} incoming.",
            f"You made that line wait so long, they started a protest. Boss docked ${penalty}.",
            f"Someone replaced you with a statue — they count faster. ${penalty} deducted.",
        ],
        "grocery store clerk": [
            f"Your coin count crashed harder than the scanner. ${penalty} fined.",
            f"Price check on your math skills: failed. Penalty: ${penalty}.",
            f"You rang up a customer’s frustration, paid with a ${penalty} fine.",
            f"Coupons and change? You lost both — ${penalty} docked.",
            f"Your math is so slow, customers aged visibly. Fine of ${penalty}.",
            f"You counted change like you were inventing math. Penalty: ${penalty}.",
            f"Boss says ‘calculate faster or pay up’ — here’s your ${penalty}.",
            f"Counting change? You turned it into a spectator sport. ${penalty} applied.",
            f"Even the self-checkout laughed at your speed. Fine: ${penalty}.",
            f"You took so long, customers started grocery shopping again. Penalty: ${penalty}.",
        ],
        "ice cream truck driver": [
            f"Ice cream melted twice waiting for you to count change. ${penalty} fined.",
            f"Machine broke down but you’re slower than that. Penalty: ${penalty}.",
            f"Ran out of cones while you counted coins — boss docked ${penalty}.",
            f"Jingle stopped because you can’t handle simple math. Fine of ${penalty}.",
            f"Sticky fingers, slower counting, pricier fine: ${penalty}.",
            f"You turned making change into a meltdown. Penalty: ${penalty}.",
            f"Customers left frozen while you counted pennies. ${penalty} applied.",
            f"Your math skills caused the ice cream truck to crash. Fine: ${penalty}.",
            f"You’re the reason cones go missing — slow math costs ${penalty}.",
            f"Counting change like a meltdown — here’s your ${penalty} fine.",
        ],
        "waiter/waitress": [
            f"Cold soup wasn’t the only thing slow — your change counting too. Penalty: ${penalty}.",
            f"Forgot the order and the math — fine of ${penalty} applied.",
            f"Slow service plus slower change counting means ${penalty} docked.",
            f"Customer left unhappy because you’re slow at math. Penalty: ${penalty}.",
            f"Spilled a drink and your math — pay ${penalty} in fines.",
            f"Your slow change counting gave customers time to rethink life. ${penalty} applied.",
            f"Counting change like you’re on break — fine: ${penalty}.",
            f"Math too slow to handle a tip — penalty of ${penalty} incoming.",
            f"You’re tipping the scales with how slow you are. Fine: ${penalty}.",
            f"Change took so long, customers started writing complaints. Penalty: ${penalty}.",
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
